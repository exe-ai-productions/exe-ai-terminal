"""Provider for everything that speaks the OpenAI interface.

This covers: mlx_lm.server, mlx_vlm.server, llama.cpp (llama-server),
Ollama, vLLM and the cloud providers with an OpenAI-compatible API.

Two quirks from practice are baked in here:

  * ``mlx_lm.server`` interprets the ``model`` field as a HuggingFace id and
    answers a short name with 404. For such servers the field is omitted as
    long as the server reports no id.
  * The servers deliver the chain of thought differently: as its own field
    (``delta.reasoning`` or ``delta.reasoning_content``) or as markers in
    the text. Both are brought to the same output here.
"""

from __future__ import annotations

import json
import os
import logging
import re
import time
from typing import Any, AsyncIterator

import httpx

from app.config import EndpointConfig
from app.parameter import uebersetzen
from app.pfade import ist_pfad
from app.providers.base import (
    ChatNachricht,
    Generierungsanfrage,
    Provider,
    ProviderFehler,
    Stueck,
    Werkzeugaufruf,
)
from app.reasoning import ReasoningParser

log = logging.getLogger(__name__)


def tempo_ermitteln(
    *,
    zeitmessung: dict[str, Any] | None,
    nutzung: dict[str, Any] | None,
    haeppchen: int,
    dauer: float,
    erstes_token_nach: float | None,
) -> dict[str, Any]:
    """Calculates the generation speed the way the model servers do themselves.

    The same formula applies everywhere — generated tokens divided by the
    pure **generation time**. Prompt processing is explicitly outside of it:
    it gets its own number via ``erstes_token_nach_sekunden`` and is never
    included. Before, the total duration went into the denominator, so the
    reported number sank the longer the chat got — on the first call after a
    model start it was off by a factor of 48 (measured against mlx_vlm and
    llama.cpp).

    Three sources, best first:

      * ``server``    — the ``timings`` block from llama.cpp/mlx. Tokens and
        generation time come from the machine where it happened.
      * ``gemessen``  — ``usage.completion_tokens`` (the truth counted by the
        server's tokenizer) against our own timing.
      * ``geschaetzt`` — just counted chunks. A chunk is not necessarily a
        token; that is why this tier is named the way it is.
    """
    zeitmessung = zeitmessung or {}
    nutzung = nutzung or {}

    # What we can measure ourselves: everything after the first token. If
    # that moment is missing, nothing arrived anyway.
    eigene_erzeugungszeit = dauer
    if erstes_token_nach is not None and dauer > erstes_token_nach:
        eigene_erzeugungszeit = dauer - erstes_token_nach

    tokens: int | None = None
    erzeugungszeit: float | None = None
    quelle = "geschaetzt"

    if zeitmessung.get("predicted_n") and zeitmessung.get("predicted_ms"):
        tokens = int(zeitmessung["predicted_n"])
        erzeugungszeit = float(zeitmessung["predicted_ms"]) / 1000
        quelle = "server"
    elif nutzung.get("completion_tokens"):
        tokens = int(nutzung["completion_tokens"])
        erzeugungszeit = eigene_erzeugungszeit
        quelle = "gemessen"
    elif haeppchen:
        tokens = haeppchen
        erzeugungszeit = eigene_erzeugungszeit

    # How big the prompt was is told by `usage` — and completely. The
    # `timings` block at this point only counts what really had to be newly
    # processed; in an ongoing chat the rest sits in the cache and is missing
    # there (measured: 524 instead of 1501 with 977 cached).
    prompt_tokens = nutzung.get("prompt_tokens") or zeitmessung.get("prompt_n")

    return {
        "erzeugte_tokens": tokens,
        "erzeugungs_sekunden": round(erzeugungszeit, 3) if erzeugungszeit else None,
        "prompt_tokens": int(prompt_tokens) if prompt_tokens else None,
        "tokens_pro_sekunde": (
            round(tokens / erzeugungszeit, 2) if tokens and erzeugungszeit else None
        ),
        "tempo_quelle": quelle if tokens else None,
    }


