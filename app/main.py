"""Entry point of the service.

One process, one port: FastAPI answers the API and serves the frontend's
static files at the same time. An nginx in front is possible at any time
without changing anything here.

Started in production via systemd, by hand:

    .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8090
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1 import router as api_v1_router
from app.api.v1.health import _health_ermitteln
from app.modelldownload import Modelldownload
from app import eewserver, einbettungsserver
from app.bildrunner import Bildrunner
from app.modellrunner import Modellrunner
from app.sddownload import Sddownload
from app.serverdownload import Serverdownload
from app.config import PROJEKT_WURZEL, Config, get_config
from app.paketierung import ressourcen
from app.db import datenbank_oeffnen, repositories_erstellen
from app.discovery import Discovery
from app.events import Ereignisse, bus
from app.generationen import Generierungsverwaltung
from app.hintergrundmeldung import anmelden as hintergrundmeldung_anmelden
from app.protokoll import ProtokollMiddleware, logging_einrichten, speicher_mb
from app.tools import WerkzeugRegistry, server_lesen
from app.tools.hintergrund import laeufe
from app.tools.mcp_auth import AuthSpeicher, OAuthVermittler
from app.wecker import Wecker

log = logging.getLogger(__name__)

# The interface ships with the program and is only ever read, so it comes
# from the shipped folder and not from beside the working directory.
STATIC_VERZEICHNIS = ressourcen() / "static"


def _standard_abonnenten_anmelden() -> None:
    """Logging hangs off the event system — not scattered through the modules' code."""

    async def chat_erstellt(chat_id: str, **_rest) -> None:
        log.info("Chat angelegt: %s", chat_id, extra={"ereignis": "chat_erstellt"})

    async def endpunkt_status(endpoint_id: str, erreichbar: bool, **_rest) -> None:
        log.info(
            "Endpunkt %s ist jetzt %s",
            endpoint_id,
            "erreichbar" if erreichbar else "nicht erreichbar",
            extra={
                "ereignis": "endpunkt_status",
                "endpunkt": endpoint_id,
                "erreichbar": erreichbar,
            },
        )

    async def antwort_fertig(endpoint_id: str = "", stats: dict | None = None, **_rest) -> None:
        messwerte = stats or {}
        log.info(
            "Antwort von %s: %s tok/s, %s s%s",
            endpoint_id,
            messwerte.get("tokens_pro_sekunde", "?"),
            messwerte.get("dauer_sekunden", "?"),
            " (abgebrochen)" if messwerte.get("abgebrochen") else "",
            extra={
                "ereignis": "antwort_fertig",
                "endpunkt": endpoint_id,
                "tokens_pro_sekunde": messwerte.get("tokens_pro_sekunde"),
                "dauer_sekunden": messwerte.get("dauer_sekunden"),
                "erstes_token_nach_sekunden": messwerte.get("erstes_token_nach_sekunden"),
                "abgebrochen": bool(messwerte.get("abgebrochen")),
                "werkzeuge": len(messwerte.get("werkzeuge") or []),
                "speicher_mb": speicher_mb(),
            },
        )

    bus.abonnieren(Ereignisse.CHAT_ERSTELLT, chat_erstellt)
    bus.abonnieren(Ereignisse.ENDPUNKT_STATUS_GEAENDERT, endpunkt_status)
    bus.abonnieren(Ereignisse.ANTWORT_FERTIG, antwort_fertig)
    bus.abonnieren(Ereignisse.ANTWORT_ABGEBROCHEN, antwort_fertig)


