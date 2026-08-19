"""API endpoints from phase 1."""

from __future__ import annotations

from app import __version__
from app.i18n import STANDARDSPRACHE


def test_health_unversioniert(client):
    """Fixed address for Uptime Kuma and systemd — must never change."""
    antwort = client.get("/health")
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["status"] == "ok"
    assert daten["version"] == __version__
    assert daten["datenbank"]["erreichbar"] is True


def test_health_unter_api_v1(client):
    antwort = client.get("/api/v1/health")
    assert antwort.status_code == 200
    assert antwort.json()["status"] == "ok"


def test_alle_api_routen_liegen_unter_v1(client):
    pfade = [
        route.path
        for route in client.app.routes
        if getattr(route, "path", "").startswith("/api")
    ]
    assert pfade, "Es muss API-Routen geben"
    assert all(pfad.startswith("/api/v1/") for pfad in pfade), pfade


def test_meta_liefert_feature_flags(client):
    daten = client.get("/api/v1/meta").json()
    assert daten["name"] == "Exe AI Terminal"
    # beta_lock is the switch that locks the writable settings.
    # The frontend reads it from here.
    assert set(daten["features"]) == {
        "mcp",
        "document_upload",
        "beta_lock",
        "shell_tool",
    }
    assert daten["verfuegbare_sprachen"] == ["de", "en"]


def test_meta_folgt_dem_sprachwunsch(client):
    deutsch = client.get("/api/v1/meta", headers={"Accept-Language": "de-DE,de;q=0.9"})
    englisch = client.get("/api/v1/meta", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert deutsch.json()["sprache"] == "de"
    assert englisch.json()["sprache"] == "en"


def test_unbekannte_sprache_faellt_auf_konfiguration_zurueck(client):
    antwort = client.get("/api/v1/meta", headers={"Accept-Language": "fr-FR"})
    assert antwort.json()["sprache"] == "de"


def test_uebersetzungskatalog_wird_ausgeliefert(client):
    daten = client.get("/api/v1/translations/en").json()
    assert daten["sprache"] == "en"
    assert daten["texte"]["chat"]["neu"] == "New chat"


def test_unbekannte_sprache_liefert_standardkatalog(client):
    """Don't check against "de": which language is the default is a
    decision and may change. What matters is the fallback itself."""
    daten = client.get("/api/v1/translations/klingonisch").json()
    assert daten["sprache"] == STANDARDSPRACHE


def test_pwa_manifest_wird_ausgeliefert(client):
    antwort = client.get("/manifest.webmanifest")
    assert antwort.status_code == 200
    assert antwort.json()["short_name"] == "Exe AI"


def test_statische_dateien_werden_ausgeliefert(client):
    antwort = client.get("/")
    assert antwort.status_code == 200
    assert "Exe AI Terminal" in antwort.text


def test_openapi_ist_erreichbar(client):
    assert client.get("/openapi.json").status_code == 200
