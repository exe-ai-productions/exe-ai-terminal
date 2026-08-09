"""Fetching the model server itself, so nobody has to install it.

The program starts models with llama.cpp's ``llama-server`` — a plain
program with prebuilt, MIT-licensed packages for every system. A machine
that does not have it gets a button instead of an instruction: the fitting
package is fetched from the official llama.cpp release, unpacked into the
user's data folder, and found there from then on.

The build number is pinned. "Latest" would mean every fresh installation
gets a different server than the one this program was tested with — an
update stays a decision, not an accident.

Same shape as the model download next door: one at a time, watchable
progress, a part-file until complete. The archive is unpacked next to the
download and the archive itself removed — what remains is the folder the
runner searches.
"""

from __future__ import annotations

import platform
import shutil
import sys
import tarfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx

# The pinned llama.cpp build and the packages per system. CPU builds on
# purpose where a GPU flavour would gamble on drivers: they run everywhere,
# and macOS carries its Metal support inside the plain package.
BUILD = "b10331"
_BASIS = f"https://github.com/ggml-org/llama.cpp/releases/download/{BUILD}"

_PAKETE: dict[tuple[str, str], str] = {
    ("darwin", "arm64"): f"llama-{BUILD}-bin-macos-arm64.tar.gz",
    ("darwin", "x86_64"): f"llama-{BUILD}-bin-macos-x64.tar.gz",
    ("win32", "amd64"): f"llama-{BUILD}-bin-win-cpu-x64.zip",
    ("win32", "arm64"): f"llama-{BUILD}-bin-win-cpu-arm64.zip",
    ("linux", "x86_64"): f"llama-{BUILD}-bin-ubuntu-x64.tar.gz",
    ("linux", "aarch64"): f"llama-{BUILD}-bin-ubuntu-arm64.tar.gz",
}

BROCKEN = 1024 * 1024
UNFERTIG = ".teil"


def paketname() -> str | None:
    """The package for this machine, or nothing when llama.cpp has none."""
    maschine = platform.machine().lower()
    if maschine == "x64":
        maschine = "amd64" if sys.platform == "win32" else "x86_64"
    schluessel = (
        "win32" if sys.platform == "win32" else "darwin" if sys.platform == "darwin" else "linux"
    )
    return _PAKETE.get((schluessel, maschine))


@dataclass
class Fortschritt:
    geladen: int
    gesamt: int
    fertig: bool = False
    fehler: str | None = None

    @property
    def anteil(self) -> float:
        return round(self.geladen / self.gesamt, 4) if self.gesamt else 0.0


class ServerdownloadFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


def gefundener_server(ordner: Path) -> Path | None:
    """The unpacked llama-server below the data folder, or nothing."""
    wurzel = Path(ordner).expanduser() / "llama.cpp"
    if not wurzel.is_dir():
        return None
    name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
    treffer = sorted(wurzel.rglob(name))
    return treffer[0] if treffer else None


class Serverdownload:
    """One fetch of the model server, watchable while it runs."""

    def __init__(self, ordner: Path) -> None:
        self._ordner = Path(ordner).expanduser() / "llama.cpp"
        self._stand: Fortschritt | None = None
        self._schloss = threading.Lock()

    def stand(self) -> Fortschritt | None:
        return self._stand

    def laeuft(self) -> bool:
        return self._stand is not None and not self._stand.fertig and not self._stand.fehler

    def starten(self) -> Fortschritt:
        with self._schloss:
            if self.laeuft():
                raise ServerdownloadFehler("laeuft_schon")
            if gefundener_server(self._ordner.parent) is not None:
                raise ServerdownloadFehler("schon_da")
            if paketname() is None:
                raise ServerdownloadFehler("kein_paket")

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

            self._entpacken(archiv, name)
            archiv.unlink(missing_ok=True)

            server = gefundener_server(self._ordner.parent)
            if server is None:
                raise ServerdownloadFehler("fehlgeschlagen")
            if sys.platform != "win32":
                server.chmod(server.stat().st_mode | 0o111)

            if self._stand:
                self._stand.fertig = True
        except Exception as fehler:  # noqa: BLE001 - the reason belongs in the state
            archiv.unlink(missing_ok=True)
            shutil.rmtree(self._ordner / BUILD, ignore_errors=True)
            if self._stand:
                self._stand.fehler = (
                    fehler.grund
                    if isinstance(fehler, ServerdownloadFehler)
                    else "fehlgeschlagen"
                )

    def _entpacken(self, archiv: Path, name: str) -> None:
        """Into a folder named after the build, so an update never mixes."""
        ziel = self._ordner / BUILD
        ziel.mkdir(parents=True, exist_ok=True)
        if name.endswith(".zip"):
            with zipfile.ZipFile(archiv) as zf:
                zf.extractall(ziel)
        else:
            with tarfile.open(archiv, "r:gz") as tf:
                tf.extractall(ziel, filter="data")