@asynccontextmanager
async def lebenszyklus(app: FastAPI):
    config: Config = app.state.config
    config.datenverzeichnis.mkdir(parents=True, exist_ok=True)

    db = datenbank_oeffnen(config)
    app.state.db = db
    app.state.repositories = repositories_erstellen(db)
    app.state.generierungen = Generierungsverwaltung()
    _standard_abonnenten_anmelden()
    # A background command reports its result into the chat when it is done.
    hintergrundmeldung_anmelden(app.state.repositories)

    # Clean up jobs (6.2): whatever was still running at the last stop is now,
    # honestly, interrupted. Pending confirmation prompts remain answerable.
    unterbrochen = app.state.repositories.auftraege.beim_start_aufraeumen()
    if unterbrochen:
        log.info(
            "%d Auftrag/Aufträge standen auf 'laeuft' und sind jetzt 'unterbrochen'",
            unterbrochen,
            extra={"ereignis": "auftraege_aufgeraeumt", "anzahl": unterbrochen},
        )

    # The browser sign-in for hosted MCP servers. Independent of the mcp
    # switch, so "connect" also works before the first server is running.
    # Redirect fixed to the loopback address — sign-in is local ONLY.
    oauth = OAuthVermittler(
        AuthSpeicher(config.pfad(config.mcp.auth_file)),
        rueckleitung=(
            f"http://127.0.0.1:{config.app.port}/api/v1/tools/oauth/callback"
        ),
    )
    app.state.mcp_oauth = oauth

    # Only build the tools when the feature is switched on.
    registry: WerkzeugRegistry | None = None
    if config.features.mcp:
        registry = WerkzeugRegistry(
            server_lesen(config.pfad(config.mcp.servers_file)),
            arbeitsverzeichnis=PROJEKT_WURZEL,
            oauth=oauth,
            shell_an=config.features.shell_tool,
            memory_pfad=config.pfad(config.app.memory_file),
            skills_orte=config.skillverzeichnisse,
        )
        await registry.starten()
    app.state.werkzeuge = registry

    discovery = Discovery(config, bus)
    app.state.discovery = discovery

    # The model runner. Built here and not per request: it holds a running
    # process, and a second instance would not know about the first.
    modellordner = config.pfad(config.app.modelle_verzeichnis)
    app.state.modellrunner = Modellrunner(modellordner, config.app.runner_programm)
    # The picture runner is built HERE and not on first use. Its whole job is
    # to hold one lock so two pictures cannot be drawn at once — and a lazy
    # "check, then create" in a request handler can be run twice at the same
    # moment by two requests, which would leave two runners holding two
    # locks and let exactly the thing happen that the lock exists to stop.
    app.state.bildrunner = Bildrunner(config.datenverzeichnis)
    # The embedding server: its own folder, its own port, its own note and
    # key. Not started here — it is a speed-up somebody switches on, and the
    # one-shot path works without it.
    app.state.einbettungsrunner = einbettungsserver.runner_bauen(
        config.pfad(config.app.einbettungsmodelle_verzeichnis),
        config.app.runner_programm,
        config.app.einbettung_port,
    )
    if app.state.einbettungsrunner.aufraeumen():
        log.info("Verwaister Einbettungsserver beendet")
    # The guardian's own small model — the fourth process this program may
    # hold. Not started here either: it comes up when Extended Workflow is
    # switched on and goes when it is switched off.
    app.state.eewrunner = eewserver.runner_bauen(
        modellordner, config.app.runner_programm
    )
    if app.state.eewrunner.aufraeumen():
        log.info("Verwaister Extended-Workflow-Server beendet")
    # A previous service run may have left its model server behind — it
    # lives in its own process group and holds the port until somebody who
    # knows about it ends it. That somebody is us, right now.
    if app.state.modellrunner.aufraeumen():
        log.info("Verwaister Modellserver aus dem vorigen Lauf beendet")
    app.state.modelldownload = Modelldownload(modellordner)
    # One folder per kind of model, keyed by the catalogue's tab names. The
    # download routes by this map, because each server reads only its own
    # folder — a file in the wrong one is invisible where it belongs and a
    # broken entry where it lands.
    app.state.modellordner_je_art = {
        "chat": modellordner,
        "einbettung": config.pfad(config.app.einbettungsmodelle_verzeichnis),
        "bild": config.pfad(config.app.bildmodelle_verzeichnis),
    }
    # The model server itself, fetchable in one click on machines that do
    # not have it — into the user's data folder, next to their models.
    app.state.serverdownload = Serverdownload(config.pfad("."))
    # The picture generator the same way. Built here rather than on first
    # use, so there is one of it: two requests arriving together would
    # otherwise each build their own and write into the same file.
    app.state.sddownload = Sddownload(config.datenverzeichnis)
    await discovery.starten()

    # The alarm clock (6.7) comes after discovery: its first pass catches up
    # on missed appointments and needs the reachability state for that.
    wecker = Wecker(app)
    app.state.wecker = wecker
    await wecker.starten()

    log.info(
        "Exe AI Terminal %s gestartet — Port %s, Sprache %s, Datenbank %s, "
        "%d/%d Endpunkte erreichbar, %d Werkzeug(e)",
        __version__,
        config.app.port,
        config.app.language,
        db.pfad,
        len(discovery.erreichbare()),
        len(discovery.alle()),
        registry.anzahl if registry else 0,
        extra={
            "ereignis": "start",
            "version": __version__,
            "port": config.app.port,
            "endpunkte_erreichbar": len(discovery.erreichbare()),
            "endpunkte_gesamt": len(discovery.alle()),
            "werkzeuge": registry.anzahl if registry else 0,
            "speicher_mb": speicher_mb(),
        },
    )
    try:
        yield
    finally:
        # No process outlives its chat unseen: whatever a background run
        # still has running goes down with the service.
        getoetet = laeufe.alle_toeten()
        if getoetet:
            log.info("%d laufende(r) Befehl(e) beim Beenden gestoppt", getoetet)
        await wecker.stoppen()
        if registry is not None:
            await registry.stoppen()
        await discovery.stoppen()
        db.schliessen()
        log.info("Exe AI Terminal beendet")


