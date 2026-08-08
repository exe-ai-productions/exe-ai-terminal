"""The OpenAI-compatible provider against a rebuilt model server.

This module talks to every model server — mlx_lm, mlx_vlm, llama.cpp,
Ollama, vLLM and the cloud providers. Trying it by hand against Mana is
not enough: the quirks of the other servers (their own reasoning field,
Harmony markers, 404 on the `model` field) never show up there.

Hence a small, real HTTP server here that behaves like the various model
servers — including Server-Sent Events over real network connections.
"""

from __future__ import annotations

import asyncio
import json
import socket

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import EndpointConfig
from app.providers import ChatNachricht, Generierungsanfrage, ProviderFehler
from app.providers.openai_kompatibel import OpenAIKompatiblerProvider, tempo_ermitteln


class ModellServerAttrappe:
    """Behaves like an OpenAI-compatible server, configurable per test."""

    def __init__(self) -> None:
        self.pakete: list[dict] = []
        # Raw SSE lines, in case a test wants to send something that is not
        # valid JSON. Takes precedence over self.pakete.
        self.rohzeilen: list[str] | None = None
        self.status = 200
        self.fehlertext = "kaputt"
        self.empfangene_koerper: list[dict] = []
        self.app = FastAPI()

        # Configurable, because the servers answer very differently here:
        # mlx_lm in the OpenAI layout, llama-server with its own list.
        self.modell_antwort: dict = {"object": "list", "data": [{"id": "testmodell"}]}

        @self.app.get("/v1/models")
        async def modelle():
            return self.modell_antwort

        @self.app.post("/v1/chat/completions")
        async def completions(request: Request):
            koerper = await request.json()
            self.empfangene_koerper.append(koerper)

            if self.status >= 400:
                return JSONResponse({"error": self.fehlertext}, status_code=self.status)

            async def strom():
                if self.rohzeilen is not None:
                    for zeile in self.rohzeilen:
                        yield zeile
                        await asyncio.sleep(0)
                else:
                    for paket in self.pakete:
                        yield f"data: {json.dumps(paket)}\n\n"
                        await asyncio.sleep(0)
                yield "data: [DONE]\n\n"

            return StreamingResponse(strom(), media_type="text/event-stream")

    def inhalt_senden(self, *texte: str) -> None:
        """Prepares normal text packets."""
        self.pakete = [
            {"choices": [{"delta": {"content": text}, "index": 0}]} for text in texte
        ]

    def rohpakete(self, pakete: list[dict]) -> None:
        self.pakete = pakete


@pytest.fixture
async def modellserver():
    attrappe = ModellServerAttrappe()

    lauscher = socket.socket()
    lauscher.bind(("127.0.0.1", 0))
    port = lauscher.getsockname()[1]
    lauscher.close()

    server = uvicorn.Server(
        uvicorn.Config(attrappe.app, host="127.0.0.1", port=port, log_level="error")
    )
    aufgabe = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)

    attrappe.basis = f"http://127.0.0.1:{port}/v1"
    try:
        yield attrappe
    finally:
        server.should_exit = True
        await aufgabe


def _provider(basis: str, **felder) -> OpenAIKompatiblerProvider:
    endpunkt = EndpointConfig.model_validate(
        {"id": "prueflabor", "name": "Prüflabor", "base_url": basis, **felder}
    )
    return OpenAIKompatiblerProvider(endpunkt)


async def _einsammeln(provider, anfrage=None):
    anfrage = anfrage or Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="Hallo")]
    )
    stuecke = []
    async for stueck in provider.streamen(anfrage):
        stuecke.append(stueck)
    return stuecke


def _text(stuecke, sorte: str) -> str:
    return "".join(s.text for s in stuecke if s.sorte == sorte)


# --- Reachability ---------------------------------------------------------


@pytest.mark.asyncio
async def test_erreichbar_wenn_der_server_antwortet(modellserver):
    assert await _provider(modellserver.basis).erreichbar() is True


@pytest.mark.asyncio
async def test_nicht_erreichbar_ohne_server():
    # Port 9 is the discard service and accepts no HTTP connection.
    assert await _provider("http://127.0.0.1:9/v1").erreichbar(timeout=1) is False


@pytest.mark.asyncio
async def test_erreichbarkeit_wirft_keine_ausnahme_bei_kaputtem_namen():
    provider = _provider("http://gibt-es-nicht.invalid/v1")
    assert await provider.erreichbar(timeout=2) is False


# --- Streaming -----------------------------------------------------------