class _WerkzeugSammler:
    """Reassembles streamed tool calls.

    The servers do not send a call in one piece but in fragments: id and
    name in the first packet, the arguments spread character by character
    over the following ones ("{", "\\"ort\\":\\"", "Berlin", "\\"", "}"). It is
    held together via the ``index`` field. Only when the stream ends is the
    call complete — nothing may be executed before that.
    """

    def __init__(self) -> None:
        self._teile: dict[int, dict[str, str]] = {}

    def aufnehmen(self, rohaufrufe: list[dict[str, Any]]) -> None:
        for rohaufruf in rohaufrufe:
            index = rohaufruf.get("index", 0)
            eintrag = self._teile.setdefault(index, {"id": "", "name": "", "argumente": ""})
            if kennung := rohaufruf.get("id"):
                eintrag["id"] = kennung
            funktion = rohaufruf.get("function") or {}
            if name := funktion.get("name"):
                eintrag["name"] = name
            if (argumente := funktion.get("arguments")) is not None:
                eintrag["argumente"] += argumente

    @property
    def leer(self) -> bool:
        return not self._teile

    def fertige_aufrufe(self) -> list[Werkzeugaufruf]:
        aufrufe: list[Werkzeugaufruf] = []
        for index, eintrag in sorted(self._teile.items()):
            if not eintrag["name"]:
                continue
            rohargumente = eintrag["argumente"].strip() or "{}"
            try:
                argumente = json.loads(rohargumente)
            except json.JSONDecodeError:
                log.warning(
                    "Werkzeugaufruf '%s' hat unlesbare Argumente: %r",
                    eintrag["name"],
                    rohargumente[:200],
                )
                argumente = {}
            if not isinstance(argumente, dict):
                argumente = {"wert": argumente}
            aufrufe.append(
                Werkzeugaufruf(
                    id=eintrag["id"] or f"aufruf_{index}",
                    name=eintrag["name"],
                    argumente=argumente,
                )
            )
        return aufrufe


