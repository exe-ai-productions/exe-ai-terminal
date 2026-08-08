"""The jobs API (phase 6.3/6.4): start an agent, log, limits, endings.

The run is a background task — the tests submit the job, poll the state
until it reaches a terminal state, and then check the log, result, and
reason. The TestClient runs the event loop in its own thread, so
``time.sleep`` in the test does not stall it.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.providers import MockProvider, Stueck, mock_endpunkt
from app.providers.base import Werkzeugaufruf
from app.tools.mcp_client import MCPWerkzeug
from app.tools.registry import WerkzeugRegistry
from tests.conftest import provider_setzen

ENDE = {"fertig", "abgebrochen", "gescheitert", "unterbrochen"}


# --- Helpers ---------------------------------------------------------------


def agent_schreiben(config, name: str = "recherche", kopf: str = "model: test") -> Path:
    ordner = Path(config.app.agenten_verzeichnis)
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.md"
    datei.write_text(f"---\n{kopf}\n---\n\nDu bist der Rechercheur.\n", encoding="utf-8")
    return datei


def auf_ende_warten(client, auftrag_id: str, timeout: float = 8.0) -> dict:
    frist = time.time() + timeout
    daten: dict = {}
    while time.time() < frist:
        daten = client.get(f"/api/v1/jobs/{auftrag_id}").json()
        if daten.get("state") in ENDE:
            return daten
        time.sleep(0.05)
    raise AssertionError(f"Auftrag kam in keinen Endzustand: {daten}")


class ImmerWerkzeuge(MockProvider):
    """Requests a tool every round — for the limit tests."""

    async def streamen(self, anfrage):
        self.letzte_anfrage = anfrage
        self.alle_anfragen.append(anfrage)
        self.durchlaeufe += 1
        if self.verzoegerung:
            import asyncio

            await asyncio.sleep(self.verzoegerung)
        yield Stueck(
            "tool_call",
            werkzeugaufrufe=[
                Werkzeugaufruf(
                    id=f"w{self.durchlaeufe}", name="addieren", argumente={"a": 1, "b": 2}
                )
            ],
        )


class RegistryDouble(WerkzeugRegistry):
    """A registry without real MCP servers: one tool, hard-wired."""

    def __init__(self) -> None:
        super().__init__([])
        self._werkzeuge = {
            "addieren": (None, MCPWerkzeug(name="addieren", beschreibung="addiert"), False),
            "verboten": (None, MCPWerkzeug(name="verboten", beschreibung="nie"), False),
        }
        self.aufrufe: list[tuple[str, dict]] = []

    async def ausfuehren(self, name, argumente, bild_senke=None, ordner=None):
        if name not in self._werkzeuge:
            raise AssertionError("Filter hat versagt")
        self.aufrufe.append((name, argumente))
        return "3"


@pytest.fixture
def mcp_client(config):
    """A client with the tool feature enabled and a registry double."""
    from fastapi.testclient import TestClient

    from app.main import app_erstellen

    config.features.mcp = True
    # Points nowhere: the lifecycle must not start any real MCP servers.
    config.mcp.servers_file = str(Path(config.app.data_dir) / "keine_server.json")
    with TestClient(app_erstellen(config)) as testclient:
        testclient.app.state.werkzeuge = RegistryDouble()
        # In the configuration the test endpoint cannot do tool calls —
        # here it can, otherwise there would be nothing to test.
        zustand = testclient.app.state.discovery.zustaende["test"]
        zustand.endpunkt.capabilities.tool_calls = True
        yield testclient


# --- Agent list ------------------------------------------------------------


def test_agentenliste_ist_leer_ohne_dateien(client):
    assert client.get("/api/v1/agents").json() == []


def test_agentenliste_zeigt_kopfteil(config, client):
    agent_schreiben(config, kopf="model: test\ntools:\n  - web_search\nmax_rounds: 7")
    (eintrag,) = client.get("/api/v1/agents").json()
    assert eintrag["name"] == "recherche"
    assert eintrag["model"] == "test"
    assert eintrag["tools"] == ["web_search"]
    assert eintrag["max_rounds"] == 7


# --- Starting and ending ---------------------------------------------------


def test_unbekannter_agent_gibt_404(client):
    antwort = client.post("/api/v1/jobs", json={"agent": "phantom", "task": "x"})
    assert antwort.status_code == 404


def test_auftrag_loeschen_entfernt_auftrag_und_protokoll(config, client):
    agent_schreiben(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["Ok."]))
    antwort = client.post("/api/v1/jobs", json={"agent": "recherche", "task": "x"})
    auftrag_id = antwort.json()["id"]
    auf_ende_warten(client, auftrag_id)

    assert client.delete(f"/api/v1/jobs/{auftrag_id}").status_code == 204
    assert client.get(f"/api/v1/jobs/{auftrag_id}").status_code == 404
    assert client.get("/api/v1/jobs").json() == []


def test_unbekannter_auftrag_loeschen_gibt_404(client):
    assert client.delete("/api/v1/jobs/phantom").status_code == 404


def test_laufenden_auftrag_loeschen_stoppt_ihn(config, client):
    """Deleting mid-run: the run is stopped, and its completion writes
    nothing anymore — the job is gone, after all (no FK error)."""
    agent_schreiben(config)
    provider_setzen(
        client, MockProvider(mock_endpunkt("test"), verzoegerung=0.4, haeppchen=["…"])
    )
    antwort = client.post("/api/v1/jobs", json={"agent": "recherche", "task": "x"})
    auftrag_id = antwort.json()["id"]

    assert client.delete(f"/api/v1/jobs/{auftrag_id}").status_code == 204
    assert client.get(f"/api/v1/jobs/{auftrag_id}").status_code == 404
    # Give the stopped run time to finish cleanly — it must not write to
    # the database anymore while doing so.
    time.sleep(0.8)
    assert client.get("/api/v1/jobs").json() == []


def test_agent_ohne_modell_nimmt_erreichbaren_endpunkt(config, client):
    agent_schreiben(config, name="ohne", kopf="max_rounds: 3")
    provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["Ok."]))
    antwort = client.post("/api/v1/jobs", json={"agent": "ohne", "task": "x"})
    assert antwort.status_code == 201
    daten = auf_ende_warten(client, antwort.json()["id"])
    assert daten["state"] == "fertig"


def test_agent_ohne_modell_mit_werkzeugen_braucht_toolfaehigen_endpunkt(config, client):
    # The test endpoint cannot do tool calls — for an agent with tools
    # the fallback must not pick it.
    agent_schreiben(config, name="ohne", kopf="tools:\n  - web_search")
    provider_setzen(client, MockProvider(mock_endpunkt("test")))
    antwort = client.post("/api/v1/jobs", json={"agent": "ohne", "task": "x"})
    assert antwort.status_code == 400


def test_auftrag_laeuft_zu_ende_und_protokolliert(config, client):
    agent_schreiben(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test"), haeppchen=["Der ", "Bericht."]))

    antwort = client.post("/api/v1/jobs", json={"agent": "recherche", "task": "Los"})
    assert antwort.status_code == 201
    daten = auf_ende_warten(client, antwort.json()["id"])

    assert daten["state"] == "fertig"
    assert daten["end_reason"] == "fertig"
    assert daten["result"] == "Der Bericht."
    assert daten["generation_id"] is None
    typen = [schritt["typ"] for schritt in daten["schritte"]]
    assert typen[0] == "status"
    assert "text" in typen
    assert typen[-1] == "ende"


def test_prompt_ist_gestapelt_global_dann_agent(config, client):
    """Decision 3: global prompt, then agent prompt, one message."""
    prompt_datei = Path(config.app.system_prompt_file)
    prompt_datei.parent.mkdir(parents=True, exist_ok=True)
    prompt_datei.write_text("GLOBAL.", encoding="utf-8")
    agent_schreiben(config)
    provider = provider_setzen(client, MockProvider(mock_endpunkt("test")))

    kennung = client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Los"}
    ).json()["id"]
    auf_ende_warten(client, kennung)

    system = provider.letzte_anfrage.nachrichten[0]
    assert system.role == "system"
    # Three layers in order: shipped instructions, the user's prompt, the
    # agent's — the agent last, because that is what makes this run an agent.
    assert "Exe AI Terminal" in system.content
    assert system.content.endswith("GLOBAL.\n\nDu bist der Rechercheur.")
    benutzer = provider.letzte_anfrage.nachrichten[1]
    assert (benutzer.role, benutzer.content) == ("user", "Los")


def test_gescheiterter_lauf_traegt_den_fehler(config, client):
    agent_schreiben(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test"), fehler="Kabelbrand"))

    kennung = client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Los"}
    ).json()["id"]
    daten = auf_ende_warten(client, kennung)

    assert daten["state"] == "gescheitert"
    assert daten["end_reason"].startswith("fehler:")
    assert "Kabelbrand" in daten["end_reason"]


def test_voller_kontext_endet_sauber_mit_bericht(config, client):
    """Decision 10: a full context is not a crash."""
    agent_schreiben(config)
    provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test"),
            fehler="the request exceeds the maximum context length of 4096",
        ),
    )

    kennung = client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Los"}
    ).json()["id"]
    daten = auf_ende_warten(client, kennung)

    assert daten["state"] == "gescheitert"
    assert daten["end_reason"] == "kontext_voll"
    assert daten["schritte"][-1]["inhalt"] == "kontext_voll"


def test_abbrechen_beendet_den_lauf(config, client):
    agent_schreiben(config)
    provider_setzen(
        client,
        MockProvider(
            mock_endpunkt("test"), haeppchen=[f"T{i} " for i in range(100)], verzoegerung=0.05
        ),
    )

    kennung = client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Los"}
    ).json()["id"]
    antwort = client.post(f"/api/v1/jobs/{kennung}/cancel")
    assert antwort.status_code == 200
    daten = auf_ende_warten(client, kennung)

    assert daten["state"] == "abgebrochen"
    assert daten["end_reason"] == "benutzer_abbruch"


def test_auftragsliste_zeigt_den_neuen_auftrag(config, client):
    agent_schreiben(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test")))
    kennung = client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Los"}
    ).json()["id"]
    auf_ende_warten(client, kennung)
    liste = client.get("/api/v1/jobs").json()
    assert [eintrag["id"] for eintrag in liste] == [kennung]


# --- Reading, writing, deleting agent files (6.6) --------------------------


def test_agentendatei_lesen(config, client):
    agent_schreiben(config)
    daten = client.get("/api/v1/agents/recherche").json()
    assert daten["name"] == "recherche"
    assert "Du bist der Rechercheur." in daten["content"]
    assert daten["kaputt"] is None


def test_fehlende_agentendatei_gibt_404(client):
    assert client.get("/api/v1/agents/phantom").status_code == 404


def test_agentendatei_speichern(config, client):
    inhalt = "---\nmodel: test\n---\n\nNeuer Prompt.\n"
    antwort = client.put("/api/v1/agents/neuling", json={"content": inhalt})
    assert antwort.status_code == 200
    assert antwort.json()["kaputt"] is None
    namen = [agent["name"] for agent in client.get("/api/v1/agents").json()]
    assert "neuling" in namen


def test_kaputte_datei_wird_gespeichert_aber_gemeldet(config, client):
    """It is the user's file: save it, yes — hide the problem, no."""
    antwort = client.put("/api/v1/agents/krank", json={"content": "kein kopfteil"})
    assert antwort.status_code == 200
    assert "Kopfteil" in antwort.json()["kaputt"]
    # It is saved — readable via the file API …
    assert client.get("/api/v1/agents/krank").status_code == 200
    # … but the agent is not in play.
    namen = [agent["name"] for agent in client.get("/api/v1/agents").json()]
    assert "krank" not in namen


