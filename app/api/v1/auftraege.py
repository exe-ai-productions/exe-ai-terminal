"""Jobs: an agent works on its own (phase 6.3/6.4).

A job run uses the same machinery as a chat — provider, tool registry, run
management from 6.1 — but with four differences:

  1. It is **not bound to a connection**: browser closed, run keeps running.
     You can watch at any time via ``GET /api/v1/chat/stream/{generation_id}``,
     in the same event format as a chat — so the UI (6.5) can use the same
     reader.
  2. **The prompt is stacked**: global prompt, then agent prompt.
     The job text is the user message.
  3. **The approval lives in the agent**: only the intersection
     of its ``tools`` list and the registry is offered, and whatever is
     offered runs without asking back. The registry remains the outer
     boundary — it checks once more itself when executing.
  4. **It always keeps a log**:
     every step, every tool call, every result — into the database,
     regardless of wherever else the agent stores things.

Two restraints per agent, rounds and time (6.4). If one runs out
or the context is full, the run ends **with a report** instead of a crash:
whatever has been produced so far is in the result, and the reason is stated
readably on the job.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

import re

from app import gedaechtnis, grundprompt, modellkennung, werkzeugwahl
from app.agenten import Agent, AgentDateiKaputt, agent_aus_text, agenten_laden
from app.api.abhaengigkeiten import hole_benutzer_id, hole_repositories, hole_sprache
from app.api.v1.generierung import (
    _werkzeug_ausfuehren,
    hole_discovery,
    hole_generierungen,
)
from app.api.v1.schemas import (
    AgentAntwort,
    AgentDatei,
    AgentDateiEintrag,
    AgentDateiSchreiben,
    AuftragAnlegen,
    AuftragAntwort,
    AuftragDetail,
)
from app.db import Repositories
from app.db.repositories.auftraege import ENDZUSTAENDE
from app.discovery import Discovery
from app.generationen import Generierung, Generierungsverwaltung
from app.i18n import t
from app.providers import ChatNachricht, Generierungsanfrage, ProviderFehler
from app.wecker import wecker_pausiert

log = logging.getLogger(__name__)

router = APIRouter(tags=["auftraege"])

# This much of a tool result ends up in the log and in the stream —
# the same truncation as in the chat: a raw search page helps no one.
ERGEBNIS_KUERZUNG = 2000
# The reasoning is display, not result — truncated is enough.
GEDANKE_KUERZUNG = 4000

# How to recognize a full context. The model servers only report this as
# error text; there is no clean error class in the OpenAI format —
# hence patterns instead of a type. Better one too few than a false match:
# whatever doesn't match stays an ordinary error.
KONTEXT_VOLL_MUSTER = ("context length", "context window", "maximum context", "too many tokens")


def _sse(typ: str, **felder) -> str:
    return f"data: {json.dumps({'typ': typ, **felder}, ensure_ascii=False)}\n\n"


def _agenten_verzeichnis(request: Request):
    config = request.app.state.config
    return config.pfad(config.app.agenten_verzeichnis)


# --- Agents -----------------------------------------------------------------


@router.get("/agents", response_model=list[AgentAntwort], summary="Verfügbare Agenten")
def agenten_auflisten(
    request: Request,
    repositories: Repositories = Depends(hole_repositories),
) -> list[AgentAntwort]:
    """Fresh from disk — broken files are missing and show up in the log."""
    agenten = agenten_laden(_agenten_verzeichnis(request))
    return [
        AgentAntwort.aus(agent, pausiert=wecker_pausiert(repositories, agent))
        for agent in agenten.values()
    ]


# Agent names are file names. This check is the barrier against path tricks
# ('../', absolute paths) — whatever doesn't match here never reaches the
# filesystem in the first place.
AGENT_NAME_MUSTER = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


def _agenten_datei(request: Request, name: str, sprache: str):
    if not AGENT_NAME_MUSTER.match(name):
        raise HTTPException(400, t("fehler.agent_name_ungueltig", sprache))
    return _agenten_verzeichnis(request) / f"{name}.md"


def _datei_antwort(name: str, text: str) -> AgentDatei:
    try:
        agent_aus_text(name, text)
        kaputt = None
    except AgentDateiKaputt as fehler:
        kaputt = str(fehler)
    return AgentDatei(name=name, content=text, kaputt=kaputt)


@router.get(
    "/agent-files",
    response_model=list[AgentDateiEintrag],
    summary="Alle Agentendateien, auch kaputte (fürs Bearbeitungsfenster)",
)
def agent_dateien_auflisten(request: Request) -> list[AgentDateiEintrag]:
    """A separate path instead of ``/agents/something`` — ``files`` would be a
    valid agent name, and the paths must not get in each other's way."""
    verzeichnis = _agenten_verzeichnis(request)
    eintraege: list[AgentDateiEintrag] = []
    if not verzeichnis.is_dir():
        return eintraege
    for datei in sorted(verzeichnis.glob("*.md")):
        try:
            agent_aus_text(datei.stem, datei.read_text(encoding="utf-8"))
            kaputt = None
        except (AgentDateiKaputt, OSError) as fehler:
            kaputt = str(fehler)
        eintraege.append(AgentDateiEintrag(name=datei.stem, kaputt=kaputt))
    return eintraege


