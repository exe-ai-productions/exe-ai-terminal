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

from app.tools import hintergrund, ordnergedaechtnis
from app.tools.grenzen import aufgeloest as _aufgeloest
from app.tools.grenzen import liegt_innerhalb
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
# The look-behind excludes the dot so "./run_tests.sh" stays one relative
# path instead of yielding the stump "/run_tests.sh".
_PFAD_MUSTER = re.compile(r"(?<![\w.-])(~[/\w.-]*|/[\w./-]+)")


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
            "A `cd` persists to the next call, as long as the folder stays "
            "inside the shared ones.\n"
            f"Nothing is interactive: a command that waits for input hangs until "
            f"it is stopped after {ZEITGRENZE_SEKUNDEN} seconds. Use the "
            "non-interactive flags (-y, --yes, --no-pager). Anything that takes "
            "longer belongs in the background: set background to true, the call "
            "returns at once and the result appears in the chat by itself when "
            "it is done.\n"
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
                "background": {
                    "type": "boolean",
                    "description": (
                        "Start it and return immediately. The result appears in "
                        "the chat when the command is done. Use it for builds, "
                        "downloads and anything else that takes minutes."
                    ),
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
        if treffer in kandidaten:
            continue
        # The raw scan cannot see quoting, so a path with spaces comes out
        # cut off at the first blank. If a properly split word carries on
        # where the match stops, the match is that word's stump, not a path
        # of its own.
        if any(t.startswith(treffer) and len(t) > len(treffer) for t in teile):
            continue
        kandidaten.append(treffer)

    for kandidat in kandidaten:
        # Strip what the shell would treat as syntax, not as part of the path.
        sauber = kandidat.strip("\"'`;|&()<>")
        if not sauber:
            continue
        # A shared folder with a blank in its name, written without quotes:
        # the split cuts the path at the blank, and the stump looks like an
        # escape. If the command carries the folder's full name, the stump is
        # our own folder cut short, not a path of its own.
        if any(
            " " in str(w) and str(w).startswith(sauber) and str(w) in befehl
            for w in wurzeln
        ):
            continue
        # Redirection targets under /dev are shell plumbing, not a reach:
        # "2>/dev/null" silences a command, it does not touch a file. Writing
        # to a raw device stays caught by the tripwire above.
        #
        # Judged on what was written, not on what it resolves to: Windows has
        # no /dev, so resolving turns the everyday "2>/dev/null" into a
        # real-looking C:\dev\null and every second command would be reported
        # as reaching outside. NUL is what the same plumbing is called there.
        geschrieben = sauber.replace("\\", "/")
        if (
            geschrieben == "/dev/null"
            or geschrieben.startswith(("/dev/std", "/dev/fd/", "/dev/tty"))
            or sauber.upper() == "NUL"
        ):
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


# The shell reports its working folder on this marker after every command, so
# a `cd` can persist to the next call without a lasting shell process. Record
# separator: it never appears in ordinary output.
MARKE = "\x1e"


def _mit_ordnermarke(befehl: str) -> str:
    """The command, followed by a line that names the folder it ended in.

    POSIX only. Under Windows the command stays as it is and every call starts
    in the same folder, as before — a second, platform-specific way of doing
    this is not worth a remembered `cd`.
    """
    return (
        "{ " + befehl + "\n} ; __exe_rc=$? ; "
        f"printf '\\n\\036%s' \"$PWD\" ; exit $__exe_rc"
    )


async def _mitlesen(strom, lauf, sammlung: list[str], name: str) -> str | None:
    """Reads one output stream line by line. Returns the folder marker if it
    came past — that is the last line of stdout and belongs to nobody else."""
    ordner_danach: str | None = None
    # The marker is printed on a line of its own, so it brings an empty line
    # with it that the command never wrote. Empty lines are therefore held
    # back until something follows them; the last one before the marker is
    # ours and goes.
    zurueckgehalten = 0

    def ausgeben(text: str) -> None:
        sammlung.append(text)
        if lauf is not None:
            hintergrund.laeufe.zeile(lauf, text, name)

    while True:
        roh = await strom.readline()
        if not roh:
            for _ in range(zurueckgehalten):
                ausgeben("")
            return ordner_danach
        text = roh.decode("utf-8", errors="replace").rstrip("\n")
        if text.startswith(MARKE):
            ordner_danach = text[len(MARKE) :]
            zurueckgehalten = max(0, zurueckgehalten - 1)
            continue
        if not text:
            zurueckgehalten += 1
            continue
        for _ in range(zurueckgehalten):
            ausgeben("")
        zurueckgehalten = 0
        ausgeben(text)


def _antwort_bauen(ausgabe: list[str], fehler: list[str], code: int | None) -> str:
    teile: list[str] = []
    if ausgabe:
        teile.append(_kuerzen("\n".join(ausgabe).rstrip()))
    if fehler:
        teile.append(("stderr:\n" if ausgabe else "") + _kuerzen("\n".join(fehler).rstrip()))
    if code not in (0, None):
        teile.append(f"[exit code {code}]")
    if not teile:
        # A successful `mkdir` says nothing at all. Silence would read like a
        # failure to the model, so say plainly that it worked.
        return "(done, no output)"
    return "\n".join(teile)


async def ausfuehren(
    argumente: dict[str, Any], ordner: list[str], chat_id: str | None = None
) -> str:
    """Runs the command and returns output the way a terminal would show it.

    ``chat_id`` is what makes a run belong somewhere: the remembered folder,
    the live lines in the terminal window and the message a background run
    leaves behind are all tied to the chat, never to the model's arguments.
    """
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

    if not Path(ordner[0]).is_dir():
        raise ShellVerboten(
            f"The shared folder '{ordner[0]}' no longer exists. Ask the user to set it again."
        )
    wurzel = ordnergedaechtnis.start_ordner(chat_id, ordner)

    im_hintergrund = bool(argumente.get("background"))
    lauf = hintergrund.laeufe.anlegen(chat_id, befehl, im_hintergrund) if chat_id else None

    log.info("Shell: %s (in %s)", befehl, wurzel)
    prozess = await _starten(befehl, wurzel)
    if lauf is not None:
        lauf.prozess = prozess

    if im_hintergrund:
        # Deliberately not awaited: the call returns now, the run reports for
        # itself when it is done.
        asyncio.ensure_future(
            _begleiten(
                prozess,
                lauf,
                chat_id,
                ordner,
                hintergrund.HINTERGRUND_GRENZE_SEKUNDEN,
            )
        )
        nummer = lauf.nummer if lauf else 1
        return (
            f"Started in the background as run #{nummer}. The result will "
            "appear in the chat when it finishes."
        )

    ergebnis, abgelaufen = await _begleiten(
        prozess, lauf, chat_id, ordner, ZEITGRENZE_SEKUNDEN
    )
    if abgelaufen:
        return (
            f"Stopped after {ZEITGRENZE_SEKUNDEN} seconds — the command was still running.\n"
            "If it is supposed to run that long, start it with background set to true."
        )
    return ergebnis


async def _starten(befehl: str, wurzel: Path):
    """The process for one command.

    The shell is the point: pipes and redirection are half of file work.

    The USER'S shell, not /bin/sh: the model writes commands for the shell
    people actually have, and asked to write "HALLO" it produced
    `echo -n HALLO`. Under /bin/sh the built-in `echo` does not know -n and
    wrote "-n HALLO" into the file. Whatever the user would get in their own
    terminal, they get here.

    Windows has no /bin/sh, and its command processor reads /c where a POSIX
    shell reads -c. Handed the wrong switch it ignores the command entirely
    and opens an interactive session instead: the caller then gets a version
    banner back and nothing was ever run. COMSPEC names whichever processor
    the system actually uses.

    PYTHONUNBUFFERED keeps a python one-liner from withholding its output.
    """
    if os.name == "nt":
        programm = os.environ.get("COMSPEC") or "cmd.exe"
        schalter = "/c"
        text = befehl
    else:
        programm = os.environ.get("SHELL") or "/bin/sh"
        schalter = "-c"
        text = _mit_ordnermarke(befehl)

    return await asyncio.create_subprocess_exec(
        programm,
        schalter,
        text,
        cwd=str(wurzel),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


async def _begleiten(
    prozess,
    lauf,
    chat_id: str | None,
    ordner: list[str],
    grenze: float,
) -> tuple[str, bool]:
    """Follows a running command to its end. Returns (answer, timed out).

    Both kinds go through here: the foreground call awaits it, a background
    run leaves it to itself and lets the result find its way into the chat.
    """
    ausgabe: list[str] = []
    fehler: list[str] = []
    abgelaufen = False
    try:
        ordner_danach, _ = await asyncio.wait_for(
            asyncio.gather(
                _mitlesen(prozess.stdout, lauf, ausgabe, "stdout"),
                _mitlesen(prozess.stderr, lauf, fehler, "stderr"),
            ),
            timeout=grenze,
        )
        await prozess.wait()
        ordnergedaechtnis.merken(chat_id, ordner_danach or "", ordner)
    except asyncio.TimeoutError:
        # Kill, don't just walk away: an abandoned process keeps writing into
        # the folder the user shared.
        abgelaufen = True
        try:
            prozess.kill()
        except (ProcessLookupError, OSError):
            pass
        await prozess.wait()

    if abgelaufen:
        antwort = (
            f"Stopped after {int(grenze)} seconds — the command was still running."
        )
    else:
        antwort = _antwort_bauen(ausgabe, fehler, prozess.returncode)

    if lauf is not None:
        hintergrund.laeufe.beenden(lauf, None if abgelaufen else prozess.returncode)
        if lauf.hintergrund and hintergrund.laeufe.abschluss is not None:
            hintergrund.laeufe.abschluss(lauf, antwort)
    return antwort, abgelaufen
