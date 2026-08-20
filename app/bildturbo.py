"""Image-Turbo: an optional persistent sd-server, so the model stays loaded.

sd-cli is the default and always works — one model load per picture. That is
right for the occasional picture, and it is what ships on. Image-Turbo is the
speed-up somebody switches on: sd-server holds the model in memory, and every
picture after the first is drawn without paying the load again. Measured on
this machine: ~12 s against ~32 s for the same SD-1.5 512 picture.

The same split the embedding server uses, and for the same reason — a speed-up,
never a dependency:

* running     → the picture comes over HTTP, the model already in memory
* not running → sd-cli draws it, exactly as before

Its own everything: its own port, its own note file, and its own binary
(``sd-server``, which sits next to ``sd-cli`` in the fetched build). Nothing is
shared, so nothing collides.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from app import prozessstopp
from app.sddownload import ORDNER

log = logging.getLogger(__name__)

# The persistent server binary — the sibling of sd-cli in the same build.
PROGRAMM = "sd-server.exe" if sys.platform == "win32" else "sd-server"

# The note that finds an orphan again after a service restart. Its own name,
# so it never erases the model server's or the embedding server's.
PID_DATEI = ".bildturbo.pid"

# The port Image-Turbo listens on — its own, away from the model server (8080),
# the embedding server and the app itself.
PORT = 8191

# How long to wait for the model to load before calling the start a failure.
# A big SDXL checkpoint on a cold cache takes a while; too short a wait would
# report a red lamp on a server that was only still loading.
STARTFRIST = 120.0
# The ceiling for one picture once the model is up: the same fifteen minutes
# the sd-cli path allows (app/bildrunner.py ZEITGRENZE). A large highres
# picture on a Mac genuinely takes six or seven, and both paths must give it
# the same generous room — the limit only guards against a truly stuck
# server, it must never cut off a slow but honest draw.
ZEICHENFRIST = 900.0

# The same step bar sd-cli prints — sd-server writes it to its stdout too,
# so the filling frame gets its honest number on the turbo path as well.
_SCHRITT_MUSTER = re.compile(r"\|\s*(\d+)/(\d+)\s*-")


def programm_finden(datenordner: Path) -> Path | None:
    """The sd-server binary, or nothing if this machine has none.

    Only the fetched build is looked at — sd-server is not a thing people put
    on their PATH the way they might sd-cli, and it must be the same build as
    the sd-cli that drew the one-shot pictures, or the two would disagree.
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


class BildturboFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


