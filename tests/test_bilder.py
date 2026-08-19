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
