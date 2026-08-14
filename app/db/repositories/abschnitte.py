"""The sections a large document was cut into, with their vectors.

Deliberately its own repository and not a few extra methods on the document
one: a document is a file somebody attached, a section is a computed thing
that only exists because the document was too big to send whole. They have
different lifetimes and different reasons to be read.

The vector is stored as a blob and comes back as a list of floats — the
packing lives in ``app/einbettung.py``, so the database layer never has to
know what a vector is.
"""

from __future__ import annotations

from app.db.repositories.base import Repository, neue_id
from app.einbettung import entpacken, packen


class AbschnittRepository(Repository):
    def speichern(
        self,
        *,
        document_id: str,
        abschnitte: list[tuple[str, list[float]]],
        modell: str = "",
    ) -> int:
        """Write a document's sections. Replaces whatever was there.

        Replacing rather than adding: a document is cut up once, and a
        second run over the same document means the first one was
        incomplete — two sets of sections for one file would be searched
        together and would return the same passage twice.

        ``modell`` is the name of the embedding model that produced the
        vectors. It travels with them because nothing in the numbers says
        which model wrote them, and comparing across models gives an order
        that looks right and is not.
        """
        self.loeschen(document_id)
        zeitstempel = self.zeitstempel()
        self.verbindung.executemany(
            """
            INSERT INTO dokument_abschnitte
                   (id, document_id, nummer, text, vektor, modell, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (neue_id(), document_id, nummer, text, packen(vektor), modell, zeitstempel)
                for nummer, (text, vektor) in enumerate(abschnitte, start=1)
            ],
        )
        return len(abschnitte)

    def auflisten(
        self, document_id: str, *, modell: str | None = None
    ) -> list[tuple[int, str, list[float]]]:
        """The sections of a document, in order.

        With ``modell`` given, only the sections that model wrote come back.
        Everything else is not a weaker match — it is a number from another
        scale, and leaving it out is what keeps the selection honest.
        """
        if modell is None:
            zeilen = self.verbindung.execute(
                """
                SELECT nummer, text, vektor FROM dokument_abschnitte
                WHERE document_id = ? ORDER BY nummer ASC
                """,
                (document_id,),
            ).fetchall()
        else:
            zeilen = self.verbindung.execute(
                """
                SELECT nummer, text, vektor FROM dokument_abschnitte
                WHERE document_id = ? AND modell = ? ORDER BY nummer ASC
                """,
                (document_id, modell),
            ).fetchall()
        return [(z["nummer"], z["text"], entpacken(z["vektor"])) for z in zeilen]

    def anzahl(self, document_id: str) -> int:
        zeile = self.verbindung.execute(
            "SELECT COUNT(*) AS n FROM dokument_abschnitte WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        return int(zeile["n"]) if zeile else 0

    def loeschen(self, document_id: str) -> int:
        cursor = self.verbindung.execute(
            "DELETE FROM dokument_abschnitte WHERE document_id = ?", (document_id,)
        )
        return cursor.rowcount
