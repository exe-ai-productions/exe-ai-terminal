"""Which models are available right now?

The candidate list lives in the configuration and is maintained by hand.
What is dynamic is *reachability*: a background loop regularly knocks on all
candidates, and the frontend gets only the ones that actually answer via
``/api/v1/models``.

When an endpoint changes state, ``endpoint_status_changed`` is published —
whoever wants to react subscribes on the event bus, without this module
having to know about it.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from app import modellkennung
from app.config import Config, EndpointConfig
from app.db.connection import jetzt_iso
from app.events import Ereignisse, EventBus
from app.parameter import unterstuetzte
from app.pfade import ist_pfad, pfad_zu_anzeigename
from app.providers import Provider, provider_bauen

log = logging.getLogger(__name__)

# How many checks in a row may go unanswered before an endpoint counts as
# gone. Three, because a single silence says nothing: OpenAI's model list
# answers in half a second or not at all, and at one strike the models
# appeared and disappeared while you were looking at them. At fifteen seconds
# between checks, a provider now has to stay quiet for the better part of a
# minute before it drops out.
STILLE_BIS_WEG = 3


def denkschalter_im_template(template: str) -> bool:
    """Does the chat template say that thinking is switchable?

    llama.cpp serves the raw template via /props — Qwen-style templates
    carry `enable_thinking` there. Any further interpretation would be
    guesswork.
    """
    return "enable_thinking" in (template or "")


def werkzeuge_im_template(template: str) -> bool:
    """Can the chat template shape tool calls?

    Tool-capable templates (Qwen, Mistral, DeepSeek …) carry the `tools`
    key — without it the server cannot build a tool list into the prompt.
    Any further interpretation would be guesswork.
    """
    return "tools" in (template or "")


async def _faehigkeiten_erkennen(
    base_url: str, timeout: float, api_key_env: str | None = None
) -> dict[str, bool] | None:
    """Asks the /props endpoint (llama.cpp) for everything the server
    reveals about itself: the thinking switch and tools live in the chat
    template, vision in the `modalities` object.

    The request carries the endpoint's key — newer llama-server builds
    guard /props like every other route, and an unauthenticated knock
    comes back 401, which used to read as "nothing there". Read fresh
    from the environment on every call, same as the provider does.

    No /props, no JSON — simply means: nothing detected (None).
    mlx_lm/mlx_vlm have no such endpoint; there the configuration alone
    counts. No error, no noise; we sniff again the next time the server
    becomes reachable.
    """
    import httpx

    wurzel = base_url.rstrip("/")
    if wurzel.endswith("/v1"):
        wurzel = wurzel[: -len("/v1")]
    kopf = {}
    if api_key_env and (wert := os.getenv(api_key_env, "").strip()):
        kopf = {"Authorization": f"Bearer {wert}"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            antwort = await client.get(wurzel + "/props", headers=kopf)
        if antwort.status_code != 200:
            return None
        daten = antwort.json()
    except Exception:  # noqa: BLE001 - purely supplementary information
        return None
    return _faehigkeiten_aus_props(daten)


def _faehigkeiten_aus_props(daten: dict[str, Any]) -> dict[str, bool]:
    """What a /props answer reveals, resolved to the three switches.

    Newer builds say it outright in `chat_template_caps`; only where that
    is missing does reading the template remain — older servers serve
    nothing else.
    """
    template = str(daten.get("chat_template", ""))
    modalitaeten = daten.get("modalities") or {}
    caps = daten.get("chat_template_caps") or {}
    werkzeuge = caps.get("supports_tool_calls")
    if werkzeuge is None:
        werkzeuge = werkzeuge_im_template(template)
    return {
        "thinking": denkschalter_im_template(template),
        "tool_calls": bool(werkzeuge),
        "vision": bool(modalitaeten.get("vision")),
    }


@dataclass
class EndpunktZustand:
    endpunkt: EndpointConfig
    provider: Provider
    erreichbar: bool = False
    # How many checks in a row went unanswered. Reset by the first answer.
    stille: int = 0
    # Whether this endpoint has ever answered at all. Only then is a silence
    # worth tolerating — something that was never there cannot be briefly
    # away.
    je_geantwortet: bool = False
    zuletzt_geprueft: str | None = None
    letzter_fehler: str | None = None
    # Asked of the server as soon as it answers for the first time.
    context_tokens: int | None = None
    # What the model is called on the server. Comes from /v1/models, not from
    # the configuration — nobody should have to maintain model names there.
    gemeldeter_name: str | None = None
    # Every model this provider offers. A local server names the one it has
    # loaded; a provider in the cloud names its catalogue. Asked, never
    # maintained — a list kept by hand is wrong the day after it is written.
    modelle: list[str] = field(default_factory=list)
    # What the server reveals about itself (llama.cpp /props): thinking,
    # tool_calls, vision. Sniffed natively — nobody maintains this in a
    # file. None = not checked yet / says nothing.
    faehigkeiten_erkannt: dict[str, bool] | None = None

    @property
    def thinking_erkannt(self) -> bool | None:
        """Convenient access for the thinking switch (interface milestone A)."""
        if self.faehigkeiten_erkannt is None:
            return None
        return self.faehigkeiten_erkannt.get("thinking")

    @property
    def quelle(self) -> str:
        """Where the model comes from, in one line.

        **Derived**, not maintained: a field in the configuration would be
        one more line someone would have to fill in — and for third-party
        servers nobody does.

        Deliberately **without the location**. The address does not know
        where the hardware sits: a model on a desktop machine elsewhere may
        be reached via 127.0.0.1 through a tunnel. "local" would simply be
        wrong there. We only name what the address really gives away — the
        engine.
        """
        return {
            "llama_cpp": "llama.cpp",
            "mlx": "MLX",
            "vllm": "vLLM",
            "openai": "OpenAI",
        }.get(self.endpunkt.parameter_dialect, self.endpunkt.parameter_dialect)

    @property
    def anzeigename(self) -> str:
        """Name for the UI — like ``gemeldeter_name``, without private path parts.

        ``gemeldeter_name`` can be a full file path (mlx_vlm.server without
        the HuggingFace cache, e.g. ``/Users/you/models/...``). This full
        path must go to the server unchanged (see
        ``OpenAIKompatiblerProvider.modellname()``) — but in the beta UI it
        would expose the local user name and folder structure. Hence here,
        for display only, the last path segment.
        """
        name = self.gemeldeter_name or self.endpunkt.name or self.endpunkt.id
        return pfad_zu_anzeigename(name) if ist_pfad(name) else name

    @property
    def auswaehlbare_modelle(self) -> list[str]:
        """What can be picked at this provider — one entry at the very least.

        A provider that reports a catalogue is fanned out into its models. One
        that reports nothing stands for itself, exactly as before: an empty
        list here would make a working local server disappear from the picker.
        """
        return list(self.modelle) if self.modelle else []

    def _capabilities_aufloesen(self) -> dict[str, Any]:
        """Merge configuration and native detection.

        An explicit entry in the config ALWAYS wins — even a "no"
        (safety rule: Gemma's tool_calls-off must not be overruled by
        detection). Only where the config is silent does the sniffed
        result count.
        """
        caps = self.endpunkt.capabilities.model_dump()
        erkannt = self.faehigkeiten_erkannt or {}
        for name in ("thinking", "tool_calls", "vision"):
            if caps.get(name) is None:
                caps[name] = bool(erkannt.get(name))
        return caps

    def kann(self, name: str) -> bool:
        """Resolved capability for the checkpoints in the backend.

        The same truth the frontend sees via als_dict() — never read
        endpunkt.capabilities directly, it can hold None.
        """
        return bool(self._capabilities_aufloesen().get(name))

    def als_dict(self, modell: str | None = None, sprache: str = "en") -> dict[str, Any]:
        """One entry for the model list.

        Without ``modell`` the provider describes itself, the way it always
        did. With one, it describes that single model of its catalogue — same
        address, same capabilities, own id and own name.

        ``sprache`` reaches the parameter labels. English when nobody says
        otherwise — the source language, so a forgotten argument can only
        ever show the original, not a translation in the wrong place.
        """
        return {
            "id": modellkennung.bauen(self.endpunkt.id, modell),
            # Which provider the entry belongs to. The frontend groups by it
            # instead of taking the id apart itself — before, the group was
            # guessed from the host name in the address.
            "anbieter": self.endpunkt.id,
            "anbieter_name": self.endpunkt.name or self.endpunkt.id,
            "modell": modell,
            # The model the configuration names for this provider. A catalogue
            # is picked from and starts empty — but what the configuration
            # points at was picked by whoever wrote it, and unpicking it in the
            # window would leave a provider that works looking unused.
            "angeheftet": bool(modell and modell == self.endpunkt.modell),
            # What the server reports wins. The entry from the configuration
            # is only the fallback when it says nothing.
            # What the server reports, then the entry in the configuration,
            # lastly the id. Nothing is invented.
            "name": (
                (pfad_zu_anzeigename(modell) if ist_pfad(modell) else modell)
                if modell
                else self.anzeigename
            ),
            "quelle": self.quelle,
            "provider": self.endpunkt.provider,
            "dialekt": self.endpunkt.parameter_dialect,
            "reasoning_format": self.endpunkt.reasoning_format,
            "erreichbar": self.erreichbar,
            "zuletzt_geprueft": self.zuletzt_geprueft,
            "context_tokens": self.context_tokens,
            "capabilities": self._capabilities_aufloesen(),
            # local | cloud | extra - see EndpointConfig.group.
            "group": self.endpunkt.group,
            # Which variable holds the access key, and whether it is filled.
            # Never the key itself — the interface has no login, so no secret
            # ever leaves the server. A provider that answers but rejects the
            # key looks exactly like a dead host from the outside; this pair
            # is what tells the two apart in the window.
            "schluessel_env": self.endpunkt.api_key_env,
            "schluessel_gesetzt": bool(
                self.endpunkt.api_key_env
                and os.environ.get(self.endpunkt.api_key_env, "").strip()
            ),
            # Only knobs this backend actually evaluates.
            "parameter": [
                p.als_dict(sprache)
                for p in unterstuetzte(self.endpunkt.parameter_dialect)
            ],
        }


class Discovery:
    """Continuously checks which endpoints answer."""

    def __init__(self, config: Config, bus: EventBus) -> None:
        self.config = config
        self.bus = bus
        self.zustaende: dict[str, EndpunktZustand] = {}
        self._aufgabe: asyncio.Task | None = None
        self._laeuft = False

        for endpunkt in config.endpoints:
            if not endpunkt.enabled:
                continue
            try:
                self.zustaende[endpunkt.id] = EndpunktZustand(
                    endpunkt=endpunkt, provider=provider_bauen(endpunkt)
                )
            except Exception as fehler:  # noqa: BLE001 - one broken entry must not topple everything
                log.error("Endpunkt '%s' übersprungen: %s", endpunkt.id, fehler)

    # --- Queries ---------------------------------------------------------

    def alle(self) -> list[EndpunktZustand]:
        return list(self.zustaende.values())

    def erreichbare(self) -> list[EndpunktZustand]:
        return [zustand for zustand in self.zustaende.values() if zustand.erreichbar]

    def provider_holen(self, endpoint_id: str) -> Provider | None:
        zustand = self.zustaende.get(endpoint_id)
        return zustand.provider if zustand else None

    def aufgefaechert(self, zustaende: list[EndpunktZustand]) -> list[tuple[EndpunktZustand, str | None]]:
        """One entry per model instead of one per provider.

        A provider that reports a catalogue appears once for each of its
        models; one that reports nothing appears once for itself. That is the
        whole difference between "one address, one model" and "one provider,
        many models" — and it lives in this one place, so nothing else has to
        know about it.
        """
        paare: list[tuple[EndpunktZustand, str | None]] = []
        for zustand in zustaende:
            modelle = zustand.auswaehlbare_modelle
            if modelle:
                paare.extend((zustand, modell) for modell in modelle)
            else:
                paare.append((zustand, None))
        return paare

    def aufloesen(self, kennung: str) -> tuple[EndpunktZustand, str | None] | None:
        """Finds provider and model for a public id.

        An id without a separator is looked up as a provider first — that is
        what chats and agents have stored from before the split, and it must
        keep working. Only then is it taken apart.
        """
        zustand = self.zustaende.get(kennung)
        if zustand is not None:
            return zustand, zustand.gemeldeter_name

        endpunkt_id, modell = modellkennung.zerlegen(kennung)
        zustand = self.zustaende.get(endpunkt_id)
        if zustand is None:
            return None
        # A model the provider does not offer is not silently swapped for
        # another — the caller reports it as not reachable, which it is.
        if modell and zustand.modelle and modell not in zustand.modelle:
            return None
        return zustand, modell or zustand.gemeldeter_name

    # --- Arriving and leaving while the service runs ----------------------

    async def anmelden(self, endpunkt: EndpointConfig) -> None:
        """Adds a candidate without a restart.

        The list is built from the configuration at startup — but a provider
        added in the window and the model server started from the window both
        arrive later, and waiting for a restart would turn both windows into
        dead ends. The check runs right away: whoever just added something is
        looking at the list this very second.

        An id that already exists is replaced, not doubled — the model server
        keeps its id across restarts, only its port may change.
        """
        try:
            zustand = EndpunktZustand(
                endpunkt=endpunkt, provider=provider_bauen(endpunkt)
            )
        except Exception as fehler:  # noqa: BLE001 - one broken entry must not topple everything
            log.error("Endpunkt '%s' nicht angemeldet: %s", endpunkt.id, fehler)
            return
        self.zustaende[endpunkt.id] = zustand
        await self.einmal_pruefen()

    async def abmelden(self, endpoint_id: str) -> None:
        """Removes a candidate — the counterpart of ``anmelden``.

        Whoever was chatting with it sees the model as gone, which is the
        truth; nothing else has to be told.
        """
        zustand = self.zustaende.pop(endpoint_id, None)
        if zustand is None or not zustand.erreichbar:
            return
        await self.bus.veroeffentlichen(
            Ereignisse.ENDPUNKT_STATUS_GEAENDERT,
            endpoint_id=endpoint_id,
            erreichbar=False,
        )

    # --- Checking --------------------------------------------------------

    async def einmal_pruefen(self) -> None:
        """One pass over all candidates — all at the same time."""
        if not self.zustaende:
            return

        zustaende = list(self.zustaende.values())
        ergebnisse = await asyncio.gather(
            *(
                zustand.provider.erreichbar(self.config.discovery.timeout_seconds)
                for zustand in zustaende
            ),
            return_exceptions=True,
        )

        for zustand, ergebnis in zip(zustaende, ergebnisse):
            if isinstance(ergebnis, BaseException):
                geantwortet = False
                zustand.letzter_fehler = str(ergebnis)
            else:
                geantwortet = bool(ergebnis)
                zustand.letzter_fehler = None

            # One silence is not an outage. A single missed answer used to drop
            # the endpoint out of the picker immediately, and a provider whose
            # model list hangs every other request made models appear and
            # vanish while you looked at them. An answer counts at once; a
            # silence has to repeat before it counts.
            if geantwortet:
                zustand.stille = 0
                zustand.je_geantwortet = True
            else:
                zustand.stille += 1
            erreichbar = geantwortet or (
                zustand.je_geantwortet and zustand.stille < STILLE_BIS_WEG
            )

            vorher = zustand.erreichbar
            zustand.erreichbar = erreichbar
            zustand.zuletzt_geprueft = jetzt_iso()

            # Ask for the context size once, as soon as the server answers
            # for the first time. It only changes when the server restarts —
            # and then it is fetched anew the next time it becomes reachable.
            if erreichbar and zustand.context_tokens is None:
                try:
                    zustand.context_tokens = await zustand.provider.kontextgroesse(
                        self.config.discovery.timeout_seconds
                    )
                except Exception:  # noqa: BLE001 - purely supplementary information
                    log.debug("Kontextgröße von '%s' nicht ermittelbar", zustand.endpunkt.id)

            # Same route for the name: fetch once, as soon as the server
            # answers. A model swap on the server is thus noticed the next
            # time it becomes reachable, not only when the service restarts.
            #
            # Unless the endpoint names its model itself. A cloud provider
            # answers /v1/models with its whole catalogue, and asking it which
            # model is "the" model has no sensible answer — the configuration
            # has to say.
            if erreichbar and zustand.gemeldeter_name is None:
                if zustand.endpunkt.modell:
                    zustand.gemeldeter_name = zustand.endpunkt.modell
                else:
                    try:
                        zustand.gemeldeter_name = await zustand.provider.modellname(
                            self.config.discovery.timeout_seconds
                        )
                    except Exception:  # noqa: BLE001 - purely supplementary information
                        log.debug("Modellname von '%s' nicht ermittelbar", zustand.endpunkt.id)

            # The catalogue, same route: asked once, as soon as the provider
            # answers. Only a provider that offers a choice gets fanned out —
            # a local server with one model reports exactly that one, and
            # naming it twice would help nobody.
            #
            # An empty answer does NOT clear what we already know. The model
            # list is the very request that hangs every other time, and
            # letting a single timeout empty the picker is the flicker this
            # loop is otherwise built to avoid.
            # A pinned model in the configuration says which one the BARE
            # provider id means — it does not say the provider has only that
            # one. Both are asked for separately: the pin answers "what does
            # `openai` alone stand for", the catalogue answers "what else is
            # there to pick".
            if erreichbar and not zustand.modelle:
                try:
                    gefunden = await zustand.provider.modelle_auflisten(
                        self.config.discovery.timeout_seconds
                    )
                except Exception:  # noqa: BLE001 - purely supplementary information
                    gefunden = []
                if len(gefunden) > 1:
                    zustand.modelle = gefunden
            # Sniff the capabilities once, as soon as the server answers —
            # llama.cpp reveals the chat template (thinking switch, tools)
            # and modalities (vision) via /props.
            if erreichbar and zustand.faehigkeiten_erkannt is None:
                # {} instead of None when the server reveals nothing —
                # otherwise every pass would knock on a dead /props again (mlx).
                zustand.faehigkeiten_erkannt = (
                    await _faehigkeiten_erkennen(
                        zustand.endpunkt.base_url,
                        self.config.discovery.timeout_seconds,
                        zustand.endpunkt.api_key_env,
                    )
                    or {}
                )

            elif not erreichbar:
                zustand.context_tokens = None
                zustand.gemeldeter_name = None
                zustand.modelle = []
                zustand.faehigkeiten_erkannt = None

            if vorher != erreichbar:
                await self.bus.veroeffentlichen(
                    Ereignisse.ENDPUNKT_STATUS_GEAENDERT,
                    endpoint_id=zustand.endpunkt.id,
                    erreichbar=erreichbar,
                )

    # --- Background loop -------------------------------------------------

    async def _schleife(self) -> None:
        abstand = max(1, self.config.discovery.interval_seconds)
        while self._laeuft:
            try:
                await self.einmal_pruefen()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - the loop must never die
                log.exception("Discovery-Durchlauf fehlgeschlagen")
            try:
                await asyncio.sleep(abstand)
            except asyncio.CancelledError:
                raise

    async def starten(self) -> None:
        if self._aufgabe is not None:
            return
        self._laeuft = True
        # A first pass right away, so the UI does not have to wait.
        await self.einmal_pruefen()
        self._aufgabe = asyncio.create_task(self._schleife(), name="discovery")
        log.info("Discovery gestartet für %d Endpunkte", len(self.zustaende))

    async def stoppen(self) -> None:
        self._laeuft = False
        if self._aufgabe is None:
            return
        self._aufgabe.cancel()
        try:
            await self._aufgabe
        except asyncio.CancelledError:
            pass
        finally:
            self._aufgabe = None
