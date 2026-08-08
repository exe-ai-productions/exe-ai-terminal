"""Endpoint discovery and provider abstraction (phase 1.4 + 1.5)."""

from __future__ import annotations

import pytest

from app.config import Config
from app.discovery import Discovery
from app.events import Ereignisse, EventBus
from app.providers import (
    MockProvider,
    ProviderFehler,
    bekannte_provider,
    mock_endpunkt,
    provider_bauen,
    provider_registrieren,
)


# --- Registry ------------------------------------------------------------


def test_bekannte_provider_enthalten_openai_und_mock():
    assert {"openai_compatible", "mock"} <= set(bekannte_provider())


def test_unbekannter_provider_meldet_sich_deutlich():
    endpunkt = mock_endpunkt("x")
    endpunkt = endpunkt.model_copy(update={"provider": "gibtsnicht"})
    with pytest.raises(ProviderFehler) as fehler:
        provider_bauen(endpunkt)
    assert "gibtsnicht" in str(fehler.value)


def test_neuer_provider_laesst_sich_nachtragen():
    """A new provider is one file plus one entry — no rebuild."""

    class EigenerProvider(MockProvider):
        pass

    provider_registrieren("eigener", EigenerProvider)
    endpunkt = mock_endpunkt("y").model_copy(update={"provider": "eigener"})
    assert isinstance(provider_bauen(endpunkt), EigenerProvider)


def test_faehigkeiten_kommen_aus_der_konfiguration():
    endpunkt = mock_endpunkt("z")
    provider = provider_bauen(endpunkt)
    assert provider.faehigkeiten["streaming"] is True
    # thinking arrived with the thinking switch (interface milestone A):
    # None in the config means "discovery detects it natively".
    assert set(provider.faehigkeiten) == {"streaming", "tool_calls", "vision", "thinking"}
    assert provider.faehigkeiten["thinking"] is None


# --- Discovery -----------------------------------------------------------


@pytest.fixture
def discovery(config: Config) -> Discovery:
    return Discovery(config, EventBus())


@pytest.mark.asyncio
async def test_erreichbarkeit_wird_geprueft(discovery: Discovery):
    await discovery.einmal_pruefen()
    erreichbar = {zustand.endpunkt.id for zustand in discovery.erreichbare()}
    # The dummy answers, the real endpoint on port 9 does not.
    assert erreichbar == {"test"}


@pytest.mark.asyncio
async def test_abgeschaltete_endpunkte_kommen_gar_nicht_vor(config: Config):
    config.endpoints[0].enabled = False
    discovery = Discovery(config, EventBus())
    assert "test" not in discovery.zustaende


@pytest.mark.asyncio
async def test_zustandswechsel_loest_ereignis_aus(config: Config):
    bus = EventBus()
    meldungen = []
    bus.abonnieren(
        Ereignisse.ENDPUNKT_STATUS_GEAENDERT,
        lambda **daten: meldungen.append(daten),
    )
    discovery = Discovery(config, bus)

    await discovery.einmal_pruefen()
    assert {"endpoint_id": "test", "erreichbar": True} in meldungen

    # Second pass with no change: no new notification.
    vorher = len(meldungen)
    await discovery.einmal_pruefen()
    assert len(meldungen) == vorher

    # Now the dummy goes down — and stays reachable at first. One silence is
    # not an outage: a provider whose model list hangs every other request
    # would otherwise make its models appear and vanish while you look at them.
    discovery.zustaende["test"].provider = MockProvider(ist_erreichbar=False)
    await discovery.einmal_pruefen()
    assert discovery.zustaende["test"].erreichbar, "ein Aussetzer wirft noch nicht raus"
    assert {"endpoint_id": "test", "erreichbar": False} not in meldungen

    # Only when the silence repeats does it count.
    await discovery.einmal_pruefen()
    await discovery.einmal_pruefen()
    assert {"endpoint_id": "test", "erreichbar": False} in meldungen


