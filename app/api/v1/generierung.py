"""Streaming proxy and cancellation (phase 1.5).

Flow of a request:

  1. Save the user message (if one comes along).
  2. Fetch the history from the database, prepend the system prompt.
  3. Stream from the chosen provider and pass every chunk on immediately.
  4. At the end, save the complete answer including reasoning and metrics
     and publish ``model_response_finished``.

If cancelled, step 4 still applies — the text produced up to that point is
not lost but saved with the ``abgebrochen`` marker. So there are no empty
gray bubbles.

The stream is Server-Sent Events. Each event is one line of JSON with a
``typ`` field: ``start``, ``content``, ``reasoning``, ``tool_confirm``,
``tool_call``, ``tool_result``, ``stats``, ``error``, ``done``.

Tools listed under ``needs_confirmation`` are not simply executed: the
stream sends ``tool_confirm`` and pauses until a decision comes in via
``/api/v1/chat/confirm``. If nobody answers, after ``BESTAETIGUNG_WARTEZEIT``
seconds the rejection applies — silence must never lead to execution.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.abhaengigkeiten import hole_benutzer_id, hole_repositories, hole_sprache
from app.api.v1.schemas import (
    AbbruchAnfrage,
    AbbruchAntwort,
    BestaetigungAnfrage,
    BestaetigungAntwort,
    GenerierungAnfrage,
)
from app.db import Repositories
from app.db.models import Chat
from app.discovery import Discovery
from app.events import Ereignisse, bus
from app.generationen import Generierung, Generierungsverwaltung
from app.i18n import t
from app.providers import ChatNachricht, Generierungsanfrage, ProviderFehler
from app.tools import WerkzeugRegistry, WerkzeugVerboten
from app import anrede, gedaechtnis, grundprompt, skills, skillwahl, werkzeugwahl

log = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["generierung"])

# How often the model may request tools within one answer. Prevents a model
# from going in circles and keeping the server busy.
# 10 instead of 5: a real research run burned three
# rounds on pages that only delivered their menu, and then got cut off.
MAX_WERKZEUG_RUNDEN = 10


# From the best to the weakest origin of the speed figure. Across several
# rounds the weakest one applies: one round without a server measurement
# makes the total inaccurate, and the figure should admit that too.
_QUELLEN_RANG = {"server": 0, "gemessen": 1, "geschaetzt": 2}


def _messwerte_mergen(alt: dict | None, neu: dict) -> dict:
    """Sum metrics across tool rounds.

    Each round delivers its own numbers — until now the last one simply won,
    and a run of two and a half minutes showed up as "23 s" in the bubble.
    Duration and chunks are added up, the speed is
    recalculated from the totals; the first token counts from the first round.

    For the speed, tokens and **generation time** are summed separately and
    only divided afterwards. The waiting time between rounds —
    tool execution and processing of the grown prompt — is thus included in
    the total duration but not in the speed. That is exactly how llama.cpp
    and mlx separate it too.
    """
    if not alt:
        return neu
    dauer = round((alt.get("dauer_sekunden") or 0) + (neu.get("dauer_sekunden") or 0), 3)
    haeppchen = (alt.get("haeppchen") or 0) + (neu.get("haeppchen") or 0)
    tokens = (alt.get("erzeugte_tokens") or 0) + (neu.get("erzeugte_tokens") or 0)
    erzeugungszeit = round(
        (alt.get("erzeugungs_sekunden") or 0) + (neu.get("erzeugungs_sekunden") or 0), 3
    )
    quellen = [q for q in (alt.get("tempo_quelle"), neu.get("tempo_quelle")) if q]
    return {
        **neu,
        "dauer_sekunden": dauer,
        "haeppchen": haeppchen,
        "erzeugte_tokens": tokens or None,
        "erzeugungs_sekunden": erzeugungszeit or None,
        "tokens_pro_sekunde": (
            round(tokens / erzeugungszeit, 2) if tokens and erzeugungszeit else None
        ),
        "tempo_quelle": (
            max(quellen, key=lambda q: _QUELLEN_RANG.get(q, 9)) if quellen else None
        ),
        "erstes_token_nach_sekunden": alt.get("erstes_token_nach_sekunden")
        or neu.get("erstes_token_nach_sekunden"),
    }

# How long to wait for the user's answer before the confirmation prompt
# counts as rejected. Generous: they may not be sitting in front of it. In
# between, we check at intervals whether anyone is still listening at all.
BESTAETIGUNG_WARTEZEIT = 300.0
BESTAETIGUNG_PRUEFTAKT = 0.5


async def _werkzeug_ausfuehren(
    registry: WerkzeugRegistry | None, aufruf, sprache: str, bild_senke=None,
    ordner: list[str] | None = None,
) -> tuple[str, bool]:
    """Executes a tool. Returns (result text, failed).

    Errors are not raised but returned to the model as text — it should get
    the chance to handle them or tell the user about them.

    The confirmation requirement is no longer an issue here: that has been
    decided before this function is even called.

    ``ordner`` are the chat's shared working folders — the shell tool runs in
    them. They come from the chat row, never from the model's arguments.
    """
    if registry is None:
        return t("fehler.werkzeug_verboten", sprache, name=aufruf.name), True

    try:
        log.info("Werkzeug '%s' wird ausgeführt: %s", aufruf.name, aufruf.argumente)
        return await registry.ausfuehren(
            aufruf.name, aufruf.argumente, bild_senke, ordner=ordner
        ), False
    except WerkzeugVerboten as fehler:
        log.warning("Abgelehnt: %s", fehler)
        return str(fehler), True
    except Exception as fehler:  # noqa: BLE001 - a broken tool must not shoot down the chat
        log.exception("Werkzeug '%s' ist fehlgeschlagen", aufruf.name)
        return f"Fehler bei '{aufruf.name}': {fehler}", True


async def _auf_entscheidung_warten(
    generierung: Generierung, aufruf_id: str
) -> bool | None:
    """Waits for the yes or no on a tool.

    ``True``/``False`` is the user's decision. ``None`` means: none came —
    because the wait time is up, the run was cancelled, or nobody is hanging
    on the other end anymore. In all three cases nothing is executed.

    We wait in small steps instead of one big one: otherwise the run would
    still hang for five minutes on a window that has long been closed.
    """
    zukunft = generierung.bestaetigung_erwarten(aufruf_id)
    rest = BESTAETIGUNG_WARTEZEIT
    try:
        while rest > 0:
            try:
                # shield: when the tick runs out, the waiting should end —
                # but the decision itself must not be lost because of it.
                return await asyncio.wait_for(
                    asyncio.shield(zukunft), timeout=BESTAETIGUNG_PRUEFTAKT
                )
            except asyncio.TimeoutError:
                rest -= BESTAETIGUNG_PRUEFTAKT
            except asyncio.CancelledError:
                if zukunft.cancelled():
                    return None
                raise
            if generierung.soll_abbrechen:
                return None
        log.info("Auf die Bestätigung für '%s' kam keine Antwort", aufruf_id)
        return None
    finally:
        generierung.bestaetigung_ablegen(aufruf_id)


def hole_discovery(request: Request) -> Discovery:
    return request.app.state.discovery


def hole_generierungen(request: Request) -> Generierungsverwaltung:
    return request.app.state.generierungen


def _sse(typ: str, **felder) -> str:
    return f"data: {json.dumps({'typ': typ, **felder}, ensure_ascii=False)}\n\n"


# How often to check whether the browser is still there. Chats only.
VERBINDUNG_PRUEFTAKT = 0.5


async def _waechter(lauf: Generierung, request: Request) -> None:
    """Sets the cancel signal as soon as the owning request is gone.

    This check used to sit in the middle of the loop. But it has to live
    here, because the loop no longer knows the request — and it has to
    **check actively**: if a run is currently hanging on a confirmation
    prompt, it writes nothing, and a vanished browser would otherwise go
    unnoticed.
    """
    try:
        while not lauf.fertig.is_set():
            if await request.is_disconnected():
                lauf.signal.set()
                return
            await asyncio.sleep(VERBINDUNG_PRUEFTAKT)
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - the watchdog must not drag down the run
        log.debug("Verbindungswaechter fuer %s beendet", lauf.id, exc_info=True)


async def _zusehen(
    lauf: Generierung, request: Request | None = None, ab: int = 0
) -> AsyncIterator[str]:
    """Delivers the events of a run — first what was missed, then live.

    With ``request`` it is the **owning** request: if it goes away and the
    run is bound to it, the run is cancelled. Without ``request`` someone is
    just watching; if they leave, the run carries on unmoved.
    """
    if request is not None and lauf.an_verbindung_gebunden:
        # Do NOT clean this up again in the finally. If the connection drops,
        # Starlette closes this generator — so the finally runs at exactly
        # the moment the watchdog is needed. Cancelling it there kills it
        # before it can report anything. Exactly this bug existed once while
        # building 6.1: the chat simply kept running after the browser was
        # closed.
        #
        # The watchdog ends by itself as soon as the run is finished.
        asyncio.create_task(_waechter(lauf, request), name=f"wache-{lauf.id}")
    async for zeile in lauf.zuschauen(ab):
        yield zeile


def _bild_daten_url(config, name: str | None) -> str | None:
    """Reads an uploaded image as a data URL for the OpenAI image format.

    A missing or unsuitable image is not a crash: the message then goes out
    without an image — the history must not fail over a deleted file.
    """
    if not name:
        return None
    from app.api.v1.bilder import BILD_NAME_MUSTER, ERLAUBTE_TYPEN, bilder_verzeichnis

    if not BILD_NAME_MUSTER.match(name):
        return None
    datei = bilder_verzeichnis(config) / name
    if not datei.is_file():
        return None
    import base64

    medientyp = {v: k for k, v in ERLAUBTE_TYPEN.items()}[datei.suffix]
    return f"data:{medientyp};base64," + base64.b64encode(datei.read_bytes()).decode()


def _system_bauen(request, repositories, chat, zustand, gewaehlt: str = "") -> str:
    """The whole system message for one request, in three layers.

    ``gewaehlt`` is a skill the user picked from the slash list. It is looked
    up rather than trusted: the name travels from the browser, and the only
    names that exist are the ones on disk.
    """
    config = request.app.state.config
    registry = getattr(request.app.state, "werkzeuge", None)
    werkzeuge_da = bool(
        registry is not None
        and config.features.mcp
        and zustand.kann("tool_calls")
        and registry.als_openai_werkzeuge()
    )
    gedaechtnis_da = gedaechtnis.mitschicken(repositories, zustand)

    # Only skills the model may reach for by itself, and only when the tools
    # exist to reach with — a catalogue without skill_load names doors that
    # cannot be opened.
    skill_katalog: list[tuple[str, str]] = []
    gewaehlte_skill = None
    if werkzeuge_da or gewaehlt:
        vorhanden = skills.skills_laden(*config.skillverzeichnisse)
        gewaehlte_skill = vorhanden.get(gewaehlt) if gewaehlt else None
        if werkzeuge_da and skillwahl.selbst_waehlen(
            repositories, modell=zustand.endpunkt.id, chat=chat.id
        ):
            skill_katalog = [
                (s.name, s.beschreibung) for s in skills.automatische(vorhanden)
            ]

    grund = grundprompt.bauen(
        werkzeuge=werkzeuge_da,
        ordner=chat.working_dirs,
        gedaechtnis=gedaechtnis_da and bool(config.memory_lesen()),
        skills=skill_katalog,
    )
    # The user's prompt is the only part `prompt_aus` suspends.
    benutzer = "" if chat.prompt_aus else config.system_prompt_lesen()
    return anrede.anhaengen(
        skills.anhaengen(
            gedaechtnis.anhaengen(
                grundprompt.mit_benutzerprompt(grund, benutzer),
                config.memory_lesen() if gedaechtnis_da else "",
            ),
            gewaehlte_skill,
        ),
        anrede.lesen(repositories),
    )


def _verlauf_bauen(
    chat: Chat, repositories: Repositories, system_prompt: str, config=None
) -> list[ChatNachricht]:
    """Builds the message list for a request.

    The system prompt is not part of the history and is not stored — it is
    freshly prepended here on every request. As a result, a change to the
    file takes effect immediately, even in chats that have existed for ages.

    ``prompt_aus`` on the chat suspends the USER's prompt — their character
    and their own rules. It does not suspend the shipped instructions: those
    describe how this machine works and include the rule that a tool result
    is data and not an order. Switching that off to see a model answer "raw"
    would switch off the guard rails with it, and nothing on the switch says
    so. One control, one job.
    """
    nachrichten: list[ChatNachricht] = []
    if system_prompt:
        nachrichten.append(ChatNachricht(role="system", content=system_prompt))
    for gespeichert in repositories.messages.auflisten(chat_id=chat.id):
        # The reasoning does not belong in the history — it is display, not context.
        inhalt = gespeichert.content
        if gespeichert.dokument:
            # Documents ride along through the whole history like images:
            # the extracted text is prepended to the
            # message so that follow-up questions can refer to it too. A
            # deleted row is not a crash — the message then goes out without
            # the text.
            dokument = repositories.documents.holen(gespeichert.dokument)
            if dokument and dokument.extracted_text:
                inhalt = (
                    f'[Attached document "{dokument.filename}"]\n'
                    f"{dokument.extracted_text}\n"
                    f"[End of document]\n\n{inhalt}"
                )
        nachrichten.append(
            ChatNachricht(
                role=gespeichert.role,
                content=inhalt,
                # Images remain part of the context: earlier attachments go
                # along again too, otherwise the model cannot refer to them.
                bild_url=_bild_daten_url(config, gespeichert.bild),
            )
        )
    return nachrichten


def _denkschalter_zusatz(thinking: bool | None, zustand) -> dict:
    """Builds the chat_template_kwargs for the thinking switch (interface close-out A).

    Only if the user has flipped the switch AND the endpoint demonstrably
    supports switching (config entry wins, otherwise the discovery's native
    detection). Everything else: empty — no guessing at the server.
    """
    if thinking is None:
        return {}
    caps = zustand.endpunkt.capabilities
    schaltbar = (
        caps.thinking
        if caps.thinking is not None
        else bool(getattr(zustand, "thinking_erkannt", False))
    )
    if not schaltbar:
        return {}
    return {"chat_template_kwargs": {"enable_thinking": thinking}}


@router.post("/completions", summary="Antwort erzeugen (Server-Sent Events)")
async def completions(
    daten: GenerierungAnfrage,
    request: Request,
    repositories: Repositories = Depends(hole_repositories),
    discovery: Discovery = Depends(hole_discovery),
    generierungen: Generierungsverwaltung = Depends(hole_generierungen),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> StreamingResponse:
    chat = repositories.chats.holen(daten.chat_id, user_id=user_id)
    if chat is None:
        raise HTTPException(404, t("fehler.chat_nicht_gefunden", sprache))

    endpoint_id = daten.endpoint_id or chat.endpoint_id
    if not endpoint_id:
        raise HTTPException(400, t("fehler.kein_modell_verfuegbar", sprache))

    # The id names provider and model together (see app/modellkennung.py);
    # what the server is told is the model name alone.
    gefunden = discovery.aufloesen(endpoint_id)
    if gefunden is None:
        raise HTTPException(
            404, t("fehler.modell_nicht_erreichbar", sprache, name=endpoint_id)
        )
    zustand, modellname = gefunden
    if not zustand.erreichbar:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            t("fehler.modell_nicht_erreichbar", sprache, name=zustand.endpunkt.name),
        )

    if daten.bild and not zustand.kann("vision"):
        # The UI grays out the attachment without vision — but the API
        # remains the outer boundary and says so itself if need be.
        raise HTTPException(400, t("fehler.kein_vision", sprache))

    if daten.dokument:
        # Only an id that really belongs to this chat gets linked —
        # the server later builds the meta card itself from the database.
        dokument = repositories.documents.holen(daten.dokument)
        if dokument is None or dokument.chat_id != chat.id:
            raise HTTPException(404, t("fehler.dokument_fehlt", sprache))

    if daten.content or daten.bild or daten.dokument:
        repositories.messages.speichern(
            chat_id=chat.id,
            role="user",
            content=daten.content or "",
            bild=daten.bild,
            dokument=daten.dokument,
        )
        repositories.chats.zeitstempel_auffrischen(chat.id)

    # Remembers the model choice on the chat so it is set next time.
    if chat.endpoint_id != endpoint_id:
        repositories.chats.aktualisieren(chat.id, endpoint_id=endpoint_id)
        chat = repositories.chats.holen(chat.id)

    # What this model is set to, resolved through the cascade: global, then
    # what holds for this model, then what holds for this chat. A new chat
    # therefore starts with the model's settings instead of at the endpoint's
    # bare defaults — which is the whole point of the table.
    eingestellt = repositories.einstellungen.zusammengefuehrt(
        "parameter", modell=endpoint_id, chat=chat.id
    )

    anfrage = Generierungsanfrage(
        nachrichten=_verlauf_bauen(
            chat,
            repositories,
            # Shipped instructions, then the user's layer, then what is
            # known about them — ONE system message, because Anthropic takes
            # a single system field and providers disagree about a second.
            #
            # The shipped part is assembled for THIS request: no tool section
            # without tools, no folder section without shared folders. What
            # does not apply would only dilute attention.
            _system_bauen(request, repositories, chat, zustand, daten.skill or ""),
            config=request.app.state.config,
        ),
        temperature=(
            daten.temperature if daten.temperature is not None else eingestellt.get("temperature")
        ),
        top_p=daten.top_p if daten.top_p is not None else eingestellt.get("top_p"),
        # Order: request, then what is set, then the default. Without the
        # default the model server's own applies — and on MLX that one is so
        # tight that a long reasoning trace eats up the entire answer.
        max_tokens=(
            daten.max_tokens
            if daten.max_tokens is not None
            else eingestellt.get("max_tokens")
            or request.app.state.config.app.default_max_tokens
        ),
        # Everything else the cascade resolved, overridable by the request.
        parameter={**eingestellt, **(daten.parameter or {})},
        # The id the server itself reports under /v1/models — not our
        # endpoint id. This used to say "mana" or "gemma-mac"; mlx_lm.server
        # interprets "model" as a HuggingFace id and answers that with a 404.
        # If nothing is reported, the field is not sent at all — better to
        # omit than to guess.
        modell=modellname,
        # The thinking switch: only goes along if the endpoint demonstrably
        # supports switching — otherwise the server keeps its default.
        zusatz=_denkschalter_zusatz(daten.thinking, zustand),
    )

    # Only offer tools if the feature is switched on and the endpoint can
    # do tool calls at all.
    registry = getattr(request.app.state, "werkzeuge", None)
    if (
        registry is not None
        and request.app.state.config.features.mcp
        and zustand.kann("tool_calls")
    ):
        # What the user switched off is handed in before the list is built,
        # so it is missing from the offer and refused on execution alike.
        werkzeugwahl.anwenden(registry, repositories, chat=chat.id)
        anfrage.werkzeuge = registry.als_openai_werkzeuge()

    platzhalter = repositories.messages.speichern(
        chat_id=chat.id, role="assistant", content=""
    )

    # The generator stays what it was — a sequence of events. What's new is
    # only who reads it: no longer the response to the browser, but the run.
    # That's why the generation now comes in as a parameter instead of from
    # the enclosing namespace.
    async def strom(generierung: Generierung) -> AsyncIterator[str]:
        antwort_text: list[str] = []
        gedanke_text: list[str] = []
        messwerte: dict = {}
        werkzeugprotokoll: list[dict] = []
        abgebrochen = False
        fehlertext: str | None = None
        quelle = None

        # Images from tool results (Recraft & co.): saved like the generated
        # images under data/bilder/, the message carries only the name —
        # the same display as in image mode, nothing new invented.
        werkzeug_bilder: list[str] = []

        def bild_senke(mime: str, daten_b64: str) -> str:
            # Named like every other image in the house (32 hex + extension) —
            # the delivery under /images/{name} checks exactly this pattern,
            # a custom prefix would fail it (found during Banane 3).
            endung = {
                "image/webp": ".webp",
                "image/png": ".png",
                "image/jpeg": ".jpg",
            }.get(mime)
            if endung is None:
                # Unknown kind: better the short note than a file that
                # would be delivered with a wrong declaration.
                raise ValueError(f"unbekannter Bildtyp {mime}")
            name = uuid4().hex + endung
            verzeichnis = request.app.state.config.datenverzeichnis / "bilder"
            verzeichnis.mkdir(parents=True, exist_ok=True)
            (verzeichnis / name).write_bytes(base64.b64decode(daten_b64))
            werkzeug_bilder.append(name)
            return name

        yield _sse(
            "start",
            generation_id=generierung.id,
            message_id=platzhalter.id,
            chat_id=chat.id,
            endpoint_id=endpoint_id,
        )

        try:
            # One pass per tool round: the model requests, we execute, the
            # result goes back, the model keeps writing. Bounded so that a
            # model doesn't go in circles.
            for runde in range(MAX_WERKZEUG_RUNDEN + 1):
                aufrufe: list = []
                quelle = zustand.provider.streamen(anfrage)

                async for stueck in quelle:
                    if generierung.soll_abbrechen:
                        abgebrochen = True
                        break

                    if stueck.sorte == "content":
                        antwort_text.append(stueck.text)
                        yield _sse("content", text=stueck.text)
                    elif stueck.sorte == "reasoning":
                        gedanke_text.append(stueck.text)
                        yield _sse("reasoning", text=stueck.text)
                    elif stueck.sorte == "stats":
                        messwerte = _messwerte_mergen(messwerte, stueck.daten)
                    elif stueck.sorte == "tool_call":
                        aufrufe = stueck.werkzeugaufrufe
                    elif stueck.sorte == "error":
                        fehlertext = stueck.text

                await quelle.aclose()
                quelle = None

                if abgebrochen or not aufrufe:
                    break

                if runde >= MAX_WERKZEUG_RUNDEN:
                    fehlertext = t("fehler.werkzeug_grenze", sprache, anzahl=MAX_WERKZEUG_RUNDEN)
                    break

                # What the model requested goes into the history …
                anfrage.nachrichten.append(
                    ChatNachricht(
                        role="assistant",
                        content="".join(antwort_text),
                        werkzeugaufrufe=aufrufe,
                    )
                )

                # … then it is executed and the result handed back.
                for aufruf in aufrufe:
                    # Confirmation-requiring tools first: the question is asked
                    # before 'tool_call' is reported — otherwise the window
                    # would say "running" while in truth nobody has agreed yet.
                    abgelehnt: str | None = None
                    if registry is not None and registry.braucht_bestaetigung(
                        aufruf.name, aufruf.argumente, chat.working_dirs
                    ):
                        # Why this one is being asked about. Without it the
                        # prompt shows a command and expects trust; with it
                        # the decision rests on something visible.
                        # The tool names its own sentence — the shell speaks
                        # of paths outside the shared folders, the memory of
                        # the rule about to be stored. Picking one sentence
                        # for all of them announced a memory entry as if it
                        # were a stray file path.
                        anlass = registry.bestaetigungsgrund(
                            aufruf.name, aufruf.argumente, chat.working_dirs
                        )
                        yield _sse(
                            "tool_confirm",
                            name=aufruf.name,
                            argumente=aufruf.argumente,
                            grund=(
                                t(anlass[0], sprache, **{anlass[1]: anlass[2]})
                                if anlass
                                else ""
                            ),
                            aufruf_id=aufruf.id,
                        )
                        entscheidung = await _auf_entscheidung_warten(
                            generierung, aufruf.id
                        )
                        if entscheidung is None:
                            if generierung.soll_abbrechen:
                                abgebrochen = True
                                break
                            abgelehnt = t(
                                "fehler.werkzeug_unbeantwortet", sprache, name=aufruf.name
                            )
                        elif entscheidung is False:
                            log.info("Werkzeug '%s' wurde abgelehnt", aufruf.name)
                            abgelehnt = t("fehler.werkzeug_abgelehnt", sprache, name=aufruf.name)

                    # The server travels with the call: the UI picks the
                    # tool's mark by it, and unlike the tool name it is fixed
                    # in the configuration and cannot be guessed wrong.
                    yield _sse(
                        "tool_call",
                        name=aufruf.name,
                        server=registry.server_von(aufruf.name) if registry else "",
                        argumente=aufruf.argumente,
                        aufruf_id=aufruf.id,
                    )
                    if abgelehnt is not None:
                        ergebnis, fehlgeschlagen = abgelehnt, True
                    else:
                        bilder_vorher = len(werkzeug_bilder)
                        ergebnis, fehlgeschlagen = await _werkzeug_ausfuehren(
                            registry, aufruf, sprache, bild_senke,
                            ordner=chat.working_dirs,
                        )
                    # Did THIS call save an image? Then the line in the stream
                    # and the log in the message carry it.
                    neues_bild = (
                        werkzeug_bilder[-1]
                        if abgelehnt is None and len(werkzeug_bilder) > bilder_vorher
                        else None
                    )
                    werkzeugprotokoll.append(
                        {
                            "name": aufruf.name,
                            # Stored alongside, so a reloaded history shows the
                            # same mark as the live run did.
                            "server": registry.server_von(aufruf.name) if registry else "",
                            "argumente": aufruf.argumente,
                            "fehlgeschlagen": fehlgeschlagen,
                            # Goes into the message so that even after a reload
                            # the history shows what the tool delivered.
                            # Truncated as in the stream — a raw search page in
                            # the database helps no one.
                            "ergebnis": ergebnis[:2000],
                            "bild": neues_bild,
                        }
                    )
                    yield _sse(
                        "tool_result",
                        name=aufruf.name,
                        aufruf_id=aufruf.id,
                        fehlgeschlagen=fehlgeschlagen,
                        text=ergebnis[:2000],
                        bild=neues_bild,
                    )
                    anfrage.nachrichten.append(
                        ChatNachricht(
                            role="tool",
                            content=ergebnis,
                            werkzeugaufruf_id=aufruf.id,
                        )
                    )

                # If cancelled during a confirmation prompt, there is no next
                # round — otherwise the model would set off once more.
                if abgebrochen:
                    break

        except ProviderFehler as fehler:
            fehlertext = str(fehler)
            log.warning("Anbieter %s: %s", endpoint_id, fehler)
        except asyncio.CancelledError:
            abgebrochen = True
            raise
        except Exception:  # noqa: BLE001
            fehlertext = t("fehler.allgemein", sprache)
            log.exception("Unerwarteter Fehler beim Streamen von %s", endpoint_id)
        finally:
            # Close the connection to the model server — that is the actual cancellation.
            if quelle is not None:
                await quelle.aclose()

            messwerte = dict(messwerte or {})
            messwerte["abgebrochen"] = abgebrochen
            if fehlertext:
                messwerte["fehler"] = fehlertext
            if werkzeugprotokoll:
                messwerte["werkzeuge"] = werkzeugprotokoll

            repositories.messages.inhalt_aktualisieren(
                platzhalter.id,
                content="".join(antwort_text),
                reasoning="".join(gedanke_text) or None,
                stats=messwerte,
                # The most recent tool image hangs on the answer — the
                # message can carry only one, and the last one is the one
                # the model talked about most recently.
                bild=werkzeug_bilder[-1] if werkzeug_bilder else None,
            )
            repositories.chats.zeitstempel_auffrischen(chat.id)
            generierungen.abmelden(generierung.id)

            await bus.veroeffentlichen(
                Ereignisse.ANTWORT_ABGEBROCHEN if abgebrochen else Ereignisse.ANTWORT_FERTIG,
                chat_id=chat.id,
                message_id=platzhalter.id,
                endpoint_id=endpoint_id,
                stats=messwerte,
            )

        if fehlertext:
            yield _sse("error", text=fehlertext)
        yield _sse("stats", daten=messwerte)
        yield _sse("done", message_id=platzhalter.id, abgebrochen=abgebrochen)

    async def arbeit(generierung: Generierung) -> None:
        async for zeile in strom(generierung):
            generierung.melden(zeile)

    # From here on the answer runs in the background. A chat nevertheless
    # stays bound to its request (see _zusehen): nobody should heat up the
    # GPU while no one is watching. A job is later started with
    # an_verbindung_gebunden=False and then keeps running.
    lauf = generierungen.starten(
        chat_id=chat.id,
        endpoint_id=endpoint_id,
        arbeit=arbeit,
        an_verbindung_gebunden=True,
    )

    return StreamingResponse(
        _zusehen(lauf, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # in case nginx ends up in front after all
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/confirm",
    response_model=BestaetigungAntwort,
    summary="Rückfrage vor einem Werkzeug beantworten",
)
def bestaetigen(
    daten: BestaetigungAnfrage,
    generierungen: Generierungsverwaltung = Depends(hole_generierungen),
) -> BestaetigungAntwort:
    """No error if nobody is waiting.

    The box may have been left standing while the answer was already over.
    That is no reason for a red message — the tool didn't run anyway.
    """
    return BestaetigungAntwort(
        zugestellt=generierungen.bestaetigen(
            daten.generation_id, daten.aufruf_id, daten.erlaubt
        )
    )


@router.get(
    "/stream/{generation_id}",
    summary="Einem laufenden Vorgang zusehen (Server-Sent Events)",
)
async def zusehen(
    generation_id: str,
    ab: int = 0,
    generierungen: Generierungsverwaltung = Depends(hole_generierungen),
    sprache: str = Depends(hole_sprache),
) -> StreamingResponse:
    """Attaches to a run that is already underway.

    ``ab`` is the counter from which reading starts. Whoever specifies
    nothing gets the run from the beginning — including everything that
    happened before watching. Whoever lost their connection counts their
    events and picks up where they left off.

    **Watching changes nothing.** Whoever leaves here cancels nothing; only
    the owning request or the stop button can do that.
    """
    lauf = generierungen.holen(generation_id)
    if lauf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.allgemein", sprache))

    return StreamingResponse(
        _zusehen(lauf, ab=ab),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/stop", response_model=AbbruchAntwort, summary="Laufende Antwort abbrechen")
def stoppen(
    daten: AbbruchAnfrage,
    generierungen: Generierungsverwaltung = Depends(hole_generierungen),
) -> AbbruchAntwort:
    if daten.generation_id:
        return AbbruchAntwort(abgebrochen=int(generierungen.abbrechen(daten.generation_id)))
    if daten.chat_id:
        return AbbruchAntwort(abgebrochen=generierungen.alle_im_chat_abbrechen(daten.chat_id))
    raise HTTPException(400, "generation_id oder chat_id wird gebraucht")