@pytest.mark.asyncio
async def test_inhalt_kommt_haeppchenweise_an(modellserver):
    modellserver.inhalt_senden("Guten ", "Tag", "!")
    stuecke = await _einsammeln(_provider(modellserver.basis))
    assert _text(stuecke, "content") == "Guten Tag!"


@pytest.mark.asyncio
async def test_messwerte_werden_erhoben(modellserver):
    modellserver.inhalt_senden("a", "b", "c")
    stuecke = await _einsammeln(_provider(modellserver.basis))
    messwerte = next(s for s in stuecke if s.sorte == "stats").daten
    assert messwerte["haeppchen"] == 3
    assert messwerte["dauer_sekunden"] >= 0
    assert messwerte["erstes_token_nach_sekunden"] is not None
    assert messwerte["endpunkt"] == "prueflabor"


# --- Speed ----------------------------------------------------------------
#
# Calculated the same way the model servers do it themselves: generated
# tokens divided by pure generation time. Prompt processing stays out of it.


def test_tempo_kommt_am_liebsten_vom_server():
    """The `timings` block beats everything else — it measures at the source."""
    werte = tempo_ermitteln(
        zeitmessung={"predicted_n": 60, "predicted_ms": 2580.0, "prompt_n": 21},
        nutzung={"completion_tokens": 60},
        haeppchen=55,
        dauer=99.0,  # deliberately absurd: must play no role
        erstes_token_nach=0.5,
    )
    assert werte["tokens_pro_sekunde"] == 23.26
    assert werte["erzeugte_tokens"] == 60
    assert werte["tempo_quelle"] == "server"


def test_promptgroesse_kommt_aus_usage_nicht_aus_timings():
    """`timings.prompt_n` counts only what was newly processed, not the cache.

    Measured against llama.cpp: 1501 prompt tokens, 977 of them from the
    cache — `prompt_n` read 524. For "how big was the prompt" that is the
    wrong number.
    """
    werte = tempo_ermitteln(
        zeitmessung={"predicted_n": 10, "predicted_ms": 500.0, "prompt_n": 524},
        nutzung={"prompt_tokens": 1501},
        haeppchen=10, dauer=3.0, erstes_token_nach=1.0,
    )
    assert werte["prompt_tokens"] == 1501


def test_ohne_timings_zaehlt_usage_auf_eigener_zeit():
    werte = tempo_ermitteln(
        zeitmessung={},
        nutzung={"completion_tokens": 40, "prompt_tokens": 900},
        haeppchen=37,
        dauer=6.0,
        erstes_token_nach=2.0,
    )
    # 40 tokens in the 4 s AFTER the first token — not in 6 s.
    assert werte["tokens_pro_sekunde"] == 10.0
    assert werte["erzeugungs_sekunden"] == 4.0
    assert werte["tempo_quelle"] == "gemessen"


def test_ohne_alles_bleiben_die_haeppchen_und_heissen_geschaetzt():
    werte = tempo_ermitteln(
        zeitmessung={}, nutzung={}, haeppchen=20, dauer=5.0, erstes_token_nach=1.0
    )
    assert werte["tokens_pro_sekunde"] == 5.0
    assert werte["tempo_quelle"] == "geschaetzt"


def test_die_promptverarbeitung_zieht_das_tempo_nicht_mehr_herunter():
    """The old bug: long prompt = absurdly low number.

    Measured against mlx_vlm with a cold model: 8 tokens generated in 0.79 s,
    preceded by 37.4 s of prompt processing. The old math reported 0.2 tok/s.
    """
    werte = tempo_ermitteln(
        zeitmessung={}, nutzung={"completion_tokens": 8}, haeppchen=8,
        dauer=38.2, erstes_token_nach=37.4,
    )
    assert werte["tokens_pro_sekunde"] == 10.0
    assert round(8 / 38.2, 2) == 0.21  # what would have been shown before


def test_ohne_ein_einziges_token_gibt_es_kein_tempo():
    werte = tempo_ermitteln(
        zeitmessung={}, nutzung={}, haeppchen=0, dauer=3.0, erstes_token_nach=None
    )
    assert werte["tokens_pro_sekunde"] is None
    assert werte["tempo_quelle"] is None


