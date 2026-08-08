"""Jobs and their log (phase 6.2, schema 5).

Both sides are checked: the new (tables, states, startup transition) and
what must remain — an existing database at version 4 has to survive the
migration without loss. The lesson from 6.1: a rebuild needs a test for
the old behavior too, not just the new one.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.db import Database, repositories_erstellen
from app.db.connection import SCHEMA_VERSION
from app.db.repositories.auftraege import ENDZUSTAENDE, ZUSTAENDE


# --- Schema and migration -------------------------------------------------


def test_frische_datenbank_hat_den_aktuellen_stand(db: Database):
    # Against the constant instead of a number: every schema bump used to
    # break this test pointlessly without checking anything.
    assert db.schema_version() == SCHEMA_VERSION


def test_migration_von_4_auf_5(tmp_path):
    """A database at version 4 gets the new tables — and keeps its chats."""
    pfad = tmp_path / "alt.db"
    alt = Database(pfad)
    alt.schema_einrichten()
    # Recreate version 4: drop the new tables, wind the version back.
    # UPDATE instead of DELETE: an empty version table would mean version 0,
    # and then the old migrations (2–4) would run again against the finished
    # schema. The steps from 5 onward do re-run over the finished schema —
    # that is intentional: the migration explicitly tolerates duplicate
    # columns.
    alt.verbindung.execute("DROP TABLE auftrag_schritte")
    alt.verbindung.execute("DROP TABLE auftraege")
    alt.verbindung.execute("UPDATE schema_version SET version = 4")
    # A chat that has to survive the migration.
    repositories_erstellen(alt).chats.erstellen(user_id="benutzer", title="Bleibt da")
    alt.schliessen()

    neu = Database(pfad)
    neu.schema_einrichten()
    assert neu.schema_version() == SCHEMA_VERSION
    repos = repositories_erstellen(neu)
    assert repos.auftraege.anzahl(user_id="benutzer") == 0
    chats = repos.chats.auflisten(user_id="benutzer")
    assert [chat.title for chat in chats] == ["Bleibt da"]
    neu.schliessen()


# --- Jobs ------------------------------------------------------------------


def test_auftrag_anlegen_und_holen(repos):
    auftrag = repos.auftraege.erstellen(
        user_id="benutzer", agent="recherche", auftrag="Sammle KI-News ein"
    )
    geladen = repos.auftraege.holen(auftrag.id)
    assert geladen is not None
    assert geladen.agent == "recherche"
    assert geladen.zustand == "laeuft"
    assert geladen.ende_grund is None


def test_auftrag_gehoert_zum_benutzer(repos):
    auftrag = repos.auftraege.erstellen(
        user_id="benutzer", agent="recherche", auftrag="Egal"
    )
    assert repos.auftraege.holen(auftrag.id, user_id="fremd") is None
    assert repos.auftraege.holen(auftrag.id, user_id="benutzer") is not None


def test_auflisten_zuletzt_bewegte_zuerst(repos):
    erster = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="1")
    zweiter = repos.auftraege.erstellen(user_id="benutzer", agent="b", auftrag="2")
    assert [a.id for a in repos.auftraege.auflisten(user_id="benutzer")] == [
        zweiter.id,
        erster.id,
    ]
    # Any activity moves the job back to the top.
    repos.auftraege.zustand_setzen(erster.id, "wartet")
    assert [a.id for a in repos.auftraege.auflisten(user_id="benutzer")][0] == erster.id


def test_alle_sechs_zustaende_sind_gueltig(repos):
    """The complete list of valid job states, pinned verbatim."""
    assert ZUSTAENDE == {
        "laeuft",
        "wartet",
        "fertig",
        "abgebrochen",
        "gescheitert",
        "unterbrochen",
    }
    auftrag = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    for zustand in sorted(ZUSTAENDE):
        geaendert = repos.auftraege.zustand_setzen(auftrag.id, zustand)
        assert geaendert.zustand == zustand


def test_unbekannter_zustand_wird_abgewiesen(repos):
    auftrag = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    with pytest.raises(ValueError, match="pausiert"):
        repos.auftraege.zustand_setzen(auftrag.id, "pausiert")


def test_datenbank_weist_zustand_selbst_ab(db: Database):
    """Even bypassing the repository, the CHECK constraint holds."""
    with pytest.raises(sqlite3.IntegrityError):
        db.verbindung.execute(
            "INSERT INTO auftraege (id, user_id, agent, auftrag, zustand,"
            " created_at, updated_at) VALUES ('x', 'u', 'a', 't', 'kaputt', '', '')"
        )


def test_ende_traegt_grund_und_ergebnis(repos):
    auftrag = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    fertig = repos.auftraege.zustand_setzen(
        auftrag.id, "fertig", ende_grund="fertig", ergebnis="Der Bericht."
    )
    assert fertig.ende_grund == "fertig"
    assert fertig.ergebnis == "Der Bericht."
    assert fertig.zustand in ENDZUSTAENDE


def test_zustandswechsel_wischt_grund_nicht_weg(repos):
    """wartet → laeuft must not erase a previously set reason."""
    auftrag = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    repos.auftraege.zustand_setzen(auftrag.id, "gescheitert", ende_grund="zeitgrenze")
    wieder = repos.auftraege.zustand_setzen(auftrag.id, "laeuft")
    assert wieder.ende_grund == "zeitgrenze"


# --- Log -------------------------------------------------------------------


def test_schritte_nummerieren_fortlaufend(repos):
    auftrag = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    erster = repos.auftraege.schritt_anlegen(auftrag.id, "status", "los")
    zweiter = repos.auftraege.schritt_anlegen(auftrag.id, "tool_call", "web_search")
    assert (erster.nummer, zweiter.nummer) == (1, 2)


def test_schritte_zaehlen_je_auftrag(repos):
    a = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="1")
    b = repos.auftraege.erstellen(user_id="benutzer", agent="b", auftrag="2")
    repos.auftraege.schritt_anlegen(a.id, "status", "x")
    schritt_b = repos.auftraege.schritt_anlegen(b.id, "status", "y")
    assert schritt_b.nummer == 1


def test_schritte_kommen_geordnet_zurueck(repos):
    auftrag = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    for inhalt in ("eins", "zwei", "drei"):
        repos.auftraege.schritt_anlegen(auftrag.id, "status", inhalt)
    assert [s.inhalt for s in repos.auftraege.schritte(auftrag.id)] == [
        "eins",
        "zwei",
        "drei",
    ]


def test_loeschen_raeumt_protokoll_mit_ab(repos, db: Database):
    """ON DELETE CASCADE — no orphaned log."""
    auftrag = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    repos.auftraege.schritt_anlegen(auftrag.id, "status", "da")
    db.verbindung.execute("DELETE FROM auftraege WHERE id = ?", (auftrag.id,))
    zeile = db.verbindung.execute(
        "SELECT COUNT(*) AS anzahl FROM auftrag_schritte"
    ).fetchone()
    assert zeile["anzahl"] == 0


# --- Service startup -------------------------------------------------------


def test_beim_start_wird_laeuft_zu_unterbrochen(repos):
    laufend = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    repos.auftraege.generation_verknuepfen(laufend.id, "tot-nach-neustart")

    anzahl = repos.auftraege.beim_start_aufraeumen()

    assert anzahl == 1
    danach = repos.auftraege.holen(laufend.id)
    assert danach.zustand == "unterbrochen"
    assert danach.ende_grund == "dienst_neustart"
    assert danach.generation_id is None


def test_beim_start_bleibt_wartet_wartend(repos):
    """Decision 12: waiting runs keep waiting — only the dead reference goes."""
    wartend = repos.auftraege.erstellen(
        user_id="benutzer", agent="a", auftrag="x", zustand="wartet"
    )
    repos.auftraege.generation_verknuepfen(wartend.id, "tot-nach-neustart")

    anzahl = repos.auftraege.beim_start_aufraeumen()

    assert anzahl == 0
    danach = repos.auftraege.holen(wartend.id)
    assert danach.zustand == "wartet"
    assert danach.ende_grund is None
    assert danach.generation_id is None


def test_beim_start_bleiben_endzustaende_unberuehrt(repos):
    fertig = repos.auftraege.erstellen(user_id="benutzer", agent="a", auftrag="x")
    repos.auftraege.zustand_setzen(fertig.id, "fertig", ende_grund="fertig")

    repos.auftraege.beim_start_aufraeumen()

    assert repos.auftraege.holen(fertig.id).zustand == "fertig"


def test_dienststart_raeumt_wirklich_auf(config):
    """The lifecycle triggers the cleanup — verified through the real app."""
    from fastapi.testclient import TestClient

    from app.db import datenbank_oeffnen
    from app.main import app_erstellen

    db = datenbank_oeffnen(config)
    repos = repositories_erstellen(db)
    auftrag = repos.auftraege.erstellen(user_id="standard", agent="a", auftrag="x")
    db.schliessen()

    with TestClient(app_erstellen(config)) as client:
        state = client.app.state
        danach = state.repositories.auftraege.holen(auftrag.id)
        assert danach.zustand == "unterbrochen"