def test_agentendatei_loeschen(config, client):
    agent_schreiben(config)
    assert client.delete("/api/v1/agents/recherche").status_code == 204
    assert client.get("/api/v1/agents/recherche").status_code == 404
    assert client.delete("/api/v1/agents/recherche").status_code == 404


def test_dateiliste_zeigt_auch_kaputte(config, client):
    """What is missing from the agent list must still be fixable in the dialog."""
    agent_schreiben(config)
    client.put("/api/v1/agents/krank", json={"content": "kein kopfteil"})
    eintraege = {e["name"]: e["kaputt"] for e in client.get("/api/v1/agent-files").json()}
    assert eintraege["recherche"] is None
    assert "Kopfteil" in eintraege["krank"]


def test_pfad_tricks_werden_abgewiesen(client):
    """Agent names are file names — dots and slashes do not get through."""
    assert client.put("/api/v1/agents/a.b", json={"content": "x"}).status_code == 400
    assert client.get("/api/v1/agents/..%2Fsystem").status_code in (400, 404)


# --- Tools: filter and approval ---------------------------------------------


def test_filter_bietet_nur_den_schnitt_an():
    registry = RegistryDouble()
    namen = [
        werkzeug["function"]["name"]
        for werkzeug in registry.als_openai_werkzeuge(nur={"addieren", "erfunden"})
    ]
    assert namen == ["addieren"]
    assert len(registry.als_openai_werkzeuge()) == 2


