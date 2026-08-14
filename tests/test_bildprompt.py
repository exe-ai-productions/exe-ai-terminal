"""The "Enhance" button behind the picture window's prompt field."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.bildprompt import MAX_EINGABE, PromptFehler, _saeubern, verbessern
from app.providers.mock import MockProvider
from tests.conftest import provider_setzen


def test_prompt_wird_umgeschrieben(client: TestClient):
    provider_setzen(
        client,
        MockProvider(haeppchen=["red bicycle, ", "morning light, 50mm"]),
    )
    antwort = client.post("/api/v1/bild/prompt", json={"prompt": "ein rotes Fahrrad"})
    assert antwort.status_code == 200
    assert antwort.json()["prompt"] == "red bicycle, morning light, 50mm"


def test_ohne_erreichbares_modell_503(client: TestClient, monkeypatch):
    # Patched instead of flags flipped: the background check would mark the
    # dummy reachable again between the two lines of this test.
    monkeypatch.setattr(client.app.state.discovery, "erreichbare", lambda: [])
    antwort = client.post("/api/v1/bild/prompt", json={"prompt": "ein rotes Fahrrad"})
    assert antwort.status_code == 503


def test_leerer_prompt_wird_abgewiesen(client: TestClient):
    provider_setzen(client, MockProvider())
    assert client.post("/api/v1/bild/prompt", json={"prompt": ""}).status_code == 422


def test_zu_langer_prompt_erreicht_das_modell_nicht(client: TestClient):
    provider_setzen(client, MockProvider())
    antwort = client.post(
        "/api/v1/bild/prompt", json={"prompt": "a" * (MAX_EINGABE + 1)}
    )
    assert antwort.status_code == 502


def test_modellfehler_wird_als_502_gemeldet(client: TestClient):
    provider_setzen(client, MockProvider(fehler="server weg"))
    antwort = client.post("/api/v1/bild/prompt", json={"prompt": "ein rotes Fahrrad"})
    assert antwort.status_code == 502


def test_leere_antwort_gilt_als_fehler(client: TestClient):
    provider_setzen(client, MockProvider(haeppchen=["  ", "\n"]))
    antwort = client.post("/api/v1/bild/prompt", json={"prompt": "ein rotes Fahrrad"})
    assert antwort.status_code == 502


@pytest.mark.parametrize(
    "roh,erwartet",
    [
        ('"red bicycle, morning light"', "red bicycle, morning light"),
        ("red bicycle, morning light.", "red bicycle, morning light"),
        ("  red bicycle  ", "red bicycle"),
        ("`red bicycle`", "red bicycle"),
    ],
)
def test_umrahmung_wird_entfernt(roh: str, erwartet: str):
    assert _saeubern(roh) == erwartet


async def test_verbessern_weist_leeren_prompt_ab():
    with pytest.raises(PromptFehler):
        await verbessern(MockProvider(), None, "   ")


async def test_anweisung_steht_als_systemnachricht_vorne():
    """The instruction has to reach the model, not just the module."""

    class Merker(MockProvider):
        def __init__(self):
            super().__init__(haeppchen=["ok"])
            self.gesehen = None

        def streamen(self, anfrage):
            self.gesehen = anfrage
            return super().streamen(anfrage)

    merker = Merker()
    await verbessern(merker, None, "ein rotes Fahrrad")
    assert merker.gesehen.nachrichten[0].role == "system"
    assert "Stable-Diffusion" in merker.gesehen.nachrichten[0].content
    assert merker.gesehen.nachrichten[1].content == "ein rotes Fahrrad"