@pytest.mark.asyncio
async def test_zwischenwerte_von_mlx_werden_verworfen(modellserver):
    """mlx sends `timings` on every chunk — with garbage values along the way.

    Measured against a live mlx server: the same response reports `null`
    along the way, then 6.6, then 14625 tok/s. Only the complete block
    at the end carries `predicted_n` and `predicted_ms` and may count.
    """
    modellserver.rohpakete(
        [
            {
                "choices": [{"delta": {"content": "a"}, "index": 0}],
                "timings": {"predicted_per_second": None},
            },
            {
                "choices": [{"delta": {"content": "b"}, "index": 0}],
                "timings": {"predicted_per_second": 14625.2},
            },
            {
                "choices": [],
                "usage": {"completion_tokens": 2},
                "timings": {"predicted_n": 2, "predicted_ms": 100.0},
            },
        ]
    )
    stuecke = await _einsammeln(_provider(modellserver.basis))
    messwerte = next(s for s in stuecke if s.sorte == "stats").daten
    assert messwerte["tokens_pro_sekunde"] == 20.0
    assert messwerte["tempo_quelle"] == "server"


@pytest.mark.asyncio
async def test_nutzungsangaben_werden_uebernommen(modellserver):
    modellserver.rohpakete(
        [
            {"choices": [{"delta": {"content": "x"}, "index": 0}]},
            {"choices": [{"delta": {}, "index": 0}], "usage": {"total_tokens": 42}},
        ]
    )
    stuecke = await _einsammeln(_provider(modellserver.basis))
    messwerte = next(s for s in stuecke if s.sorte == "stats").daten
    assert messwerte["nutzung"]["total_tokens"] == 42


@pytest.mark.asyncio
async def test_unlesbares_paket_wird_uebersprungen(modellserver):
    """A broken packet must not shoot down the whole stream."""
    modellserver.rohzeilen = [
        'data: {"choices": [{"delta": {"content": "vorher"}}]}\n\n',
        "data: das ist kein json\n\n",
        ": ein Kommentar, den Server zum Offenhalten schicken\n\n",
        "\n",
        'data: {"choices": [{"delta": {"content": "nachher"}}]}\n\n',
    ]
    stuecke = await _einsammeln(_provider(modellserver.basis))
    assert _text(stuecke, "content") == "vorhernachher"


# --- Reasoning in all three formats ---------------------------------------


@pytest.mark.asyncio
async def test_natives_reasoning_feld(modellserver):
    """Gemma 4 delivers the reasoning in delta.reasoning."""
    modellserver.rohpakete(
        [
            {"choices": [{"delta": {"reasoning": "Ich überlege"}, "index": 0}]},
            {"choices": [{"delta": {"content": "Die Antwort"}, "index": 0}]},
        ]
    )
    stuecke = await _einsammeln(_provider(modellserver.basis, reasoning_format="native"))
    assert _text(stuecke, "reasoning") == "Ich überlege"
    assert _text(stuecke, "content") == "Die Antwort"


@pytest.mark.asyncio
async def test_gedankengang_zaehlt_beim_tempo_mit(modellserver):
    """Otherwise a model with long reasoning reports absurdly low values."""
    modellserver.rohpakete(
        [{"choices": [{"delta": {"reasoning": f"Schritt {i} "}, "index": 0}]} for i in range(9)]
        + [{"choices": [{"delta": {"content": "Antwort"}, "index": 0}]}]
    )
    stuecke = await _einsammeln(_provider(modellserver.basis, reasoning_format="native"))
    messwerte = next(s for s in stuecke if s.sorte == "stats").daten
    assert messwerte["haeppchen"] == 10


@pytest.mark.asyncio
async def test_reasoning_content_wird_auch_erkannt(modellserver):
    """Some servers call the field reasoning_content."""
    modellserver.rohpakete(
        [{"choices": [{"delta": {"reasoning_content": "Gedanke"}, "index": 0}]}]
    )
    stuecke = await _einsammeln(_provider(modellserver.basis, reasoning_format="native"))
    assert _text(stuecke, "reasoning") == "Gedanke"


@pytest.mark.asyncio
async def test_think_tags_ueber_paketgrenzen(modellserver):
    modellserver.inhalt_senden("<thi", "nk>Gedanke</thi", "nk>Antwort")
    stuecke = await _einsammeln(_provider(modellserver.basis, reasoning_format="think"))
    assert _text(stuecke, "reasoning") == "Gedanke"
    assert _text(stuecke, "content") == "Antwort"


@pytest.mark.asyncio
async def test_harmony_marker(modellserver):
    modellserver.inhalt_senden(
        "<|channel|>analysis<|message|>Denken<|end|>",
        "<|channel|>final<|message|>Antwort<|return|>",
    )
    stuecke = await _einsammeln(_provider(modellserver.basis, reasoning_format="harmony"))
    assert _text(stuecke, "reasoning") == "Denken"
    assert _text(stuecke, "content") == "Antwort"


