"""The switch, and what reaches the model because of it.

The point of the switch is a measured one: tool descriptions cost the local
model about a second per twenty-eight tokens, and everything that stands
permanently in the prompt is paid for on every single request. A skill that
has to be named by hand costs nothing at all — so only the automatic half is
worth a control, and the typed half deliberately has none.
"""

from __future__ import annotations

from app import skills, skillwahl
from app.providers import MockProvider, mock_endpunkt
from app.tools import WerkzeugRegistry
from tests.conftest import provider_setzen


def _mit_werkzeugen(client):
    """The test service starts without a tool registry. The catalogue is tied
    to one on purpose — naming skills the model has no skill_load to open is
    listing doors that are not there."""
    config = client.app.state.config
    config.features.mcp = True
    client.app.state.werkzeuge = WerkzeugRegistry(
        [], skills_orte=config.skillverzeichnisse
    )
    # The endpoint from the test configuration declares no capabilities, and
    # without tool_calls no tool section is built at all.
    client.app.state.discovery.zustaende["test"].endpunkt = mock_endpunkt("test")
    return config


def _skill(config, name, beschreibung="Da", auto=True):
    _, eigen = config.skillverzeichnisse
    ordner = eigen / name
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / skills.SKILL_DATEI).write_text(
        f"---\ndescription: {beschreibung}\nauto: {str(auto).lower()}\n---\n\nTu es.\n",
        encoding="utf-8",
    )


def _system(provider: MockProvider) -> str:
    system = [n for n in provider.letzte_anfrage.nachrichten if n.role == "system"]
    assert len(system) == 1
    return system[0].content


def _fragen(client, chat_id) -> MockProvider:
    provider = provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["ok"]))
    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    return provider


# --- the setting itself ------------------------------------------------------


def test_die_vorgabe_ist_an(repos):
    assert skillwahl.selbst_waehlen(repos) is True


def test_ein_modell_darf_es_fuer_sich_abschalten(repos):
    """The whole reason it sits in the cascade: off on the small local model
    that would only be slowed down, on for one that chooses well."""
    repos.einstellungen.setzen("modell:qwen", skillwahl.SCHLUESSEL, {"an": False})
    assert skillwahl.selbst_waehlen(repos, modell="qwen") is False
    assert skillwahl.selbst_waehlen(repos, modell="ein-anderes") is True


def test_ein_falscher_wert_wird_nicht_gespeichert(client):
    """The route is the gate: a settings column holds JSON and cannot check
    anything by itself."""
    antwort = client.put(
        f"/api/v1/settings/global/{skillwahl.SCHLUESSEL}", json={"wert": "nein"}
    )
    assert antwort.json()["wert"] in (None, {})


# --- and what the model gets -------------------------------------------------


def test_eine_automatische_skill_steht_im_prompt(client, chat_id):
    _skill(_mit_werkzeugen(client), "handoff", "Fasst das Gespräch zusammen")
    text = _system(_fragen(client, chat_id))
    assert "handoff — Fasst das Gespräch zusammen" in text


def test_eine_getippte_skill_kostet_nichts(client, chat_id):
    """It is reachable by name the whole time and still spends no token."""
    _skill(_mit_werkzeugen(client), "handoff", auto=False)
    assert "handoff" not in _system(_fragen(client, chat_id))


def test_abgeschaltet_steht_gar_kein_verzeichnis_drin(client, chat_id):
    _skill(_mit_werkzeugen(client), "handoff")
    client.put(
        f"/api/v1/settings/global/{skillwahl.SCHLUESSEL}", json={"wert": {"an": False}}
    )
    assert "skill_load" not in _system(_fragen(client, chat_id))


def test_ohne_werkzeuge_gibt_es_auch_kein_verzeichnis(client, chat_id):
    """A catalogue without skill_load names doors that cannot be opened."""
    _skill(_mit_werkzeugen(client), "handoff")
    client.app.state.config.features.mcp = False
    assert "handoff" not in _system(_fragen(client, chat_id))
