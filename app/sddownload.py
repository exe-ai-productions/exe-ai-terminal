"""Fetching the picture generator itself, so nobody has to build it.

The sibling of ``app/serverdownload.py``, and for the same reason. Drawing a
picture needs ``sd-cli`` from stable-diffusion.cpp — a plain program with
prebuilt, MIT-licensed packages for every system this program ships on. A
machine that does not have it used to get a sentence ("the generator is not
set up on this PC") and no way to act on it. Now it gets a button: the
fitting package is fetched from the official release, unpacked into the
user's data folder, and found there from then on.

Fetching instead of shipping is deliberate. The packages carry a few dozen
megabytes of shared libraries per system; putting all three into every
installer would grow it by more than the program itself, and building on the
user's machine would need a compiler nobody agreed to install.

The build is pinned. "Latest" would mean every fresh installation gets a
different generator than the one this program was tested with — an update
stays a decision, not an accident.

**Everything lands in ONE folder.** The binary looks for its shared library
next to itself (``@executable_path`` on macOS, the same idea elsewhere), so
the archive is unpacked flat and nothing is sorted afterwards.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
import threading
import zipfile
from pathlib import Path

import httpx

# The progress record is the model server's, on purpose: what a download
# reports is the same three numbers whichever program it is fetching, and a
# second copy of it would only be a second thing to keep in step.
from app.serverdownload import Fortschritt

# The pinned stable-diffusion.cpp build and the packages per system.
#
# CPU builds on purpose where a GPU flavour would gamble on drivers: they
# run everywhere, and the macOS package carries its Metal support inside the
# plain build.
#
# NOTE ON THE FILE NAMES: they carry the version of the machine that BUILT
# them ("macOS-26.5.2", "Ubuntu-24.04"), not the version they run on. That
# is the upstream project's naming, so a new pin means reading the release's
# asset list again rather than substituting the tag. Which is why the table
# stands here, in one place, complete, and nothing is assembled from parts
# at call time.
BAU = "master-820-de298c2"
_BASIS = f"https://github.com/leejet/stable-diffusion.cpp/releases/download/{BAU}"

_PAKETE: dict[tuple[str, str], str] = {
    # One universal binary for both kinds of Mac — the arm64 package carries
    # an x86_64 slice as well, so an Intel Mac is served by the same file.
    ("darwin", "arm64"): "sd-master-de298c2-bin-Darwin-macOS-26.5.2-arm64.zip",
    ("darwin", "x86_64"): "sd-master-de298c2-bin-Darwin-macOS-26.5.2-arm64.zip",
    ("win32", "amd64"): "sd-master-de298c2-bin-win-cpu-x64.zip",
    ("linux", "x86_64"): "sd-master-de298c2-bin-Linux-Ubuntu-24.04-x86_64.zip",
}

# Where it lands, and where ``bildrunner.programm_finden`` looks.
ORDNER = "stable-diffusion.cpp"
PROGRAMM = "sd-cli.exe" if sys.platform == "win32" else "sd-cli"

BROCKEN = 1024 * 1024
UNFERTIG = ".teil"


def paketname() -> str | None:
    """The package for this machine, or nothing when there is none."""
    maschine = platform.machine().lower()
    if maschine in {"x64", "amd64", "x86_64"}:
        maschine = "amd64" if sys.platform == "win32" else "x86_64"
    if maschine in {"aarch64", "arm64"} and sys.platform == "darwin":
        maschine = "arm64"
    schluessel = (
        "win32" if sys.platform == "win32" else "darwin" if sys.platform == "darwin" else "linux"
    )
    return _PAKETE.get((schluessel, maschine))


class SddownloadFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


def gefundenes_programm(datenordner: Path) -> Path | None:
    """The unpacked sd-cli below the data folder, or nothing.

    Two places, in this order: the bare folder, which is where somebody who
    unpacked a build by hand puts it, and below it, which is where a fetch
    lands — one level down, in a folder named after the build, so a later
    pin never mixes two builds in one directory.
    """
    wurzel = Path(datenordner).expanduser() / ORDNER
    if not wurzel.is_dir():
        return None
    direkt = wurzel / PROGRAMM
    if direkt.is_file() and os.access(direkt, os.X_OK):
        return direkt
    for treffer in sorted(wurzel.rglob(PROGRAMM)):
        if treffer.is_file() and os.access(treffer, os.X_OK):
            return treffer
    return None


class Sddownload:
    """One fetch of the picture generator, watchable while it runs."""

    def __init__(self, datenordner: Path) -> None:
        self._datenordner = Path(datenordner).expanduser()
        self._ordner = self._datenordner / ORDNER
        self._stand: Fortschritt | None = None
        self._schloss = threading.Lock()

    def stand(self) -> Fortschritt | None:
        return self._stand

    def laeuft(self) -> bool:
        return self._stand is not None and not self._stand.fertig and not self._stand.fehler

    def starten(self) -> Fortschritt:
        with self._schloss:
            if self.laeuft():
                raise SddownloadFehler("laeuft_schon")
            if gefundenes_programm(self._datenordner) is not None:
                raise SddownloadFehler("schon_da")
            if paketname() is None:
                raise SddownloadFehler("kein_paket")

            self._stand = Fortschritt(geladen=0, gesamt=0)
            threading.Thread(target=self._holen, daemon=True).start()
            return self._stand

    def _holen(self) -> None:
        name = paketname()
        assert name is not None
        self._ordner.mkdir(parents=True, exist_ok=True)
        archiv = self._ordner / (name + UNFERTIG)

        try:
            with httpx.stream(
                "GET", f"{_BASIS}/{name}", follow_redirects=True, timeout=60
            ) as antwort:
                antwort.raise_for_status()
                if self._stand:
                    self._stand.gesamt = int(antwort.headers.get("content-length") or 0)
                with archiv.open("wb") as schreiben:
                    for brocken in antwort.iter_bytes(BROCKEN):
                        schreiben.write(brocken)
                        if self._stand:
                            self._stand.geladen += len(brocken)

            self._entpacken(archiv)
            archiv.unlink(missing_ok=True)

            programm = self._rechte_setzen()
            if programm is None:
                raise SddownloadFehler("fehlgeschlagen")

            if self._stand:
                self._stand.fertig = True
        except Exception as fehler:  # noqa: BLE001 - the reason belongs in the state
            archiv.unlink(missing_ok=True)
            shutil.rmtree(self._ordner / BAU, ignore_errors=True)
            if self._stand:
                self._stand.fehler = (
                    fehler.grund if isinstance(fehler, SddownloadFehler) else "fehlgeschlagen"
                )

    def _entpacken(self, archiv: Path) -> None:
        """Into a folder named after the build, so an update never mixes.

        Flat inside that folder, because the binary finds its shared library
        beside itself and nowhere else. All three packages are zip files —
        the upstream project publishes nothing else.
        """
        ziel = self._ordner / BAU
        ziel.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archiv) as zf:
            zf.extractall(ziel)

    def _rechte_setzen(self) -> Path | None:
        """The executable bit, which a zip file does not carry across.

        Python's zip reader drops the mode bits, so an unpacked ``sd-cli``
        arrives without permission to run — and a generator that cannot be
        started is the same as one that was never fetched. The search that
        follows deliberately looks for the FILE first and sets the bit
        afterwards: looking for something executable before there is
        anything executable would never find it.
        """
        ziel = self._ordner / BAU
        gefunden = sorted(ziel.rglob(PROGRAMM))
        if not gefunden:
            return None
        programm = gefunden[0]
        if sys.platform != "win32":
            for datei in programm.parent.iterdir():
                # The shared libraries beside it need the bit as well on
                # some systems, and setting it on a plain text file next to
                # them costs nothing.
                if datei.is_file():
                    datei.chmod(datei.stat().st_mode | 0o111)
        return programm