@router.get(
    "/agents/{name}",
    response_model=AgentDatei,
    summary="Die rohe Agentendatei (fürs Bearbeitungsfenster)",
)
def agent_datei_lesen(
    name: str, request: Request, sprache: str = Depends(hole_sprache)
) -> AgentDatei:
    datei = _agenten_datei(request, name, sprache)
    if not datei.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            t("fehler.agent_nicht_gefunden", sprache, name=name),
        )
    return _datei_antwort(name, datei.read_text(encoding="utf-8"))


@router.put(
    "/agents/{name}",
    response_model=AgentDatei,
    summary="Agentendatei speichern",
)
def agent_datei_schreiben(
    name: str,
    daten: AgentDateiSchreiben,
    request: Request,
    sprache: str = Depends(hole_sprache),
) -> AgentDatei:
    """Always saves — it is the user's file.

    If the front matter is no good, the reason goes into ``kaputt``: the agent
    is out of play, the service keeps running, the editor window can show it.
    Same approach as when loading (6.3), just visible earlier.
    """
    datei = _agenten_datei(request, name, sprache)
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(daten.content, encoding="utf-8")
    return _datei_antwort(name, daten.content)


@router.delete(
    "/agents/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    # The same trio as for chat deletion: 204 explicitly means no response
    # body, and FastAPI wants all three settings, otherwise it rejects the
    # route at startup.
    response_class=Response,
    response_model=None,
    summary="Agentendatei löschen",
)
def agent_datei_loeschen(
    name: str, request: Request, sprache: str = Depends(hole_sprache)
) -> None:
    datei = _agenten_datei(request, name, sprache)
    if not datei.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            t("fehler.agent_nicht_gefunden", sprache, name=name),
        )
    datei.unlink()


# --- Jobs -------------------------------------------------------------------


@router.post(
    "/jobs",
    response_model=AuftragAntwort,
    status_code=status.HTTP_201_CREATED,
    summary="Auftrag an einen Agenten geben",
)
async def auftrag_starten(
    daten: AuftragAnlegen,
    request: Request,
    repositories: Repositories = Depends(hole_repositories),
    discovery: Discovery = Depends(hole_discovery),
    generierungen: Generierungsverwaltung = Depends(hole_generierungen),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> AuftragAntwort:
    agent = agenten_laden(_agenten_verzeichnis(request)).get(daten.agent)
    if agent is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            t("fehler.agent_nicht_gefunden", sprache, name=daten.agent),
        )

    auftrag = auftrag_anstossen(
        config=request.app.state.config,
        repositories=repositories,
        discovery=discovery,
        generierungen=generierungen,
        registry=getattr(request.app.state, "werkzeuge", None),
        agent=agent,
        task=daten.task,
        endpoint_id=daten.endpoint_id,
        user_id=user_id,
        sprache=sprache,
    )
    return AuftragAntwort.aus(auftrag)


