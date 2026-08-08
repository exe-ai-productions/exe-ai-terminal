"""Anthropic — its own provider, because its API is not OpenAI's.

Registering Anthropic under `openai_compatible` cannot work, and the
differences are not cosmetic:

* the route is `/v1/messages`, not `/v1/chat/completions`
* the key travels as `x-api-key`, not as `Authorization: Bearer`
* an `anthropic-version` header is mandatory
* the system prompt is a top-level field, not a message with role `system`
* `max_tokens` is required — leaving it out is an error, not a default
* tools have `input_schema` where OpenAI has `parameters`, and a tool result
  is a content block inside a user message rather than its own role
* the stream sends typed events (`content_block_delta`, `message_delta`)
  instead of choice deltas, and reasoning arrives as `thinking`, not as a
  parsed-out tag

What this file does is translate all of that in both directions, so the rest
of the terminal never learns that Anthropic is different.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, AsyncIterator

import httpx

from app.config import EndpointConfig
from app.parameter import uebersetzen
from app.providers.base import (
    ChatNachricht,
    Generierungsanfrage,
    Provider,
    ProviderFehler,
    Stueck,
    Werkzeugaufruf,
)

log = logging.getLogger(__name__)

# The version the API expects. It is not optional: without the header the
# request is rejected.
API_VERSION = "2023-06-01"

# Anthropic demands a limit and does not supply one. This is what applies when
# nothing was set — high enough not to cut off an answer mid-sentence.
MAX_TOKENS_VORGABE = 8192


class AnthropicProvider(Provider):
    def __init__(self, endpunkt: EndpointConfig, timeout: float = 600.0) -> None:
        super().__init__(endpunkt)
        self.timeout = timeout

    @property
    def _kopfzeilen(self) -> dict[str, str]:
        """Headers for every request.

        The key is never in config.yaml, only the NAME of its environment
        variable — same rule as everywhere else. It is read fresh each time,
        so a key changed in .env takes effect without a restart.
        """
        kopf = {
            "content-type": "application/json",
            "anthropic-version": API_VERSION,
        }
        name = self.endpunkt.api_key_env
        wert = os.getenv(name, "").strip() if name else ""
        if wert:
            kopf["x-api-key"] = wert
        return kopf

    # --- Sign of life and catalogue --------------------------------------

    async def erreichbar(self, timeout: float = 3.0) -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._kopfzeilen) as client:
                antwort = await client.get(f"{self.endpunkt.base_url}/models")
            # 401 means the address answers and the key is wrong — worth
            # distinguishing from a dead host, so it is logged, not swallowed.
            if antwort.status_code == 401:
                log.info("Anthropic antwortet, aber der Schlüssel wird abgelehnt")
                return False
            return antwort.status_code < 400
        except (httpx.HTTPError, OSError):
            return False

    async def modelle_auflisten(self, timeout: float = 3.0) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._kopfzeilen) as client:
                antwort = await client.get(f"{self.endpunkt.base_url}/models?limit=100")
            if antwort.status_code >= 400:
                return []
            daten = antwort.json()
        except (httpx.HTTPError, OSError, ValueError):
            return []
        namen = []
        for eintrag in daten.get("data") or []:
            kennung = eintrag.get("id") if isinstance(eintrag, dict) else None
            if isinstance(kennung, str) and kennung.strip():
                namen.append(kennung.strip())
        return namen

    async def modellname(self, timeout: float = 3.0) -> str | None:
        if self.endpunkt.modell:
            return self.endpunkt.modell
        namen = await self.modelle_auflisten(timeout)
        return namen[0] if namen else None

    # --- Translating a request -------------------------------------------

    @staticmethod
    def _werkzeuge_uebersetzen(werkzeuge: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """OpenAI tool definitions into Anthropic's shape.

        The registry speaks OpenAI everywhere, so the translation happens here
        rather than making every tool know two formats.
        """
        raus = []
        for w in werkzeuge:
            f = w.get("function") or {}
            if not f.get("name"):
                continue
            raus.append({
                "name": f["name"],
                "description": f.get("description", ""),
                "input_schema": f.get("parameters") or {"type": "object", "properties": {}},
            })
        return raus

    def _nachrichten_bauen(
        self, nachrichten: list[ChatNachricht]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Splits the history into system prompt and messages.

        Anthropic keeps the system prompt out of the conversation; a message
        with role `system` would be rejected. Tool results are content blocks
        in a user message, which is why they are folded into the previous one
        instead of standing alone.
        """
        system: list[str] = []
        raus: list[dict[str, Any]] = []

        for n in nachrichten:
            if n.role == "system":
                if n.content:
                    system.append(n.content)
                continue

            if n.role == "tool":
                block = {
                    "type": "tool_result",
                    "tool_use_id": n.werkzeugaufruf_id or "",
                    "content": n.content or "",
                }
                # Several results in a row belong into one user message —
                # Anthropic rejects two user turns following each other.
                if raus and raus[-1]["role"] == "user" and isinstance(raus[-1]["content"], list):
                    raus[-1]["content"].append(block)
                else:
                    raus.append({"role": "user", "content": [block]})
                continue

            if n.role == "assistant" and n.werkzeugaufrufe:
                bloecke: list[dict[str, Any]] = []
                if n.content:
                    bloecke.append({"type": "text", "text": n.content})
                for aufruf in n.werkzeugaufrufe:
                    bloecke.append({
                        "type": "tool_use",
                        "id": aufruf.id,
                        "name": aufruf.name,
                        "input": aufruf.argumente or {},
                    })
                raus.append({"role": "assistant", "content": bloecke})
                continue

            if n.bild_url:
                # Anthropic wants the raw base64 plus its media type, where
                # OpenAI takes the whole data URL.
                inhalt: list[dict[str, Any]] = []
                kopf, _, rumpf = n.bild_url.partition(",")
                typ = kopf.removeprefix("data:").removesuffix(";base64") or "image/png"
                inhalt.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": typ, "data": rumpf},
                })
                if n.content:
                    inhalt.append({"type": "text", "text": n.content})
                raus.append({"role": n.role, "content": inhalt})
                continue

            raus.append({"role": n.role, "content": n.content or ""})

        # An empty history would be rejected; better an empty turn than a 400.
        if not raus:
            raus.append({"role": "user", "content": ""})
        return ("\n\n".join(system) if system else None, raus)

    def _koerper_bauen(self, anfrage: Generierungsanfrage) -> dict[str, Any]:
        system, nachrichten = self._nachrichten_bauen(anfrage.nachrichten)
        koerper: dict[str, Any] = {
            "model": anfrage.modell or self.endpunkt.modell or "",
            "messages": nachrichten,
            "stream": True,
            # Required, not optional — a missing limit is an error here.
            "max_tokens": anfrage.max_tokens or MAX_TOKENS_VORGABE,
        }
        if system:
            koerper["system"] = system
        if anfrage.werkzeuge:
            werkzeuge = self._werkzeuge_uebersetzen(anfrage.werkzeuge)
            if werkzeuge:
                koerper["tools"] = werkzeuge

        eigene = dict(anfrage.parameter)
        if anfrage.temperature is not None:
            eigene["temperature"] = anfrage.temperature
        if anfrage.top_p is not None:
            eigene["top_p"] = anfrage.top_p
        uebersetzt = uebersetzen(self.endpunkt.parameter_dialect, eigene)
        # max_tokens is already set above and must not be overwritten by None.
        uebersetzt.pop("max_tokens", None)
        koerper.update(uebersetzt)
        koerper.update(anfrage.zusatz)
        return koerper

    # --- Streaming --------------------------------------------------------

    async def streamen(self, anfrage: Generierungsanfrage) -> AsyncIterator[Stueck]:
        """Translates Anthropic's typed events into our chunks.

        The shape is different from OpenAI's: content arrives as
        `content_block_delta`, a tool call is assembled from `content_block_start`
        plus a series of `input_json_delta` fragments, and the token counts
        come in `message_start` and `message_delta`.
        """
        adresse = f"{self.endpunkt.base_url}/messages"
        koerper = self._koerper_bauen(anfrage)

        beginn = time.monotonic()
        erstes_token_nach: float | None = None
        token_gezaehlt = 0
        eingang = 0
        ausgang = 0
        # Tool calls under construction, by block index: their arguments
        # arrive as a string in pieces and are only valid JSON at the end.
        offene: dict[int, dict[str, Any]] = {}
        fertige: list[Werkzeugaufruf] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self._kopfzeilen) as client:
                async with client.stream("POST", adresse, json=koerper) as antwort:
                    if antwort.status_code >= 400:
                        rohtext = (await antwort.aread()).decode("utf-8", "replace")
                        raise ProviderFehler(
                            f"{self.name} antwortete mit {antwort.status_code}: {rohtext[:400]}"
                        )

                    async for zeile in antwort.aiter_lines():
                        if not zeile.startswith("data:"):
                            continue
                        roh = zeile[5:].strip()
                        if not roh:
                            continue
                        try:
                            daten = json.loads(roh)
                        except ValueError:
                            continue

                        typ = daten.get("type")

                        if typ == "message_start":
                            nutzung = (daten.get("message") or {}).get("usage") or {}
                            eingang = nutzung.get("input_tokens") or 0

                        elif typ == "content_block_start":
                            block = daten.get("content_block") or {}
                            if block.get("type") == "tool_use":
                                offene[daten.get("index", 0)] = {
                                    "id": block.get("id") or "",
                                    "name": block.get("name") or "",
                                    "roh": "",
                                }

                        elif typ == "content_block_delta":
                            delta = daten.get("delta") or {}
                            art = delta.get("type")
                            if art == "text_delta":
                                text = delta.get("text") or ""
                                if text:
                                    if erstes_token_nach is None:
                                        erstes_token_nach = time.monotonic() - beginn
                                    token_gezaehlt += 1
                                    yield Stueck(sorte="content", text=text)
                            elif art == "thinking_delta":
                                # Reasoning arrives declared, so no tag has to
                                # be parsed out of the text as elsewhere.
                                gedanke = delta.get("thinking") or ""
                                if gedanke:
                                    yield Stueck(sorte="reasoning", text=gedanke)
                            elif art == "input_json_delta":
                                offen = offene.get(daten.get("index", 0))
                                if offen is not None:
                                    offen["roh"] += delta.get("partial_json") or ""

                        elif typ == "content_block_stop":
                            offen = offene.pop(daten.get("index", 0), None)
                            if offen and offen["name"]:
                                try:
                                    argumente = json.loads(offen["roh"] or "{}")
                                except ValueError:
                                    argumente = {}
                                fertige.append(Werkzeugaufruf(
                                    id=offen["id"], name=offen["name"],
                                    argumente=argumente if isinstance(argumente, dict) else {},
                                ))

                        elif typ == "message_delta":
                            nutzung = daten.get("usage") or {}
                            ausgang = nutzung.get("output_tokens") or ausgang

                        elif typ == "error":
                            fehler = daten.get("error") or {}
                            raise ProviderFehler(
                                f"{self.name}: {fehler.get('message') or 'unbekannter Fehler'}"
                            )

        except ProviderFehler:
            raise
        except (httpx.HTTPError, OSError) as fehler:
            raise ProviderFehler(f"{self.name} nicht erreichbar: {fehler}") from fehler

        if fertige:
            yield Stueck(sorte="tool_call", werkzeugaufrufe=fertige)

        dauer = time.monotonic() - beginn
        tokens = ausgang or token_gezaehlt
        yield Stueck(sorte="stats", daten={
            "dauer_sekunden": round(dauer, 3),
            "tokens": tokens,
            "prompt_tokens": eingang,
            "gesamt_tokens": eingang + tokens,
            "tokens_pro_sekunde": round(tokens / dauer, 2) if tokens and dauer else None,
            "erstes_token_nach_sekunden": (
                round(erstes_token_nach, 3) if erstes_token_nach is not None else None
            ),
            "tempo_quelle": "anthropic",
        })