class OpenAIKompatiblerProvider(Provider):
    def __init__(self, endpunkt: EndpointConfig, timeout: float = 600.0) -> None:
        super().__init__(endpunkt)
        self.timeout = timeout

    @property
    def _kopfzeilen(self) -> dict[str, str]:
        """Access key, in case the endpoint demands one.

        The key is never in config.yaml, only the NAME of its environment
        variable. It is read fresh on every request — so a key changed in
        .env takes effect without a restart.

        If the variable is missing, requests go out without the header and
        the provider answers with 401. That is intentional: a silent
        workaround would be worse than a clear error message.
        """
        name = self.endpunkt.api_key_env
        if not name:
            return {}
        wert = os.getenv(name, "").strip()
        return {"Authorization": f"Bearer {wert}"} if wert else {}

    # --- Reachability ----------------------------------------------------

    async def erreichbar(self, timeout: float = 3.0) -> bool:
        adresse = f"{self.endpunkt.base_url}{self.endpunkt.health_path}"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._kopfzeilen) as client:
                antwort = await client.get(adresse)
            # 401/403 means: the server is up but will not let us in —
            # usually a missing or wrong key. Reporting that as "reachable"
            # would be a lie: the endpoint would appear in the model picker
            # and fail on every request. Better honestly unreachable.
            if antwort.status_code in (401, 403):
                return False
            return antwort.status_code < 500
        except (httpx.HTTPError, OSError):
            return False

    async def modellname(self, timeout: float = 3.0) -> str | None:
        """What the model is called on the server — the server itself is asked.

        The same address that is already queried for the sign of life
        ({base_url}{health_path}, i.e. /v1/models); before, the answer was
        just thrown away.

        Two formats occur:

        * {"data": [{"id": ...}]} — the usual OpenAI layout, this is how
          mlx_lm.server answers.
        * {"models": [{"name": ...}]} — this is how llama-server answers.

        **File paths are deferred, not discarded.** mlx_lm.server often
        reports the same model twice: once under its id and once under the
        path in the HuggingFace cache — then the clean id wins.
        mlx_vlm.server, on the other hand, sometimes reports **only one**
        entry, and that is the path to the locally loaded model (not a
        HuggingFace cache path, but for example
        ``/Users/you/models/Qwen3.6-27B-MLX-8bit``). If there were no
        fallback tier here, ``modellname()`` would find nothing,
        ``anfrage.modell`` would stay empty, the ``model`` field would be
        omitted from the request — and mlx_vlm.server, unlike mlx_lm.server,
        strictly requires it and answers without it with 422.

        **The return value here is always the full, unchanged id** — even
        when it is a path. Tested: mlx_vlm.server accepts in the ``model``
        field only exactly what it reported itself; a shortened name is
        misunderstood as a HuggingFace repo and fails. The shortening for
        the UI (the full path would reveal the local user name) therefore
        happens NOT here but exclusively at display time in
        ``EndpunktZustand.anzeigename`` (``discovery.py``) — the server
        always gets the original.
        """
        adresse = f"{self.endpunkt.base_url}{self.endpunkt.health_path}"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._kopfzeilen) as client:
                antwort = await client.get(adresse)
            if antwort.status_code >= 400:
                return None
            daten = antwort.json()
        except (httpx.HTTPError, OSError, ValueError):
            return None

        eintraege = daten.get("data") or daten.get("models") or []
        if not isinstance(eintraege, list):
            return None
        pfad_rueckfall: str | None = None
        for eintrag in eintraege:
            if not isinstance(eintrag, dict):
                continue
            kennung = eintrag.get("id") or eintrag.get("name") or eintrag.get("model")
            if not isinstance(kennung, str) or not kennung.strip():
                continue
            kennung = kennung.strip()
            if ist_pfad(kennung):
                if pfad_rueckfall is None:
                    pfad_rueckfall = kennung
                continue
            return kennung
        return pfad_rueckfall

    async def modelle_auflisten(self, timeout: float = 3.0) -> list[str]:
        """Every model the server reports, in the order it reports them.

        Same address as the sign of life. A local server names the one model
        it has loaded; a provider in the cloud names its whole catalogue.
        Paths are dropped here, unlike in `modellname`: they are how a local
        server refers to its own file, never something to choose from a list.
        """
        adresse = f"{self.endpunkt.base_url}{self.endpunkt.health_path}"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._kopfzeilen) as client:
                antwort = await client.get(adresse)
            if antwort.status_code >= 400:
                return []
            daten = antwort.json()
        except (httpx.HTTPError, OSError, ValueError):
            return []

        eintraege = daten.get("data") or daten.get("models") or []
        if not isinstance(eintraege, list):
            return []
        namen: list[str] = []
        for eintrag in eintraege:
            if not isinstance(eintrag, dict):
                continue
            kennung = eintrag.get("id") or eintrag.get("name") or eintrag.get("model")
            if not isinstance(kennung, str) or not kennung.strip():
                continue
            kennung = kennung.strip()
            if ist_pfad(kennung) or kennung in namen:
                continue
            namen.append(kennung)
        return namen

    async def kontextgroesse(self, timeout: float = 3.0) -> int | None:
        """Queries the context size from the server.

        A configured value wins. Otherwise ``/props`` is tried — llama.cpp
        answers it with ``n_ctx``. Servers that do not know it (e.g.
        mlx_lm.server) answer with 404, and then there simply is no number
        instead of an invented one.

        ``/props`` sits at the root, not under ``/v1`` — hence the version
        segment is cut off.
        """
        if self.endpunkt.context_tokens:
            return self.endpunkt.context_tokens

        wurzel = re.sub(r"/v\d+$", "", self.endpunkt.base_url)
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._kopfzeilen) as client:
                antwort = await client.get(f"{wurzel}/props")
            if antwort.status_code != 200:
                return None
            daten = antwort.json()
        except (httpx.HTTPError, OSError, ValueError):
            return None

        wert = (daten.get("default_generation_settings") or {}).get("n_ctx") or daten.get("n_ctx")
        return int(wert) if isinstance(wert, (int, float)) and wert > 0 else None

    # --- Streaming -------------------------------------------------------

    @staticmethod
    def _nachricht_bauen(nachricht: ChatNachricht) -> dict[str, Any]:
        eintrag: dict[str, Any] = {"role": nachricht.role, "content": nachricht.content}
        if nachricht.bild_url:
            # OpenAI image format: content becomes an array of text and
            # image. The text part is dropped when nothing was typed — an
            # empty text confuses some servers.
            teile: list[dict[str, Any]] = []
            if nachricht.content:
                teile.append({"type": "text", "text": nachricht.content})
            teile.append({"type": "image_url", "image_url": {"url": nachricht.bild_url}})
            eintrag["content"] = teile
        if nachricht.werkzeugaufrufe:
            eintrag["tool_calls"] = [
                {
                    "id": aufruf.id,
                    "type": "function",
                    "function": {
                        "name": aufruf.name,
                        "arguments": json.dumps(aufruf.argumente, ensure_ascii=False),
                    },
                }
                for aufruf in nachricht.werkzeugaufrufe
            ]
        if nachricht.werkzeugaufruf_id:
            eintrag["tool_call_id"] = nachricht.werkzeugaufruf_id
        return eintrag

    def _koerper_bauen(self, anfrage: Generierungsanfrage) -> dict[str, Any]:
        koerper: dict[str, Any] = {
            "messages": [self._nachricht_bauen(n) for n in anfrage.nachrichten],
            "stream": True,
        }
        if self.endpunkt.send_usage_option:
            # Without this request most servers send no token counts while
            # streaming — and the context display would stay empty.
            koerper["stream_options"] = {"include_usage": True}
        if anfrage.werkzeuge:
            koerper["tools"] = anfrage.werkzeuge
            koerper["tool_choice"] = "auto"
        # Only send what is actually set — otherwise null values override the
        # server's defaults.
        # First the three main values, then everything else — both under our
        # own names, translated into the backend's dialect. What the server
        # does not know is dropped instead of making it reject with an error.
        eigene = dict(anfrage.parameter)
        if anfrage.temperature is not None:
            eigene["temperature"] = anfrage.temperature
        if anfrage.top_p is not None:
            eigene["top_p"] = anfrage.top_p
        if anfrage.max_tokens is not None:
            eigene["max_tokens"] = anfrage.max_tokens
        koerper.update(uebersetzen(self.endpunkt.parameter_dialect, eigene))
        # OpenAI's newer chat models reject max_tokens and expect
        # max_completion_tokens; every current OpenAI model accepts the new
        # name. Other OpenAI-compatible servers still want max_tokens, so
        # only api.openai.com is rewritten.
        if "api.openai.com" in self.endpunkt.base_url and "max_tokens" in koerper:
            koerper["max_completion_tokens"] = koerper.pop("max_tokens")
        # Only when the server has reported an id. Without one the field is
        # dropped: llama.cpp ignores it anyway, and mlx_lm.server answers an
        # invented id with 404.
        if anfrage.modell:
            koerper["model"] = anfrage.modell
        koerper.update(anfrage.zusatz)
        return koerper

    async def streamen(self, anfrage: Generierungsanfrage) -> AsyncIterator[Stueck]:
        adresse = f"{self.endpunkt.base_url}/chat/completions"
        koerper = self._koerper_bauen(anfrage)
        parser = ReasoningParser(
            self.endpunkt.reasoning_format
            if self.endpunkt.reasoning_format != "native"
            else "none"
        )

        beginn = time.monotonic()
        erstes_token_nach: float | None = None
        token_gezaehlt = 0
        nutzung: dict[str, Any] = {}
        zeitmessung: dict[str, Any] = {}
        sammler = _WerkzeugSammler()

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self._kopfzeilen) as client:
                async with client.stream("POST", adresse, json=koerper) as antwort:
                    if antwort.status_code >= 400:
                        rohtext = (await antwort.aread()).decode("utf-8", "replace")
                        raise ProviderFehler(
                            f"{self.name} antwortete mit {antwort.status_code}: {rohtext[:400]}"
                        )

                    async for zeile in antwort.aiter_lines():
                        if not zeile or not zeile.startswith("data:"):
                            continue
                        nutzlast = zeile[5:].strip()
                        if nutzlast == "[DONE]":
                            break
                        try:
                            paket = json.loads(nutzlast)
                        except json.JSONDecodeError:
                            log.warning("Unlesbares Paket von %s: %r", self.id, nutzlast[:200])
                            continue

                        if verbrauch := paket.get("usage"):
                            nutzung = verbrauch

                        # llama.cpp and mlx include their own timing
                        # (`timings`) — not an OpenAI standard, but the best
                        # source there is: only the server itself knows how
                        # long the pure generating took, without the prompt
                        # processing before it. Only the complete block at
                        # the end is taken; mlx sends an interim value on
                        # every chunk, and it jumps from zero via 6 up to
                        # 14625 tok/s (measured).
                        messung = paket.get("timings")
                        if (
                            isinstance(messung, dict)
                            and messung.get("predicted_n")
                            and messung.get("predicted_ms")
                        ):
                            zeitmessung = messung

                        auswahl = (paket.get("choices") or [{}])[0]
                        delta = auswahl.get("delta") or {}

                        # Dedicated field for the chain of thought (Gemma 4 and others).
                        gedanke = delta.get("reasoning") or delta.get("reasoning_content")
                        if gedanke:
                            # Counts toward the speed: the model generates
                            # tokens here just as with visible text.
                            # Otherwise a model with a long chain of thought
                            # reports absurdly low values.
                            if erstes_token_nach is None:
                                erstes_token_nach = time.monotonic() - beginn
                            token_gezaehlt += 1
                            yield Stueck("reasoning", gedanke)

                        # Tool calls arrive in pieces — collect first.
                        if rohaufrufe := delta.get("tool_calls"):
                            sammler.aufnehmen(rohaufrufe)

                        inhalt = delta.get("content")
                        if inhalt:
                            if erstes_token_nach is None:
                                erstes_token_nach = time.monotonic() - beginn
                            token_gezaehlt += 1
                            for sorte, text in parser.feed(inhalt):
                                yield Stueck(sorte, text)

            for sorte, text in parser.finish():
                yield Stueck(sorte, text)

            # Only now are the arguments complete and allowed to be executed.
            if not sammler.leer:
                aufrufe = sammler.fertige_aufrufe()
                if aufrufe:
                    yield Stueck("tool_call", werkzeugaufrufe=aufrufe)

        except ProviderFehler:
            raise
        except httpx.HTTPError as fehler:
            raise ProviderFehler(f"{self.name} nicht erreichbar: {fehler}") from fehler

        dauer = time.monotonic() - beginn
        yield Stueck(
            "stats",
            daten={
                "dauer_sekunden": round(dauer, 3),
                "erstes_token_nach_sekunden": (
                    round(erstes_token_nach, 3) if erstes_token_nach is not None else None
                ),
                "haeppchen": token_gezaehlt,
                **tempo_ermitteln(
                    zeitmessung=zeitmessung,
                    nutzung=nutzung,
                    haeppchen=token_gezaehlt,
                    dauer=dauer,
                    erstes_token_nach=erstes_token_nach,
                ),
                "nutzung": nutzung or None,
                "endpunkt": self.id,
            },
        )
