"""The notes: the user's own pad, beside the conversation.

Kept in the data folder rather than in the browser. localStorage was enough
for a plain text box; a note with a heading, formatting and a life of its own
belongs where the rest of the user's work lives — it survives a browser
change, a private window and a cleared cache, and it can be backed up with
everything else.

App-wide and chat-independent on purpose. A note tied to a conversation is
gone the moment the conversation is, which is exactly when people still need
what they wrote down.

**The markup is fenced in.** A note carries four kinds of emphasis and
nothing else. What comes in is rebuilt from a whitelist rather than filtered:
a filter has to think of every attack, a rebuild only has to know what is
allowed. Nothing from a note is ever executed, and nothing in it can reach
out of it.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

DATEI = "notizen.json"

# The four kinds of emphasis, and the line break that comes with typing.
ERLAUBT = {"b", "strong", "i", "em", "u", "mark", "br", "div", "p"}
# What a mark may say about itself: which of the quiet colours it wears.
FARBEN = {"gelb", "blau", "gruen"}

MAX_UEBERSCHRIFT = 200
MAX_INHALT = 100_000


class _Saeuberung(HTMLParser):
    """Rebuilds the text from what is allowed, dropping the rest.

    Tags outside the whitelist lose their brackets but keep their text — a
    pasted paragraph should not vanish because it arrived in a wrapper.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.teile: list[str] = []
        self.offen: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ERLAUBT:
            return
        if tag == "br":
            self.teile.append("<br>")
            return
        if tag == "mark":
            farbe = dict(attrs).get("data-farbe") or ""
            if farbe in FARBEN:
                self.teile.append(f'<mark data-farbe="{farbe}">')
            else:
                self.teile.append("<mark>")
        else:
            self.teile.append(f"<{tag}>")
        self.offen.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in ERLAUBT or tag == "br":
            return
        if tag in self.offen:
            # Close everything that was opened inside it, so nothing stays
            # dangling — a stray open tag would swallow the rest of the note.
            while self.offen:
                letzter = self.offen.pop()
                self.teile.append(f"</{letzter}>")
                if letzter == tag:
                    break

    def handle_data(self, daten: str) -> None:
        self.teile.append(
            daten.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    def ergebnis(self) -> str:
        while self.offen:
            self.teile.append(f"</{self.offen.pop()}>")
        return "".join(self.teile)


def saeubern(roh: str) -> str:
    """The note as it may be stored: four kinds of emphasis, nothing else."""
    text = str(roh or "")[:MAX_INHALT]
    # A comment can hide a tag from the parser's eye; it has no business in a
    # note either way.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    saeuberung = _Saeuberung()
    saeuberung.feed(text)
    saeuberung.close()
    return saeuberung.ergebnis()


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat()


class Notizen:
    """The notes file. Read on every access, written whole — a handful of
    notes is nothing to build a database around."""

    def __init__(self, ordner: Path) -> None:
        self.pfad = Path(ordner) / DATEI

    def alle(self) -> list[dict[str, Any]]:
        if not self.pfad.exists():
            return []
        try:
            daten = json.loads(self.pfad.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return daten if isinstance(daten, list) else []

    def _schreiben(self, liste: list[dict[str, Any]]) -> None:
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.pfad.write_text(
            json.dumps(liste, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def anlegen(self, ueberschrift: str, inhalt: str) -> dict[str, Any]:
        notiz = {
            "id": uuid.uuid4().hex,
            "ueberschrift": str(ueberschrift or "")[:MAX_UEBERSCHRIFT].strip(),
            "inhalt": saeubern(inhalt),
            "geaendert": _jetzt(),
        }
        self._schreiben([*self.alle(), notiz])
        return notiz

    def aendern(self, notiz_id: str, ueberschrift: str, inhalt: str) -> dict[str, Any] | None:
        liste = self.alle()
        for notiz in liste:
            if notiz.get("id") == notiz_id:
                notiz["ueberschrift"] = str(ueberschrift or "")[:MAX_UEBERSCHRIFT].strip()
                notiz["inhalt"] = saeubern(inhalt)
                notiz["geaendert"] = _jetzt()
                self._schreiben(liste)
                return notiz
        return None

    def loeschen(self, notiz_id: str) -> bool:
        liste = self.alle()
        rest = [n for n in liste if n.get("id") != notiz_id]
        if len(rest) == len(liste):
            return False
        self._schreiben(rest)
        return True