def auftrag_anstossen(
    *,
    config,
    repositories: Repositories,
    discovery: Discovery,
    generierungen: Generierungsverwaltung,
    registry,
    agent: Agent,
    task: str,
    endpoint_id: str | None,
    user_id: str,
    sprache: str,
):
    """Creates the job and starts the background run.

    Extracted from the route because the scheduler (6.7) takes the same path —
    errors come as ``HTTPException``: the route passes them through, the
    scheduler catches them and tries again on the next pass.
    """
    endpoint_id = endpoint_id or agent.modell
    if not endpoint_id:
        # No model chosen and none stored in the agent: the first reachable
        # endpoint takes over. If the agent has tools, only endpoints capable
        # of tool calls qualify — the others must never be given tools at all.
        for kandidat, modell in discovery.aufgefaechert(discovery.erreichbare()):
            if agent.werkzeuge and not kandidat.kann("tool_calls"):
                continue
            endpoint_id = modellkennung.bauen(kandidat.endpunkt.id, modell)
            break
    if not endpoint_id:
        raise HTTPException(400, t("fehler.kein_modell_verfuegbar", sprache))
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

    auftrag = repositories.auftraege.erstellen(
        user_id=user_id, agent=agent.name, auftrag=task, endpoint_id=endpoint_id
    )

    # Stacked: global prompt, then agent prompt (decision 3). A single
    # system message, because not every local server can handle several.
    #
    # Same three layers as in the chat: shipped instructions, the user's
    # prompt, what is known about them — and the agent's prompt on top, since
    # that is what makes this run an agent at all.
    #
    # No folder section: a job is not bound to a chat and has no shared
    # folders. The memory rides along under the same switch — a job runs on
    # the same models and sends to the same providers.
    mit_gedaechtnis = gedaechtnis.mitschicken(repositories, zustand)
    grund = grundprompt.bauen(
        werkzeuge=bool(
            registry is not None and config.features.mcp
            and zustand.kann("tool_calls") and agent.werkzeuge
        ),
        ordner=False,
        gedaechtnis=mit_gedaechtnis and bool(config.memory_lesen()),
    )
    basis = gedaechtnis.anhaengen(
        grundprompt.mit_benutzerprompt(grund, config.system_prompt_lesen()),
        config.memory_lesen() if mit_gedaechtnis else "",
    )
    system_teile = [teil for teil in (basis, agent.prompt) if teil]
    nachrichten = [ChatNachricht(role="system", content="\n\n".join(system_teile))]
    nachrichten.append(ChatNachricht(role="user", content=task))

    anfrage = Generierungsanfrage(
        nachrichten=nachrichten,
        max_tokens=config.app.default_max_tokens,
        modell=modellname,
    )

    if (
        registry is not None
        and config.features.mcp
        and zustand.kann("tool_calls")
        and agent.werkzeuge
    ):
        # Only the intersection of the agent's list and the registry. Whatever
        # the agent names but the server doesn't know is made visible instead
        # of silently swallowed — otherwise you'd go hunting for the bug in
        # the model.
        #
        # A job has no chat scope of its own, so the global off-list applies:
        # switching a tool off is meant to hold for everything, not only for
        # what happens to be typed by hand.
        werkzeugwahl.anwenden(registry, repositories)
        anfrage.werkzeuge = registry.als_openai_werkzeuge(nur=set(agent.werkzeuge))
        fehlend = set(agent.werkzeuge) - set(registry.namen())
        if fehlend:
            repositories.auftraege.schritt_anlegen(
                auftrag.id,
                "status",
                f"Werkzeuge nicht verfügbar: {', '.join(sorted(fehlend))}",
            )

    lauf = generierungen.starten(
        # chat_id carries the job id here — the run management doesn't ask
        # what's behind it, and the ids cannot collide.
        chat_id=auftrag.id,
        endpoint_id=endpoint_id,
        arbeit=_auftragslauf(
            auftrag_id=auftrag.id,
            agent=agent,
            anfrage=anfrage,
            zustand=zustand,
            registry=registry,
            repositories=repositories,
            generierungen=generierungen,
            sprache=sprache,
        ),
        an_verbindung_gebunden=False,
    )
    repositories.auftraege.generation_verknuepfen(auftrag.id, lauf.id)

    return repositories.auftraege.holen(auftrag.id)


@router.get("/jobs", response_model=list[AuftragAntwort], summary="Aufträge auflisten")
def auftraege_auflisten(
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    limit: int = 100,
    offset: int = 0,
) -> list[AuftragAntwort]:
    eintraege = repositories.auftraege.auflisten(
        user_id=user_id, limit=limit, offset=offset
    )
    return [AuftragAntwort.aus(auftrag) for auftrag in eintraege]


@router.get(
    "/jobs/{auftrag_id}",
    response_model=AuftragDetail,
    summary="Ein Auftrag samt Protokoll",
)
def auftrag_holen(
    auftrag_id: str,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> AuftragDetail:
    auftrag = repositories.auftraege.holen(auftrag_id, user_id=user_id)
    if auftrag is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, t("fehler.auftrag_nicht_gefunden", sprache)
        )
    return AuftragDetail.aus_mit_schritten(
        auftrag, repositories.auftraege.schritte(auftrag.id)
    )


