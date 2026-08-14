"""Switching a tool off has to reach the model, not just the window.

The model switch once looked like it worked and stored nothing: the settings
route only lets keys through that someone vouches for, and it knew nothing
about the new one, so every write came back 400 while the interface quietly
restored its own state. These tests therefore go through the real route and
then check the registry — the two places where a lie would show.
"""

from __future__ import annotations

import pytest

from app import werkzeugwahl
from app.tools.registry import WerkzeugRegistry, WerkzeugVerboten


# --- Checking the value -----------------------------------------------------


def test_nur_nicht_leere_texte_kommen_durch():
    assert werkzeugwahl.aus_pruefen(["run_command", "", "  ", 7, None]) == ["run_command"]


def test_namen_werden_getrimmt_und_entdoppelt():
    assert werkzeugwahl.aus_pruefen([" a ", "a", "b"]) == ["a", "b"]


def test_ein_zu_langer_name_faellt_raus():
    lang = "x" * (werkzeugwahl.MAX_LAENGE + 1)
    assert werkzeugwahl.aus_pruefen([lang, "kurz"]) == ["kurz"]


def test_was_keine_liste_ist_gilt_als_nichts():
    assert werkzeugwahl.aus_pruefen({"a": 1}) == []
    assert werkzeugwahl.aus_pruefen("run_command") == []


# --- The way through the real route -----------------------------------------


def test_die_route_speichert_die_liste(client):
    antwort = client.put(
        "/api/v1/settings/global/werkzeuge_aus",
        json={"wert": ["run_command", "notion-search"]},
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["wert"] == ["run_command", "notion-search"]

    gelesen = client.get("/api/v1/settings/resolved/werkzeuge_aus")
    assert gelesen.json()["wert"] == ["run_command", "notion-search"]


def test_eine_leere_liste_loescht_statt_zu_schatten(client):
    client.put("/api/v1/settings/global/werkzeuge_aus", json={"wert": ["a"]})
    antwort = client.put("/api/v1/settings/global/werkzeuge_aus", json={"wert": []})
    assert antwort.json()["wert"] is None


def test_muell_wird_nicht_gespeichert(client):
    antwort = client.put(
        "/api/v1/settings/global/werkzeuge_aus", json={"wert": [123, {"a": 1}]}
    )
    assert antwort.status_code == 200
    assert antwort.json()["wert"] is None


# --- Enforcement in the registry --------------------------------------------


class _Werkzeug:
    def __init__(self, name: str) -> None:
        self.name = name
        self.beschreibung = ""
        self.server = "test"

    def als_openai_werkzeug(self) -> dict:
        return {"type": "function", "function": {"name": self.name}}


class _Client:
    async def werkzeug_aufrufen(self, name, argumente, bild_senke=None):
        return "gelaufen"


def _registry() -> WerkzeugRegistry:
    registry = WerkzeugRegistry([])
    client = _Client()
    for name in ("suchen", "schreiben"):
        registry._werkzeuge[name] = (client, _Werkzeug(name), False)
    return registry


def test_abgeschaltetes_wird_nicht_angeboten():
    registry = _registry()
    registry.abgeschaltet = {"schreiben"}
    namen = [w["function"]["name"] for w in registry.als_openai_werkzeuge()]
    assert namen == ["suchen"]


def test_abgeschaltetes_wird_auch_nicht_ausgefuehrt():
    """The second lock. A run can be older than the click: it may already
    carry a call for something that has since been switched off."""
    registry = _registry()
    registry.abgeschaltet = {"schreiben"}
    with pytest.raises(WerkzeugVerboten):
        import asyncio

        asyncio.run(registry.ausfuehren("schreiben", {}))


def test_ohne_abschaltung_bleibt_alles_wie_vorher():
    registry = _registry()
    namen = sorted(w["function"]["name"] for w in registry.als_openai_werkzeuge())
    assert namen == ["schreiben", "suchen"]


def test_das_eingebaute_werkzeug_laesst_sich_ebenso_abschalten():
    from app.tools import shell

    registry = WerkzeugRegistry([], shell_an=True)
    assert any(
        w["function"]["name"] == shell.WERKZEUG_NAME
        for w in registry.als_openai_werkzeuge()
    )
    registry.abgeschaltet = {shell.WERKZEUG_NAME}
    assert all(
        w["function"]["name"] != shell.WERKZEUG_NAME
        for w in registry.als_openai_werkzeuge()
    )


def test_die_dateiwerkzeuge_lassen_sich_einzeln_abschalten():
    """Switch writing off and a read-only agent is left — that is the point
    of splitting the one shell tool into five."""
    from app.tools import dateiwerkzeuge, shell

    registry = WerkzeugRegistry([], shell_an=True)
    registry.abgeschaltet = {shell.WERKZEUG_NAME, "write_file", "edit_file", "ask_user"}
    namen = sorted(w["function"]["name"] for w in registry.als_openai_werkzeuge())
    assert namen == ["list_dir", "read_file"]

    registry.abgeschaltet = {shell.WERKZEUG_NAME, "ask_user", *dateiwerkzeuge.NAMEN}
    assert registry.als_openai_werkzeuge() == []


# --- What travels from the cascade into the registry ------------------------


def test_anwenden_holt_die_liste_aus_der_kaskade(repos):
    repos.einstellungen.setzen("global", werkzeugwahl.SCHLUESSEL, ["schreiben"])
    registry = _registry()
    werkzeugwahl.anwenden(registry, repos)
    assert registry.abgeschaltet == {"schreiben"}


def test_der_chat_schlaegt_das_globale(repos):
    """A list cannot be merged key by key, so it travels whole from the most
    specific scope that set one — the chat decides for itself instead of
    silently inheriting half of the global list."""
    repos.einstellungen.setzen("global", werkzeugwahl.SCHLUESSEL, ["schreiben"])
    repos.einstellungen.setzen("chat:abc", werkzeugwahl.SCHLUESSEL, ["suchen"])
    registry = _registry()
    werkzeugwahl.anwenden(registry, repos, chat="abc")
    assert registry.abgeschaltet == {"suchen"}


def test_ohne_eintrag_ist_nichts_abgeschaltet(repos):
    registry = _registry()
    werkzeugwahl.anwenden(registry, repos)
    assert registry.abgeschaltet == set()


def test_anwenden_ohne_registry_tut_nichts(repos):
    werkzeugwahl.anwenden(None, repos)  # must not blow up


# --- And the whole way: click -> route -> what the model is handed ----------


def test_ein_abgeschaltetes_werkzeug_erreicht_das_modell_nicht(client, chat_id):
    """The one test that would have caught the model-switch bug.

    Everything in between is real: the switch writes through the settings
    route, the chat route reads the cascade, and what the provider is handed
    is what the model would get. A test that only checks the registry would
    still pass while the write silently came back 400.
    """
    from app.providers import MockProvider, mock_endpunkt
    from tests.conftest import provider_setzen

    registry = _registry()
    client.app.state.werkzeuge = registry
    client.app.state.config.features.mcp = True

    provider = MockProvider(mock_endpunkt("test"), haeppchen=["fertig"])
    provider_setzen(client, provider)
    # Without this the route offers nothing at all and the test would pass
    # for the wrong reason.
    client.app.state.discovery.zustaende["test"].endpunkt.capabilities.tool_calls = True

    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "hallo"},
    )
    angeboten = [w["function"]["name"] for w in (provider.letzte_anfrage.werkzeuge or [])]
    assert sorted(angeboten) == ["schreiben", "suchen"]

    # The switch, through the real route, the way the interface flips it.
    antwort = client.put(
        "/api/v1/settings/global/werkzeuge_aus", json={"wert": ["schreiben"]}
    )
    assert antwort.status_code == 200, antwort.text

    client.post(
        "/api/v1/chat/completions",
        json={"chat_id": chat_id, "endpoint_id": "test", "content": "und jetzt?"},
    )
    angeboten = [w["function"]["name"] for w in (provider.letzte_anfrage.werkzeuge or [])]
    assert angeboten == ["suchen"]


