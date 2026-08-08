"""Access to jobs and their transcript (phase 6.2).

The states are listed here again even though the database already enforces
them via CHECK: the code should be able to report a typo before SQLite
answers with a terse IntegrityError.
"""

from __future__ import annotations

from app.db.models import Auftrag, AuftragSchritt
from app.db.repositories.base import Repository, neue_id

ZUSTAENDE = {"laeuft", "wartet", "fertig", "abgebrochen", "gescheitert", "unterbrochen"}

# States in which a job is over. Everything else is still alive.
ENDZUSTAENDE = {"fertig", "abgebrochen", "gescheitert", "unterbrochen"}


class AuftragRepository(Repository):
    # --- Jobs ------------------------------------------------------------

    def erstellen(
        self,
        *,
        user_id: str,
        agent: str,
        auftrag: str,
        endpoint_id: str | None = None,
        zustand: str = "laeuft",
    ) -> Auftrag:
        self._zustand_pruefen(zustand)
        eintrag = Auftrag(
            id=neue_id(),
            user_id=user_id,
            agent=agent,
            auftrag=auftrag,
            zustand=zustand,
            endpoint_id=endpoint_id,
            created_at=self.zeitstempel(),
            updated_at=self.zeitstempel(),
        )
        self.verbindung.execute(
            """
            INSERT INTO auftraege (id, user_id, agent, auftrag, zustand,
                                   endpoint_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                eintrag.id,
                eintrag.user_id,
                eintrag.agent,
                eintrag.auftrag,
                eintrag.zustand,
                eintrag.endpoint_id,
                eintrag.created_at,
                eintrag.updated_at,
            ),
        )
        return eintrag

    def holen(self, auftrag_id: str, *, user_id: str | None = None) -> Auftrag | None:
        sql = "SELECT * FROM auftraege WHERE id = ?"
        parameter: list[object] = [auftrag_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            parameter.append(user_id)
        zeile = self.verbindung.execute(sql, parameter).fetchone()
        return Auftrag.aus_zeile(zeile) if zeile else None

    def auflisten(
        self, *, user_id: str, limit: int = 100, offset: int = 0
    ) -> list[Auftrag]:
        """Most recently touched first. rowid as tiebreaker, as with chats."""
        zeilen = self.verbindung.execute(
            "SELECT * FROM auftraege WHERE user_id = ? "
            "ORDER BY updated_at DESC, rowid DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
        return [Auftrag.aus_zeile(zeile) for zeile in zeilen]

    def zustand_setzen(
        self,
        auftrag_id: str,
        zustand: str,
        *,
        ende_grund: str | None = None,
        ergebnis: str | None = None,
    ) -> Auftrag | None:
        """Sets the state — and, at an ending, the readable reason (6.4).

        ``ende_grund`` and ``ergebnis`` are only written when they come
        along: a state change ``wartet`` → ``laeuft`` must not wipe away a
        previously set reason.
        """
        self._zustand_pruefen(zustand)
        zuweisungen = ["zustand = ?", "updated_at = ?"]
        werte: list[object] = [zustand, self.zeitstempel()]
        if ende_grund is not None:
            zuweisungen.append("ende_grund = ?")
            werte.append(ende_grund)
        if ergebnis is not None:
            zuweisungen.append("ergebnis = ?")
            werte.append(ergebnis)
        werte.append(auftrag_id)
        self.verbindung.execute(
            f"UPDATE auftraege SET {', '.join(zuweisungen)} WHERE id = ?", werte
        )
        return self.holen(auftrag_id)

    def generation_verknuepfen(self, auftrag_id: str, generation_id: str | None) -> None:
        """Remembers the living in-memory run — or clears the reference."""
        self.verbindung.execute(
            "UPDATE auftraege SET generation_id = ? WHERE id = ?",
            (generation_id, auftrag_id),
        )

    def loeschen(self, auftrag_id: str, *, user_id: str | None = None) -> bool:
        """Deletes the job along with its transcript (ON DELETE CASCADE)."""
        sql = "DELETE FROM auftraege WHERE id = ?"
        parameter: list[object] = [auftrag_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            parameter.append(user_id)
        cursor = self.verbindung.execute(sql, parameter)
        return cursor.rowcount > 0

    def anzahl(self, *, user_id: str) -> int:
        zeile = self.verbindung.execute(
            "SELECT COUNT(*) AS anzahl FROM auftraege WHERE user_id = ?", (user_id,)
        ).fetchone()
        return int(zeile["anzahl"])

    # --- For the alarm clock (6.7) ---------------------------------------

    def letzter_start(self, *, agent: str) -> str | None:
        """When the agent was last started — no matter by whom.

        The alarm clock uses this to ask whether a due time is already done:
        a run since the due time counts, including a manually started one —
        the report in question exists then, after all.
        """
        zeile = self.verbindung.execute(
            "SELECT created_at FROM auftraege WHERE agent = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (agent,),
        ).fetchone()
        return zeile["created_at"] if zeile else None

    def laeuft_gerade(self, *, agent: str) -> bool:
        """Whether a run of the agent is still active (running or waiting)."""
        zeile = self.verbindung.execute(
            "SELECT 1 FROM auftraege WHERE agent = ? "
            "AND zustand IN ('laeuft', 'wartet') LIMIT 1",
            (agent,),
        ).fetchone()
        return zeile is not None

    def letzte_zustaende(self, *, agent: str, anzahl: int) -> list[str]:
        """The states of the most recent runs, newest first.

        Basis of the pause rule: three ``gescheitert`` in a row, and the
        alarm clock leaves the agent alone until a run ends well again.
        """
        zeilen = self.verbindung.execute(
            "SELECT zustand FROM auftraege WHERE agent = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (agent, anzahl),
        ).fetchall()
        return [zeile["zustand"] for zeile in zeilen]

    # --- Transcript ------------------------------------------------------

    def schritt_anlegen(self, auftrag_id: str, typ: str, inhalt: str) -> AuftragSchritt:
        """Appends a line to the transcript. The number counts from 1 per job.

        MAX+1 instead of a dedicated counter: SQLite allows only one writer
        at a time anyway, so a race for the same number is ruled out.
        """
        schritt = AuftragSchritt(
            id=neue_id(),
            auftrag_id=auftrag_id,
            nummer=0,
            typ=typ,
            inhalt=inhalt,
            created_at=self.zeitstempel(),
        )
        cursor = self.verbindung.execute(
            """
            INSERT INTO auftrag_schritte (id, auftrag_id, nummer, typ, inhalt, created_at)
            VALUES (?, ?,
                    (SELECT COALESCE(MAX(nummer), 0) + 1
                       FROM auftrag_schritte WHERE auftrag_id = ?),
                    ?, ?, ?)
            RETURNING nummer
            """,
            (schritt.id, auftrag_id, auftrag_id, typ, inhalt, schritt.created_at),
        )
        schritt.nummer = int(cursor.fetchone()["nummer"])
        return schritt

    def schritte(self, auftrag_id: str) -> list[AuftragSchritt]:
        zeilen = self.verbindung.execute(
            "SELECT * FROM auftrag_schritte WHERE auftrag_id = ? ORDER BY nummer",
            (auftrag_id,),
        ).fetchall()
        return [AuftragSchritt.aus_zeile(zeile) for zeile in zeilen]

    # --- Service startup -------------------------------------------------

    def beim_start_aufraeumen(self) -> int:
        """Whatever is on ``laeuft`` becomes ``unterbrochen`` — ``wartet`` stays.

        After a restart, a running background
        task no longer exists, so the job is, honestly, interrupted. A
        waiting confirmation prompt, on the other hand, can still be
        answered — it only loses its dead in-memory reference.
        """
        cursor = self.verbindung.execute(
            "UPDATE auftraege SET zustand = 'unterbrochen', ende_grund = ?, "
            "generation_id = NULL, updated_at = ? WHERE zustand = 'laeuft'",
            ("dienst_neustart", self.zeitstempel()),
        )
        self.verbindung.execute(
            "UPDATE auftraege SET generation_id = NULL WHERE zustand = 'wartet'"
        )
        return cursor.rowcount

    # --- Internal --------------------------------------------------------

    @staticmethod
    def _zustand_pruefen(zustand: str) -> None:
        if zustand not in ZUSTAENDE:
            raise ValueError(
                f"Unbekannter Zustand '{zustand}'. "
                f"Erlaubt: {', '.join(sorted(ZUSTAENDE))}"
            )
