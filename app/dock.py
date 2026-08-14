"""The document dock: four places for files the user keeps at hand.

A clipboard that belongs to the person, not to a conversation — four files
one drags into the chat when they are needed, and that stay put when the
chat is gone.

**The dock keeps its own copy.** A path into the user's folders would break
the moment they tidy up, and it would quietly hand the program a file it was
never given. Copying into the data folder means the original may vanish and
the dock still works.

**The model never sees it.** Nothing here reaches the prompt, the tools or
the context. A file leaves the dock only when the user drags it into the
input field, and then it travels the ordinary way an attachment does.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ORDNER = "dock"
DATEI = "dock.json"

# Four places, and that is the whole point: a clipboard with room for
# everything is a folder, and folders exist already.
PLAETZE = 4

# What a name may become on disk. The name the user sees is kept as it was;
# the file itself gets a safe one, so nothing can escape the folder.
_UNSICHER = re.compile(r"[^A-Za-z0-9._-]+")


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat()


def sicherer_name(name: str) -> str:
    sauber = _UNSICHER.sub("_", Path(str(name or "datei")).name).strip("._") or "datei"
    return sauber[:120]


class Dock:
    """The four places and their files."""

    def __init__(self, datenordner: Path) -> None:
        self.ordner = Path(datenordner) / ORDNER
        self.pfad = Path(datenordner) / DATEI

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

    def voll(self) -> bool:
        return len(self.alle()) >= PLAETZE

    def ablegen(self, name: str, daten: bytes, typ: str = "") -> dict[str, Any]:
        """Copies a file into the dock. Raises ValueError when it is full."""
        liste = self.alle()
        if len(liste) >= PLAETZE:
            raise ValueError(f"Das Dock hat nur {PLAETZE} Plätze.")

        kennung = uuid.uuid4().hex
        endung = Path(sicherer_name(name)).suffix
        self.ordner.mkdir(parents=True, exist_ok=True)
        (self.ordner / f"{kennung}{endung}").write_bytes(daten)

        eintrag = {
            "id": kennung,
            "name": Path(str(name or "")).name or "Datei",
            "datei": f"{kennung}{endung}",
            "typ": str(typ or ""),
            "groesse": len(daten),
            "abgelegt": _jetzt(),
        }
        self._schreiben([*liste, eintrag])
        return eintrag

    def holen(self, kennung: str) -> tuple[dict[str, Any], Path] | None:
        for eintrag in self.alle():
            if eintrag.get("id") == kennung:
                pfad = self.ordner / str(eintrag.get("datei") or "")
                # The name in the file comes from us, but a file that was
                # edited by hand must not point out of the folder.
                if pfad.parent.resolve() != self.ordner.resolve() or not pfad.is_file():
                    return None
                return eintrag, pfad
        return None

    def entfernen(self, kennung: str) -> bool:
        liste = self.alle()
        rest = [e for e in liste if e.get("id") != kennung]
        if len(rest) == len(liste):
            return False
        gefunden = self.holen(kennung)
        if gefunden is not None:
            gefunden[1].unlink(missing_ok=True)
        self._schreiben(rest)
        return True
