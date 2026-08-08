"""Interface milestones B + C: native capability detection and feature switches."""

from __future__ import annotations

from app.config import Capabilities, EndpointConfig
from app.discovery import EndpunktZustand, werkzeuge_im_template


def _zustand(caps: dict, erkannt: dict | None = None) -> EndpunktZustand:
    endpunkt = EndpointConfig(
        id="x", base_url="http://127.0.0.1:9/v1", capabilities=Capabilities(**caps)
    )
    zustand = EndpunktZustand(endpunkt=endpunkt, provider=None)
    zustand.faehigkeiten_erkannt = erkannt
    return zustand


# --- B: Detection ----------------------------------------------------------


def test_werkzeuge_im_template():
    assert werkzeuge_im_template("{%- if tools %}…{% endif %}") is True
    assert werkzeuge_im_template("nichts dergleichen") is False
    assert werkzeuge_im_template("") is False


def test_erkennung_fuellt_nur_die_luecken():
    # Config is silent, nothing detected -> everything off.
    leer = _zustand({})
    assert not leer.kann("vision")
    assert not leer.kann("tool_calls")
    # Config is silent, the server reveals it -> the detection counts.
    voll = _zustand({}, {"vision": True, "tool_calls": True, "thinking": True})
    assert voll.kann("vision")
    assert voll.kann("tool_calls")
    assert voll.kann("thinking")


def test_config_gewinnt_immer_auch_ein_nein():
    # The Gemma rule: an explicit no beats any detection.
    gemma = _zustand(
        {"tool_calls": False, "vision": True},
        {"tool_calls": True, "vision": True, "thinking": True},
    )
    assert not gemma.kann("tool_calls")
    assert gemma.kann("vision")
    # And an explicit yes applies even without detection.
    assert _zustand({"tool_calls": True}).kann("tool_calls")


def test_aufgeloeste_faehigkeiten_gehen_ans_frontend():
    zustand = _zustand({}, {"vision": True, "tool_calls": False, "thinking": True})
    caps = zustand.als_dict()["capabilities"]
    assert caps["vision"] is True
    assert caps["tool_calls"] is False
    assert caps["thinking"] is True


# --- C: Feature switches -----------------------------------------------------


def _chat(client):
    return client.post("/api/v1/chats", json={"title": "Schalter"}).json()


def test_document_upload_aus_sperrt_die_api(client):
    client.app.state.config.features.document_upload = False
    try:
        chat = _chat(client)
        antwort = client.post(
            f"/api/v1/documents?chat_id={chat['id']}&name=notiz.txt",
            content=b"egal",
        )
        assert antwort.status_code == 403
    finally:
        client.app.state.config.features.document_upload = True


def test_image_generation_aus_sperrt_die_api(client):
    client.app.state.config.features.image_generation = False
    try:
        chat = _chat(client)
        antwort = client.post(
            "/api/v1/images/generate",
            json={"chat_id": chat["id"], "prompt": "ein Berg"},
        )
        assert antwort.status_code == 403
    finally:
        client.app.state.config.features.image_generation = True


def test_meta_traegt_die_schalter(client):
    daten = client.get("/api/v1/meta").json()
    assert daten["features"]["document_upload"] is True
    assert daten["features"]["image_generation"] is True
