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
import shutil
import signal
import socket
import subprocess
import threading
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
    """The llama-server binary, or nothing if this machine has none."""
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
    return None


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


def modelle_auflisten(ordner: Path) -> list[Modelldatei]:
    """The startable GGUF files in the model folder, largest first."""
    if not ordner.is_dir():
        return []
    dateien = [
        Modelldatei(name=p.name, groesse_gb=round(p.stat().st_size / 1e9, 1))
        for p in sorted(ordner.glob("*.gguf"))
        if p.is_file() and not ist_mmproj(p.name)
    ]
    return sorted(dateien, key=lambda d: d.groesse_gb, reverse=True)


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


class Modellrunner:
    """One model server, started and stopped from the program."""

    def __init__(self, modelle_ordner: Path, programm: str | None = None) -> None:
        self._ordner = Path(modelle_ordner).expanduser()
        self._programm_vorgabe = programm
        self._prozess: subprocess.Popen | None = None
        self._lauf: Lauf | None = None
        self._protokoll: deque[str] = deque(maxlen=PROTOKOLL_ZEILEN)
        self._schloss = threading.Lock()

    # --- What can be seen without starting anything ------------------------

    @property
    def programm(self) -> Path | None:
        return programm_finden(self._programm_vorgabe)

    @property
    def ordner(self) -> Path:
        return self._ordner

    def modelle(self) -> list[Modelldatei]:
        return modelle_auflisten(self._ordner)

    def mmproj(self) -> list[str]:
        return mmproj_auflisten(self._ordner)

    def laeuft(self) -> bool:
        return self._prozess is not None and self._prozess.poll() is None

    def lauf(self) -> Lauf | None:
        return self._lauf if self.laeuft() else None

    def protokoll(self) -> list[str]:
        return list(self._protokoll)

    def befehl(self, modell: str, kontext: int, schichten: int, port: int) -> list[str]:
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
        # A model whose eyes lie next to it gets them attached — that is the
        # whole difference between a vision model and the same model mute.
        augen = passende_mmproj(self._ordner, modell)
        if augen is not None:
            zeile += ["--mmproj", str(augen)]
        return zeile

    # --- Starting and stopping ---------------------------------------------

    def starten(self, modell: str, *, kontext: int = 8192, schichten: int = 99,
                port: int = 8080) -> Lauf:
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

            # A taken port would let the new server die quietly while the
            # old one keeps answering — the settings in the form would then
            # look applied and never be.
            with socket.socket() as fuehler:
                if fuehler.connect_ex(("127.0.0.1", port)) == 0:
                    raise RunnerFehler("port_belegt")

            self._protokoll.clear()
            self._prozess = subprocess.Popen(
                self.befehl(modell, kontext, schichten, port),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                # No shell, and its own process group so stopping takes the
                # whole thing and not just the parent.
                start_new_session=True,
            )
            self._lauf = Lauf(modell=modell, kontext=kontext, schichten=schichten, port=port)
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
            try:
                # The whole group: llama-server starts helpers of its own, and
                # a signal to the parent alone leaves them holding the port.
                os.killpg(os.getpgid(self._prozess.pid), signal.SIGTERM)
                self._prozess.wait(timeout=10)
            except (ProcessLookupError, PermissionError):
                pass
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self._prozess.pid), signal.SIGKILL)
            self._prozess = None
            self._lauf = None
            self._pid_vergessen()
            return True

    # --- The orphan after a service restart --------------------------------

    def _pid_merken(self, pid: int) -> None:
        try:
            self._ordner.mkdir(parents=True, exist_ok=True)
            (self._ordner / PID_DATEI).write_text(
                json.dumps({"pid": pid}), encoding="utf-8"
            )
        except OSError:
            # A note that cannot be written costs the cleanup after a crash,
            # never the start itself.
            pass

    def _pid_vergessen(self) -> None:
        (self._ordner / PID_DATEI).unlink(missing_ok=True)

    def aufraeumen(self, ist_unserer=_ist_llama_server) -> bool:
        """Ends the server a previous service run left behind.

        The server lives in its own process group, so a service crash or
        restart leaves it running — holding the port, answering with
        yesterday's settings, and making every new start die quietly. At
        service start this reads the note, makes sure the process really is
        a llama-server (ids get recycled), and ends it.
        """
        datei = self._ordner / PID_DATEI
        try:
            pid = int(json.loads(datei.read_text(encoding="utf-8"))["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            return False
        self._pid_vergessen()
        if not ist_unserer(pid):
            return False
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return False
        return True


class RunnerFehler(Exception):
    """Carries the key of the sentence to show, not the sentence itself."""

    def __init__(self, grund: str) -> None:
        super().__init__(grund)
        self.grund = grund