@router.post(
    "/jobs/{auftrag_id}/cancel",
    response_model=AuftragAntwort,
    summary="Auftrag abbrechen",
)
def auftrag_abbrechen(
    auftrag_id: str,
    repositories: Repositories = Depends(hole_repositories),
    generierungen: Generierungsverwaltung = Depends(hole_generierungen),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> AuftragAntwort:
    auftrag = repositories.auftraege.holen(auftrag_id, user_id=user_id)
    if auftrag is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, t("fehler.auftrag_nicht_gefunden", sprache)
        )

    if auftrag.generation_id and generierungen.abbrechen(auftrag.generation_id):
        # The run is alive: it gets the signal and records state and reason
        # itself once it has stopped — exactly like the stop button in chat.
        return AuftragAntwort.aus(auftrag)

    if auftrag.zustand not in ENDZUSTAENDE:
        # No live run (waiting/interrupted): record it directly.
        auftrag = repositories.auftraege.zustand_setzen(
            auftrag.id, "abgebrochen", ende_grund="benutzer_abbruch"
        )
    return AuftragAntwort.aus(auftrag)


@router.delete(
    "/jobs/{auftrag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # The 204 trio, as with chat and agent deletion: explicitly no response
    # body, otherwise FastAPI rejects the route at startup.
    response_class=Response,
    response_model=None,
    summary="Auftrag löschen",
)
def auftrag_loeschen(
    auftrag_id: str,
    repositories: Repositories = Depends(hole_repositories),
    generierungen: Generierungsverwaltung = Depends(hole_generierungen),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> None:
    auftrag = repositories.auftraege.holen(auftrag_id, user_id=user_id)
    if auftrag is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, t("fehler.auftrag_nicht_gefunden", sprache)
        )
    # A still-living run is stopped first — gone means gone, not
    # "keeps running headless". On completion the run notices itself that
    # its job has disappeared and writes nothing more.
    if auftrag.generation_id:
        generierungen.abbrechen(auftrag.generation_id)
    repositories.auftraege.loeschen(auftrag_id, user_id=user_id)


# --- The run itself ---------------------------------------------------------