async def test_wer_nie_geantwortet_hat_gilt_nicht_als_erreichbar(config: Config):
    """The tolerance is for outages, not for endpoints that were never there.

    Without this an unconfigured provider would show up in the picker for its
    first three checks — a model you cannot talk to.
    """
    discovery = Discovery(config, EventBus())
    for zustand in discovery.zustaende.values():
        zustand.provider = MockProvider(ist_erreichbar=False)

    await discovery.einmal_pruefen()
    assert not any(z.erreichbar for z in discovery.zustaende.values())


@pytest.mark.asyncio
async def test_ein_kaputter_endpunkt_reisst_die_pruefung_nicht_mit(discovery: Discovery):
    class KaputterProvider(MockProvider):
        async def erreichbar(self, timeout: float = 3.0) -> bool:
            raise RuntimeError("Netzwerk brennt")

    discovery.zustaende["test"].provider = KaputterProvider()
    await discovery.einmal_pruefen()

    assert discovery.zustaende["test"].erreichbar is False
    assert "Netzwerk brennt" in discovery.zustaende["test"].letzter_fehler


@pytest.mark.asyncio
async def test_starten_und_stoppen_hinterlaesst_keine_aufgabe(discovery: Discovery):
    await discovery.starten()
    assert discovery._aufgabe is not None
    await discovery.stoppen()
    assert discovery._aufgabe is None


# --- /api/v1/models ------------------------------------------------------


def test_models_liefert_nur_erreichbare(client):
    daten = client.get("/api/v1/models").json()
    assert [eintrag["id"] for eintrag in daten] == ["test"]
    assert daten[0]["capabilities"]["streaming"] is True
    assert daten[0]["reasoning_format"] == "think"


def test_models_mit_alle_zeigt_auch_die_abwesenden(client):
    daten = client.get("/api/v1/models", params={"alle": True}).json()
    kennungen = {eintrag["id"]: eintrag["erreichbar"] for eintrag in daten}
    assert kennungen == {"test": True, "abwesend": False}


def test_models_kann_frisch_pruefen(client):
    daten = client.get("/api/v1/models", params={"jetzt_pruefen": True}).json()
    assert daten[0]["zuletzt_geprueft"] is not None


# --- Arriving and leaving at runtime --------------------------------------


@pytest.mark.asyncio
async def test_ein_endpunkt_kann_im_lauf_ankommen(config: Config):
    """What the window just added must not wait for a restart."""
    discovery = Discovery(config, EventBus())
    await discovery.anmelden(mock_endpunkt("spaeter"))
    assert "spaeter" in discovery.zustaende
    # The check ran right away — whoever added it is looking at the list.
    assert discovery.zustaende["spaeter"].erreichbar


@pytest.mark.asyncio
async def test_dieselbe_kennung_ersetzt_statt_zu_doppeln(config: Config):
    discovery = Discovery(config, EventBus())
    await discovery.anmelden(mock_endpunkt("runner"))
    erster = discovery.zustaende["runner"]
    await discovery.anmelden(mock_endpunkt("runner"))
    assert discovery.zustaende["runner"] is not erster
    assert sum(1 for kennung in discovery.zustaende if kennung == "runner") == 1


@pytest.mark.asyncio
async def test_abmelden_sagt_bescheid(config: Config):
    bus = EventBus()
    meldungen = []
    bus.abonnieren(
        Ereignisse.ENDPUNKT_STATUS_GEAENDERT,
        lambda **daten: meldungen.append(daten),
    )
    discovery = Discovery(config, bus)
    await discovery.anmelden(mock_endpunkt("kurz"))
    await discovery.abmelden("kurz")
    assert "kurz" not in discovery.zustaende
    assert {"endpoint_id": "kurz", "erreichbar": False} in meldungen


@pytest.mark.asyncio
async def test_abmelden_von_niemandem_ist_still(config: Config):
    discovery = Discovery(config, EventBus())
    await discovery.abmelden("gibtsnicht")
