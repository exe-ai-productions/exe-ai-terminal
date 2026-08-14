"""Starting and stopping a model server, with everything it does in view.

The program has always waited for a model server somebody else had started.
Everything that mattered about that server — how much context it holds, how
much of it sits on the graphics card, which file it loaded, why — lived in a
shell script nobody opens, and its output went into a log file nobody reads.

This module runs the server itself, so those things can be shown.

**GGUF only, on purpose.** `llama-server` is a plain program with prebuilt
versions for macOS, Windows and Linux, which means it can travel with an
installer. MLX is a Python package and would mean carrying a second Python
into a frozen program; it is a fine way to run a model on this machine and a
poor way to hand one to somebody else.

Three rules hold the whole thing together:

* **One server at a time.** Two would fight over the port and, worse, over
  the memory — the second one usually takes the machine down with it.
* **Only files from the model folder.** The path never comes from outside;
  a name is looked up in the folder, and what is not in there cannot start.
* **No shell.** The program is called directly with its arguments, so
  nothing in a file name can turn into a command.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import threading

from app import modellzuordnung
from app import prozessstopp
from app.feineinstellungen import Feineinstellungen, flags as feinflags
from app.modellprofil import startflags
from app.prozessspeicher import rss_gb
from collections import deque
from dataclasses import dataclass
from pathlib import Path

# Where a package manager puts it. Searched after PATH, because somebody who
# put it somewhere of their own means it.
BEKANNTE_ORTE = (
    "/opt/homebrew/bin/llama-server",
    "/usr/local/bin/llama-server",
    "/usr/bin/llama-server",
)

# How much of the output is kept. Enough to see a start fail, not enough to
# grow into a memory leak on a server that runs for days.
PROTOKOLL_ZEILEN = 400

# Where the started server's process id is noted. The server outlives the
# service on purpose (its own process group, so a service crash does not
# take the model down mid-answer) — but after a restart the service must
# find its own orphan again, or the next start dies quietly on a taken port.
PID_DATEI = ".modellserver.pid"

# The environment variable both sides share: the started llama-server reads
# it as its API key, the provider reads it to sign requests. Loopback keeps
# strangers out of the network; the key keeps out the browser on this very
# machine, where any open web page may knock on localhost. It travels as
# environment on purpose — on the command line it would sit in plain sight
# in the process list and the window that shows the command.
SCHLUESSEL_VARIABLE = "EXE_RUNNER_API_KEY"


def _ist_llama_server(pid: int) -> bool:
    """Is this process id really our kind of server?

    Asked before an orphan is ended: process ids get recycled, and ending
    whatever happens to hold one now would hit an innocent program.
    """
    try:
        antwort = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "llama-server" in antwort.stdout


def programm_finden(vorgabe: str | None = None) -> Path | None:
    """The llama-server binary, or nothing if this machine has none.

    Last on the list is the copy the program fetched itself — after PATH
    and the package managers' places, because somebody who installed their
    own build means that one.
    """
    if vorgabe:
        pfad = Path(vorgabe).expanduser()
        return pfad if pfad.is_file() and os.access(pfad, os.X_OK) else None

    gefunden = shutil.which("llama-server")
    if gefunden:
        return Path(gefunden)

    for ort in BEKANNTE_ORTE:
        pfad = Path(ort)
        if pfad.is_file() and os.access(pfad, os.X_OK):
            return pfad

    from app.paketierung import daten
    from app.serverdownload import gefundener_server

    return gefundener_server(daten())


@dataclass
class Modelldatei:
    name: str
    groesse_gb: float


def ist_mmproj(name: str) -> bool:
    """A vision projector, not a model.

    It belongs NEXT to a model (llama-server's ``--mmproj``) and cannot be
    started on its own — offered as a model it would sit in the picker as
    one that never answers.
    """
    return "mmproj" in name.lower()


def ist_mtp(name: str) -> bool:
    """A multi-token-prediction module, not a model.

    It cannot chat on its own, but it is the best draft a model can get:
    a few hundred megabytes trained alongside the big file to guess its
    next words. Started with ``--spec-type draft-mtp`` it rides along;
    offered as a model it would sit in the picker as one that never
    answers.
    """
    return "mtp" in name.lower()


def modelle_auflisten(ordner: Path) -> list[Modelldatei]:
    """The startable GGUF files in the model folder, largest first.

    Companion files are not models: vision projectors (mmproj) belong NEXT
    to a model, and multi-token-prediction modules (mtp) ride along as
    draft modules — offered as models, both would sit in the picker as
    entries that never answer.
    """
    if not ordner.is_dir():
        return []
    dateien = [
        Modelldatei(name=p.name, groesse_gb=round(p.stat().st_size / 1e9, 1))
        for p in sorted(ordner.glob("*.gguf"))
        if p.is_file() and not ist_mmproj(p.name) and not ist_mtp(p.name)
    ]
    return sorted(dateien, key=lambda d: d.groesse_gb, reverse=True)


def mtp_auflisten(ordner: Path) -> list[Modelldatei]:
    """The draft modules lying in the folder, with their sizes.

    Sizes ride along because the draft is a passenger in the memory plan —
    a quarter gigabyte is honest weight, just not much of it.
    """
    if not ordner.is_dir():
        return []
    return [
        Modelldatei(name=p.name, groesse_gb=round(p.stat().st_size / 1e9, 1))
        for p in sorted(ordner.glob("*.gguf"))
        if p.is_file() and ist_mtp(p.name) and not ist_mmproj(p.name)
    ]


def mmproj_auflisten(ordner: Path) -> list[str]:
    """The vision companions lying in the folder — names only."""
    if not ordner.is_dir():
        return []
    return sorted(p.name for p in ordner.glob("*.gguf") if p.is_file() and ist_mmproj(p.name))


def passende_mmproj(ordner: Path, modell: str) -> Path | None:
    """The projector that belongs to this model, or nothing.

    The tie is the file name: the projector must read ``<prefix>mmproj…``
    where ``<prefix>`` is also how the model file starts, at least four
    characters of it. That keeps ``Qwen3.6-35B-A3B-mmproj…`` away from
    ``Qwen3.6-27B-…`` — their shared prefix ends before the word mmproj —
    and a bare ``mmproj-BF16.gguf`` away from everything, because nothing
    guarantees whose eyes those are.
    """
    beste: tuple[int, Path] | None = None
    for name in mmproj_auflisten(ordner):
        laenge = 0
        for a, b in zip(name, modell):
            if a != b:
                break
            laenge += 1
        rest = name[laenge:]
        # The shared prefix may end right before a separator — the model
        # continues with its quant, the projector with "-mmproj".
        if rest[:1] in "-._":
            rest = rest[1:]
        if laenge < 4 or not rest.startswith("mmproj"):
            continue
        if beste is None or laenge > beste[0]:
            beste = (laenge, ordner / name)
    return beste[1] if beste else None


@dataclass
class Lauf:
    """What is running right now — the answer to every status question."""

    modell: str
    kontext: int
    schichten: int
    port: int
    # The draft model for speculative decoding, when one was chosen — a
    # small model guesses ahead, the big one only checks.
    drafter: str | None = None


class Modellrunner:
    """One model server, started and stopped from the program."""

    def __init__(
        self,
        modelle_ordner: Path,
        programm: str | None = None,
        *,
        port: int = 8080,
        pid_datei: str = PID_DATEI,
        schluessel_variable: str = SCHLUESSEL_VARIABLE,
        zusatzflags: tuple[str, ...] = (),
        sampling_flags: bool = True,
    ) -> None:
        """One server of one kind.

        Everything that could collide between two of these is a parameter:
        the port, the note that finds an orphan again, the environment
        variable carrying the key, and the flags that make the difference
        between a chat server and an embedding server. The first build had
        them as module constants, and a second server would have taken the
        first one's port and overwritten its key on start.
        """
        self._ordner = Path(modelle_ordner).expanduser()
        self._programm_vorgabe = programm
        self._port = port
        self._pid_datei = pid_datei
        self._schluessel_variable = schluessel_variable
        self._zusatzflags = tuple(zusatzflags)
        self._sampling_flags = sampling_flags
        self._prozess: subprocess.Popen | None = None
        self._lauf: Lauf | None = None
        # The key this server was started with. Kept here as well as in the
        # environment: the environment is one namespace for the whole
        # process, and whoever wants to talk to THIS server should ask THIS
        # runner rather than a global.
        self._schluessel: str | None = None
        self._protokoll: deque[str] = deque(maxlen=PROTOKOLL_ZEILEN)
        self._schloss = threading.Lock()

    # --- What can be seen without starting anything ------------------------

    @property
    def programm(self) -> Path | None:
        return programm_finden(self._programm_vorgabe)

    @property
    def ordner(self) -> Path:
        return self._ordner

    @property
    def port_vorgabe(self) -> int:
        return self._port

    @property
    def schluessel(self) -> str | None:
        """The key this server signs with, or nothing while it is down."""
        return self._schluessel if self.laeuft() else None

    def modelle(self) -> list[Modelldatei]:
        return modelle_auflisten(self._ordner)

    def mmproj(self) -> list[str]:
        return mmproj_auflisten(self._ordner)

    def mtp(self) -> list[Modelldatei]:
        return mtp_auflisten(self._ordner)

    def laeuft(self) -> bool:
        return self._prozess is not None and self._prozess.poll() is None

    def lauf(self) -> Lauf | None:
        return self._lauf if self.laeuft() else None

    def protokoll(self) -> list[str]:
        return list(self._protokoll)

    def befehl(
        self,
        modell: str,
        kontext: int,
        schichten: int,
        port: int,
        drafter: str | None = None,
        fein: Feineinstellungen | None = None,
    ) -> list[str]:
        """The command as it will be run — the same list, shown and executed.

        Building it in one place is the point: what the window shows cannot
        drift away from what actually starts.
        """
        zeile = [
            str(self.programm or "llama-server"),
            "--model", str(self._ordner / modell),
            "--ctx-size", str(kontext),
            "--n-gpu-layers", str(schichten),
            "--host", "127.0.0.1",
            "--port", str(port),
        ]
        # --jinja plus the family's published sampling lore — without these
        # a model's tool calls arrive in a language it was never taught. An
        # embedding server has no sampling and no tools, so it gets none of
        # it; what it needs instead is in `zusatzflags`.
        if self._sampling_flags:
            zeile += startflags(modell)
        zeile += list(self._zusatzflags)
        # The advanced section's levers. They say nothing where they agree
        # with the engine, so a command with none of them set looks exactly
        # as it did before the section existed.
        zeile += feinflags(fein)
        if drafter:
            zeile += ["--model-draft", str(self._ordner / drafter)]
            # A prediction module needs its own mode; fed into the plain
            # draft path it fails to build a context. A small sibling
            # model is the plain path and needs no flag.
            if ist_mtp(drafter):
                zeile += ["--spec-type", "draft-mtp"]
        # A model whose eyes lie next to it gets them attached — that is the
        # whole difference between a vision model and the same model mute.
        # The declared projector wins over the name heuristic: the manifest is
        # written when the pair is fetched together, while the heuristic reads
        # shared prefixes and can pick the wrong one when two models share one.
        augen = self._manifest_pfad(modell, "mmproj")
        if augen is None:
            augen = passende_mmproj(self._ordner, modell)
        if augen is not None:
            zeile += ["--mmproj", str(augen)]
        return zeile

    def _manifest_pfad(self, modell: str, rolle: str) -> Path | None:
        """The manifest companion for a model, as a path inside the folder.

        The name comes back validated and existing from the manifest; the
        resolve check here is the same folder boundary a start obeys, so a
        hand-edited note can never point a flag outside the model folder.
        """
        name = modellzuordnung.fuer(self._ordner, modell).get(rolle)
        if not name:
            return None
        pfad = (self._ordner / name).resolve()
        if pfad.parent != self._ordner.resolve() or not pfad.is_file():
            return None
        return pfad

    # --- Starting and stopping ---------------------------------------------

    def belegt_gb(self) -> float | None:
        """Live resident memory of the running server, or None when idle."""
        with self._schloss:
            if self._prozess is None or self._prozess.poll() is not None:
                return None
            return rss_gb(self._prozess.pid)

    def starten(self, modell: str, *, kontext: int = 8192, schichten: int = 99,
                port: int | None = None, drafter: str | None = None,
                fein: Feineinstellungen | None = None) -> Lauf:
        port = self._port if port is None else port
        with self._schloss:
            if self.laeuft():
                raise RunnerFehler("laeuft_schon")

            programm = self.programm
            if programm is None:
                raise RunnerFehler("kein_programm")

            # A name, never a path: whatever is in the folder can start, and
            # nothing else can be reached by writing ../ in front of it.
            ziel = (self._ordner / modell).resolve()
            if ziel.parent != self._ordner.resolve() or not ziel.is_file():
                raise RunnerFehler("kein_modell")

            # No draft chosen by the caller: fall back to the one the manifest
            # declared for this model, so the bond survives a restart and the
            # status reports it. The manifest returns a validated, existing
            # name; the guard below is the same folder boundary either way.
            if drafter is None:
                drafter = modellzuordnung.fuer(self._ordner, modell).get("mtp")

            # The draft model obeys the same rule as the main one: a name
            # from the folder or nothing.
            if drafter:
                dziel = (self._ordner / drafter).resolve()
                if dziel.parent != self._ordner.resolve() or not dziel.is_file():
                    raise RunnerFehler("kein_modell")

            # A taken port would let the new server die quietly while the
            # old one keeps answering — the settings in the form would then
            # look applied and never be.
            with socket.socket() as fuehler:
                if fuehler.connect_ex(("127.0.0.1", port)) == 0:
                    raise RunnerFehler("port_belegt")

            self._protokoll.clear()
            # A fresh key per start; the service keeps it in its own
            # environment, where the provider picks it up to sign requests.
            schluessel = secrets.token_urlsafe(24)
            os.environ[self._schluessel_variable] = schluessel
            self._schluessel = schluessel
            self._prozess = subprocess.Popen(
                self.befehl(modell, kontext, schichten, port, drafter, fein),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={**os.environ, "LLAMA_API_KEY": schluessel},
                # No shell, and its own process group so stopping takes the
                # whole thing and not just the parent.
                start_new_session=True,
            )
            self._lauf = Lauf(
                modell=modell, kontext=kontext, schichten=schichten, port=port, drafter=drafter
            )
            self._pid_merken(self._prozess.pid)
            threading.Thread(target=self._mitlesen, daemon=True).start()
            return self._lauf

    def _mitlesen(self) -> None:
        """Keeps the output where it can be shown instead of in a file."""
        prozess = self._prozess
        if prozess is None or prozess.stdout is None:
            return
        for zeile in prozess.stdout:
            self._protokoll.append(zeile.rstrip("\n"))

    def stoppen(self) -> bool:
        with self._schloss:
            if not self.laeuft() or self._prozess is None:
                return False
            # The whole tree: llama-server starts helpers of its own, and a
            # signal to the parent alone leaves them holding the port. How
            # that is reached differs per system, which is why it lives in
            # its own module.
            prozessstopp.beenden(self._prozess)
            self._prozess = None
            self._lauf = None
            self._pid_vergessen()
            # The key dies with the server it belonged to — this runner's key,
            # not the module constant: three runners share this class, and
            # each carries the name of its own variable.
            os.environ.pop(self._schluessel_variable, None)
            return True

    # --- The orphan after a service restart --------------------------------

    def _pid_merken(self, pid: int) -> None:
        try:
            self._ordner.mkdir(parents=True, exist_ok=True)
            (self._ordner / self._pid_datei).write_text(
                json.dumps({"pid": pid}), encoding="utf-8"
            )
        except OSError:
            # A note that cannot be written costs the cleanup after a crash,
            # never the start itself.
            pass

    def _pid_vergessen(self) -> None:
        (self._ordner / self._pid_datei).unlink(missing_ok=True)

    def aufraeumen(self, ist_unserer=_ist_llama_server) -> bool:
        """Ends the server a previous service run left behind.

        The server lives in its own process group, so a service crash or
        restart leaves it running — holding the port, answering with
        yesterday's settings, and making every new start die quietly. At
        service start this reads the note, makes sure the process really is
        a llama-server (ids get recycled), and ends it.
        """
        datei = self._ordner / self._pid_datei
        try:
            pid = int(json.loads(datei.read_text(encoding="utf-8"))["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            return False
        self._pid_vergessen()
        if not ist_unserer(pid):
            return False
        return prozessstopp.beenden_nach_pid(pid)


class RunnerFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund
