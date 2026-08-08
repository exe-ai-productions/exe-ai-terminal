"""The shell tool — `run_command`.

One generic tool with a free command string, deliberately not a set of small
ones (`create_file`, `move`, `list_dir`). The core cases are opening
folders, creating and moving files — everyday file work. A single command
string covers all of it, including the things nobody thought of in advance.

Why this is built in and not a separate MCP server: the working folders
belong to the chat and change while the program runs. An outside process
would have to be told the folder with every call — and anything passed as an
argument can be forged by the model. Built in, the terminal takes the folder
from the chat itself; the model never gets a say in where it works.

The safety story:

* **The share is the boundary.** Setting a working folder IS the permission.
  Inside it nothing asks again — creating, moving, deleting all run through.
  That was chosen over confirming every single action, which would have made
  the tool useless in practice.
* **Outside it, the model asks.** A command that reaches beyond the shared
  folders triggers the ordinary confirmation prompt above the input field.
* **Without a shared folder the tool stays shut.** No folder, no execution —
  the model is told so plainly.
* **The block list is a tripwire, not a sandbox.** It stops the obviously
  catastrophic (`sudo`, `rm -rf /`, fork bombs, piping the net into a shell).
  It is NOT a security boundary and does not pretend to be one: a container
  or chroot was consciously rejected for build cost and platform dependence.

The command runs through the shell on purpose — pipes and redirection are
half of what file work is. That is the point of the exercise, not an
oversight.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any

from app.tools.mcp_client import MCPWerkzeug

log = logging.getLogger(__name__)

SERVER_NAME = "shell"
WERKZEUG_NAME = "run_command"

# How long a command may run before it is stopped. Long enough for a real
# build, short enough that a hung process does not block the chat forever.
ZEITGRENZE_SEKUNDEN = 120

# How much output goes back to the model. A `find /` would otherwise fill the
# whole context with paths.
MAX_AUSGABE_ZEICHEN = 20_000

# The tripwire. Deliberately short: every pattern here has to be worth its
# false positives, otherwise it only trains people to work around it.
#
# These are matched against the raw command string, so they also catch what
# hides in the middle of a pipeline.
GEFAEHRLICH: tuple[tuple[str, str], ...] = (
    (r"(^|[;&|]\s*)sudo\b", "sudo"),
    (r"(^|[;&|]\s*)su\s", "su"),
    (r"\brm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf][a-zA-Z]*\s+/(\s|$|\*)", "rm -rf /"),
    (r"\bmkfs(\.|\s)", "mkfs"),
    (r"\bdd\b[^|]*\bof=/dev/", "dd auf ein Gerät"),
    (r":\(\)\s*\{.*\}\s*;?\s*:", "Fork-Bombe"),
    (r"\bchmod\s+(-[a-zA-Z]+\s+)*777\s+/(\s|$)", "chmod 777 /"),
    (r"\b(shutdown|reboot|halt|poweroff)\b", "Herunterfahren"),
    # curl … | sh — fetching something from the net straight into a shell is
    # how a machine gets taken over, and it is never what file work needs.
    (r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z|k)?sh\b", "Netz-Inhalt in eine Shell geleitet"),
    (r"\b(launchctl|systemctl)\b", "Systemdienste"),
    (r">\s*/dev/(sd|nvme|disk)", "Schreiben auf ein Gerät"),
)

# Where a command may reach without asking: the shared folders. Everything
# else needs the user's yes. What counts as "reaching outside" is a
# heuristic, not a proof — see `greift_nach_draussen`.
_PFAD_MUSTER = re.compile(r"(?<![\w-])(~[/\w.-]*|/[\w./-]+)")


class ShellVerboten(Exception):
    """The command hit the tripwire, or there is no shared folder."""


def werkzeug_beschreibung() -> MCPWerkzeug:
    """The tool as the model sees it.

    The description says what it can do AND where — a model that does not
    know its boundary writes paths that then trigger a prompt for no reason.
    """
    return MCPWerkzeug(
        name=WERKZEUG_NAME,
        beschreibung=(
            "Runs a shell command on the user's computer and returns its output. "
            "Use it for everyday file work: creating, reading, moving, renaming "
            "and deleting files, listing folders, opening a folder or file in the "
            "desktop UI.\n"
            "It runs in the user's own shell, so pipes, redirection and globs "
            "work, inside the folders shared with this chat — relative paths "
            "resolve against the first one. Without a shared folder nothing runs.\n"
            f"Nothing is interactive: a command that waits for input hangs until "
            f"it is stopped after {ZEITGRENZE_SEKUNDEN} seconds. Use the "
            "non-interactive flags (-y, --yes, --no-pager). Start anything "
            "long-running in the background instead.\n"
            f"Output is cut off at {MAX_AUSGABE_ZEICHEN:,} characters — narrow the "
            "command down rather than asking for everything and reading the "
            "first part of it.\n"
            "A few commands are refused outright, among them sudo, wiping a "
            "disk, and piping something off the net straight into a shell. That "
            "is not a permission question and rephrasing will not help; say so "
            "and suggest another way."
        ),
        schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run, e.g. \"ls -la\" or \"mkdir notes\".",
                },
            },
            "required": ["command"],
        },
        server=SERVER_NAME,
    )


def blockiert(befehl: str) -> str | None:
    """Name of the pattern that stops this command, or None."""
    for muster, benennung in GEFAEHRLICH:
        if re.search(muster, befehl, re.IGNORECASE):
            return benennung
    return None


def _aufgeloest(pfad: str, wurzel: Path) -> Path:
    roh = Path(pfad).expanduser()
    return (roh if roh.is_absolute() else wurzel / roh).resolve()


def liegt_innerhalb(pfad: Path, ordner: list[Path]) -> bool:
    for freigegeben in ordner:
        try:
            pfad.relative_to(freigegeben)
            return True
        except ValueError:
            continue
    return False


def greift_nach_draussen(befehl: str, ordner: list[str]) -> str | None:
    """The path in the command that leaves the shared folders, or None.

    A heuristic on purpose. It reads every path-shaped word out of the
    command and checks whether it still lands inside a shared folder — `~`
    and `..` included, since those are the two ordinary ways out. What it
    cannot see is a path built at runtime (`$(cat file)`); that is the honest
    limit of a tripwire and the reason the share, not this function, is the
    actual boundary.
    """
    if not ordner:
        return None
    wurzeln = [Path(o).resolve() for o in ordner]
    wurzel = wurzeln[0]

    # Split like a shell would, so quoted paths stay in one piece. A command
    # that cannot be split (unbalanced quotes) falls back to the raw scan.
    try:
        teile = shlex.split(befehl)
    except ValueError:
        teile = befehl.split()

    kandidaten: list[str] = []
    for teil in teile:
        if teil.startswith("-"):
            continue
        if teil.startswith(("~", "/")) or ".." in teil:
            kandidaten.append(teil)
    for treffer in _PFAD_MUSTER.findall(befehl):
        if treffer not in kandidaten:
            kandidaten.append(treffer)

    for kandidat in kandidaten:
        # Strip what the shell would treat as syntax, not as part of the path.
        sauber = kandidat.strip("\"'`;|&()<>")
        if not sauber:
            continue
        try:
            ziel = _aufgeloest(sauber, wurzel)
        except (OSError, RuntimeError):
            continue
        if not liegt_innerhalb(ziel, wurzeln):
            return str(ziel)
    return None


# Which sentence explains this tool's confirmation, and what fills its
# placeholder. The tool knows its own reason; a caller that guessed one for
# everybody wrote "Reaches <a memory entry> — outside the shared folders".
GRUND_SCHLUESSEL = "werkzeug.grund_ausserhalb"
GRUND_PLATZHALTER = "pfad"


def aussenpfad(argumente: dict[str, Any], ordner: list[str]) -> str | None:
    """The path this call reaches to outside the shared folders, or None.

    This is both the reason to ask and the answer to "why am I being asked?".
    The prompt shows it, so the decision rests on something visible instead of
    on trust.
    """
    befehl = str(argumente.get("command") or "").strip()
    if not befehl or not ordner:
        return None
    return greift_nach_draussen(befehl, ordner)


def braucht_bestaetigung(argumente: dict[str, Any], ordner: list[str]) -> bool:
    """Whether this call has to be confirmed by the user.

    Inside the shared folders: no. Outside: yes. Without any shared folder
    the tool does not run at all, so there is nothing to confirm either.
    """
    return aussenpfad(argumente, ordner) is not None


def _kuerzen(text: str) -> str:
    if len(text) <= MAX_AUSGABE_ZEICHEN:
        return text
    rest = len(text) - MAX_AUSGABE_ZEICHEN
    return text[:MAX_AUSGABE_ZEICHEN] + f"\n… [{rest} weitere Zeichen abgeschnitten]"


async def ausfuehren(argumente: dict[str, Any], ordner: list[str]) -> str:
    """Runs the command and returns output the way a terminal would show it."""
    befehl = str(argumente.get("command") or "").strip()
    if not befehl:
        raise ShellVerboten("No command given.")
    if not ordner:
        raise ShellVerboten(
            "No working folder is shared with this chat. Ask the user to share "
            "one via the plus menu — until then no command can run."
        )

    if (grund := blockiert(befehl)) is not None:
        log.warning("Shell-Befehl abgewiesen (%s): %s", grund, befehl)
        raise ShellVerboten(
            f"This command was refused because it matches a blocked pattern ({grund}). "
            "It is not about permissions — commands like this are refused outright."
        )

    wurzel = Path(ordner[0])
    if not wurzel.is_dir():
        raise ShellVerboten(
            f"The shared folder '{wurzel}' no longer exists. Ask the user to set it again."
        )

    log.info("Shell: %s (in %s)", befehl, wurzel)
    # The shell is the point: pipes and redirection are half of file work.
    #
    # The USER'S shell, not /bin/sh: the model
    # writes commands for the shell people actually have, and asked to write
    # "HALLO" it produced `echo -n HALLO`. Under /bin/sh the built-in `echo`
    # does not know -n and wrote "-n HALLO" into the file. Whatever the user
    # would get in their own terminal, they get here.
    #
    # PYTHONUNBUFFERED keeps a python one-liner from withholding its output.
    prozess = await asyncio.create_subprocess_exec(
        os.environ.get("SHELL") or "/bin/sh",
        "-c",
        befehl,
        cwd=str(wurzel),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        roh_aus, roh_fehler = await asyncio.wait_for(
            prozess.communicate(), timeout=ZEITGRENZE_SEKUNDEN
        )
    except asyncio.TimeoutError:
        # Kill, don't just walk away: an abandoned process keeps writing into
        # the folder the user shared.
        try:
            prozess.kill()
        except ProcessLookupError:
            pass
        await prozess.wait()
        return (
            f"Stopped after {ZEITGRENZE_SEKUNDEN} seconds — the command was still running.\n"
            "If it is supposed to run that long, start it in the background."
        )

    ausgabe = roh_aus.decode("utf-8", errors="replace").rstrip()
    fehler = roh_fehler.decode("utf-8", errors="replace").rstrip()

    teile: list[str] = []
    if ausgabe:
        teile.append(_kuerzen(ausgabe))
    if fehler:
        teile.append(("stderr:\n" if ausgabe else "") + _kuerzen(fehler))
    if prozess.returncode != 0:
        teile.append(f"[exit code {prozess.returncode}]")
    if not teile:
        # A successful `mkdir` says nothing at all. Silence would read like a
        # failure to the model, so say plainly that it worked.
        return "(done, no output)"
    return "\n".join(teile)
