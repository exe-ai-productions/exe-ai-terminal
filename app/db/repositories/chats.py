"""Access to chats."""

from __future__ import annotations

import json

from app.db.models import Chat
from app.db.repositories.base import Repository, neue_id


class ChatRepository(Repository):
    def erstellen(
        self,
        *,
        user_id: str,
        title: str,
        endpoint_id: str | None = None,
    ) -> Chat:
        chat = Chat(
            id=neue_id(),
            user_id=user_id,
            title=title,
            created_at=self.zeitstempel(),
            updated_at=self.zeitstempel(),
            endpoint_id=endpoint_id,
        )
        self.verbindung.execute(
            """
            INSERT INTO chats (id, user_id, title, endpoint_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chat.id,
                chat.user_id,
                chat.title,
                chat.endpoint_id,
                chat.created_at,
                chat.updated_at,
            ),
        )
        return chat

    def holen(self, chat_id: str, *, user_id: str | None = None) -> Chat | None:
        sql = "SELECT * FROM chats WHERE id = ?"
        parameter: list[object] = [chat_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            parameter.append(user_id)
        zeile = self.verbindung.execute(sql, parameter).fetchone()
        return Chat.aus_zeile(zeile) if zeile else None

    def auflisten(
        self, *, user_id: str, suche: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[Chat]:
        """Pinned first, then the newest. ``suche`` filters on the title."""
        sql = "SELECT * FROM chats WHERE user_id = ?"
        parameter: list[object] = [user_id]
        if suche:
            sql += " AND title LIKE ?"
            parameter.append(f"%{suche}%")
        # Pinned ones always sit on top. rowid as tiebreaker: equal
        # timestamps must not lead to a random order.
        sql += " ORDER BY pinned DESC, updated_at DESC, rowid DESC LIMIT ? OFFSET ?"
        parameter.extend([limit, offset])
        zeilen = self.verbindung.execute(sql, parameter).fetchall()
        return [Chat.aus_zeile(zeile) for zeile in zeilen]

    def aktualisieren(self, chat_id: str, **felder: object) -> Chat | None:
        """Changes individual fields. Unknown field names are rejected."""
        erlaubt = {
            "title",
            "prompt_aus",
            "endpoint_id",
            "pinned",
            "working_dirs",
        }
        # Model parameters do not live here any more: they are settings and
        # sit in the cascade (app/db/repositories/einstellungen.py), where a
        # value can hold for one chat, one model, or everything.
        # The working folders: a list from the outside, JSON in the
        # column. An empty list means NULL — no difference between "none
        # chosen" and "empty list stored".
        if isinstance(felder.get("working_dirs"), list):
            ordner = felder["working_dirs"]
            felder["working_dirs"] = json.dumps(ordner, ensure_ascii=False) if ordner else None
        unbekannt = set(felder) - erlaubt
        if unbekannt:
            raise ValueError(f"Unbekannte Felder: {', '.join(sorted(unbekannt))}")
        if not felder:
            return self.holen(chat_id)

        zuweisungen = ", ".join(f"{name} = ?" for name in felder)
        # SQLite has no boolean — True/False become 1/0.
        werte = [int(wert) if isinstance(wert, bool) else wert for wert in felder.values()]
        werte.extend([self.zeitstempel(), chat_id])
        self.verbindung.execute(
            f"UPDATE chats SET {zuweisungen}, updated_at = ? WHERE id = ?", werte
        )
        return self.holen(chat_id)

    def anheften(self, chat_id: str, angeheftet: bool = True) -> Chat | None:
        """Lifts a chat permanently to the top of the list.

        Deliberately does not touch ``updated_at``: pinning is not usage.
        Otherwise, on unpinning, a chat would jump to a spot where it has no
        business being, content-wise.
        """
        self.verbindung.execute(
            "UPDATE chats SET pinned = ? WHERE id = ?", (int(angeheftet), chat_id)
        )
        return self.holen(chat_id)

    def zeitstempel_auffrischen(self, chat_id: str) -> None:
        """Lifts a chat upward in the sort order (new message)."""
        self.verbindung.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?", (self.zeitstempel(), chat_id)
        )

    def loeschen(self, chat_id: str, *, user_id: str | None = None) -> bool:
        """Deletes the chat along with messages and documents (ON DELETE CASCADE)."""
        sql = "DELETE FROM chats WHERE id = ?"
        parameter: list[object] = [chat_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            parameter.append(user_id)
        cursor = self.verbindung.execute(sql, parameter)
        geloescht = cursor.rowcount > 0
        if geloescht:
            # Settings of this chat go with it. The database cannot do this by
            # itself: the scope is a text field, not a foreign key, so nothing
            # cascades — without this the rows would outlive their chat.
            self.verbindung.execute(
                "DELETE FROM einstellungen WHERE bereich = ?", (f"chat:{chat_id}",)
            )
        return geloescht

    def anzahl(self, *, user_id: str) -> int:
        zeile = self.verbindung.execute(
            "SELECT COUNT(*) AS anzahl FROM chats WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(zeile["anzahl"])
