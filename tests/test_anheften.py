"""Pinning and emoji in titles.

Both are promises to the user that can easily break unnoticed —
hence pinned down here.
"""

from __future__ import annotations

import sqlite3

from app.db import Database, repositories_erstellen
from app.db.connection import MIGRATIONEN, SCHEMA_VERSION


# --- Pinning -------------------------------------------------------------


def test_neuer_chat_ist_nicht_angeheftet(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Neu")
    assert chat.pinned is False
    assert repos.chats.holen(chat.id).pinned is False


def test_angehefteter_chat_steht_oben(repos):
    alt = repos.chats.erstellen(user_id="benutzer", title="Alt")
    repos.chats.erstellen(user_id="benutzer", title="Neuer")
    repos.chats.erstellen(user_id="benutzer", title="Neuester")

    repos.chats.anheften(alt.id)

    liste = repos.chats.auflisten(user_id="benutzer")
    assert liste[0].id == alt.id
    assert liste[0].pinned is True


def test_mehrere_angeheftete_bleiben_untereinander_sortiert(repos):
    erster = repos.chats.erstellen(user_id="benutzer", title="Erster")
    zweiter = repos.chats.erstellen(user_id="benutzer", title="Zweiter")
    repos.chats.erstellen(user_id="benutzer", title="Ohne Nadel")

    repos.chats.anheften(erster.id)
    repos.chats.anheften(zweiter.id)

    liste = repos.chats.auflisten(user_id="benutzer")
    assert [c.pinned for c in liste] == [True, True, False]
    # Among the pinned chats, most recently used still comes first.
    assert liste[0].id == zweiter.id


def test_loesen_stellt_die_alte_reihenfolge_wieder_her(repos):
    alt = repos.chats.erstellen(user_id="benutzer", title="Alt")
    neu = repos.chats.erstellen(user_id="benutzer", title="Neu")

    repos.chats.anheften(alt.id)
    assert repos.chats.auflisten(user_id="benutzer")[0].id == alt.id

    repos.chats.anheften(alt.id, False)
    assert repos.chats.auflisten(user_id="benutzer")[0].id == neu.id


def test_anheften_gilt_nicht_als_benutzung(repos):
    """Otherwise the chat jumps to the wrong spot when unpinned."""
    chat = repos.chats.erstellen(user_id="benutzer", title="Test")
    vorher = repos.chats.holen(chat.id).updated_at

    repos.chats.anheften(chat.id)
    assert repos.chats.holen(chat.id).updated_at == vorher

    repos.chats.anheften(chat.id, False)
    assert repos.chats.holen(chat.id).updated_at == vorher


def test_suche_beachtet_die_anheftung_ebenfalls(repos):
    treffer_alt = repos.chats.erstellen(user_id="benutzer", title="Netzwerk alt")
    repos.chats.erstellen(user_id="benutzer", title="Netzwerk neu")
    repos.chats.anheften(treffer_alt.id)

    liste = repos.chats.auflisten(user_id="benutzer", suche="Netzwerk")
    assert liste[0].id == treffer_alt.id


# --- Via the API ---------------------------------------------------------


def test_anheften_ueber_die_api(client):
    alt = client.post("/api/v1/chats", json={"title": "Alt"}).json()["id"]
    client.post("/api/v1/chats", json={"title": "Neu"})

    antwort = client.patch(f"/api/v1/chats/{alt}", json={"pinned": True})
    assert antwort.status_code == 200
    assert antwort.json()["pinned"] is True

    liste = client.get("/api/v1/chats").json()
    assert liste[0]["id"] == alt


def test_anheften_und_umbenennen_in_einem_zug(client):
    chat = client.post("/api/v1/chats", json={"title": "Alt"}).json()["id"]
    antwort = client.patch(
        f"/api/v1/chats/{chat}", json={"pinned": True, "title": "📌 Wichtig"}
    ).json()
    assert antwort["pinned"] is True
    assert antwort["title"] == "📌 Wichtig"


def test_loesen_ueber_die_api(client):
    chat = client.post("/api/v1/chats", json={"title": "Test"}).json()["id"]
    client.patch(f"/api/v1/chats/{chat}", json={"pinned": True})
    antwort = client.patch(f"/api/v1/chats/{chat}", json={"pinned": False})
    assert antwort.json()["pinned"] is False


# --- Emoji in titles -----------------------------------------------------


def test_emoji_im_titel_ueberlebt_die_datenbank(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="📁 Netzwerk")
    assert repos.chats.holen(chat.id).title == "📁 Netzwerk"


def test_zusammengesetztes_emoji_bleibt_heil(repos):
    """The family emoji consists of four characters plus invisible joiners."""
    titel = "👨‍👩‍👧‍👦 Familie"
    chat = repos.chats.erstellen(user_id="benutzer", title=titel)
    geholt = repos.chats.holen(chat.id)
    assert geholt.title == titel
    assert len(geholt.title) == len(titel)


def test_suche_findet_ein_emoji(repos):
    repos.chats.erstellen(user_id="benutzer", title="🦊 Fuchs")
    repos.chats.erstellen(user_id="benutzer", title="Ohne Bild")
    treffer = repos.chats.auflisten(user_id="benutzer", suche="🦊")
    assert len(treffer) == 1


def test_emoji_ueber_die_api(client):
    angelegt = client.post("/api/v1/chats", json={"title": "🚀 Rakete"}).json()
    assert angelegt["title"] == "🚀 Rakete"
    assert client.get(f"/api/v1/chats/{angelegt['id']}").json()["title"] == "🚀 Rakete"


# --- Migration -----------------------------------------------------------


def test_bestehende_datenbank_wird_nachgezogen(tmp_path):
    """A database on the old schema must not break at startup."""
    pfad = tmp_path / "alt.db"
    alt = sqlite3.connect(pfad)
    alt.executescript(
        """
        CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT NOT NULL);
        CREATE TABLE chats (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
            -- Deliberately the old state: this table replicates a
            -- database at schema version 1. The column existed back
            -- then; migration 4 removes it again.
            system_prompt TEXT, endpoint_id TEXT, temperature REAL, top_p REAL,
            max_tokens INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        -- messages also existed in version 1 — migration 6 adds the
        -- image column there and needs the table.
        CREATE TABLE messages (
            id TEXT NOT NULL PRIMARY KEY, chat_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, reasoning TEXT,
            stats_json TEXT, created_at TEXT NOT NULL
        );
        -- documents has also been around since version 1 (phase 1
        -- foundation) — migration 7 adds pages/truncated.
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, chat_id TEXT NOT NULL,
            filename TEXT NOT NULL, mime_type TEXT, size_bytes INTEGER,
            extracted_text TEXT, created_at TEXT NOT NULL
        );
        INSERT INTO schema_version VALUES (1, '2020-01-02T00:00:00+00:00');
        INSERT INTO chats (id, user_id, title, created_at, updated_at)
        VALUES ('alt1', 'benutzer', 'Alter Chat', '2020-01-01T10:00:00+00:00',
                '2020-01-01T10:00:00+00:00');
        """
    )
    alt.commit()
    alt.close()

    db = Database(pfad)
    db.schema_einrichten()
    repos = repositories_erstellen(db)

    # The old chat is still there and has the new column with its default.
    chat = repos.chats.holen("alt1")
    assert chat is not None
    assert chat.title == "Alter Chat"
    assert chat.pinned is False
    assert db.schema_version() == SCHEMA_VERSION

    # And it can be pinned.
    assert repos.chats.anheften("alt1").pinned is True
    db.schliessen()


def test_migration_laeuft_nicht_doppelt(tmp_path):
    pfad = tmp_path / "wiederholt.db"
    for _ in range(3):
        db = Database(pfad)
        db.schema_einrichten()
        db.schliessen()

    db = Database(pfad)
    anzahl = db.verbindung.execute(
        "SELECT COUNT(*) AS n FROM schema_version"
    ).fetchone()["n"]
    assert anzahl == 1
    db.schliessen()


def test_migrationsliste_ist_aufsteigend_und_passt_zur_version():
    versionen = [version for version, _ in MIGRATIONEN]
    assert versionen == sorted(versionen)
    assert max(versionen) <= SCHEMA_VERSION