def test_agentenwerkzeug_laeuft_ohne_rueckfrage(config, mcp_client):
    """Decision 6: what is listed in the agent runs — nobody gets asked."""
    agent_schreiben(config, kopf="model: test\ntools:\n  - addieren\nmax_rounds: 3")
    provider_setzen(
        mcp_client,
        ImmerWerkzeuge(mock_endpunkt("test")),
    )

    kennung = mcp_client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Rechne"}
    ).json()["id"]
    daten = auf_ende_warten(mcp_client, kennung)

    registry = mcp_client.app.state.werkzeuge
    assert registry.aufrufe, "das Werkzeug wurde nie ausgeführt"
    typen = [schritt["typ"] for schritt in daten["schritte"]]
    assert "tool_call" in typen and "tool_result" in typen
    # No tool_confirm — neither in the log nor as a waiting state.
    assert "tool_confirm" not in typen


def test_rundengrenze_beendet_mit_lesbarem_grund(config, mcp_client):
    agent_schreiben(config, kopf="model: test\ntools:\n  - addieren\nmax_rounds: 2")
    provider_setzen(mcp_client, ImmerWerkzeuge(mock_endpunkt("test")))

    kennung = mcp_client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Rechne"}
    ).json()["id"]
    daten = auf_ende_warten(mcp_client, kennung)

    assert daten["state"] == "gescheitert"
    assert daten["end_reason"] == "rundengrenze"
    assert len(mcp_client.app.state.werkzeuge.aufrufe) == 2


