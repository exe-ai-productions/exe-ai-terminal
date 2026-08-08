"""Settings as a cascade.

One table for every setting, and one rule for resolving them: go from general
to specific, and the last value that is actually set wins.

    default (config.yaml)  →  global  →  modell:<id>  →  chat:<id>

Before this, a value could only live on a single chat. Whatever was set there
applied to that one conversation and to nothing else, so every new chat began
at the endpoint's defaults and had to be corrected by hand. Other settings sat
in browser storage, which meant a different truth on every device.

Adding a setting means adding a row, not changing the schema. What is stored
is checked by the caller — a JSON column cannot do it.
"""

from __future__ import annotations

import json
from typing import Any

from app.db.repositories.base import Repository

GLOBAL = "global"


def modell_bereich(endpoint_id: str) -> str:
    return f"modell:{endpoint_id}"


def chat_bereich(chat_id: str) -> str:
    return f"chat:{chat_id}"


class EinstellungenRepository(Repository):
    # --- single scopes ----------------------------------------------------

    def holen(self, bereich: str, schluessel: str) -> Any | None:
        """The value of exactly this scope, or None if nothing is set there.

        None means "not set" and never "set to nothing" — that difference is
        what makes the cascade work: an unset scope steps aside for the one
        above it instead of overwriting it with emptiness.
        """
        zeile = self.verbindung.execute(
            "SELECT wert_json FROM einstellungen WHERE bereich = ? AND schluessel = ?",
            (bereich, schluessel),
        ).fetchone()
        if zeile is None:
            return None
        try:
            return json.loads(zeile["wert_json"])
        except json.JSONDecodeError:
            # An unreadable row must not take the chat down: it counts as
            # unset, and the next save overwrites it.
            return None

    def setzen(self, bereich: str, schluessel: str, wert: Any) -> None:
        """Stores a value. `None` removes the entry — see `holen`."""
        if wert is None:
            self.loeschen(bereich, schluessel)
            return
        self.verbindung.execute(
            """
            INSERT INTO einstellungen (bereich, schluessel, wert_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (bereich, schluessel) DO UPDATE SET
                wert_json = excluded.wert_json,
                updated_at = excluded.updated_at
            """,
            (bereich, schluessel, json.dumps(wert, ensure_ascii=False), self.zeitstempel()),
        )

    def loeschen(self, bereich: str, schluessel: str) -> None:
        self.verbindung.execute(
            "DELETE FROM einstellungen WHERE bereich = ? AND schluessel = ?",
            (bereich, schluessel),
        )

    def bereich_leeren(self, bereich: str) -> None:
        """Everything of one scope — used when a chat is deleted."""
        self.verbindung.execute("DELETE FROM einstellungen WHERE bereich = ?", (bereich,))

    # --- the cascade ------------------------------------------------------

    def kette(self, schluessel: str, *, modell: str | None = None,
              chat: str | None = None) -> list[str]:
        """The scopes to ask, from general to specific."""
        bereiche = [GLOBAL]
        if modell:
            bereiche.append(modell_bereich(modell))
        if chat:
            bereiche.append(chat_bereich(chat))
        return bereiche

    def aufgeloest(self, schluessel: str, *, modell: str | None = None,
                   chat: str | None = None, vorgabe: Any = None) -> Any:
        """The value that applies here — the most specific one that is set."""
        wert = vorgabe
        for bereich in self.kette(schluessel, modell=modell, chat=chat):
            gefunden = self.holen(bereich, schluessel)
            if gefunden is not None:
                wert = gefunden
        return wert

    def zusammengefuehrt(self, schluessel: str, *, modell: str | None = None,
                         chat: str | None = None,
                         vorgabe: dict[str, Any] | None = None) -> Any:
        """Same, but for settings that are a set of values.

        Merged key by key instead of replaced wholesale: a model that sets
        only the temperature keeps the global top-p rather than dropping it.
        That is what makes a cascade useful — you override one knob, not the
        whole panel.

        Not everything is a set of values, though. A list has no keys to merge
        along, and merging two of them would mean either concatenating (which
        no scope asked for) or dropping one silently. Such a value therefore
        travels whole, and the most specific scope that set it wins — which is
        the same rule, applied to something that cannot be taken apart.
        """
        zusammen: dict[str, Any] = dict(vorgabe or {})
        ganz: Any = None
        for bereich in self.kette(schluessel, modell=modell, chat=chat):
            gefunden = self.holen(bereich, schluessel)
            if gefunden is None:
                continue
            if isinstance(gefunden, dict):
                zusammen.update(gefunden)
            else:
                ganz = gefunden
        return ganz if ganz is not None else zusammen

    def herkunft(self, schluessel: str, *, modell: str | None = None,
                 chat: str | None = None) -> dict[str, str]:
        """Which scope each key comes from — so the UI can show it.

        Without this the cascade is a black box: you see a number and cannot
        tell whether it is yours, the model's, or the default.
        """
        woher: dict[str, str] = {}
        for bereich in self.kette(schluessel, modell=modell, chat=chat):
            gefunden = self.holen(bereich, schluessel)
            if isinstance(gefunden, dict):
                for name in gefunden:
                    woher[name] = bereich
        return woher
