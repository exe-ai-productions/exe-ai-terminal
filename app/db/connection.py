"""Database connection and schema setup.

This file and the repositories are the only places in the project that know
SQL. If SQLite is later replaced by PostgreSQL, the swap happens right here.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)

SCHEMA_DATEI = Path(__file__).resolve().parent / "schema.sql"
SCHEMA_VERSION = 11

# Schema changes for databases that already exist.
#
# schema.sql always describes the target state — for a new database it is
# enough. An existing database, however, must be brought along without losing
# chats. Each entry here runs exactly once.
#
# Rule: only append, never rewrite. A step once published stays put, even if
# it later seems superfluous — otherwise databases end up in different states
# depending on their age.
MIGRATIONEN: list[tuple[int, list[str]]] = [
    (
        2,
        [
            "ALTER TABLE chats ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0",
            # The old index does not know the new column and would no longer
            # kick in for sorting.
            "DROP INDEX IF EXISTS idx_chats_user_updated",
        ],
    ),
    (
        3,
        [
            # Further model parameters as JSON. Deliberately one column
            # instead of one per knob: which ones exist depends on the
            # backend and changes with its versions. A table change for every
            # new knob would be the wrong price.
            "ALTER TABLE chats ADD COLUMN parameter_json TEXT",
        ],
    ),
    (
        4,
        [
            # The system prompt moves from the database into a file and is
            # freshly prepended on every request. What remains on the chat is
            # only the question of whether it is suspended for this one chat.
            "ALTER TABLE chats ADD COLUMN prompt_aus INTEGER NOT NULL DEFAULT 0",
            # The old copy goes away. It was a snapshot from the time of
            # creation and never saw later changes — exactly the reason for
            # the rework.
            "ALTER TABLE chats DROP COLUMN system_prompt",
        ],
    ),
    (
        5,
        # Persist runs (phase 6.2): the tables auftraege and
        # auftrag_schritte are pure additions and live in schema.sql, which
        # runs after the migrations anyway. The entry here only bumps the
        # version so the database knows it is aware of the addition.
        [],
    ),
    (
        6,
        [
            # Vision: a user message can carry an
            # image. Only the file name under data/bilder/ is stored — the
            # bytes belong in the file system, not in the database.
            "ALTER TABLE messages ADD COLUMN bild TEXT",
        ],
    ),
    (
        7,
        [
            # Document upload (4.1): a user message can carry a
            # document — only the id is stored; text and facts live in
            # documents (ready since phase 1, and it gains two columns:
            # page count and whether it was truncated).
            "ALTER TABLE messages ADD COLUMN dokument TEXT",
            "ALTER TABLE documents ADD COLUMN pages INTEGER",
            "ALTER TABLE documents ADD COLUMN truncated INTEGER NOT NULL DEFAULT 0",
        ],
    ),
    (
        8,
        [
            # The working directory (shell tool): every
            # chat may have its own folder the model is later allowed to
            # work in — like `cd` in a real terminal. It is set by the user,
            # never by the model. NULL means: none chosen, the shell tool
            # stays closed.
            "ALTER TABLE chats ADD COLUMN working_dir TEXT",
        ],
    ),
    (
        9,
        [
            # One folder becomes several: a chat may have
            # up to four folders shared with it — the first is the working
            # directory commands run in, the others are additional sources.
            # The limit lives in the handler.
            #
            # The old single column moves over as a one-element list and is
            # then dropped: two columns for the same thing would be exactly
            # the kind of leftover someone later reads the wrong one of.
            "ALTER TABLE chats ADD COLUMN working_dirs TEXT",
            "UPDATE chats SET working_dirs = json_array(working_dir) "
            "WHERE working_dir IS NOT NULL",
            "ALTER TABLE chats DROP COLUMN working_dir",
        ],
    ),
    (
        10,
        [
            # Settings become a cascade. Until now a value could only live on
            # a single chat, so every new chat started at the endpoint's
            # defaults and had to be set by hand again. The table itself is in
            # schema.sql, which runs after the migrations; what happens here
            # is the move.
            #
            # Existing chat values keep working: they become 'chat:<id>'
            # entries, the most specific scope, so nothing changes for an old
            # conversation. Afterwards the four columns go — two places for
            # one setting is exactly the leftover somebody later reads the
            # wrong one from.
            #
            # The table is created here and not left to schema.sql: that one
            # runs AFTER the migrations, and the move below needs it now.
            """
            CREATE TABLE IF NOT EXISTS einstellungen (
                bereich    TEXT NOT NULL,
                schluessel TEXT NOT NULL,
                wert_json  TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (bereich, schluessel)
            )
            """,
            """
            INSERT OR REPLACE INTO einstellungen (bereich, schluessel, wert_json, updated_at)
            SELECT 'chat:' || id, 'parameter',
                   json_patch(
                       COALESCE(parameter_json, '{}'),
                       json_object(
                           'temperature', temperature,
                           'top_p',       top_p,
                           'max_tokens',  max_tokens
                       )
                   ),
                   updated_at
              FROM chats
             WHERE parameter_json IS NOT NULL
                OR temperature IS NOT NULL
                OR top_p IS NOT NULL
                OR max_tokens IS NOT NULL
            """,
            "ALTER TABLE chats DROP COLUMN parameter_json",
            "ALTER TABLE chats DROP COLUMN temperature",
            "ALTER TABLE chats DROP COLUMN top_p",
            "ALTER TABLE chats DROP COLUMN max_tokens",
        ],
    ),
    (
        11,
        [
            # Which embedding model a vector came out of. Without it, sections
            # written by one model are compared against a question embedded by
            # another: the numbers line up, the similarities sort, and the
            # answer is built from whichever sections happened to be stored
            # first. Sections from before this step carry the empty name and
            # are therefore never compared — they are recomputed on the next
            # upload, which is cheaper than guessing which model wrote them.
            "ALTER TABLE dokument_abschnitte ADD COLUMN modell TEXT NOT NULL DEFAULT ''",
        ],
    ),
]


def jetzt_iso() -> str:
    """Current moment as ISO 8601 in UTC — uniform across the whole project.

    Microseconds are necessary: at coarser resolution, two chats changed in
    quick succession get the same timestamp and the sorting in the sidebar
    becomes random. The notation stays sortable because ISO 8601 with a
    fixed number of digits also compares correctly as text.
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Database:
    """Thin shell around SQLite: connection, transactions, schema setup."""

    def __init__(self, pfad: str | Path) -> None:
        self.pfad = Path(pfad)
        self._lokal = threading.local()
        if str(self.pfad) != ":memory:":
            self.pfad.parent.mkdir(parents=True, exist_ok=True)
        # For ":memory:" the same connection must persist, otherwise the
        # database is empty again after every close.
        self._geteilte_speicher_verbindung: sqlite3.Connection | None = None

    # --- Connection ------------------------------------------------------

    def _neue_verbindung(self) -> sqlite3.Connection:
        verbindung = sqlite3.connect(
            self.pfad, check_same_thread=False, isolation_level=None
        )
        verbindung.row_factory = sqlite3.Row
        verbindung.execute("PRAGMA foreign_keys = ON")
        if str(self.pfad) != ":memory:":
            verbindung.execute("PRAGMA journal_mode = WAL")
        verbindung.execute("PRAGMA busy_timeout = 5000")
        return verbindung

    @property
    def verbindung(self) -> sqlite3.Connection:
        if str(self.pfad) == ":memory:":
            if self._geteilte_speicher_verbindung is None:
                self._geteilte_speicher_verbindung = self._neue_verbindung()
            return self._geteilte_speicher_verbindung

        vorhandene = getattr(self._lokal, "verbindung", None)
        if vorhandene is None:
            vorhandene = self._neue_verbindung()
            self._lokal.verbindung = vorhandene
        return vorhandene

    @contextmanager
    def transaktion(self) -> Iterator[sqlite3.Connection]:
        """All or nothing — on an exception we roll back."""
        verbindung = self.verbindung
        verbindung.execute("BEGIN")
        try:
            yield verbindung
        except Exception:
            verbindung.execute("ROLLBACK")
            raise
        else:
            verbindung.execute("COMMIT")

    def schliessen(self) -> None:
        if self._geteilte_speicher_verbindung is not None:
            self._geteilte_speicher_verbindung.close()
            self._geteilte_speicher_verbindung = None
        vorhandene = getattr(self._lokal, "verbindung", None)
        if vorhandene is not None:
            vorhandene.close()
            self._lokal.verbindung = None

    # --- Schema ----------------------------------------------------------

    def schema_einrichten(self) -> None:
        """Creates tables if they are missing and brings the schema up to date.

        Order matters: on an existing database the migrations run first, then
        schema.sql. The other way around, schema.sql would stumble over
        columns that do not exist yet.
        """
        verbindung = self.verbindung
        neu = (
            verbindung.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chats'"
            ).fetchone()
            is None
        )

        if neu:
            # Fresh database: schema.sql already describes the target state,
            # the migrations are already contained in it.
            verbindung.executescript(SCHEMA_DATEI.read_text(encoding="utf-8"))
            verbindung.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, jetzt_iso()),
            )
            log.info("Schema angelegt (Version %s) in %s", SCHEMA_VERSION, self.pfad)
            return

        self._migrationen_anwenden()
        # Afterwards schema.sql creates everything that has been added since —
        # new tables as well as renewed indexes.
        verbindung.executescript(SCHEMA_DATEI.read_text(encoding="utf-8"))

    def _migrationen_anwenden(self) -> None:
        verbindung = self.verbindung
        zeile = verbindung.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        stand = zeile["version"] if zeile else 0

        for version, anweisungen in MIGRATIONEN:
            if version <= stand:
                continue
            for anweisung in anweisungen:
                try:
                    verbindung.execute(anweisung)
                except sqlite3.OperationalError as fehler:
                    # A step that has nothing left to do is not a failure.
                    # Three ways that shows: the column an ADD wants is
                    # already there, the column a DROP wants is already gone,
                    # or the whole table is still missing.
                    #
                    # The last one is the case of a database older than the
                    # table itself. Migrations run before schema.sql, so a
                    # column added to a young table is asked for while the
                    # table does not exist yet — and schema.sql, a moment
                    # later, creates it with the column already in place.
                    # Everything else is a real error and goes up.
                    text = str(fehler).lower()
                    if not any(
                        satz in text
                        for satz in ("duplicate column", "no such column", "no such table")
                    ):
                        raise
                    log.info("Migration %s hatte nichts zu tun", version)
            verbindung.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, jetzt_iso()),
            )
            log.info("Schema auf Version %s gehoben", version)

        if stand > SCHEMA_VERSION:
            log.warning(
                "Die Datenbank hat Schema-Version %s, dieser Stand kennt nur %s — "
                "läuft hier eine ältere Fassung des Programms?",
                stand,
                SCHEMA_VERSION,
            )

    def schema_version(self) -> int | None:
        zeile = self.verbindung.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return zeile["version"] if zeile else None
