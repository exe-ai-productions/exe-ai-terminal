"""Adding a cloud provider from the window, end to end.

The window's whole promise is "key in, models appear". What the endpoint
must leave behind is checked here: the entry in config.yaml, the key in
.env and in the running environment, and — without any restart — the
candidate in discovery. The last one is the difference between a window
and a dead end.
"""

from __future__ import annotations

import os

import pytest
import yaml

from app import paketierung


@pytest.fixture
def eigener_ordner(tmp_path, monkeypatch):
    """Redirects the user folder, so no test writes the project's own
    config.yaml or .env."""
    monkeypatch.setattr(paketierung, "daten", lambda: tmp_path)
    (tmp_path / "config.yaml").write_text("endpoints: []\n", encoding="utf-8")
    # Whatever the endpoint puts into the environment is rolled back by
    # monkeypatch, because the name is registered here first.
    monkeypatch.setenv("EIGENE_API_KEY", "vorher")
    return tmp_path


def test_ein_anbieter_erscheint_ohne_neustart(client, eigener_ordner):
    antwort = client.post(
        "/api/v1/providers",
        json={
            "art": "eigen",
            "kennung": "eigene",
            "url": "http://127.0.0.1:9/v1",
            "schluessel": "sk-test-1234",
        },
    )
    assert antwort.status_code == 200
    assert antwort.json() == {"id": "eigene", "api_key_env": "EIGENE_API_KEY"}

    # The candidate is there while the window is still open.
    zustand = client.app.state.discovery.zustaende.get("eigene")
    assert zustand is not None
    assert zustand.endpunkt.group == "cloud"

    # The running service can use the key at once; the file serves the next
    # start.
    assert os.environ["EIGENE_API_KEY"] == "sk-test-1234"
    assert "EIGENE_API_KEY=sk-test-1234" in (eigener_ordner / ".env").read_text()

    gespeichert = yaml.safe_load((eigener_ordner / "config.yaml").read_text())
    assert gespeichert["endpoints"][0]["id"] == "eigene"


def test_dieselbe_kennung_gibt_es_nur_einmal(client, eigener_ordner):
    daten = {
        "art": "eigen",
        "kennung": "doppelt",
        "url": "http://127.0.0.1:9/v1",
        "schluessel": "sk-test-1234",
    }
    assert client.post("/api/v1/providers", json=daten).status_code == 200
    assert client.post("/api/v1/providers", json=daten).status_code == 409


def test_ein_bekannter_anbieter_braucht_keine_adresse(client, eigener_ordner, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "vorher")
    antwort = client.post(
        "/api/v1/providers",
        json={"art": "anthropic", "schluessel": "sk-ant-test-1234"},
    )
    assert antwort.status_code == 200
    zustand = client.app.state.discovery.zustaende.get("anthropic")
    assert zustand is not None
    assert zustand.endpunkt.base_url == "https://api.anthropic.com/v1"