class Bildturbo:
    """One persistent picture server, switched on and off by hand."""

    def __init__(self, datenordner: Path) -> None:
        self._datenordner = Path(datenordner).expanduser()
        self._prozess: subprocess.Popen | None = None
        self._modell: str | None = None
        # The rest of the harness the server was started with — the "Gespann".
        # VAE and detector bind at start (they are start flags, not per-request
        # HTTP fields), so a request that wants a different one needs a fresh
        # server. LoRAs are NOT here: they travel in the prompt and need only
        # the folder, which is always pointed at, so they never force a restart.
        self._vae: str | None = None
        self._ad_modell: str | None = None
        self._ad_prompt: str = ""
        self._zeichnet = False
        # Set by ``abbrechen`` so the draw it interrupts reports itself as a
        # silent stop, not a failure.
        self._abgebrochen = False
        self._schloss = threading.Lock()
        self._pid_datei = self._datenordner / PID_DATEI
        # The running picture's honest step counter, fed by the stdout reader.
        # None whenever no picture is in flight — the loader prints bars too,
        # so counting is armed per request (``_zaehl``) and disarmed after.
        self._fortschritt: dict | None = None
        self._zaehl: dict | None = None

    @property
    def programm(self) -> Path | None:
        return programm_finden(self._datenordner)

    @property
    def modell(self) -> str | None:
        return self._modell if self.laeuft() else None

    def laeuft(self) -> bool:
        return self._prozess is not None and self._prozess.poll() is None

    def passt_zu(
        self,
        modell: str,
        vae: str | None = None,
        ad_modell: str | None = None,
        ad_prompt: str = "",
    ) -> bool:
        """Does the running server already carry this Gespann — same model, VAE
        and detector? Then the picture goes straight over HTTP. A mismatch (or a
        stopped server) means the caller must restart it with the new flags
        first. The detector's prompt counts too: it is a start flag, so a
        different one is a different server; it is only compared when a detector
        is actually set."""
        if not self.laeuft():
            return False
        soll_ad_prompt = ad_prompt if ad_modell else ""
        return (
            self._modell == modell
            and (self._vae or None) == (vae or None)
            and (self._ad_modell or None) == (ad_modell or None)
            and (self._ad_prompt or "") == (soll_ad_prompt or "")
        )

    def zustand(self) -> str:
        """What the plus-menu plaque colours itself by.

        ``aus`` (grey) → off. ``bereit`` (green) → up and idle. ``zeichnet``
        (blue) → a picture is in flight, or the server is still coming up.
        ``fehler`` (red) → it was started but the process is gone.
        """
        if self._prozess is None:
            return "aus"
        if self._prozess.poll() is not None:
            return "fehler"
        if self._zeichnet or not self._bereit():
            return "zeichnet"
        return "bereit"

    def _bereit(self) -> bool:
        """Does the server already answer — i.e. has the model finished
        loading? Cheap enough to ask on every status poll."""
        try:
            antwort = httpx.get(f"http://127.0.0.1:{PORT}/sdapi/v1/options", timeout=1.0)
            return antwort.status_code == 200
        except httpx.HTTPError:
            return False

    def starten(
        self,
        modell_pfad: Path,
        *,
        vae: Path | None = None,
        ad_modell: Path | None = None,
        ad_prompt: str = "",
        lora_ordner: Path | None = None,
        embd_ordner: Path | None = None,
    ) -> None:
        """Bring the server up on the given model and Gespann. Returns once the
        process is launched; the model may still be loading (the plaque shows
        blue until it answers, and ``bereit_abwarten`` is how the request path
        waits for it). Idempotent-ish: a running server is stopped first so a
        model or Gespann switch is one call.

        VAE and detector are start flags — they bind to this one server, so a
        different one means a fresh start. The LoRA folder is pointed at
        whenever it is given (even with no LoRA in this first picture), and the
        apply mode is pinned to ``at_runtime``: the auto/immediate path applies
        0 of N tensors on this Metal build and then aborts in sampling (proven
        17.08., commit aaad442) — exactly the lock the sd-cli path already sets.
        """
        with self._schloss:
            programm = self.programm
            if programm is None:
                raise BildturboFehler("bild.kein_programm")
            self._stoppen_intern()
            self._raeum_waise()
            befehl = [
                str(programm),
                "-m", str(modell_pfad),
                "--listen-ip", "127.0.0.1",
                "--listen-port", str(PORT),
                # Flash attention in the diffusion model — this build supports
                # it (it is what makes the turbo a turbo), and here it is safe
                # because it is OUR binary, not an old one a user swapped in.
                "--diffusion-fa",
            ]
            if vae is not None:
                befehl += ["--vae", str(vae)]
            if ad_modell is not None:
                befehl += ["--ad-model", str(ad_modell)]
                if ad_prompt:
                    befehl += ["--ad-prompt", ad_prompt]
            if lora_ordner is not None:
                befehl += [
                    "--lora-model-dir", str(lora_ordner),
                    "--lora-apply-mode", "at_runtime",
                ]
            if embd_ordner is not None:
                befehl += ["--embd-dir", str(embd_ordner)]
            self._prozess = subprocess.Popen(
                befehl,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
            threading.Thread(
                target=self._zaehler_lesen, args=(self._prozess,), daemon=True
            ).start()
            self._modell = Path(modell_pfad).name
            self._vae = Path(vae).name if vae is not None else None
            self._ad_modell = Path(ad_modell).name if ad_modell is not None else None
            self._ad_prompt = ad_prompt if ad_modell is not None else ""
            self._pid_merken(self._prozess.pid)

    def bereit_abwarten(self, frist: float = STARTFRIST) -> bool:
        """Block until the server answers — i.e. the model has finished
        loading — or the deadline passes. Used by the request path after a
        Gespann restart: the very next thing it does is draw, and a draw against
        a still-loading server would fail. Returns False if the process died or
        the model never came up in time."""
        ende = time.monotonic() + frist
        while time.monotonic() < ende:
            if not self.laeuft():
                return False
            if self._bereit():
                return True
            time.sleep(0.5)
        return self._bereit()

    def stoppen(self) -> bool:
        """Switch the add-on off. True when there was one to switch off."""
        with self._schloss:
            return self._stoppen_intern()

    def abbrechen(self) -> bool:
        """Break off a picture being drawn right now. True when there was one.

        A turbo draw blocks in an HTTP call that has no cancel, so the only way
        to interrupt it is to end the server under it — the draw's request then
        fails, and the ``_abgebrochen`` flag turns that failure into the silent
        stop the user asked for. The loaded model goes with the server; the
        next turbo picture pays the load once more, which a deliberate stop of
        a whole series is worth. When nothing is drawing, this does nothing —
        a stop pressed on an idle warm server must not tear it down."""
        if not self._zeichnet:
            return False
        self._abgebrochen = True
        self.stoppen()
        return True

    def _stoppen_intern(self) -> bool:
        prozess = self._prozess
        self._modell = None
        self._vae = None
        self._ad_modell = None
        self._ad_prompt = ""
        self._zeichnet = False
        self._pid_datei.unlink(missing_ok=True)
        if prozess is None or prozess.poll() is not None:
            self._prozess = None
            return False
        prozessstopp.beenden(prozess, frist=5.0)
        self._prozess = None
        return True

    def fortschritt(self) -> dict | None:
        """The running picture's step counter, or None when nothing is in
        flight — the same shape the sd-cli runner reports, so the one
        progress endpoint can serve both paths."""
        if not self.laeuft() or not self._zeichnet:
            return None
        return self._fortschritt

    def _zaehler_lesen(self, prozess: subprocess.Popen) -> None:
        """Lifelong stdout reader for one server process. Counting is armed
        per request by ``zeichnen``: only bars whose total equals the
        requested step count are painting passes (the loader prints bars
        with tensor counts), and pass counting mirrors the sd-cli reader —
        a step number falling back means the next pass (detector) began."""
        rest = ""
        letzte_zaehl = None
        while True:
            try:
                stueck = prozess.stdout.read(256)
            except (OSError, ValueError):
                break
            if not stueck:
                break
            zaehl = self._zaehl
            if zaehl is None:
                rest = ""
                letzte_zaehl = None
                continue
            # A fresh counter means the next picture began — drop the tail
            # carried from the last one, or a leftover bar of picture N could
            # be matched at the start of N+1 on this lifelong reader.
            if zaehl is not letzte_zaehl:
                rest = ""
                letzte_zaehl = zaehl
            text = rest + stueck
            for treffer in _SCHRITT_MUSTER.finditer(text):
                if treffer.end() <= len(rest):
                    continue  # already seen in the previous round
                schritt, gesamt = int(treffer.group(1)), int(treffer.group(2))
                # Same rule as the sd-cli reader: before painting starts only
                # the requested step count counts; afterwards every bar is
                # real remaining work (detector faces with their own step
                # count included), and extra passes stay inside the last
                # share instead of pushing past the end.
                if gesamt != zaehl["schritte"] and not zaehl["malt"]:
                    continue
                zaehl["malt"] = True
                if schritt < zaehl["letzter"]:
                    zaehl["fertige"] = min(zaehl["fertige"] + 1, zaehl["paesse"] - 1)
                zaehl["letzter"] = schritt
                anteil = (zaehl["fertige"] + schritt / gesamt) / zaehl["paesse"]
                self._fortschritt = {
                    "anteil": min(anteil, 0.99),
                    "schritt": schritt,
                    "gesamt": gesamt,
                }
            rest = text[-64:]

    def zeichnen(self, auftrag: dict) -> bytes:
        """Draw one picture over the running server and return the PNG bytes.

        ``auftrag`` is the A1111 txt2img body already assembled by the caller —
        this module only speaks HTTP and knows nothing of the parameter names.
        """
        if not self.laeuft():
            raise BildturboFehler("bild.turbo_aus")
        self._zeichnet = True
        self._abgebrochen = False
        schritte = int(auftrag.get("steps") or 0)
        if schritte > 0:
            # One painting pass, plus one more when the detector repaints.
            self._fortschritt = {"anteil": 0.0, "schritt": 0, "gesamt": schritte}
            self._zaehl = {
                "schritte": schritte,
                "paesse": 1 + (1 if self._ad_modell else 0),
                "fertige": 0,
                "letzter": 0,
                "malt": False,
            }
        try:
            antwort = httpx.post(
                f"http://127.0.0.1:{PORT}/sdapi/v1/txt2img",
                json=auftrag,
                timeout=ZEICHENFRIST,
            )
            antwort.raise_for_status()
            bilder = antwort.json().get("images") or []
            if not bilder:
                raise BildturboFehler("bild.gescheitert")
            return base64.b64decode(bilder[0])
        except httpx.HTTPError as fehler:
            # A draw broken off by ``abbrechen`` (the server was ended under
            # it) is not a failure — it is the stop the user asked for, and it
            # must read as the same silent abort the sd-cli path returns.
            if self._abgebrochen:
                raise BildturboFehler("bild.abgebrochen") from fehler
            raise BildturboFehler("bild.gescheitert") from fehler
        finally:
            self._zeichnet = False
            self._abgebrochen = False
            self._zaehl = None
            self._fortschritt = None

    # --- Orphan handling: a server outlives a service crash on its own
    #     process group; after a restart the service ends the leftover so the
    #     port is free again. ------------------------------------------------

    def _pid_merken(self, pid: int) -> None:
        try:
            self._pid_datei.write_text(str(pid), encoding="utf-8")
        except OSError:
            log.debug("Bildturbo-PID nicht notierbar", exc_info=True)

    def _raeum_waise(self) -> None:
        try:
            alt = int(self._pid_datei.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return
        try:
            antwort = subprocess.run(
                ["ps", "-p", str(alt), "-o", "comm="],
                capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return
        if "sd-server" in antwort.stdout:
            try:
                os.kill(alt, 15)
            except OSError:
                pass
        self._pid_datei.unlink(missing_ok=True)
