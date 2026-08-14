"""The CLI module's one shell command.

It runs through the same runner the model uses — that is the whole point, and
the tests here are about the places where a second way in would have opened:
the shared folders, the block list, and the chat it belongs to.

The one deliberate difference: outside the shared folders the CLI refuses
instead of asking. A confirmation needs a running answer to hold the call
open, and the CLI has none.
"""

from __future__ import annotations


def _chat_mit_ordner(client, chat_id, ordner):
    client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(ordner)]})


def test_ein_befehl_laeuft_im_freigegebenen_ordner(client, chat_id, tmp_path):
    (tmp_path / "notiz.txt").write_text("hallo", encoding="utf-8")
    _chat_mit_ordner(client, chat_id, tmp_path)

    antwort = client.post(f"/api/v1/laeufe/{chat_id}/befehl", json={"command": "ls"})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["fehlgeschlagen"] is False
    assert "notiz.txt" in daten["text"]


def test_der_lauf_taucht_im_terminal_auf(client, chat_id, tmp_path):
    """Same runs list the terminal module reads — one channel, not two."""
    _chat_mit_ordner(client, chat_id, tmp_path)
    client.post(f"/api/v1/laeufe/{chat_id}/befehl", json={"command": "echo hallo"})

    laeufe = client.get(f"/api/v1/laeufe/{chat_id}").json()
    assert [l["befehl"] for l in laeufe] == ["echo hallo"]
    assert laeufe[0]["ausgabe"] == "hallo"


def test_ausserhalb_wird_abgelehnt_statt_gefragt(client, chat_id, tmp_path):
    _chat_mit_ordner(client, chat_id, tmp_path)
    antwort = client.post(f"/api/v1/laeufe/{chat_id}/befehl", json={"command": "ls /etc"})
    daten = antwort.json()
    assert daten["fehlgeschlagen"] is True
    assert "/etc" in daten["text"]


def test_die_sperrliste_gilt_auch_hier(client, chat_id, tmp_path):
    _chat_mit_ordner(client, chat_id, tmp_path)
    antwort = client.post(
        f"/api/v1/laeufe/{chat_id}/befehl", json={"command": "sudo rm etwas"}
    )
    assert antwort.json()["fehlgeschlagen"] is True


def test_ohne_freigegebenen_ordner_laeuft_nichts(client, chat_id):
    antwort = client.post(f"/api/v1/laeufe/{chat_id}/befehl", json={"command": "ls"})
    assert antwort.json()["fehlgeschlagen"] is True


def test_ein_fremder_chat_hat_keine_befehle(client, tmp_path):
    antwort = client.post("/api/v1/laeufe/gibtsnicht/befehl", json={"command": "ls"})
    assert antwort.status_code == 404