def app_erstellen(config: Config | None = None) -> FastAPI:
    config = config or get_config()
    logging_einrichten(config)

    app = FastAPI(
        title="Exe AI Terminal",
        version=__version__,
        description="Eigenes Interface zu lokalen und entfernten Sprachmodellen.",
        lifespan=lebenszyklus,
    )
    app.state.config = config
    # Outermost, so every request gets an id — including those that abort
    # with an error along the way.
    app.add_middleware(ProtokollMiddleware)

    # A browser on this machine can aim any web page at loopback; writes
    # from foreign origins are turned away — see app/herkunftswaechter.py.
    from app.herkunftswaechter import Herkunftswaechter
    app.add_middleware(Herkunftswaechter)

    # Beta latch: locks the write-access settings. The form in the UI shows
    # it, this latch enforces it — see app/beta.py.
    if config.features.beta_lock:
        from app.beta import BetaRiegel
        app.add_middleware(BetaRiegel)

    # HTML ALWAYS checks back with the server: index.html carries the reference to the current
    # bundle — if the browser blindly pulls it from cache, the app keeps
    # running on the old version after an update. The bundles themselves may
    # cache forever, their file name changes with every build.
    # no-cache means: use it, yes, but only after checking back (a 304 is cheap).
    @app.middleware("http")
    async def html_nie_stumpf_cachen(request, call_next):
        antwort = await call_next(request)
        if antwort.headers.get("content-type", "").startswith("text/html"):
            antwort.headers["Cache-Control"] = "no-cache"
        return antwort

    app.include_router(api_v1_router)

    # Unversioned health check — fixed address for monitoring/systemd.
    @app.get("/health", tags=["health"], summary="Zustand des Dienstes")
    def health():
        return _health_ermitteln(config, app.state.repositories)

    # PWA: the manifest must live at a fixed address.
    @app.get("/manifest.webmanifest", include_in_schema=False)
    def manifest():
        datei = STATIC_VERZEICHNIS / "manifest.webmanifest"
        if not datei.exists():
            return JSONResponse({"detail": "Manifest fehlt"}, status_code=404)
        return FileResponse(datei, media_type="application/manifest+json")

    # Mount static files last so the API routes take precedence.
    # The Vite-built Svelte folder will land here later.
    if STATIC_VERZEICHNIS.exists():
        app.mount(
            "/", StaticFiles(directory=STATIC_VERZEICHNIS, html=True), name="static"
        )
    else:
        log.warning("Kein static-Verzeichnis unter %s", STATIC_VERZEICHNIS)

    return app


app = app_erstellen()


if __name__ == "__main__":
    import uvicorn

    konfiguration = get_config()
    uvicorn.run(
        "app.main:app",
        host=konfiguration.app.host,
        port=konfiguration.app.port,
        reload=False,
    )
