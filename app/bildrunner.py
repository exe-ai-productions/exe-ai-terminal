"""Making a picture on this machine, with nothing leaving it.

The sibling of ``app/modellrunner.py``, and deliberately built the other way
round. A language model is a SERVER: it is started once, holds its weights,
and answers for hours. An image is a single call — the program starts,
loads, draws, writes a file and is gone. Keeping a picture server warm
would hold gigabytes for something that runs for half a minute every few
minutes.

That difference is why there is no port here, no health check and no
orphan to find again after a restart: one call, one image, one file.

**One run at a time.** Two of these side by side would ask the machine for
both models at once, and on a shared memory pool that is how a Mac starts
swapping instead of drawing. The lock is not about the program, it is about
the memory.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from app import prozessstopp

log = logging.getLogger(__name__)

# The program is called `sd-cli` in the official packages. Looked for on
# PATH first, then in the data folder — the same order as the model server,
# so somebody who installed their own build gets theirs.
PROGRAMM = "sd-cli.exe" if sys.platform == "win32" else "sd-cli"
ORDNER = "stable-diffusion.cpp"

# Long enough for a big picture on a slow machine, short enough that a run
# gone wrong does not hold the lock for the rest of the evening.
ZEITGRENZE = 300

# How long a cancelled generator gets to end before it is killed. Short: the
# caller is holding a request open on this answer, and a program told to stop
# drawing has nothing left to finish.
ABBRUCH_FRIST = 5


class BildFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund


@dataclass(frozen=True)
class LoRA:
    """One LoRA and how strongly it applies.

    ONE strength, and that is not a simplification on our side: sd.cpp
    applies a LoRA with a single multiplier. The separate model and clip
    strengths people know from ComfyUI are that program's concept; offering
    two fields here would mean silently dropping one of them.
    """

    name: str
    staerke: float = 0.70


@dataclass(frozen=True)
class Auftrag:
    """One picture, fully described. Checked before it gets here."""

    modell: Path
    prompt: str
    negativ: str = ""
    breite: int = 512
    hoehe: int = 512
    schritte: int = 20
    cfg: float = 7.0
    seed: int = -1
    sampler: str = "euler_a"
    scheduler: str = "karras"
    # Stackable, in the order they were added — that order is what the
    # prompt syntax carries, so it is what the picture gets.
    loras: tuple[LoRA, ...] = ()
    lora_ordner: Path | None = None
    # An image to start from, and how much of it to paint over. 1.0 means
    # nothing of it survives, which is what a picture made from nothing is —
    # so without a starting image the value never leaves 1.0.
    startbild: Path | None = None
    staerke: float = 1.0
    # Black and white, the starting image's size: white is what gets drawn
    # again. Only means anything beside a starting image — a mask without
    # one has nothing to mask.
    maske: Path | None = None


def programm_finden(datenordner: Path) -> Path | None:
    """The sd-cli binary, or nothing if this machine has none.

    PATH first, so somebody who installed their own build gets theirs. Then
    the data folder, which is where the fetch next door puts it — bare for a
    build unpacked by hand, one level down in a build-named folder for a
    fetched one. That second case is what makes the fetch worth having: a
    program nobody can find is a program nobody got.
    """
    gefunden = shutil.which(PROGRAMM)
    if gefunden:
        return Path(gefunden)
    from app.sddownload import gefundenes_programm

    return gefundenes_programm(datenordner)


def modelle(bildordner: Path) -> list[str]:
    """The image models lying in their own folder, by file name."""
    ordner = Path(bildordner).expanduser()
    if not ordner.is_dir():
        return []
    return sorted(
        p.name for p in ordner.iterdir() if p.is_file() and p.suffix in {".gguf", ".safetensors"}
    )


def loras(bildordner: Path) -> list[str]:
    """The LoRA files in their own folder below the image models."""
    ordner = Path(bildordner).expanduser() / "lora"
    if not ordner.is_dir():
        return []
    return sorted(
        p.name for p in ordner.iterdir()
        if p.is_file() and p.suffix in {".gguf", ".safetensors", ".ckpt", ".pt"}
    )


def lora_pfad(bildordner: Path, name: str) -> Path:
    """A LoRA NAME turned into a path, under the same rule as a model."""
    if not name or "/" in name or "\\" in name or name != Path(name).name:
        raise BildFehler("bild.lora_unbekannt")
    if name not in loras(bildordner):
        raise BildFehler("bild.lora_unbekannt")
    return Path(bildordner).expanduser() / "lora" / name


def modell_pfad(bildordner: Path, name: str) -> Path:
    """A model NAME turned into a path — never the other way round.

    The name comes from a request, so it is treated as hostile: only a bare
    file name is accepted, and only one that is really lying in the image
    model folder. Anything with a separator in it, or anything the folder
    does not contain, is refused before it can become a path at all.
    """
    if not name or "/" in name or "\\" in name or name != Path(name).name:
        raise BildFehler("bild.modell_unbekannt")
    if name not in modelle(bildordner):
        raise BildFehler("bild.modell_unbekannt")
    return Path(bildordner).expanduser() / name


class Bildrunner:
    """One picture at a time, on this machine."""

    def __init__(self, datenordner: Path) -> None:
        self._datenordner = Path(datenordner).expanduser()
        self._schloss = threading.Lock()
        # The running program, so a stop can actually reach it. Without this
        # the only way out of a picture was to wait five minutes for the
        # time limit — and the panel had no way of saying so.
        self._prozess: subprocess.Popen | None = None
        self._abgebrochen = False

    @property
    def programm(self) -> Path | None:
        return programm_finden(self._datenordner)

    def laeuft(self) -> bool:
        return self._schloss.locked()

    def stoppen(self) -> bool:
        """End the running picture. True when there was one to end.

        The whole tree goes, not just the parent — a generator that kept
        working after the stop would hold the lock and the memory for a
        picture nobody is waiting for anymore.

        How a tree is reached differs per system, which is why it lives in
        ``app/prozessstopp.py``. Reaching for the POSIX call directly is what
        made this button do nothing on Windows: ``os.killpg`` does not exist
        there and raises AttributeError, which is not an OSError and so fell
        straight through the guard below it.

        Waited on rather than fired and forgotten: the caller releases the
        lock on the strength of this answer, and a second generator started
        while the first is still drawing is the one thing a machine at its
        memory limit cannot take.
        """
        prozess = self._prozess
        if prozess is None or prozess.poll() is not None:
            return False
        self._abgebrochen = True
        prozessstopp.beenden(prozess, frist=ABBRUCH_FRIST)
        return True

    def befehl(self, auftrag: Auftrag, ziel: Path) -> list[str]:
        """The command line, built in one place so it can be read in one."""
        programm = self.programm
        if programm is None:
            raise BildFehler("bild.kein_programm")
        # A LoRA is not a command-line option in this program — it is
        # written into the prompt, and the folder is pointed at separately.
        # So the stack is appended to the prompt here rather than passed as
        # flags, which is also why the order of the list survives.
        prompt = auftrag.prompt
        for lora in auftrag.loras:
            prompt += f" <lora:{Path(lora.name).stem}:{lora.staerke}>"
        teile = [
            str(programm),
            "-m", str(auftrag.modell),
            "-p", prompt,
            "-W", str(auftrag.breite),
            "-H", str(auftrag.hoehe),
            "--steps", str(auftrag.schritte),
            "--cfg-scale", str(auftrag.cfg),
            "--seed", str(auftrag.seed),
            "--sampling-method", auftrag.sampler,
            "--scheduler", auftrag.scheduler,
            "-o", str(ziel),
        ]
        if auftrag.negativ:
            teile += ["--negative-prompt", auftrag.negativ]
        if auftrag.loras and auftrag.lora_ordner is not None:
            teile += ["--lora-model-dir", str(auftrag.lora_ordner)]
        # The strength only means anything beside a starting image. Sent
        # without one it would be a number the program quietly ignores, and
        # a control that does nothing is worse than no control.
        if auftrag.startbild is not None:
            teile += ["-i", str(auftrag.startbild), "--strength", str(auftrag.staerke)]
            if auftrag.maske is not None:
                teile += ["--mask", str(auftrag.maske)]
        return teile

    def erzeugen(self, auftrag: Auftrag, ziel: Path) -> Path:
        """Draw one picture into `ziel`. Blocks for as long as it takes."""
        if not self._schloss.acquire(blocking=False):
            raise BildFehler("bild.laeuft_schon")
        try:
            befehl = self.befehl(auftrag, ziel)
            ziel.parent.mkdir(parents=True, exist_ok=True)
            # The prompt is left out of the log on purpose: what somebody
            # asks a picture generator for is their business, and a log file
            # is read by whoever gets the machine next.
            log.info(
                "Bild: %s, %dx%d, %d Schritte, Seed %s",
                auftrag.modell.name, auftrag.breite, auftrag.hoehe,
                auftrag.schritte, auftrag.seed,
            )
            self._abgebrochen = False
            try:
                # Popen and not run(): a stop has to be able to reach the
                # program, and run() hands back only the finished result.
                # Its own process group, so ending it takes the whole thing.
                self._prozess = subprocess.Popen(
                    befehl,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
            except OSError as fehler:
                raise BildFehler("bild.kein_programm") from fehler
            try:
                _, fehlertext = self._prozess.communicate(timeout=ZEITGRENZE)
            except subprocess.TimeoutExpired as fehler:
                self.stoppen()
                # Collect the child so no zombie is left behind.
                self._prozess.communicate()
                raise BildFehler("bild.zeit_abgelaufen") from fehler
            if self._abgebrochen:
                # A stopped picture is not a failed one. The difference
                # matters at the other end: one is reported, the other is
                # what the user just asked for.
                ziel.unlink(missing_ok=True)
                raise BildFehler("bild.abgebrochen")
            if self._prozess.returncode != 0 or not ziel.is_file():
                log.warning(
                    "Bild gescheitert (%s): %s",
                    self._prozess.returncode, (fehlertext or "")[-500:],
                )
                raise BildFehler("bild.gescheitert")
            return ziel
        finally:
            self._prozess = None
            self._schloss.release()