@pytest.mark.asyncio
async def test_bei_native_wird_der_text_nicht_zerlegt(modellserver):
    """Otherwise a <think> in normal text would be wrongly swallowed."""
    modellserver.inhalt_senden("<think>kein Marker</think>")
    stuecke = await _einsammeln(_provider(modellserver.basis, reasoning_format="native"))
    assert _text(stuecke, "content") == "<think>kein Marker</think>"


# --- Request body ---------------------------------------------------------


@pytest.mark.asyncio
async def test_modellfeld_faellt_ohne_kennung_weg(modellserver):
    """Without a reported id, the field is not sent at all.

    mlx_lm.server interprets "model" as a HuggingFace id and answers
    anything else with 404. Sending nothing is better than guessing.
    """
    modellserver.inhalt_senden("x")
    anfrage = Generierungsanfrage(nachrichten=[ChatNachricht(role="user", content="Hi")])
    await _einsammeln(_provider(modellserver.basis), anfrage)
    assert "model" not in modellserver.empfangene_koerper[0]


@pytest.mark.asyncio
async def test_gemeldete_kennung_geht_unveraendert_mit(modellserver):
    """Whatever the server reports under /v1/models goes back exactly as is."""
    modellserver.inhalt_senden("x")
    anfrage = Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="Hi")],
        modell="zecanard/gemma-4-26B-A4B-it",
    )
    await _einsammeln(_provider(modellserver.basis), anfrage)
    assert modellserver.empfangene_koerper[0]["model"] == "zecanard/gemma-4-26B-A4B-it"


@pytest.mark.asyncio
async def test_nicht_gesetzte_parameter_werden_nicht_mitgeschickt(modellserver):
    """Otherwise null values would override the server's defaults."""
    modellserver.inhalt_senden("x")
    await _einsammeln(_provider(modellserver.basis))
    koerper = modellserver.empfangene_koerper[0]
    assert "temperature" not in koerper
    assert "top_p" not in koerper
    assert "max_tokens" not in koerper


@pytest.mark.asyncio
async def test_gesetzte_parameter_kommen_an(modellserver):
    modellserver.inhalt_senden("x")
    anfrage = Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="Hi")],
        temperature=0.4,
        top_p=0.9,
        max_tokens=256,
    )
    await _einsammeln(_provider(modellserver.basis), anfrage)
    koerper = modellserver.empfangene_koerper[0]
    assert (koerper["temperature"], koerper["top_p"], koerper["max_tokens"]) == (0.4, 0.9, 256)


@pytest.mark.asyncio
async def test_werkzeuge_werden_mitgeschickt(modellserver):
    modellserver.inhalt_senden("x")
    werkzeug = {"type": "function", "function": {"name": "suchen", "parameters": {}}}
    anfrage = Generierungsanfrage(
        nachrichten=[ChatNachricht(role="user", content="Hi")], werkzeuge=[werkzeug]
    )
    await _einsammeln(_provider(modellserver.basis), anfrage)
    koerper = modellserver.empfangene_koerper[0]
    assert koerper["tools"] == [werkzeug]
    assert koerper["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_werkzeugverlauf_wird_richtig_uebersetzt(modellserver):
    """Call and result must arrive in the format the servers expect."""
    from app.providers.base import Werkzeugaufruf

    modellserver.inhalt_senden("fertig")
    anfrage = Generierungsanfrage(
        nachrichten=[
            ChatNachricht(role="user", content="rechne"),
            ChatNachricht(
                role="assistant",
                content="",
                werkzeugaufrufe=[Werkzeugaufruf(id="a1", name="addieren", argumente={"a": 1})],
            ),
            ChatNachricht(role="tool", content="42", werkzeugaufruf_id="a1"),
        ]
    )
    await _einsammeln(_provider(modellserver.basis), anfrage)

    nachrichten = modellserver.empfangene_koerper[0]["messages"]
    assert nachrichten[1]["tool_calls"][0]["id"] == "a1"
    assert json.loads(nachrichten[1]["tool_calls"][0]["function"]["arguments"]) == {"a": 1}
    assert nachrichten[2]["tool_call_id"] == "a1"


# --- Tool calls from the stream -------------------------------------------


@pytest.mark.asyncio
async def test_zerstueckelter_werkzeugaufruf_wird_zusammengesetzt(modellserver):
    """Exactly the packet sequence llama.cpp sent for Mana."""
    modellserver.rohpakete(
        [
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "W1", "type": "function",
                 "function": {"name": "wetter", "arguments": "{"}}]}, "index": 0}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": '"ort":"'}}]}, "index": 0}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": "Berlin"}}]}, "index": 0}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"arguments": '"}'}}]}, "index": 0}]},
            {"choices": [{"delta": {}, "finish_reason": "tool_calls", "index": 0}]},
        ]
    )
    stuecke = await _einsammeln(_provider(modellserver.basis))
    aufrufe = next(s for s in stuecke if s.sorte == "tool_call").werkzeugaufrufe
    assert len(aufrufe) == 1
    assert aufrufe[0].id == "W1"
    assert aufrufe[0].name == "wetter"
    assert aufrufe[0].argumente == {"ort": "Berlin"}


