"""The persistent memory: does it reach the model, and only where it may?

Two halves are worth proving. That prompt and memory arrive as ONE system
message, because the providers disagree about a second one and Anthropic
takes a single field. And that the two switches really decide — the local
one and the cloud one, nothing finer.

The route is part of it on purpose. A settings key that nobody vouches for
comes back as 400 while the interface quietly restores its own state; that
exact bug hid behind the model switch for a whole day.
"""

from __future__ import annotations

from app import gedaechtnis
from app.providers import MockProvider, mock_endpunkt
from tests.conftest import provider_setzen


# --- Checking the switches --------------------------------------------------


def test_nur_die_beiden_schalter_kommen_durch():
    geprueft = gedaechtnis.schalter_pruefen(
        {"lokal": True, "cloud": False, "erfunden": True}
    )
    assert geprueft == {"lokal": True, "cloud": False}


def test_was_kein_objekt_ist_gilt_als_nichts():
    assert gedaechtnis.schalter_pruefen(["lokal"]) == {}
    assert gedaechtnis.schalter_pruefen(True) == {}


def test_werte_werden_zu_echten_wahrheitswerten():
    assert gedaechtnis.schalter_pruefen({"lokal": 1, "cloud": ""}) == {
        "lokal": True,
        "cloud": False,
    }


# --- Assembling into one system message -------------------------------------


def test_prompt_und_gedaechtnis_werden_eine_nachricht():
    zusammen = gedaechtnis.anhaengen("Du bist knapp.", "## Rules\n- Englisch.")
    assert zusammen.startswith("Du bist knapp.")
    assert "## Rules" in zusammen
    assert gedaechtnis.EINLEITUNG in zusammen


def test_ohne_gedaechtnis_bleibt_der_prompt_unberuehrt():
    assert gedaechtnis.anhaengen("Du bist knapp.", "") == "Du bist knapp."
    assert gedaechtnis.anhaengen("Du bist knapp.", "   ") == "Du bist knapp."


def test_ohne_prompt_steht_das_gedaechtnis_allein():
    zusammen = gedaechtnis.anhaengen("", "## Facts\n- Arbeitet am Mac.")
    assert zusammen.startswith(gedaechtnis.EINLEITUNG)
    assert "Arbeitet am Mac" in zusammen


# --- The default: on here, off out there ------------------------------------


class _Endpunkt:
    def __init__(self, group: str) -> None:
        self.group = group


class _Zustand:
    def __init__(self, group: str) -> None:
        self.endpunkt = _Endpunkt(group)


def test_vorgabe_lokal_an_cloud_aus(repos):
    assert gedaechtnis.mitschicken(repos, _Zustand("local")) is True
    assert gedaechtnis.mitschicken(repos, _Zustand("cloud")) is False


def test_beide_schalter_lassen_sich_umdrehen(repos):
    repos.einstellungen.setzen(
        "global", gedaechtnis.SCHLUESSEL, {"lokal": False, "cloud": True}
    )
    assert gedaechtnis.mitschicken(repos, _Zustand("local")) is False
    assert gedaechtnis.mitschicken(repos, _Zustand("cloud")) is True


def test_ein_schalter_allein_laesst_den_anderen_in_ruhe(repos):
    """The stored value is merged key by key, so switching the cloud on does
    not silently drop what was decided about local."""
    repos.einstellungen.setzen("global", gedaechtnis.SCHLUESSEL, {"cloud": True})
    assert gedaechtnis.mitschicken(repos, _Zustand("local")) is True
    assert gedaechtnis.mitschicken(repos, _Zustand("cloud")) is True


# --- And the whole way: file -> route -> what the model is handed ------------


def _system_nachricht(provider: MockProvider) -> str:
    nachrichten = provider.letzte_anfrage.nachrichten
    system = [n for n in nachrichten if n.role == "system"]
    assert len(system) == 1, "Prompt und Gedächtnis müssen EINE Nachricht sein"
    return system[0].content


def test_das_gedaechtnis_erreicht_das_modell(client, chat_id):
    client.app.state.config.memory_schreiben("## Facts\n- Heißt der Prüfstein.")
    client.app.state.config.system_prompt_schreiben("Sei knapp.")
    # The test endpoint has no group of its own and therefore counts as
    # local, which is the half that is on by default.

    provider = MockProvider(mock_endpunkt("test"), haeppchen=["ok"])
    provider_setzen(client, provider)
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )

    system = _system_nachricht(provider)
    assert "Sei knapp." in system
    assert "Heißt der Prüfstein." in system


def test_abgeschaltet_bleibt_es_zuhause(client, chat_id):
    client.app.state.config.memory_schreiben("## Facts\n- Geheim.")
    client.app.state.config.system_prompt_schreiben("Sei knapp.")
    client.put(
        "/api/v1/settings/global/gedaechtnis", json={"wert": {"lokal": False}}
    )

    provider = MockProvider(mock_endpunkt("test"), haeppchen=["ok"])
    provider_setzen(client, provider)
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )

    system = _system_nachricht(provider)
    assert "Sei knapp." in system
    assert "Geheim." not in system


def test_die_route_speichert_die_schalter(client):
    antwort = client.put(
        "/api/v1/settings/global/gedaechtnis",
        json={"wert": {"lokal": False, "cloud": True}},
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["wert"] == {"lokal": False, "cloud": True}


def test_eine_fehlende_datei_ist_kein_fehler(client):
    """The as-shipped state, and the state after somebody deleted everything
    the program had learned about them."""
    assert client.app.state.config.memory_lesen() == ""
