"""Where the built-in file tools may reach — the shared folders and nothing else.

The rule was written for the shell tool and holds for every tool that touches
the disk, so it lives in one place instead of in five:

* **The share is the boundary.** A working folder shared with the chat IS the
  permission. Inside it nothing asks again.
* **Outside it, the model asks.** The path leaves the shared folders, the
  ordinary confirmation appears above the input field, and only a yes lets the
  call through.
* **Without a shared folder the tools stay shut.** No folder, no file work.

The file tools have it easier than the shell: their path arrives as an
explicit argument, so there is nothing to guess. The shell has to scan a free
command string for anything path-shaped, which is a heuristic and stays in
``shell.py`` where it belongs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# What a tool says when nobody shared a folder with the chat. One wording for
# all of them: the user reads it once and knows what to do.
OHNE_ORDNER = (
    "No working folder is shared with this chat. Ask the user to share one via "
    "the plus menu — until then this tool cannot run."
)


class GrenzeVerletzt(Exception):
    """The call cannot run: no shared folder, or the path is unusable."""


def aufgeloest(pfad: str, wurzel: Path) -> Path:
    """The absolute path this argument means, relative ones against the root."""
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


def wurzeln(ordner: list[str]) -> list[Path]:
    """The shared folders as resolved paths, in the order they were shared."""
    return [Path(o).resolve() for o in ordner]


def ziel(pfad: str, ordner: list[str]) -> Path:
    """The path a call works on — or an explanation why it cannot work at all.

    Raises when no folder is shared: the tools are shut then, and saying so
    plainly beats returning something that only fails later.
    """
    if not ordner:
        raise GrenzeVerletzt(OHNE_ORDNER)
    basis = wurzeln(ordner)[0]
    if not basis.is_dir():
        raise GrenzeVerletzt(
            f"The shared folder '{basis}' no longer exists. Ask the user to set it again."
        )
    try:
        return aufgeloest(pfad, basis)
    except (OSError, RuntimeError) as fehler:
        raise GrenzeVerletzt(f"'{pfad}' is not a usable path ({fehler}).") from fehler


def aussenpfad(
    argumente: dict[str, Any], ordner: list[str], schluessel: str = "path"
) -> str | None:
    """The path this call reaches to outside the shared folders, or None.

    This is both the reason to ask and the answer to "why am I being asked?" —
    the prompt shows the path, so the decision rests on something visible.
    """
    if not ordner:
        return None
    roh = str(argumente.get(schluessel) or "").strip()
    if not roh:
        return None
    freigaben = wurzeln(ordner)
    try:
        gemeint = aufgeloest(roh, freigaben[0])
    except (OSError, RuntimeError):
        return None
    return None if liegt_innerhalb(gemeint, freigaben) else str(gemeint)
