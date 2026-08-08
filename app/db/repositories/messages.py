"""Access to messages."""

from __future__ import annotations

import json
from typing import Any

from app.db.models import Message
from app.db.repositories.base import Repository, neue_id


class MessageRepository(Repository):
    def speichern(
        self,
        *,
        chat_id: str,
        role: str,
        content: str,
        reasoning: str | None = None,
        stats: dict[str, Any] | None = None,
        bild: str | None = None,
        dokument: str | None = None,
    ) -> Message:
        nachricht = Message(
            id=neue_id(),
            chat_id=chat_id,
            role=role,
            content=content,
            created_at=self.zeitstempel(),
            reasoning=reasoning,
            stats=stats or {},
            bild=bild,
            dokument=dokument,
        )
        self.verbindung.execute(
            """
            INSERT INTO messages (id, chat_id, role, content, reasoning, stats_json,
                                  bild, dokument, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nachricht.id,
                nachricht.chat_id,
                nachricht.role,
                nachricht.content,
                nachricht.reasoning,
                json.dumps(nachricht.stats, ensure_ascii=False) if nachricht.stats else None,
                nachricht.bild,
                nachricht.dokument,
                nachricht.created_at,
            ),
        )
        return nachricht

    def holen(self, message_id: str) -> Message | None:
        zeile = self.verbindung.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return Message.aus_zeile(zeile) if zeile else None

    def auflisten(self, *, chat_id: str, limit: int = 500, offset: int = 0) -> list[Message]:
        """Oldest first — the order of the conversation."""
        zeilen = self.verbindung.execute(
            """
            SELECT * FROM messages
            WHERE chat_id = ?
            ORDER BY created_at ASC, rowid ASC
            LIMIT ? OFFSET ?
            """,
            (chat_id, limit, offset),
        ).fetchall()
        return [Message.aus_zeile(zeile) for zeile in zeilen]

    def letzte(self, *, chat_id: str, role: str | None = None) -> Message | None:
        sql = "SELECT * FROM messages WHERE chat_id = ?"
        parameter: list[object] = [chat_id]
        if role is not None:
            sql += " AND role = ?"
            parameter.append(role)
        sql += " ORDER BY created_at DESC, rowid DESC LIMIT 1"
        zeile = self.verbindung.execute(sql, parameter).fetchone()
        return Message.aus_zeile(zeile) if zeile else None

    def inhalt_aktualisieren(
        self,
        message_id: str,
        *,
        content: str,
        reasoning: str | None = None,
        stats: dict[str, Any] | None = None,
        bild: str | None = None,
    ) -> Message | None:
        """Needed for streaming: create a placeholder, fill it at the end.

        ``bild``: file name of a tool image under data/bilder/.
        COALESCE, so None does not wipe away an image that may exist.
        """
        self.verbindung.execute(
            "UPDATE messages SET content = ?, reasoning = ?, stats_json = ?, "
            "bild = COALESCE(?, bild) WHERE id = ?",
            (
                content,
                reasoning,
                json.dumps(stats, ensure_ascii=False) if stats else None,
                bild,
                message_id,
            ),
        )
        return self.holen(message_id)

    def loeschen(self, message_id: str) -> bool:
        cursor = self.verbindung.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        return cursor.rowcount > 0

    def loeschen_ab(self, *, chat_id: str, ab_zeitstempel: str) -> int:
        """For "regenerate": discard everything from a point in the history on."""
        cursor = self.verbindung.execute(
            "DELETE FROM messages WHERE chat_id = ? AND created_at >= ?",
            (chat_id, ab_zeitstempel),
        )
        return cursor.rowcount

    def anzahl(self, *, chat_id: str) -> int:
        zeile = self.verbindung.execute(
            "SELECT COUNT(*) AS anzahl FROM messages WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return int(zeile["anzahl"])
