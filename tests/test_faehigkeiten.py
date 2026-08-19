"""Interface milestones B + C: native capability detection and feature switches."""

from __future__ import annotations

from app.config import Capabilities, EndpointConfig
from app.discovery import (
    EndpunktZustand,
    _faehigkeiten_aus_props,
    _faehigkeiten_erkennen,
    werkzeuge_im_template,
)


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


def test_template_caps_gewinnen_gegen_das_template():
    # The server's own word counts, in both directions — a template full of
    # tool syntax does not overrule an explicit no, and a bare template does
    # not overrule an explicit yes.
    nein = _faehigkeiten_aus_props(
        {
            "chat_template": "{%- if tools %}{{ tool_call }}{% endif %}",
            "chat_template_caps": {"supports_tool_calls": False},
        }
    )
    assert nein["tool_calls"] is False
    ja = _faehigkeiten_aus_props(
        {"chat_template": "nichts", "chat_template_caps": {"supports_tool_calls": True}}
    )
    assert ja["tool_calls"] is True


def test_ohne_caps_zaehlt_das_template():
    # Older servers serve no chat_template_caps — there the template remains.
    alt = _faehigkeiten_aus_props({"chat_template": "{%- if tools %}…{% endif %}"})
    assert alt["tool_calls"] is True
    assert _faehigkeiten_aus_props({})["tool_calls"] is False


async def test_props_anfrage_traegt_den_schluessel(monkeypatch):
    # Newer llama-server builds guard /props like every other route: without
    # the key the answer is 401 and the detection read as "can nothing".
    import httpx

    gesehen = {}

    def handler(request):
        gesehen["auth"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={
                "chat_template_caps": {"supports_tool_calls": True},
                "modalities": {"vision": False},
            },
        )

    echter_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: echter_client(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setenv("EXE_TEST_SCHLUESSEL", "geheim")
    ergebnis = await _faehigkeiten_erkennen("http://127.0.0.1:9/v1", 1.0, "EXE_TEST_SCHLUESSEL")
    assert gesehen["auth"] == "Bearer geheim"
    assert ergebnis == {"thinking": False, "tool_calls": True, "vision": False}


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


def test_meta_traegt_die_schalter(client):
    daten = client.get("/api/v1/meta").json()
    assert daten["features"]["document_upload"] is True
