"""Showing a working folder in the file manager.

The route exists to be refused: what matters is not that it opens a folder
but that it opens no other one. A path the chat never shared is turned down
even when it exists, and the opening itself is only reached after that
check — which is why it is patched away here.
"""

from __future__ import annotations

from pathlib import Path


def test_ein_freigegebener_ordner_wird_geoeffnet(client, chat_id, tmp_path, monkeypatch):
    geoeffnet: list[Path] = []
    monkeypatch.setattr(
        "app.api.v1.arbeitsordner.ordner_oeffnen", lambda pfad: geoeffnet.append(pfad)
    )
    client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(tmp_path)]})

    antwort = client.post(
        "/api/v1/ordner/oeffnen",
        json={"chat_id": chat_id, "pfad": str(tmp_path.resolve())},
    )
    assert antwort.status_code == 200
    assert geoeffnet == [tmp_path.resolve()]


def test_ein_fremder_ordner_wird_abgewiesen(client, chat_id, tmp_path, monkeypatch):
    geoeffnet: list[Path] = []
    monkeypatch.setattr(
        "app.api.v1.arbeitsordner.ordner_oeffnen", lambda pfad: geoeffnet.append(pfad)
    )
    client.patch(f"/api/v1/chats/{chat_id}", json={"working_dirs": [str(tmp_path)]})

    antwort = client.post(
        "/api/v1/ordner/oeffnen", json={"chat_id": chat_id, "pfad": "/etc"}
    )
    assert antwort.status_code == 403
    assert geoeffnet == []


def test_ohne_chat_gibt_es_nichts_zu_zeigen(client, tmp_path):
    antwort = client.post(
        "/api/v1/ordner/oeffnen", json={"chat_id": "gibtsnicht", "pfad": str(tmp_path)}
    )
    assert antwort.status_code == 404
