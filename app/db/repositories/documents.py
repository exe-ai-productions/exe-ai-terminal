"""Access to uploaded documents (per chat).

Only used from phase 4.1 on, but present from day one so the schema does not
have to move later.
"""

from __future__ import annotations

from app.db.models import Document
from app.db.repositories.base import Repository, neue_id


class DocumentRepository(Repository):
    def speichern(
        self,
        *,
        chat_id: str,
        filename: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        extracted_text: str | None = None,
        pages: int | None = None,
        truncated: bool = False,
    ) -> Document:
        dokument = Document(
            id=neue_id(),
            chat_id=chat_id,
            filename=filename,
            created_at=self.zeitstempel(),
            mime_type=mime_type,
            size_bytes=size_bytes,
            extracted_text=extracted_text,
            pages=pages,
            truncated=truncated,
        )
        self.verbindung.execute(
            """
            INSERT INTO documents (id, chat_id, filename, mime_type, size_bytes,
                                   extracted_text, pages, truncated, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dokument.id,
                dokument.chat_id,
                dokument.filename,
                dokument.mime_type,
                dokument.size_bytes,
                dokument.extracted_text,
                dokument.pages,
                1 if dokument.truncated else 0,
                dokument.created_at,
            ),
        )
        return dokument

    def holen(self, document_id: str) -> Document | None:
        zeile = self.verbindung.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        return Document.aus_zeile(zeile) if zeile else None

    def auflisten(self, *, chat_id: str) -> list[Document]:
        zeilen = self.verbindung.execute(
            "SELECT * FROM documents WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        ).fetchall()
        return [Document.aus_zeile(zeile) for zeile in zeilen]

    def loeschen(self, document_id: str) -> bool:
        cursor = self.verbindung.execute(
            "DELETE FROM documents WHERE id = ?", (document_id,)
        )
        return cursor.rowcount > 0
