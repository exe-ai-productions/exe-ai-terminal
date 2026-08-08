"""The tool form (A6): read, validate and write mcp_servers.json.

The registry restart itself runs in the background and needs real MCP
servers — that belongs to test_werkzeuge.py. Here is the form itself:
validation, round trip through the API, the placeholder traffic light.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.tools.registry import konfiguration_pruefen


@pytest.fixture(autouse=True)
def eigene_serverdatei(config):
    """The form writes into the test directory — never into the project's
    real file (the default path is relative to the project root!)."""
    config.mcp.servers_file = str(Path(config.app.data_dir) / "mcp_servers.json")

GUELTIG = json.dumps(
    {
        "mcpServers": {
            "searxng": {
                "type": "stdio",
                "command": ".venv/bin/python",
                "args": ["mcp/searxng_server.py"],
                "env": {"SEARXNG_URL": "http://127.0.0.1:8888"},
                "enabled": True,
                "allowed_tools": ["web_search"],
                "needs_confirmation": [],
            }
        }
    },
    indent=2,
)


# --- The validation --------------------------------------------------------


def test_gueltige_datei_besteht():
    assert konfiguration_pruefen(GUELTIG) is None


def test_kaputtes_json_wird_benannt():
    assert "JSON" in konfiguration_pruefen("{ kaputt")


def test_mcp_servers_muss_da_sein():
    assert "mcpServers" in konfiguration_pruefen("{}")


def test_unbekanntes_feld_faellt_auf():
    text = json.dumps({"mcpServers": {"x": {"command": "a", "comand_typo": "b"}}})
    meldung = konfiguration_pruefen(text)
    assert "x" in meldung and "comand_typo" in meldung


def test_falsche_typen_fallen_auf():
    text = json.dumps({"mcpServers": {"x": {"args": "kein-array"}}})
    assert "'args'" in konfiguration_pruefen(text)
    text = json.dumps({"mcpServers": {"x": {"enabled": "ja"}}})
    assert "'enabled'" in konfiguration_pruefen(text)
    text = json.dumps({"mcpServers": {"x": {"allowed_tools": [1]}}})
    assert "'allowed_tools'" in konfiguration_pruefen(text)


# --- The API ---------------------------------------------------------------


def test_lesen_ohne_datei_zeigt_das_geruest(client):
    daten = client.get("/api/v1/tools/config").json()
    assert daten["kaputt"] is None
    assert "mcpServers" in daten["content"]


def test_rundreise_sichern_und_lesen(config, client):
    antwort = client.put("/api/v1/tools/config", json={"content": GUELTIG})
    assert antwort.status_code == 200
    assert antwort.json()["kaputt"] is None

    daten = client.get("/api/v1/tools/config").json()
    assert daten["content"] == GUELTIG
    assert Path(config.pfad(config.mcp.servers_file)).read_text(encoding="utf-8") == GUELTIG


def test_kaputte_datei_wird_gesichert_aber_benannt(config, client):
    antwort = client.put("/api/v1/tools/config", json={"content": "{ kaputt"})
    assert antwort.status_code == 200
    assert "JSON" in antwort.json()["kaputt"]
    # It gets saved anyway — it is the user's file.
    assert Path(config.pfad(config.mcp.servers_file)).read_text(encoding="utf-8") == "{ kaputt"


def test_platzhalter_ampel(client, monkeypatch):
    monkeypatch.setenv("MASKE_TEST_GESETZT", "wert")
    monkeypatch.delenv("MASKE_TEST_FEHLT", raising=False)
    text = json.dumps(
        {
            "mcpServers": {
                "x": {
                    "command": "a",
                    "env": {
                        "EINS": "${MASKE_TEST_GESETZT}",
                        "ZWEI": "${MASKE_TEST_FEHLT}",
                    },
                }
            }
        }
    )
    antwort = client.put("/api/v1/tools/config", json={"content": text}).json()
    ampel = {p["name"]: p["gesetzt"] for p in antwort["platzhalter"]}
    assert ampel == {"MASKE_TEST_GESETZT": True, "MASKE_TEST_FEHLT": False}


def test_platzhalter_ampel_kennt_api_key_env(client, monkeypatch):
    """`api_key_env` points to the .env like ${…} — the traffic light shows both."""
    monkeypatch.setenv("MASKE_TEST_GESETZT", "wert")
    monkeypatch.delenv("MASKE_TEST_FEHLT", raising=False)
    text = json.dumps(
        {
            "mcpServers": {
                "gehostet": {
                    "type": "http",
                    "url": "https://beispiel.invalid/mcp",
                    "api_key_env": "MASKE_TEST_FEHLT",
                },
                "zweiter": {
                    "type": "http",
                    "url": "https://beispiel.invalid/mcp",
                    "api_key_env": "MASKE_TEST_GESETZT",
                },
            }
        }
    )
    antwort = client.put("/api/v1/tools/config", json={"content": text}).json()
    assert antwort["kaputt"] is None
    ampel = {p["name"]: p["gesetzt"] for p in antwort["platzhalter"]}
    assert ampel == {"MASKE_TEST_GESETZT": True, "MASKE_TEST_FEHLT": False}
