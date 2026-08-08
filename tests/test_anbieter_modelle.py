"""One provider, many models.

An endpoint used to be one model. Now it is the provider, and the models it
offers are asked of it. These tests pin down what must not break in the
process — above all: an id stored before the split still has to work.
"""

from __future__ import annotations

import pytest

from app import modellkennung
from app.config import Config
from app.discovery import Discovery
from app.events import EventBus
from app.providers import MockProvider


# --- The id ---------------------------------------------------------------


def test_ohne_modell_bleibt_die_kennung_der_anbieter():
    assert modellkennung.bauen("mana", None) == "mana"
    assert modellkennung.zerlegen("mana") == ("mana", None)


def test_mit_modell_stehen_beide_in_der_kennung():
    assert modellkennung.bauen("openai", "gpt-5.5") == "openai:gpt-5.5"
    assert modellkennung.zerlegen("openai:gpt-5.5") == ("openai", "gpt-5.5")


def test_ein_doppelpunkt_im_modellnamen_bleibt_erhalten():
    """Split at the FIRST colon — endpoint ids never carry one, model names may."""
    assert modellkennung.zerlegen("x:a:b") == ("x", "a:b")


# --- The fan-out ----------------------------------------------------------


@pytest.fixture
def discovery(config: Config) -> Discovery:
    return Discovery(config, EventBus())


@pytest.mark.asyncio
async def test_ein_anbieter_mit_katalog_erscheint_je_modell(discovery: Discovery):
    discovery.zustaende["test"].provider = MockProvider(
        modelle=["gpt-5.5", "gpt-5.4-mini"]
    )
    await discovery.einmal_pruefen()

    kennungen = [
        modellkennung.bauen(zustand.endpunkt.id, modell)
        for zustand, modell in discovery.aufgefaechert(discovery.erreichbare())
    ]
    assert kennungen == ["test:gpt-5.5", "test:gpt-5.4-mini"]


@pytest.mark.asyncio
async def test_ein_anbieter_ohne_katalog_steht_fuer_sich(discovery: Discovery):
    """A local server has one model loaded — naming it twice helps nobody."""
    await discovery.einmal_pruefen()
    paare = discovery.aufgefaechert(discovery.erreichbare())
    assert [(z.endpunkt.id, m) for z, m in paare] == [("test", None)]


@pytest.mark.asyncio
async def test_ein_einzelnes_modell_faechert_nicht_auf(discovery: Discovery):
    """One reported model is not a catalogue — otherwise every local server
    would grow a colon and a repetition in its id."""
    discovery.zustaende["test"].provider = MockProvider(modelle=["qwen"])
    await discovery.einmal_pruefen()
    assert discovery.zustaende["test"].modelle == []


# --- Resolving back -------------------------------------------------------


@pytest.mark.asyncio
async def test_alte_kennung_ohne_modell_findet_weiter_ihren_anbieter(discovery: Discovery):
    """Chats and agents have the bare id stored. It must keep working."""
    discovery.zustaende["test"].provider = MockProvider(modelle=["a", "b"])
    await discovery.einmal_pruefen()

    zustand, modell = discovery.aufloesen("test")
    assert zustand.endpunkt.id == "test"
    # Without a model named, whatever the provider reports for itself applies.
    assert modell == zustand.gemeldeter_name


@pytest.mark.asyncio
async def test_kennung_mit_modell_liefert_genau_dieses_modell(discovery: Discovery):
    discovery.zustaende["test"].provider = MockProvider(modelle=["a", "b"])
    await discovery.einmal_pruefen()

    zustand, modell = discovery.aufloesen("test:b")
    assert (zustand.endpunkt.id, modell) == ("test", "b")


@pytest.mark.asyncio
async def test_ein_modell_das_der_anbieter_nicht_hat_wird_nicht_ersetzt(discovery: Discovery):
    """Silently swapping in another model would answer as a model nobody chose."""
    discovery.zustaende["test"].provider = MockProvider(modelle=["a", "b"])
    await discovery.einmal_pruefen()

    assert discovery.aufloesen("test:gibtsnicht") is None


def test_unbekannter_anbieter_loest_nicht_auf(discovery: Discovery):
    assert discovery.aufloesen("gibtsnicht:egal") is None


# --- What the list says ---------------------------------------------------


@pytest.mark.asyncio
async def test_die_modellliste_nennt_anbieter_und_modell(discovery: Discovery):
    discovery.zustaende["test"].provider = MockProvider(modelle=["a", "b"])
    await discovery.einmal_pruefen()

    zustand = discovery.zustaende["test"]
    eintrag = zustand.als_dict("b")
    assert eintrag["id"] == "test:b"
    assert eintrag["anbieter"] == "test"
    assert eintrag["modell"] == "b"
    assert eintrag["name"] == "b"


def test_der_schluessel_wird_gemeldet_aber_nie_gezeigt(discovery: Discovery, monkeypatch):
    """The window needs to tell "no key" apart from "dead host" — both look
    the same from outside. What travels is the variable NAME and a yes/no,
    never the value: the interface has no login."""
    zustand = discovery.zustaende["test"]
    zustand.endpunkt = zustand.endpunkt.model_copy(update={"api_key_env": "TEST_SCHLUESSEL"})

    monkeypatch.delenv("TEST_SCHLUESSEL", raising=False)
    eintrag = zustand.als_dict()
    assert eintrag["schluessel_env"] == "TEST_SCHLUESSEL"
    assert eintrag["schluessel_gesetzt"] is False

    monkeypatch.setenv("TEST_SCHLUESSEL", "geheim")
    eintrag = zustand.als_dict()
    assert eintrag["schluessel_gesetzt"] is True
    assert "geheim" not in str(eintrag)


def test_ohne_schluesselfeld_steht_nichts_da(discovery: Discovery):
    """A local server wants no key — an empty traffic light would be noise."""
    eintrag = discovery.zustaende["test"].als_dict()
    assert eintrag["schluessel_env"] is None
    assert eintrag["schluessel_gesetzt"] is False


@pytest.mark.asyncio
async def test_ein_ausfall_leert_den_katalog(discovery: Discovery):
    """Whatever is not reachable offers nothing — a stale catalogue would
    show models you cannot talk to."""
    discovery.zustaende["test"].provider = MockProvider(modelle=["a", "b"])
    await discovery.einmal_pruefen()
    assert discovery.zustaende["test"].modelle

    discovery.zustaende["test"].provider = MockProvider(ist_erreichbar=False)
    for _ in range(4):
        await discovery.einmal_pruefen()
    assert discovery.zustaende["test"].modelle == []
