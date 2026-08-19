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
import re
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
# 300 killed honest runs: an SDXL highres pass renders a second time at
# 2048² and legitimately needs several minutes on Metal. The limit exists
# for HUNG processes, not slow ones — the stop button covers impatience.
ZEITGRENZE = 900

# How long a cancelled generator gets to end before it is killed. Short: the
# caller is holding a request open on this answer, and a program told to stop
# drawing has nothing left to finish.
ABBRUCH_FRIST = 5

# The painter's progress bar on stderr: "|####      | 12/28 - 3.10it/s".
# The loader prints bars in the same shape with tensor counts, which is why
# the reader only trusts bars whose total equals the requested step count.
_SCHRITT_MUSTER = re.compile(r"\|\s*(\d+)/(\d+)\s*-")


class BildFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself.

    `protokoll` optionally carries the painter's REAL last words (raw
    stderr) — shown verbatim to the user, never paraphrased: a rewritten
    error catalogue would only hide the one line that explains the crash
    (house rule)."""

    def __init__(self, grund: str, protokoll: str | None = None) -> None:
        super().__init__(grund)
        self.grund = grund
        self.protokoll = protokoll


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
    # How many of CLIP's last layers to ignore. -1 means "unspecified", which
    # the generator turns into the right value per model class. A few models
    # (notably some SD-1.5 anime checkpoints) were trained expecting one layer
    # skipped and look wrong without it.
    clip_skip: int = -1
    # A standalone VAE — the part that turns the model's internal number-image
    # into real pixels. A model's built-in VAE is often the weak link; the
    # right external one is where washed-out colour and mushy detail come back.
    vae: Path | None = None
    # ADetailer: a small detector that finds faces and redraws each one at
    # full resolution, so a face that came out as a smear in a wide shot is
    # painted again sharp. The model file is the detector (a YOLO net); an
    # empty file means the pass is off.
    ad_modell: Path | None = None
    ad_prompt: str = ""
    # Flash attention in the diffusion model — faster where the machine can do
    # it, no effect on the picture. ON by default: measured on the shipped build
    # (master-820), the second, high-resolution pass of the highres fix drops
    # from ~30 s per step to ~3.5 s — nine times faster, the difference between
    # a usable highres fix and one that runs past the time limit and gets
    # killed. The persistent server (Image-Turbo) already runs with it. The risk
    # it was held back for — an older sd-cli a user swapped in that predates the
    # flag and refuses the unknown argument — is against the binary we ship, so
    # the default follows our build, not a hypothetical replacement.
    diffusion_fa: bool = True
    # Highres fix: draw at the base size, then upscale and paint over the
    # result at the larger size, so fine detail the first pass could not fit
    # arrives on the second. `hires_scale` is how much larger (2.0 = double);
    # `hires_steps` 0 reuses the main step count. Off by default — it roughly
    # doubles the time, and most drafts do not need it.
    hires: bool = False
    hires_scale: float = 2.0
    hires_steps: int = 0
    # Process the VAE in tiles to save memory on a big picture. Off by
    # default; the plumbing is here for a low-memory machine that would
    # otherwise run out on the final decode.
    vae_tiling: bool = False


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


# The two companion kinds, each in its own subfolder below the image models —
# the same shape as `lora/`, so nothing collides with a model in the picker.
VAE_ORDNER = "vae"
YOLO_ORDNER = "adetailer"


def _im_unterordner(bildordner: Path, unter: str) -> list[str]:
    ordner = Path(bildordner).expanduser() / unter
    if not ordner.is_dir():
        return []
    return sorted(
        p.name for p in ordner.iterdir()
        if p.is_file() and p.suffix in {".gguf", ".safetensors", ".ckpt", ".pt", ".pth", ".onnx"}
    )


def vaes(bildordner: Path) -> list[str]:
    """The standalone VAE files in their own folder below the image models."""
    return _im_unterordner(bildordner, VAE_ORDNER)


def yolos(bildordner: Path) -> list[str]:
    """The ADetailer detector models in their own folder."""
    return _im_unterordner(bildordner, YOLO_ORDNER)


def _begleiter_pfad(bildordner: Path, name: str, unter: str, vorhanden: list[str]) -> Path:
    """A companion NAME turned into a path — hostile name treated as hostile,
    exactly like a model or a LoRA: bare file name, really in its folder."""
    if not name or "/" in name or "\\" in name or name != Path(name).name:
        raise BildFehler("bild.begleiter_unbekannt")
    if name not in vorhanden:
        raise BildFehler("bild.begleiter_unbekannt")
    return Path(bildordner).expanduser() / unter / name


def vae_pfad(bildordner: Path, name: str) -> Path:
    return _begleiter_pfad(bildordner, name, VAE_ORDNER, vaes(bildordner))


def yolo_pfad(bildordner: Path, name: str) -> Path:
    return _begleiter_pfad(bildordner, name, YOLO_ORDNER, yolos(bildordner))


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
        # The live step counter of the running picture, or None while no
        # picture runs — what the filling frame in the interface drinks from.
        self._fortschritt: dict | None = None

    def fortschritt(self) -> dict | None:
        """The running picture's honest progress, or nothing while idle."""
        return self._fortschritt if self.laeuft() else None

    def reservieren(self) -> None:
        """Take the one-picture-at-a-time lock without drawing — the turbo
        path borrows it so a turbo picture and an sd-cli picture can never
        run at once, and a second request cannot restart the server under a
        running draw. Pairs with ``freigeben``."""
        if not self._schloss.acquire(blocking=False):
            raise BildFehler("bild.laeuft_schon")

    def freigeben(self) -> None:
        self._schloss.release()

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
            # NEVER the auto mode: on this Metal build the "immediately"
            # path applies 0 of N tensors and then aborts inside sampling
            # (ggml-backend.cpp:930, found live with LCM and Hyper-SD).
            # at_runtime applies every tensor and renders — proven live
            # with LCM-SD15, LCM-SDXL and Hyper-SD15.
            teile += ["--lora-apply-mode", "at_runtime"]
        # The quality companions. Each is left off entirely when unset, so the
        # command line carries only what was actually chosen.
        if auftrag.clip_skip > 0:
            teile += ["--clip-skip", str(auftrag.clip_skip)]
        if auftrag.vae is not None:
            teile += ["--vae", str(auftrag.vae)]
        if auftrag.diffusion_fa:
            teile += ["--diffusion-fa"]
        if auftrag.vae_tiling:
            teile += ["--vae-tiling"]
        if auftrag.hires:
            teile += ["--hires", "--hires-scale", str(auftrag.hires_scale)]
            if auftrag.hires_steps > 0:
                teile += ["--hires-steps", str(auftrag.hires_steps)]
        if auftrag.ad_modell is not None:
            teile += ["--ad-model", str(auftrag.ad_modell)]
            if auftrag.ad_prompt:
                teile += ["--ad-prompt", auftrag.ad_prompt]
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
                # BOTH streams are read live, each by its own reader: the
                # painter prints its log and the step counter on stdout,
                # ggml its asserts on stderr — the counter feeds the filling
                # frame, and both texts together feed the honest error.
                self._prozess = subprocess.Popen(
                    befehl,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
            except OSError as fehler:
                raise BildFehler("bild.kein_programm") from fehler

            # Honest percent: only bars whose total equals the requested
            # step count are painting passes (the loader prints bars too,
            # with tensor counts). A run has a known number of passes —
            # base, plus highres, plus one detailer pass — and the overall
            # share is passes done plus the current pass's fraction.
            erwartete_paesse = 1 + (1 if auftrag.hires else 0) + (1 if auftrag.ad_modell else 0)
            ausgabeteile: list[str] = []
            fehlerteile: list[str] = []
            self._fortschritt = {"anteil": 0.0, "schritt": 0, "gesamt": auftrag.schritte}
            fertige_paesse = 0
            letzter_schritt = 0

            # The stream handles are caught in locals BEFORE the threads
            # start: a reader that outlives the wait (a grandchild holding
            # the pipe open) must never reach for self._prozess after the
            # finally block has nulled it.
            ausgang, fehlerkanal = self._prozess.stdout, self._prozess.stderr

            def _zaehler_lesen() -> None:
                nonlocal fertige_paesse, letzter_schritt
                rest = ""
                malt = False  # the first painting bar has been seen
                while True:
                    stueck = ausgang.read(256)
                    if not stueck:
                        break
                    ausgabeteile.append(stueck)
                    text = rest + stueck
                    for treffer in _SCHRITT_MUSTER.finditer(text):
                        if treffer.end() <= len(rest):
                            continue  # already seen in the previous round
                        schritt, gesamt = int(treffer.group(1)), int(treffer.group(2))
                        # Before painting starts, only a bar with the requested
                        # step count is a painting pass — everything else is
                        # the loader. Once painting has begun, EVERY later bar
                        # is real remaining work: the detector repaints each
                        # found face, often with its own step count, and
                        # filtering those out froze the number.
                        if gesamt != auftrag.schritte and not malt:
                            continue
                        malt = True
                        if schritt < letzter_schritt:
                            # A new pass began. More faces than expected stay
                            # inside the last pass's share instead of pushing
                            # the figure past the end.
                            fertige_paesse = min(fertige_paesse + 1, erwartete_paesse - 1)
                        letzter_schritt = schritt
                        anteil = (fertige_paesse + schritt / gesamt) / erwartete_paesse
                        self._fortschritt = {
                            "anteil": min(anteil, 0.99),
                            "schritt": schritt,
                            "gesamt": gesamt,
                        }
                    rest = text[-64:]

            def _fehler_lesen() -> None:
                while True:
                    stueck = fehlerkanal.read(256)
                    if not stueck:
                        break
                    fehlerteile.append(stueck)

            leser = [
                threading.Thread(target=_zaehler_lesen, daemon=True),
                threading.Thread(target=_fehler_lesen, daemon=True),
            ]
            for l in leser:
                l.start()
            try:
                self._prozess.wait(timeout=ZEITGRENZE)
            except subprocess.TimeoutExpired as fehler:
                self.stoppen()
                # Collect the child so no zombie is left behind.
                self._prozess.wait()
                for l in leser:
                    l.join(timeout=5)
                raise BildFehler("bild.zeit_abgelaufen") from fehler
            for l in leser:
                l.join(timeout=5)
            # Both voices together: the painter's log (stdout) carries the
            # [ERROR] lines, ggml's aborts land on stderr.
            fehlertext = "".join(ausgabeteile) + "\n" + "".join(fehlerteile)
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
                # The user sees the painter's REAL lines, verbatim. The
                # telling ones (asserts, [ERROR]) usually stand BEFORE the
                # backtrace, so they are picked first; the raw tail only
                # fills in when no such line exists. Selection, never
                # rewording.
                zeilen = (fehlertext or "").splitlines()
                kern = [
                    z for z in zeilen
                    if "GGML_ASSERT" in z or "GGML_ABORT" in z
                    or "[ERROR]" in z or "error:" in z.lower()
                    # ggml aborts print "file.cpp:930: <reason>" without any
                    # ERROR marker — that reason line IS the crash message.
                    or (re.search(r"\.\w+:\d+: ", z) and not z.lstrip().startswith(("[INFO", "[WARN", "[DEBUG")))
                ]
                auszug = "\n".join(kern[-8:]) if kern else (fehlertext or "")[-1200:]
                raise BildFehler("bild.gescheitert", protokoll=auszug[-1200:])
            return ziel
        finally:
            self._prozess = None
            self._fortschritt = None
            self._schloss.release()
