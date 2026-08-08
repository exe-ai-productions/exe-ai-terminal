"""The structured server routes of the tile gallery.

GET reads the entries including live state, PUT creates and makes targeted
changes, DELETE cleans up — all through mcp_servers.json as the single
source of truth that the raw text field uses too.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def eigene_serverdatei(config):
    """Never touch the project's real file."""
    config.mcp.servers_file = str(Path(config.app.data_dir) / "mcp_servers.json")


def _datei(config) -> dict:
    pfad = config.pfad(config.mcp.servers_file)
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_leere_welt_ist_eine_leere_liste(client):
    assert client.get("/api/v1/tools/servers").json() == []


def test_anlegen_und_lesen(client, config, monkeypatch):
    monkeypatch.setenv("GALERIE_TEST_TOKEN", "geheim")
    antwort = client.put(
        "/api/v1/tools/servers/github",
        json={
            "type": "http",
            "url": "https://beispiel.invalid/mcp",
            "api_key_env": "GALERIE_TEST_TOKEN",
            "enabled": True,
        },
    )
    assert antwort.status_code == 200
    assert antwort.json()["kaputt"] is None

    (eintrag,) = client.get("/api/v1/tools/servers").json()
    assert eintrag["name"] == "github"
    assert eintrag["type"] == "http"
    assert eintrag["enabled"] is True
    assert eintrag["schluessel_gesetzt"] is True
    assert eintrag["laeuft"] is False  # features.mcp is off in tests
    assert eintrag["alle_werkzeuge"] == []

    # The file is the same truth the text field sees.
    assert _datei(config)["mcpServers"]["github"]["url"] == "https://beispiel.invalid/mcp"


def test_gezieltes_aendern_laesst_den_rest_stehen(client, config):
    client.put(
        "/api/v1/tools/servers/recraft",
        json={"type": "http", "url": "https://beispiel.invalid/mcp", "enabled": True,
              "allowed_tools": ["bild_erzeugen"]},
    )
    antwort = client.put("/api/v1/tools/servers/recraft", json={"enabled": False})
    assert antwort.status_code == 200

    eintrag = _datei(config)["mcpServers"]["recraft"]
    assert eintrag["enabled"] is False
    assert eintrag["url"] == "https://beispiel.invalid/mcp"
    assert eintrag["allowed_tools"] == ["bild_erzeugen"]


def test_null_loescht_die_positivliste(client, config):
    client.put(
        "/api/v1/tools/servers/recraft",
        json={"type": "http", "url": "https://beispiel.invalid/mcp",
              "allowed_tools": ["eins"]},
    )
    client.put("/api/v1/tools/servers/recraft", json={"allowed_tools": None})
    assert "allowed_tools" not in _datei(config)["mcpServers"]["recraft"]


def test_kaputtes_wird_nicht_geschrieben(client, config):
    antwort = client.put("/api/v1/tools/servers/kaputt", json={"type": "http"})
    assert antwort.status_code == 400
    assert "url" in antwort.json()["detail"]
    assert not config.pfad(config.mcp.servers_file).exists()


def test_fehlender_schluessel_zeigt_rot(client, monkeypatch):
    monkeypatch.delenv("GALERIE_TEST_TOKEN", raising=False)
    client.put(
        "/api/v1/tools/servers/github",
        json={"type": "http", "url": "https://beispiel.invalid/mcp",
              "api_key_env": "GALERIE_TEST_TOKEN"},
    )
    (eintrag,) = client.get("/api/v1/tools/servers").json()
    assert eintrag["schluessel_gesetzt"] is False


def test_entfernen_samt_zugang(client, config):
    client.put(
        "/api/v1/tools/servers/recraft",
        json={"type": "http", "url": "https://beispiel.invalid/mcp"},
    )
    # A remembered credential must disappear along with the entry.
    client.app.state.mcp_oauth.speicher.setzen("recraft", access_token="zugang-1")

    antwort = client.delete("/api/v1/tools/servers/recraft")
    assert antwort.status_code == 204
    assert _datei(config)["mcpServers"] == {}
    assert client.app.state.mcp_oauth.speicher.eintrag("recraft") is None


def test_entfernen_ohne_eintrag_ist_404(client):
    assert client.delete("/api/v1/tools/servers/nie-da").status_code == 404
