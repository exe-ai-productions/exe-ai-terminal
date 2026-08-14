"""Where the next command starts — the folder a `cd` left behind.

A shell command runs in its own process, so a `cd` normally dies with it and
the next call starts over in the first shared folder. Models write `cd build`
and then `make` as two calls, and the second one fails.

The fix is deliberately small: after each command the shell reports its
working folder, and that folder is remembered for the next call of the same
chat. **No lasting shell process** — one would hang around, would need a
second way of working under Windows, and would keep an environment alive that
nobody can see.

The memory lives in this process only. A restart puts every chat back into
its first shared folder, which is the honest answer after a restart anyway.
"""

from __future__ import annotations

from pathlib import Path

from app.tools.grenzen import liegt_innerhalb, wurzeln

# chat -> the folder its last command left behind.
_gemerkt: dict[str, str] = {}


def start_ordner(chat_id: str | None, ordner: list[str]) -> Path:
    """The folder this call starts in: what a `cd` left, else the first share."""
    basis = wurzeln(ordner)[0]
    if not chat_id:
        return basis
    gemerkt = _gemerkt.get(chat_id)
    if not gemerkt:
        return basis
    pfad = Path(gemerkt)
    # A folder that has since been dropped from the shares, or deleted, must
    # not keep a chat working outside what the user allows.
    if pfad.is_dir() and liegt_innerhalb(pfad, wurzeln(ordner)):
        return pfad
    _gemerkt.pop(chat_id, None)
    return basis


def merken(chat_id: str | None, pfad: str, ordner: list[str]) -> None:
    """Remembers where the command ended up — but only inside the shares."""
    if not chat_id or not pfad:
        return
    try:
        ziel = Path(pfad).resolve()
    except (OSError, RuntimeError):
        return
    if ziel.is_dir() and liegt_innerhalb(ziel, wurzeln(ordner)):
        _gemerkt[chat_id] = str(ziel)
    else:
        _gemerkt.pop(chat_id, None)


def vergessen(chat_id: str | None = None) -> None:
    if chat_id is None:
        _gemerkt.clear()
    else:
        _gemerkt.pop(chat_id, None)