def test_zeitgrenze_beendet_mit_lesbarem_grund(config, mcp_client):
    agent_schreiben(
        config,
        kopf="model: test\ntools:\n  - addieren\nmax_rounds: 50\nmax_minutes: 0.0001",
    )
    provider_setzen(
        mcp_client, ImmerWerkzeuge(mock_endpunkt("test"), verzoegerung=0.05)
    )

    kennung = mcp_client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Rechne"}
    ).json()["id"]
    daten = auf_ende_warten(mcp_client, kennung)

    assert daten["state"] == "gescheitert"
    assert daten["end_reason"] == "zeitgrenze"


def test_agent_ohne_werkzeugliste_bekommt_keine_werkzeuge(config, mcp_client):
    """What is not listed is not offered — even if the server can do more."""
    agent_schreiben(config, kopf="model: test")
    provider = provider_setzen(mcp_client, MockProvider(mock_endpunkt("test")))

    kennung = mcp_client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Los"}
    ).json()["id"]
    auf_ende_warten(mcp_client, kennung)

    assert provider.letzte_anfrage.werkzeuge == []


def test_fehlende_werkzeuge_stehen_im_protokoll(config, mcp_client):
    agent_schreiben(
        config, kopf="model: test\ntools:\n  - addieren\n  - erfunden"
    )
    provider_setzen(mcp_client, MockProvider(mock_endpunkt("test")))

    kennung = mcp_client.post(
        "/api/v1/jobs", json={"agent": "recherche", "task": "Los"}
    ).json()["id"]
    daten = auf_ende_warten(mcp_client, kennung)

    status_schritte = [s["inhalt"] for s in daten["schritte"] if s["typ"] == "status"]
    assert any("erfunden" in inhalt for inhalt in status_schritte)
