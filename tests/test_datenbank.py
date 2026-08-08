"""Database and repositories."""

from __future__ import annotations

import pytest

from app.db import Database, repositories_erstellen
from app.db.connection import SCHEMA_VERSION


def test_schema_wird_angelegt(db: Database):
    tabellen = {
        zeile["name"]
        for zeile in db.verbindung.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"chats", "messages", "documents", "schema_version"} <= tabellen
    assert db.schema_version() == SCHEMA_VERSION


def test_schema_einrichten_ist_wiederholbar(db: Database):
    db.schema_einrichten()
    db.schema_einrichten()
    anzahl = db.verbindung.execute("SELECT COUNT(*) AS n FROM schema_version").fetchone()["n"]
    assert anzahl == 1


# --- Chats ---------------------------------------------------------------


def test_chat_erstellen_und_holen(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Erster Chat")
    geholt = repos.chats.holen(chat.id)
    assert geholt is not None
    assert geholt.title == "Erster Chat"
    assert geholt.user_id == "benutzer"


def test_chat_gehoert_zum_benutzer(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Meiner")
    assert repos.chats.holen(chat.id, user_id="benutzer") is not None
    assert repos.chats.holen(chat.id, user_id="jemand_anderes") is None


def test_chats_auflisten_neueste_zuerst(repos):
    """Even with identical timestamps, the ordering must be deterministic."""
    alt = repos.chats.erstellen(user_id="benutzer", title="Alt")
    neu = repos.chats.erstellen(user_id="benutzer", title="Neu")

    liste = repos.chats.auflisten(user_id="benutzer")
    assert [chat.id for chat in liste] == [neu.id, alt.id]

    # The older chat gets touched and must move to the top as a result.
    repos.chats.zeitstempel_auffrischen(alt.id)
    liste = repos.chats.auflisten(user_id="benutzer")
    assert [chat.id for chat in liste][0] == alt.id


def test_chats_suchen_filtert_titel(repos):
    repos.chats.erstellen(user_id="benutzer", title="Netzwerk-Probleme")
    repos.chats.erstellen(user_id="benutzer", title="Kochrezepte")

    treffer = repos.chats.auflisten(user_id="benutzer", suche="Netzwerk")
    assert len(treffer) == 1
    assert treffer[0].title == "Netzwerk-Probleme"


def test_chat_parameter_aktualisieren(repos):
    """Parameters left the chat row — they live in the settings cascade."""
    chat = repos.chats.erstellen(user_id="benutzer", title="Test")
    repos.einstellungen.setzen(f"chat:{chat.id}", "parameter", {"top_k": 30})
    assert repos.einstellungen.holen(f"chat:{chat.id}", "parameter") == {"top_k": 30}

def test_unbekanntes_feld_wird_abgewiesen(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Test")
    with pytest.raises(ValueError):
        repos.chats.aktualisieren(chat.id, geheimnis="hallo")


def test_chat_loeschen(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Weg damit")
    assert repos.chats.loeschen(chat.id) is True
    assert repos.chats.holen(chat.id) is None
    assert repos.chats.loeschen(chat.id) is False


# --- Messages --------------------------------------------------------------


def test_nachricht_speichern_und_auflisten(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    repos.messages.speichern(chat_id=chat.id, role="user", content="Hallo")
    repos.messages.speichern(
        chat_id=chat.id,
        role="assistant",
        content="Guten Tag",
        reasoning="Kurz überlegt",
        stats={"tokens_pro_sekunde": 12.4, "tokens": 3},
    )

    nachrichten = repos.messages.auflisten(chat_id=chat.id)
    assert [n.role for n in nachrichten] == ["user", "assistant"]
    assert nachrichten[1].reasoning == "Kurz überlegt"
    assert nachrichten[1].stats["tokens_pro_sekunde"] == 12.4


def test_stats_ueberleben_die_datenbank(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    nachricht = repos.messages.speichern(
        chat_id=chat.id, role="assistant", content="x", stats={"dauer_sekunden": 1.5}
    )
    geholt = repos.messages.holen(nachricht.id)
    assert geholt.stats == {"dauer_sekunden": 1.5}


def test_nachricht_ohne_stats_hat_leeres_dict(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    nachricht = repos.messages.speichern(chat_id=chat.id, role="user", content="x")
    assert repos.messages.holen(nachricht.id).stats == {}


def test_ungueltige_rolle_wird_abgewiesen(repos):
    import sqlite3

    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    with pytest.raises(sqlite3.IntegrityError):
        repos.messages.speichern(chat_id=chat.id, role="hausmeister", content="x")


def test_nachricht_nachtraeglich_fuellen(repos):
    """During streaming, an empty placeholder is created first."""
    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    platzhalter = repos.messages.speichern(chat_id=chat.id, role="assistant", content="")
    gefuellt = repos.messages.inhalt_aktualisieren(
        platzhalter.id, content="Fertige Antwort", reasoning="…", stats={"tokens": 42}
    )
    assert gefuellt.content == "Fertige Antwort"
    assert gefuellt.stats["tokens"] == 42


def test_letzte_nachricht_je_rolle(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    repos.messages.speichern(chat_id=chat.id, role="user", content="erste")
    repos.messages.speichern(chat_id=chat.id, role="assistant", content="antwort")
    repos.messages.speichern(chat_id=chat.id, role="user", content="zweite")

    assert repos.messages.letzte(chat_id=chat.id).content == "zweite"
    assert repos.messages.letzte(chat_id=chat.id, role="assistant").content == "antwort"


def test_chat_loeschen_raeumt_nachrichten_mit_ab(repos):
    """ON DELETE CASCADE — otherwise orphans linger in the database."""
    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    repos.messages.speichern(chat_id=chat.id, role="user", content="Hallo")
    repos.documents.speichern(chat_id=chat.id, filename="brief.pdf")

    repos.chats.loeschen(chat.id)

    assert repos.messages.auflisten(chat_id=chat.id) == []
    assert repos.documents.auflisten(chat_id=chat.id) == []


def test_nachricht_ohne_chat_wird_abgewiesen(repos):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        repos.messages.speichern(chat_id="gibtsnicht", role="user", content="x")


# --- Documents -------------------------------------------------------------


def test_dokument_speichern_und_auflisten(repos):
    chat = repos.chats.erstellen(user_id="benutzer", title="Chat")
    dokument = repos.documents.speichern(
        chat_id=chat.id,
        filename="handbuch.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        extracted_text="Inhalt des Handbuchs",
    )
    liste = repos.documents.auflisten(chat_id=chat.id)
    assert len(liste) == 1
    assert liste[0].id == dokument.id
    assert liste[0].extracted_text == "Inhalt des Handbuchs"


# --- Transactions ------------------------------------------------------------


def test_transaktion_rollt_bei_fehler_zurueck(db: Database):
    repos = repositories_erstellen(db)
    vorher = repos.chats.anzahl(user_id="benutzer")

    with pytest.raises(RuntimeError):
        with db.transaktion():
            repos.chats.erstellen(user_id="benutzer", title="Wird verworfen")
            raise RuntimeError("Abbruch")

    assert repos.chats.anzahl(user_id="benutzer") == vorher
