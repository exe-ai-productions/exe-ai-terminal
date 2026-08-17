"""Fetching a model file into the model folder.

The point of this module is that nobody has to open a terminal. Pick a model,
press one button, watch a bar fill — and afterwards the file lies where the
runner looks for it. A command to copy would have been quicker to build and
would have missed the whole purpose of the program.

Four rules, and each of them keeps a way out of the folder shut:

* **Only huggingface.co.** The address is built here from a repository and a
  file name; it never arrives from outside.
* **Only ``.gguf``.** That is what the runner can start. Anything else in
  the folder would be dead weight at best.
* **The name is a name.** It ends up in a folder, so a slash or a ``..`` in
  it would end up somewhere else.
* **One download at a time.** Two would fight over the same disk and give
  two half-files.

A file being written carries a ``.teil`` ending until it is complete, and is
only then renamed. Nothing half-downloaded is ever mistaken for a model —
which is what a model server would do, right before it fails to explain why.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import httpx

from app import modellzuordnung

BASIS = "https://huggingface.co"
ENDUNG = ".gguf"
UNFERTIG = ".teil"

# Big enough not to wake the loop for every packet, small enough that the bar
# still moves while a fibre line is running.
BROCKEN = 1024 * 1024


@dataclass
class Fortschritt:
    datei: str
    geladen: int
    gesamt: int
    fertig: bool = False
    fehler: str | None = None

    @property
    def anteil(self) -> float:
        return round(self.geladen / self.gesamt, 4) if self.gesamt else 0.0


class DownloadFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


def _pruefen(datei: str) -> str:
    if "/" in datei or "\\" in datei or ".." in datei or datei.startswith("."):
        raise DownloadFehler("name")
    if not datei.lower().endswith(ENDUNG):
        raise DownloadFehler("endung")
    return datei


class Modelldownload:
    """One download, watchable while it runs."""

    def __init__(self, ordner: Path) -> None:
        self._ordner = Path(ordner).expanduser()
        self._stand: Fortschritt | None = None
        self._abbruch = threading.Event()
        self._schloss = threading.Lock()

    def stand(self) -> Fortschritt | None:
        return self._stand

    def laeuft(self) -> bool:
        return self._stand is not None and not self._stand.fertig and not self._stand.fehler

    def abbrechen(self) -> bool:
        if not self.laeuft():
            return False
        self._abbruch.set()
        return True

    def starten(
        self,
        repo: str,
        datei: str,
        ziel: str | None = None,
        gehoert_zu: str | None = None,
        rolle: str | None = None,
        ordner: Path | None = None,
    ) -> Fortschritt:
        """``ziel`` is the local name, when it must differ from the remote one.

        Vision companions need this: several repositories call their
        projector plainly ``mmproj-BF16.gguf``, and two of those in one
        folder would silently overwrite each other. The remote name stays in
        the address, the local name keeps the model it belongs to.

        ``gehoert_zu`` and ``rolle`` declare that this file is a companion of
        another model: when both are set, the bond is written into the folder
        manifest once the file is truly in place, so the runner reads it
        instead of guessing. Left absent, a download behaves as before.

        ``ordner`` is the destination folder, when it is not the chat model
        folder this instance was built on. Each server reads only its own
        folder, so the file must land where its kind of server looks — an
        embedding model in the chat folder is invisible to the embedding
        server and a broken entry in the chat list.
        """
        with self._schloss:
            if self.laeuft():
                raise DownloadFehler("laeuft_schon")

            zielordner = Path(ordner).expanduser() if ordner else self._ordner
            _pruefen(datei)
            ziel = _pruefen(ziel) if ziel else datei
            if (zielordner / ziel).is_file():
                raise DownloadFehler("schon_da")

            self._abbruch.clear()
            self._stand = Fortschritt(datei=ziel, geladen=0, gesamt=0)
            threading.Thread(
                target=self._holen,
                args=(repo, datei, ziel, gehoert_zu, rolle, zielordner),
                daemon=True,
            ).start()
            return self._stand

    def _holen(
        self,
        repo: str,
        datei: str,
        ziel_name: str,
        gehoert_zu: str | None = None,
        rolle: str | None = None,
        ordner: Path | None = None,
    ) -> None:
        zielordner = ordner if ordner is not None else self._ordner
        zielordner.mkdir(parents=True, exist_ok=True)
        ziel = zielordner / ziel_name
        halb = zielordner / (ziel_name + UNFERTIG)
        adresse = f"{BASIS}/{repo}/resolve/main/{datei}"

        # A Hugging Face token, when the user set one: lifts rate limits and
        # opens gated models. Everything public works without it.
        import os

        kopf = {}
        wert = os.environ.get("HF_TOKEN", "").strip()
        if wert:
            kopf["Authorization"] = f"Bearer {wert}"

        try:
            with httpx.stream(
                "GET", adresse, follow_redirects=True, timeout=60, headers=kopf
            ) as antwort:
                antwort.raise_for_status()
                gesamt = int(antwort.headers.get("content-length") or 0)
                if self._stand:
                    self._stand.gesamt = gesamt

                with halb.open("wb") as schreiben:
                    for brocken in antwort.iter_bytes(BROCKEN):
                        if self._abbruch.is_set():
                            raise DownloadFehler("abgebrochen")
                        schreiben.write(brocken)
                        if self._stand:
                            self._stand.geladen += len(brocken)

            # Only now does it become a model. Renaming is the one step that
            # makes a finished file visible to the runner.
            halb.replace(ziel)

            # The bond is recorded only after the file is truly in place, so a
            # cancelled or failed fetch leaves no dangling manifest entry.
            if gehoert_zu and rolle:
                modellzuordnung.eintragen(zielordner, gehoert_zu, rolle, ziel_name)

            if self._stand:
                self._stand.geladen = ziel.stat().st_size
                self._stand.gesamt = self._stand.geladen
                self._stand.fertig = True

        except Exception as fehler:  # noqa: BLE001 - the reason belongs in the state
            halb.unlink(missing_ok=True)
            if self._stand:
                self._stand.fehler = (
                    fehler.grund if isinstance(fehler, DownloadFehler) else "fehlgeschlagen"
                )
