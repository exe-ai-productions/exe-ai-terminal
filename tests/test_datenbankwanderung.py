"""An update must not cost anybody their chats.

schema.sql describes the target state and every statement in it says IF NOT
EXISTS, so a database that already exists gets new tables for free. What it
does NOT get for free is a new COLUMN on a table it already has — IF NOT
EXISTS does nothing there, and the ALTER has to be written down as a
migration.

These tests build a database at an older schema version, run the upgrade over
it the way a service start does, and check both halves: the new shape is
there, and the old content is still there.
"""

from __future__ import annotations

import sqlite3

from app.db import Database
from app.db.connection import MIGRATIONEN, SCHEMA_VERSION


def _spalten(db: Database, tabelle: str) -> set[str]:
    return {
        zeile["name"]
        for zeile in db.verbindung.execute(f"PRAGMA table_info({tabelle})").fetchall()
    }


def _auf_version_zuruecksetzen(db: Database, version: int) -> None:
    """Make the database look like it was built before `version` ran."""
    db.verbindung.execute("DELETE FROM schema_version WHERE version > ?", (version,))
    db.verbindung.commit()


# --- The shape ------------------------------------------------------------


def test_eine_neue_datenbank_hat_alles(db: Database):
    assert "modell" in _spalten(db, "dokument_abschnitte")


def test_die_wanderungen_sind_lueckenlos_bis_zur_version():
    """A version nobody wrote a step for is a step that never runs."""
    nummern = [nummer for nummer, _ in MIGRATIONEN]
    assert nummern == sorted(nummern), "Wanderungen stehen nicht in Reihenfolge"
    assert len(nummern) == len(set(nummern)), "eine Versionsnummer ist doppelt"
    assert max(nummern) <= SCHEMA_VERSION


# --- The upgrade ----------------------------------------------------------


def test_eine_bestehende_datenbank_bekommt_die_neue_spalte(tmp_path):
    pfad = tmp_path / "alt.db"
    db = Database(pfad)
    db.schema_einrichten()

    # Back to the state before the column existed: drop it and forget the step.
    db.verbindung.execute("ALTER TABLE dokument_abschnitte DROP COLUMN modell")
    _auf_version_zuruecksetzen(db, 10)
    assert "modell" not in _spalten(db, "dokument_abschnitte")

    # What a service start does.
    db.schema_einrichten()

    assert "modell" in _spalten(db, "dokument_abschnitte")


def test_der_inhalt_ueberlebt_die_wanderung(tmp_path):
    """The point of the whole exercise."""
    pfad = tmp_path / "alt.db"
    db = Database(pfad)
    db.schema_einrichten()
    db.verbindung.execute(
        "INSERT INTO chats (id, user_id, title, created_at, updated_at)"
        " VALUES ('c1', 'u1', 'Ein alter Chat', '2020-01-01', '2020-01-01')"
    )
    db.verbindung.commit()

    db.verbindung.execute("ALTER TABLE dokument_abschnitte DROP COLUMN modell")
    _auf_version_zuruecksetzen(db, 10)
    db.schema_einrichten()

    zeile = db.verbindung.execute("SELECT title FROM chats WHERE id = 'c1'").fetchone()
    assert zeile is not None
    assert zeile["title"] == "Ein alter Chat"


def test_zweimal_wandern_aendert_nichts_mehr(tmp_path):
    pfad = tmp_path / "alt.db"
    db = Database(pfad)
    db.schema_einrichten()
    db.verbindung.execute("ALTER TABLE dokument_abschnitte DROP COLUMN modell")
    _auf_version_zuruecksetzen(db, 10)

    db.schema_einrichten()
    db.schema_einrichten()

    spalten = [
        z["name"]
        for z in db.verbindung.execute("PRAGMA table_info(dokument_abschnitte)").fetchall()
    ]
    assert spalten.count("modell") == 1


def test_eine_datenbank_aelter_als_die_tabelle_wandert_trotzdem(tmp_path):
    """The oldest case, and the one that caught this.

    Migrations run before schema.sql. A column added to a young table is
    therefore asked for on databases that do not have that table yet — and
    the ALTER fails with "no such table". schema.sql creates it a moment
    later, with the column already in it, so there is nothing to repair;
    the step simply has nothing to do.
    """
    pfad = tmp_path / "sehr_alt.db"
    db = Database(pfad)
    db.schema_einrichten()

    # An installation from before sections existed at all.
    db.verbindung.execute("DROP TABLE dokument_abschnitte")
    _auf_version_zuruecksetzen(db, 1)
    db.verbindung.commit()

    db.schema_einrichten()

    assert "modell" in _spalten(db, "dokument_abschnitte")


def test_die_wanderung_stolpert_nicht_ueber_eine_spalte_die_schon_da_ist(tmp_path):
    """A database built from the current schema.sql already has the result."""
    pfad = tmp_path / "neu.db"
    db = Database(pfad)
    db.schema_einrichten()
    _auf_version_zuruecksetzen(db, 10)

    # Must not raise: the ALTER hits an existing column, which means the step
    # has effectively already happened.
    db.schema_einrichten()
    assert "modell" in _spalten(db, "dokument_abschnitte")


# --- What the column is for -----------------------------------------------


def test_abschnitte_werden_nach_modell_getrennt(tmp_path):
    from app.db import repositories_erstellen

    pfad = tmp_path / "d.db"
    db = Database(pfad)
    db.schema_einrichten()
    repos = repositories_erstellen(db)

    chat = repos.chats.erstellen(user_id="u1", title="c")
    dokument = repos.documents.speichern(
        chat_id=chat.id, filename="bericht.pdf", mime_type="application/pdf", size_bytes=10
    )

    repos.abschnitte.speichern(
        document_id=dokument.id,
        abschnitte=[("erster", [1.0, 0.0]), ("zweiter", [0.0, 1.0])],
        modell="nomic-embed-text.gguf",
    )

    # The same model gets its sections back.
    assert len(repos.abschnitte.auflisten(dokument.id, modell="nomic-embed-text.gguf")) == 2
    # Another model gets nothing — not a weaker match, a different scale.
    assert repos.abschnitte.auflisten(dokument.id, modell="bge-m3.gguf") == []
    # Without asking, everything comes back, the way the count does.
    assert len(repos.abschnitte.auflisten(dokument.id)) == 2
