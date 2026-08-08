"""Anthropic speaks its own protocol — this pins down the translation.

Everything here is about the two directions: our request into the shape the
Messages API wants, and its typed stream events back into our chunks.
Nothing talks to the network; the stream is fed in as raw lines.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import EndpointConfig
from app.providers import provider_bauen
from app.providers.anthropic import API_VERSION, MAX_TOKENS_VORGABE, AnthropicProvider
from app.providers.base import ChatNachricht, Generierungsanfrage, Werkzeugaufruf


def endpunkt(**felder) -> EndpointConfig:
    return EndpointConfig.model_validate({
        "id": "anthropic",
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "parameter_dialect": "anthropic",
        "api_key_env": "TEST_ANTHROPIC_KEY",
        **felder,
    })


def bauen(**felder) -> AnthropicProvider:
    return AnthropicProvider(endpunkt(**felder))


# --- Registry -------------------------------------------------------------


def test_anthropic_ist_ein_eigener_anbieter():
    assert isinstance(provider_bauen(endpunkt()), AnthropicProvider)


# --- Headers --------------------------------------------------------------


def test_der_schluessel_reist_als_x_api_key(monkeypatch):
    """Not as a bearer token — the Messages API would reject that."""
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "geheim")
    kopf = bauen()._kopfzeilen
    assert kopf["x-api-key"] == "geheim"
    assert "Authorization" not in kopf


def test_die_version_reist_immer_mit(monkeypatch):
    monkeypatch.delenv("TEST_ANTHROPIC_KEY", raising=False)
    kopf = bauen()._kopfzeilen
    assert kopf["anthropic-version"] == API_VERSION
    # No key set: the header stays away and the API answers 401. A silent
    # workaround would be worse than a clear error.
    assert "x-api-key" not in kopf


# --- Request body ---------------------------------------------------------


def test_der_systemprompt_steht_oben_und_nicht_im_verlauf():
    koerper = bauen()._koerper_bauen(Generierungsanfrage(nachrichten=[
        ChatNachricht(role="system", content="Sei kurz."),
        ChatNachricht(role="user", content="Hallo"),
    ]))
    assert koerper["system"] == "Sei kurz."
    assert [n["role"] for n in koerper["messages"]] == ["user"]


def test_mehrere_systemnachrichten_werden_zu_einer():
    koerper = bauen()._koerper_bauen(Generierungsanfrage(nachrichten=[
        ChatNachricht(role="system", content="Eins"),
        ChatNachricht(role="system", content="Zwei"),
        ChatNachricht(role="user", content="Hallo"),
    ]))
    assert koerper["system"] == "Eins\n\nZwei"


def test_ohne_antwortlaenge_gilt_die_vorgabe():
    """max_tokens is required here — a missing limit is an error, not a default."""
    koerper = bauen()._koerper_bauen(Generierungsanfrage(nachrichten=[
        ChatNachricht(role="user", content="Hallo"),
    ]))
    assert koerper["max_tokens"] == MAX_TOKENS_VORGABE


def test_die_eingestellte_antwortlaenge_gewinnt():
    koerper = bauen()._koerper_bauen(Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="Hallo")],
        max_tokens=1234,
    ))
    assert koerper["max_tokens"] == 1234


def test_was_der_dialekt_nicht_kennt_faellt_weg():
    """Anthropic knows no seed and no penalties — sending them would be a 400."""
    koerper = bauen()._koerper_bauen(Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="Hallo")],
        temperature=0.7,
        parameter={"seed": 42, "presence_penalty": 1.0, "top_k": 20},
    ))
    assert koerper["temperature"] == 0.7
    assert koerper["top_k"] == 20
    assert "seed" not in koerper
    assert "presence_penalty" not in koerper


def test_werkzeuge_bekommen_input_schema_statt_parameters():
    koerper = bauen()._koerper_bauen(Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="Hallo")],
        werkzeuge=[{
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Führt aus",
                "parameters": {"type": "object", "properties": {"befehl": {"type": "string"}}},
            },
        }],
    ))
    assert koerper["tools"] == [{
        "name": "run_command",
        "description": "Führt aus",
        "input_schema": {"type": "object", "properties": {"befehl": {"type": "string"}}},
    }]


def test_ein_werkzeugaufruf_wird_zu_einem_block_der_antwort():
    koerper = bauen()._koerper_bauen(Generierungsanfrage(nachrichten=[
        ChatNachricht(role="user", content="Wie spät?"),
        ChatNachricht(
            role="assistant", content="",
            werkzeugaufrufe=[Werkzeugaufruf(id="a1", name="uhr", argumente={"ort": "Berlin"})],
        ),
        ChatNachricht(role="tool", content="12:00", werkzeugaufruf_id="a1"),
    ]))
    assistent = koerper["messages"][1]
    assert assistent["content"] == [
        {"type": "tool_use", "id": "a1", "name": "uhr", "input": {"ort": "Berlin"}}
    ]
    # The result is a block inside a user message, not a role of its own.
    assert koerper["messages"][2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "a1", "content": "12:00"}],
    }


def test_mehrere_ergebnisse_landen_in_einer_nachricht():
    """Two user turns in a row are rejected — they belong together."""
    koerper = bauen()._koerper_bauen(Generierungsanfrage(nachrichten=[
        ChatNachricht(role="user", content="Los"),
        ChatNachricht(
            role="assistant", content="",
            werkzeugaufrufe=[
                Werkzeugaufruf(id="a1", name="x"), Werkzeugaufruf(id="a2", name="y"),
            ],
        ),
        ChatNachricht(role="tool", content="eins", werkzeugaufruf_id="a1"),
        ChatNachricht(role="tool", content="zwei", werkzeugaufruf_id="a2"),
    ]))
    assert len(koerper["messages"]) == 3
    assert len(koerper["messages"][2]["content"]) == 2


def test_ein_bild_wird_in_rohdaten_und_medientyp_zerlegt():
    """Anthropic wants base64 plus media type, OpenAI takes the whole data URL."""
    koerper = bauen()._koerper_bauen(Generierungsanfrage(nachrichten=[
        ChatNachricht(role="user", content="Was ist das?",
                      bild_url="data:image/png;base64,AAAB"),
    ]))
    assert koerper["messages"][0]["content"][0] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": "AAAB"},
    }


# --- Stream ---------------------------------------------------------------


def strom(*ereignisse: dict) -> httpx.MockTransport:
    zeilen = "".join(f"data: {json.dumps(e)}\n\n" for e in ereignisse)
    return httpx.MockTransport(
        lambda _: httpx.Response(200, text=zeilen, headers={"content-type": "text/event-stream"})
    )


async def stuecke(provider: AnthropicProvider, transport, anfrage=None):
    original = httpx.AsyncClient

    def gefaelscht(**kwargs):
        kwargs["transport"] = transport
        return original(**kwargs)

    httpx.AsyncClient = gefaelscht
    try:
        return [s async for s in provider.streamen(
            anfrage or Generierungsanfrage(
                nachrichten=[ChatNachricht(role="user", content="Hallo")]
            )
        )]
    finally:
        httpx.AsyncClient = original


@pytest.mark.asyncio
async def test_text_kommt_als_inhalt_an():
    ergebnis = await stuecke(bauen(), strom(
        {"type": "message_start", "message": {"usage": {"input_tokens": 7}}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "Hallo "}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "Welt"}},
        {"type": "message_delta", "usage": {"output_tokens": 2}},
    ))
    assert "".join(s.text for s in ergebnis if s.sorte == "content") == "Hallo Welt"

    stats = [s for s in ergebnis if s.sorte == "stats"][0]
    assert stats.daten["prompt_tokens"] == 7
    assert stats.daten["tokens"] == 2


@pytest.mark.asyncio
async def test_gedanken_kommen_als_reasoning_an():
    """Declared, not parsed out of the text — no tag has to be hunted for."""
    ergebnis = await stuecke(bauen(), strom(
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "thinking_delta", "thinking": "Ich überlege"}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "Antwort"}},
    ))
    assert [(s.sorte, s.text) for s in ergebnis if s.sorte in ("reasoning", "content")] == [
        ("reasoning", "Ich überlege"),
        ("content", "Antwort"),
    ]


@pytest.mark.asyncio
async def test_ein_werkzeugaufruf_wird_aus_bruchstuecken_zusammengesetzt():
    ergebnis = await stuecke(bauen(), strom(
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "tool_use", "id": "t1", "name": "run_command"}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "input_json_delta", "partial_json": '{"befehl":'}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "input_json_delta", "partial_json": '"ls"}'}},
        {"type": "content_block_stop", "index": 0},
    ))
    aufrufe = [s for s in ergebnis if s.sorte == "tool_call"][0].werkzeugaufrufe
    assert len(aufrufe) == 1
    assert aufrufe[0].id == "t1"
    assert aufrufe[0].name == "run_command"
    assert aufrufe[0].argumente == {"befehl": "ls"}


@pytest.mark.asyncio
async def test_unlesbare_argumente_werfen_den_aufruf_nicht_weg():
    """Better an empty argument set than a call that vanishes silently."""
    ergebnis = await stuecke(bauen(), strom(
        {"type": "content_block_start", "index": 0,
         "content_block": {"type": "tool_use", "id": "t1", "name": "x"}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "input_json_delta", "partial_json": "{kaputt"}},
        {"type": "content_block_stop", "index": 0},
    ))
    aufrufe = [s for s in ergebnis if s.sorte == "tool_call"][0].werkzeugaufrufe
    assert aufrufe[0].argumente == {}


@pytest.mark.asyncio
async def test_ein_fehler_im_strom_wird_gemeldet():
    from app.providers.base import ProviderFehler

    with pytest.raises(ProviderFehler) as fehler:
        await stuecke(bauen(), strom(
            {"type": "error", "error": {"message": "overloaded"}},
        ))
    assert "overloaded" in str(fehler.value)


# --- Catalogue ------------------------------------------------------------


@pytest.mark.asyncio
async def test_die_modelle_kommen_vom_anbieter():
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json={"data": [
            {"id": "claude-opus-5"}, {"id": "claude-sonnet-5"},
        ]})
    )
    provider = bauen()
    original = httpx.AsyncClient

    def gefaelscht(**kwargs):
        kwargs["transport"] = transport
        return original(**kwargs)

    httpx.AsyncClient = gefaelscht
    try:
        assert await provider.modelle_auflisten() == ["claude-opus-5", "claude-sonnet-5"]
    finally:
        httpx.AsyncClient = original