def _auftragslauf(
    *,
    auftrag_id: str,
    agent: Agent,
    anfrage: Generierungsanfrage,
    zustand,
    registry,
    repositories: Repositories,
    generierungen: Generierungsverwaltung,
    sprache: str,
):
    """Builds the background work for a job.

    Returns the ``arbeit`` function that the run management executes. The
    loop is the one from chat, but without confirmation prompts — the
    approval has already been made, it lives in the agent.
    """

    def protokoll(typ: str, inhalt: str) -> None:
        repositories.auftraege.schritt_anlegen(auftrag_id, typ, inhalt)

    async def arbeit(generierung: Generierung) -> None:
        antwort_text: list[str] = []
        messwerte: dict = {}
        fehlertext: str | None = None
        ende_grund: str | None = None
        abgebrochen = False
        quelle = None
        frist = time.monotonic() + agent.minuten * 60

        generierung.melden(
            _sse(
                "start",
                generation_id=generierung.id,
                auftrag_id=auftrag_id,
                agent=agent.name,
                endpoint_id=zustand.endpunkt.id,
            )
        )
        protokoll("status", "gestartet")

        try:
            for runde in range(agent.runden + 1):
                runden_text: list[str] = []
                runden_gedanke: list[str] = []
                aufrufe: list = []
                quelle = zustand.provider.streamen(anfrage)

                async for stueck in quelle:
                    if generierung.soll_abbrechen:
                        abgebrochen = True
                        break
                    if stueck.sorte == "content":
                        runden_text.append(stueck.text)
                        generierung.melden(_sse("content", text=stueck.text))
                    elif stueck.sorte == "reasoning":
                        runden_gedanke.append(stueck.text)
                        generierung.melden(_sse("reasoning", text=stueck.text))
                    elif stueck.sorte == "stats":
                        messwerte = stueck.daten
                    elif stueck.sorte == "tool_call":
                        aufrufe = stueck.werkzeugaufrufe
                    elif stueck.sorte == "error":
                        fehlertext = stueck.text

                await quelle.aclose()
                quelle = None

                antwort_text.extend(runden_text)
                if runden_gedanke:
                    protokoll("reasoning", "".join(runden_gedanke)[:GEDANKE_KUERZUNG])
                if runden_text:
                    protokoll("text", "".join(runden_text))

                if abgebrochen or fehlertext or not aufrufe:
                    break

                # The two restraints (6.4): rounds first, then time.
                # Checked at the round boundary — cutting off mid-answer
                # would mean throwing away what has already been produced.
                if runde >= agent.runden:
                    ende_grund = "rundengrenze"
                    break
                if time.monotonic() > frist:
                    ende_grund = "zeitgrenze"
                    break

                anfrage.nachrichten.append(
                    ChatNachricht(
                        role="assistant",
                        content="".join(runden_text),
                        werkzeugaufrufe=aufrufe,
                    )
                )

                for aufruf in aufrufe:
                    generierung.melden(
                        _sse(
                            "tool_call",
                            name=aufruf.name,
                            argumente=aufruf.argumente,
                            aufruf_id=aufruf.id,
                        )
                    )
                    protokoll(
                        "tool_call",
                        json.dumps(
                            {"name": aufruf.name, "argumente": aufruf.argumente},
                            ensure_ascii=False,
                        ),
                    )
                    # No confirmation prompt (decision 6): whatever the agent
                    # names is approved. The registry still checks once more —
                    # it remains the outer boundary.
                    ergebnis, fehlgeschlagen = await _werkzeug_ausfuehren(
                        registry, aufruf, sprache
                    )
                    generierung.melden(
                        _sse(
                            "tool_result",
                            name=aufruf.name,
                            aufruf_id=aufruf.id,
                            fehlgeschlagen=fehlgeschlagen,
                            text=ergebnis[:ERGEBNIS_KUERZUNG],
                        )
                    )
                    protokoll(
                        "tool_result",
                        json.dumps(
                            {
                                "name": aufruf.name,
                                "fehlgeschlagen": fehlgeschlagen,
                                "text": ergebnis[:ERGEBNIS_KUERZUNG],
                            },
                            ensure_ascii=False,
                        ),
                    )
                    anfrage.nachrichten.append(
                        ChatNachricht(
                            role="tool",
                            content=ergebnis,
                            werkzeugaufruf_id=aufruf.id,
                        )
                    )

        except ProviderFehler as fehler:
            text = str(fehler)
            if any(muster in text.lower() for muster in KONTEXT_VOLL_MUSTER):
                # A full context is not a crash (decision 10): the run ends
                # cleanly, and what has been produced so far is the report.
                ende_grund = "kontext_voll"
            else:
                fehlertext = text
            log.warning("Auftrag %s, Anbieter: %s", auftrag_id, fehler)
        except asyncio.CancelledError:
            abgebrochen = True
            raise
        except Exception:  # noqa: BLE001 - one run must not drag down the service
            fehlertext = t("fehler.allgemein", sprache)
            log.exception("Auftrag %s ist unerwartet gescheitert", auftrag_id)
        finally:
            if quelle is not None:
                await quelle.aclose()

            ergebnis = "".join(antwort_text)
            if abgebrochen:
                zustand_ende, grund = "abgebrochen", "benutzer_abbruch"
            elif fehlertext:
                zustand_ende = "gescheitert"
                grund = f"fehler: {fehlertext}"[:300]
            elif ende_grund in ("rundengrenze", "zeitgrenze", "kontext_voll"):
                # A snapped restraint is not a success — but it is a clean
                # ending with a report: whatever exists is in the result.
                zustand_ende, grund = "gescheitert", ende_grund
            else:
                zustand_ende, grund = "fertig", "fertig"

            if repositories.auftraege.holen(auftrag_id) is not None:
                protokoll("ende", grund)
                repositories.auftraege.zustand_setzen(
                    auftrag_id, zustand_ende, ende_grund=grund, ergebnis=ergebnis or None
                )
                repositories.auftraege.generation_verknuepfen(auftrag_id, None)
            # Otherwise: the job was deleted while the run was going (DELETE
            # stops first, then deletes) — there is nothing left to write the
            # ending to, and a log step without a job would be a foreign key
            # violation.
            generierungen.abmelden(generierung.id)

            if fehlertext:
                generierung.melden(_sse("error", text=fehlertext))
            generierung.melden(_sse("stats", daten=dict(messwerte or {})))
            generierung.melden(
                _sse("done", auftrag_id=auftrag_id, zustand=zustand_ende, grund=grund)
            )

    return arbeit
