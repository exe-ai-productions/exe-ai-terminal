"""Vision input: upload, delivery, lockdown."""

from __future__ import annotations

from app.providers import ChatNachricht
from app.providers.openai_kompatibel import OpenAIKompatiblerProvider

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"testbild"


def test_bild_rundreise(client):
    antwort = client.post(
        "/api/v1/images", content=PNG_BYTES, headers={"Content-Type": "image/png"}
    )
    assert antwort.status_code == 201
    name = antwort.json()["bild"]
    assert name.endswith(".png")

    geholt = client.get(f"/api/v1/images/{name}")
    assert geholt.status_code == 200
    assert geholt.content == PNG_BYTES
    assert geholt.headers["content-type"].startswith("image/png")


def test_falscher_typ_wird_abgewiesen(client):
    antwort = client.post(
        "/api/v1/images", content=b"GIF89a", headers={"Content-Type": "image/gif"}
    )
    assert antwort.status_code == 415


def test_fremde_namen_erreichen_das_dateisystem_nicht(client):
    assert client.get("/api/v1/images/../../config.yaml").status_code in (404, 422)
    assert client.get("/api/v1/images/boese.png").status_code == 404


def test_bild_ohne_vision_gibt_400(client):
    chat = client.post("/api/v1/chats", json={"title": "Vision"}).json()
    hochgeladen = client.post(
        "/api/v1/images", content=PNG_BYTES, headers={"Content-Type": "image/png"}
    ).json()["bild"]
    antwort = client.post(
        "/api/v1/chat/completions",
        json={
            "chat_id": chat["id"],
            "endpoint_id": "test",
            "content": "Was ist auf dem Bild?",
            "bild": hochgeladen,
        },
    )
    # The test endpoint has no vision — the API is the outer boundary.
    assert antwort.status_code == 400


def test_stopp_ohne_lauf_gibt_404(client):
    antwort = client.post("/api/v1/images/stop", json={"generation_id": "gibtsnicht"})
    assert antwort.status_code == 404


def test_gestoppte_erzeugung_laesst_den_chat_unberuehrt(client, monkeypatch):
    """If the user stops, `abgebrochen` comes back — no image, no
    messages, no error. The fake also checks in passing that the route
    really passes a stop event to the generator."""
    import app.bildgeneratoren as bildgeneratoren

    class StoppGenerator:
        id = "fake"
        dialekt = "comfyui"

        async def erreichbar(self, timeout=4.0):
            return True

        async def erzeugen(self, prompt, stopp=None):
            assert stopp is not None
            raise bildgeneratoren.BildAbbruch()

    monkeypatch.setattr(bildgeneratoren, "generatoren", lambda config: [StoppGenerator()])

    chat = client.post("/api/v1/chats", json={"title": "Stopp"}).json()
    antwort = client.post(
        "/api/v1/images/generate",
        json={"chat_id": chat["id"], "prompt": "egal", "generation_id": "abc123"},
    )
    assert antwort.status_code == 200
    assert antwort.json()["abgebrochen"] is True
    assert antwort.json()["bild"] is None
    assert client.get(f"/api/v1/chats/{chat['id']}/messages").json() == []


def test_provider_baut_das_bildformat():
    nachricht = ChatNachricht(
        role="user", content="Was ist das?", bild_url="data:image/png;base64,QUJD"
    )
    eintrag = OpenAIKompatiblerProvider._nachricht_bauen(nachricht)
    assert eintrag["content"] == [
        {"type": "text", "text": "Was ist das?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
    ]

    ohne_text = ChatNachricht(role="user", content="", bild_url="data:image/png;base64,QUJD")
    eintrag = OpenAIKompatiblerProvider._nachricht_bauen(ohne_text)
    assert eintrag["content"] == [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}}
    ]


# --- API keys for paid image services --------------------------------------


def test_bild_endpunkt_schickt_den_schluessel_mit(monkeypatch):
    """fal.ai, Recraft, OpenAI — they all want a key in the header.

    The value is never in config.yaml; only the NAME of the environment
    variable is. It is read fresh on every request.
    """
    from app.bildgeneratoren import BildGenerator
    from app.config import PROJEKT_WURZEL, BildEndpunktConfig

    eintrag = BildEndpunktConfig(
        id="bezahlt",
        dialect="openai_images",
        base_url="https://example.invalid/v1",
        api_key_env="TEST_BILD_SCHLUESSEL",
    )
    generator = BildGenerator(eintrag, PROJEKT_WURZEL)

    monkeypatch.setenv("TEST_BILD_SCHLUESSEL", "geheim123")
    assert generator._kopfzeilen == {"Authorization": "Bearer geheim123"}

    # A changed value takes effect immediately, no restart needed.
    monkeypatch.setenv("TEST_BILD_SCHLUESSEL", "neu456")
    assert generator._kopfzeilen == {"Authorization": "Bearer neu456"}


def test_bild_endpunkt_ohne_schluessel_schickt_keine_kopfzeile(monkeypatch):
    """Local servers don't want one — then nothing must be sent along."""
    from app.bildgeneratoren import BildGenerator
    from app.config import PROJEKT_WURZEL, BildEndpunktConfig

    lokal = BildGenerator(
        BildEndpunktConfig(id="lokal", dialect="comfyui", base_url="http://127.0.0.1:8188"),
        PROJEKT_WURZEL,
    )
    assert lokal._kopfzeilen == {}

    # Variable configured but not set: better no header at all than
    # "Bearer " without a value — the service then clearly answers 401.
    monkeypatch.delenv("FEHLT_ABSICHTLICH", raising=False)
    ohne_wert = BildGenerator(
        BildEndpunktConfig(
            id="x", dialect="openai_images", base_url="https://example.invalid/v1",
            api_key_env="FEHLT_ABSICHTLICH",
        ),
        PROJEKT_WURZEL,
    )
    assert ohne_wert._kopfzeilen == {}