@pytest.mark.asyncio
async def test_ohne_werkzeugaufruf_kein_tool_call_stueck(modellserver):
    modellserver.inhalt_senden("nur Text")
    stuecke = await _einsammeln(_provider(modellserver.basis))
    assert not [s for s in stuecke if s.sorte == "tool_call"]


# --- Errors ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_fehler_wird_zu_providerfehler(modellserver):
    modellserver.status = 404
    modellserver.fehlertext = "Model not found"
    with pytest.raises(ProviderFehler) as fehler:
        await _einsammeln(_provider(modellserver.basis))
    assert "404" in str(fehler.value)
    assert "Model not found" in str(fehler.value)


@pytest.mark.asyncio
async def test_serverfehler_wird_zu_providerfehler(modellserver):
    modellserver.status = 500
    with pytest.raises(ProviderFehler):
        await _einsammeln(_provider(modellserver.basis))


@pytest.mark.asyncio
async def test_nicht_erreichbarer_server_wird_zu_providerfehler():
    with pytest.raises(ProviderFehler) as fehler:
        await _einsammeln(_provider("http://127.0.0.1:9/v1"))
    assert "nicht erreichbar" in str(fehler.value)


# --- Model name from the server -------------------------------------------
#
# The name in the UI comes from the server, not from the configuration:
# nobody should have to maintain model names, least of all for third-party
# models they have never seen.


@pytest.mark.asyncio
async def test_modellname_aus_dem_openai_aufbau(modellserver):
    """mlx_lm.server and the cloud providers answer like this."""
    modellserver.modell_antwort = {"object": "list", "data": [{"id": "testmodell"}]}
    assert await _provider(modellserver.basis).modellname() == "testmodell"


@pytest.mark.asyncio
async def test_modellname_aus_der_llama_liste(modellserver):
    """llama-server answers with its own list under 'models'."""
    modellserver.modell_antwort = {
        "models": [{"name": "qwen3.6-35b-a3b", "model": "qwen3.6-35b-a3b"}]
    }
    assert await _provider(modellserver.basis).modellname() == "qwen3.6-35b-a3b"


@pytest.mark.asyncio
async def test_modellname_ueberspringt_dateipfade(modellserver):
    """mlx_lm.server reports the same model twice.

    Once under its id and once under its path in the HuggingFace cache.
    Even if the path comes first, it must not pass as the name — it says
    nothing about what is loaded.
    """
    modellserver.modell_antwort = {
        "object": "list",
        "data": [
            {"id": "/Users/wer/.cache/huggingface/hub/models--x--y/snapshots/abc123"},
            {"id": "zecanard/gemma-4-26B-A4B-it-MLX-6bit"},
        ],
    }
    name = await _provider(modellserver.basis).modellname()
    assert name == "zecanard/gemma-4-26B-A4B-it-MLX-6bit"


@pytest.mark.asyncio
async def test_modellname_schraegstrich_allein_ist_kein_pfad(modellserver):
    """'zecanard/gemma-4' is a perfectly normal model name, not a path."""
    modellserver.modell_antwort = {"object": "list", "data": [{"id": "org/modell-7b"}]}
    assert await _provider(modellserver.basis).modellname() == "org/modell-7b"


@pytest.mark.asyncio
async def test_modellname_leer_wenn_nichts_brauchbares_kommt(modellserver):
    """Then the fallback to the configuration entry kicks in."""
    modellserver.modell_antwort = {"object": "list", "data": []}
    assert await _provider(modellserver.basis).modellname() is None


@pytest.mark.asyncio
async def test_modellname_leer_bei_unbrauchbarer_antwort(modellserver):
    """A server that sends something completely different must break nothing."""
    modellserver.modell_antwort = {"irgendwas": "anderes"}
    assert await _provider(modellserver.basis).modellname() is None
