"""Putting a file from the chat into a working folder.

The interesting part is not that saving works — it is everywhere it must
refuse. A name that is secretly a path, a folder nobody released, a chat
with no folder at all.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def chat_mit_ordner(client, tmp_path):
    """A chat that has released exactly one folder."""
    chat_id = client.post("/api/v1/chats", json={"title": "Ablage"}).json()["id"]
    client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(tmp_path)]})
    return chat_id


def ablegen(client, chat_id, name, inhalt="hallo", **rest):
    return client.post(
        "/api/v1/outputs",
        json={"chat_id": chat_id, "name": name, "inhalt": inhalt, **rest},
    )


# --- The normal case ------------------------------------------------------


def test_datei_landet_im_freigegebenen_ordner(client, chat_mit_ordner, tmp_path):
    antwort = ablegen(client, chat_mit_ordner, "bericht.html", "<h1>da</h1>")
    assert antwort.status_code == 200

    ziel = tmp_path / "bericht.html"
    assert ziel.read_text(encoding="utf-8") == "<h1>da</h1>"
    assert antwort.json()["pfad"] == str(ziel.resolve())


def test_gleicher_name_wird_ueberschrieben(client, chat_mit_ordner, tmp_path):
    ablegen(client, chat_mit_ordner, "notiz.md", "erste")
    ablegen(client, chat_mit_ordner, "notiz.md", "zweite")
    assert (tmp_path / "notiz.md").read_text(encoding="utf-8") == "zweite"


# --- Where it has to refuse -----------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "../draussen.txt",
        "unter/ordner.txt",
        "..\\windows.txt",
        ".versteckt.txt",
    ],
)
def test_ein_name_ist_nie_ein_pfad(client, chat_mit_ordner, name):
    assert ablegen(client, chat_mit_ordner, name).status_code == 400


@pytest.mark.parametrize("name", ["start.command", "programm.exe", "lauf.bat", "app.desktop"])
def test_startbare_dateien_werden_abgelehnt(client, chat_mit_ordner, name):
    assert ablegen(client, chat_mit_ordner, name).status_code == 415


def test_ohne_freigegebenen_ordner_geht_nichts(client):
    chat_id = client.post("/api/v1/chats", json={"title": "Ohne"}).json()["id"]
    assert ablegen(client, chat_id, "datei.txt").status_code == 409


def test_fremder_ordner_wird_abgelehnt(client, chat_mit_ordner, tmp_path):
    fremd = tmp_path.parent / "woanders"
    fremd.mkdir(exist_ok=True)
    antwort = ablegen(client, chat_mit_ordner, "datei.txt", ordner=str(fremd))
    assert antwort.status_code == 403
    assert not (fremd / "datei.txt").exists()


def test_unbekannter_chat_ist_ein_vierhundertvier(client):
    assert ablegen(client, "gibtsnicht", "datei.txt").status_code == 404