def test_nur_die_shell_ausserhalb_der_ordner_fragt_nach(tmp_path):
    """The whole program has exactly ONE prompt, and this is it.

    Not a style choice: a prompt that comes ten times a session gets clicked
    away without being read, and then the one that matters goes with it. What
    stands in for the others is that their result is visible and reversible —
    a memory line, a written skill, a switched-on skill all sit in the
    settings window and can be undone in a click. A command that has already
    run cannot.
    """
    from app.tools import memory, shell, skill

    registry = WerkzeugRegistry(
        [],
        shell_an=True,
        memory_pfad=tmp_path / "memory.md",
        skills_orte=(tmp_path / "haus", tmp_path / "mein"),
    )
    ordner = [str(tmp_path)]

    fragt = shell.WERKZEUG_NAME, {"command": f"rm -rf /Users/wer-auch-immer"}
    assert registry.braucht_bestaetigung(*fragt, ordner) is True

    stumm = [
        # Deleting inside the shared folder — sharing it IS the permission.
        (shell.WERKZEUG_NAME, {"command": f"rm -rf {tmp_path}/alles"}),
        (memory.WERKZEUG_NAME, {"text": "x", "kind": "rule"}),
        (memory.WERKZEUG_NAME, {"text": "x", "kind": "fact"}),
        (skill.LADEN, {"name": "handoff"}),
        (skill.SCHREIBEN, {"name": "x", "auto": True}),
    ]
    for name, argumente in stumm:
        assert registry.braucht_bestaetigung(name, argumente, ordner) is False, name
