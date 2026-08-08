"""Which tools are available (phase 1.6) — and their editor form (A6).

Shows only what remains after the lockdown — i.e. exactly what the model
actually gets offered. Since A6 the administration hangs here as well:
``GET/PUT /tools/config`` read and write the ``mcp_servers.json`` raw, with
a broken-check like the agent files. Saving means applying: a valid file
restarts the registry in the background.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re

from dotenv import dotenv_values, load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.api.abhaengigkeiten import hole_config
from app.config import PROJEKT_WURZEL, Config
from app.tools import WerkzeugRegistry, server_lesen
from app.tools.mcp_auth import MCPAnmeldeFehler, OAuthVermittler
from app.tools.registry import konfiguration_pruefen

log = logging.getLogger(__name__)

router = APIRouter(tags=["werkzeuge"])

# If the file does not exist yet, the editor form shows this skeleton.
KONFIG_VORLAGE = '{\n  "mcpServers": {}\n}\n'

PLATZHALTER_MUSTER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Two quick saves in a row must not brawl over app.state.
_neustart_sperre = asyncio.Lock()


class WerkzeugAntwort(BaseModel):
    name: str
    beschreibung: str
    server: str
    needs_confirmation: bool


class WerkzeugeAntwort(BaseModel):
    aktiv: bool
    server: list[str]
    werkzeuge: list[WerkzeugAntwort]


def hole_registry(request: Request) -> WerkzeugRegistry | None:
    return getattr(request.app.state, "werkzeuge", None)


@router.get("/tools", response_model=WerkzeugeAntwort, summary="Freigegebene Werkzeuge")
def werkzeuge(
    registry: WerkzeugRegistry | None = Depends(hole_registry),
    config: Config = Depends(hole_config),
) -> WerkzeugeAntwort:
    if registry is None:
        return WerkzeugeAntwort(aktiv=False, server=[], werkzeuge=[])
    return WerkzeugeAntwort(
        aktiv=config.features.mcp,
        server=sorted(registry.clients),
        werkzeuge=[WerkzeugAntwort(**eintrag) for eintrag in registry.uebersicht()],
    )


# --- The editor form (A6): reading and writing mcp_servers.json -------------


class PlatzhalterAntwort(BaseModel):
    name: str
    gesetzt: bool


class WerkzeugKonfiguration(BaseModel):
    content: str
    kaputt: str | None
    platzhalter: list[PlatzhalterAntwort]


class WerkzeugKonfigurationSchreiben(BaseModel):
    content: str


def _platzhalter(text: str) -> list[PlatzhalterAntwort]:
    """The ${…} placeholders with their traffic light: set or missing.

    The .env is read fresh on every request — a token just entered via SSH
    shows green immediately, without restarting the service.
    The values themselves never leave the server (the UI has no login).
    """
    env_datei = dotenv_values(PROJEKT_WURZEL / ".env")
    namen = set(PLATZHALTER_MUSTER.findall(text))
    # `api_key_env` points to the same place (.env), just without the
    # ${…} notation — the traffic light should show it just the same.
    try:
        rohdaten = json.loads(text)
        for felder in (rohdaten.get("mcpServers") or {}).values():
            if isinstance(felder, dict):
                wert = felder.get("api_key_env")
                if isinstance(wert, str) and wert:
                    namen.add(wert)
    except (json.JSONDecodeError, AttributeError):
        pass  # a broken file has its own message
    return [
        PlatzhalterAntwort(
            name=name, gesetzt=bool(os.environ.get(name) or env_datei.get(name))
        )
        for name in sorted(namen)
    ]


def _konfig_antwort(text: str) -> WerkzeugKonfiguration:
    return WerkzeugKonfiguration(
        content=text, kaputt=konfiguration_pruefen(text), platzhalter=_platzhalter(text)
    )


@router.get(
    "/tools/config",
    response_model=WerkzeugKonfiguration,
    summary="Die rohe Werkzeug-Konfiguration (für die Maske)",
)
def werkzeug_konfiguration(config: Config = Depends(hole_config)) -> WerkzeugKonfiguration:
    pfad = config.pfad(config.mcp.servers_file)
    text = pfad.read_text(encoding="utf-8") if pfad.exists() else KONFIG_VORLAGE
    return _konfig_antwort(text)


@router.put(
    "/tools/config",
    response_model=WerkzeugKonfiguration,
    summary="Werkzeug-Konfiguration sichern und anwenden",
)
async def werkzeug_konfiguration_schreiben(
    daten: WerkzeugKonfigurationSchreiben,
    request: Request,
    config: Config = Depends(hole_config),
) -> WerkzeugKonfiguration:
    """Always saves — it is the user's file.

    If it's no good, the reason goes into ``kaputt`` and nothing is applied.
    If it's good, the tool servers restart in the background — the response
    does not wait for that (an npx cold start can take a while), the form's
    read display fetches the result via ``GET /tools``.
    """
    pfad = config.pfad(config.mcp.servers_file)
    pfad.write_text(daten.content, encoding="utf-8")
    antwort = _konfig_antwort(daten.content)
    if antwort.kaputt is None and config.features.mcp:
        asyncio.create_task(
            _registry_neustarten(request.app, config), name="registry-neustart"
        )
    return antwort


# --- The server entries, structured (for the tile gallery) ------------------
#
# The gallery writes mcp_servers.json in structured form instead of raw: an
# entry is created, toggled, or removed without anyone typing JSON.
# The file remains the single truth — the text field behind it works
# unchanged, both paths write to the same place.


class WerkzeugKurz(BaseModel):
    name: str
    beschreibung: str


class ServerUebersicht(BaseModel):
    name: str
    type: str
    url: str | None
    enabled: bool
    api_key_env: str | None
    allowed_tools: list[str] | None
    needs_confirmation: list[str]
    # Is the server currently alive in the registry?
    laeuft: bool
    # Only with api_key_env: is the key present in the .env?
    schluessel_gesetzt: bool | None
    # If it is running: ALL tools the server offers — the checkbox list
    # shows them in full, approved is the intersection.
    alle_werkzeuge: list[WerkzeugKurz]


class ServerSchreiben(BaseModel):
    type: str | None = None
    url: str | None = None
    enabled: bool | None = None
    api_key_env: str | None = None
    allowed_tools: list[str] | None = None
    needs_confirmation: list[str] | None = None


def _rohdaten_lesen(config: Config) -> dict:
    pfad = config.pfad(config.mcp.servers_file)
    if not pfad.exists():
        return {"mcpServers": {}}
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"mcpServers": {}}
    if not isinstance(daten, dict) or not isinstance(daten.get("mcpServers"), dict):
        return {"mcpServers": {}}
    return daten


def _schluessel_gesetzt(name: str | None) -> bool | None:
    if not name:
        return None
    env_datei = dotenv_values(PROJEKT_WURZEL / ".env")
    return bool(os.environ.get(name) or env_datei.get(name))


@router.get(
    "/tools/servers",
    response_model=list[ServerUebersicht],
    summary="Die Server-Einträge samt Live-Zustand (für die Galerie)",
)
def server_uebersicht(
    registry: WerkzeugRegistry | None = Depends(hole_registry),
    config: Config = Depends(hole_config),
) -> list[ServerUebersicht]:
    uebersicht = []
    for eintrag in server_lesen(config.pfad(config.mcp.servers_file)):
        client = registry.clients.get(eintrag.name) if registry else None
        uebersicht.append(
            ServerUebersicht(
                name=eintrag.name,
                type=eintrag.type,
                url=eintrag.url,
                enabled=eintrag.enabled,
                api_key_env=eintrag.api_key_env,
                allowed_tools=eintrag.allowed_tools,
                needs_confirmation=eintrag.needs_confirmation,
                laeuft=client is not None,
                schluessel_gesetzt=_schluessel_gesetzt(eintrag.api_key_env),
                alle_werkzeuge=[
                    WerkzeugKurz(name=w.name, beschreibung=w.beschreibung)
                    for w in (client.werkzeuge if client else [])
                ],
            )
        )
    return sorted(uebersicht, key=lambda e: e.name)


@router.put(
    "/tools/servers/{name}",
    response_model=WerkzeugKonfiguration,
    summary="Einen Server-Eintrag anlegen oder ändern (für die Galerie)",
)
async def server_schreiben(
    name: str,
    daten: ServerSchreiben,
    request: Request,
    config: Config = Depends(hole_config),
) -> WerkzeugKonfiguration:
    """Only named fields are touched; an explicit null deletes the field
    (allowed_tools: null again means: offer everything).

    Unlike the raw text field, what would be broken is NOT saved here —
    the gallery types no JSON, so there is no honest reason to accept a
    broken file.
    """
    rohdaten = _rohdaten_lesen(config)
    eintrag = rohdaten["mcpServers"].setdefault(name, {})
    for feld, wert in daten.model_dump(exclude_unset=True).items():
        if wert is None:
            eintrag.pop(feld, None)
        else:
            eintrag[feld] = wert

    text = json.dumps(rohdaten, ensure_ascii=False, indent=2) + "\n"
    kaputt = konfiguration_pruefen(text)
    if kaputt is not None:
        raise HTTPException(400, kaputt)

    config.pfad(config.mcp.servers_file).write_text(text, encoding="utf-8")
    if config.features.mcp:
        asyncio.create_task(
            _registry_neustarten(request.app, config), name="registry-neustart"
        )
    return _konfig_antwort(text)


@router.delete(
    "/tools/servers/{name}",
    status_code=204,
    response_model=None,
    response_class=Response,
    summary="Einen Server-Eintrag entfernen (samt Zugang)",
)
async def server_entfernen(
    name: str,
    request: Request,
    config: Config = Depends(hole_config),
) -> None:
    rohdaten = _rohdaten_lesen(config)
    if name not in rohdaten["mcpServers"]:
        raise HTTPException(404, f"'{name}' ist nicht eingetragen")
    del rohdaten["mcpServers"][name]
    text = json.dumps(rohdaten, ensure_ascii=False, indent=2) + "\n"
    config.pfad(config.mcp.servers_file).write_text(text, encoding="utf-8")
    # Whoever throws away the entry doesn't want to keep the access either.
    vermittler = getattr(request.app.state, "mcp_oauth", None)
    if vermittler is not None:
        vermittler.vergessen(name)
    if config.features.mcp:
        asyncio.create_task(
            _registry_neustarten(request.app, config), name="registry-neustart"
        )


# --- The browser sign-in (OAuth) for hosted servers -------------------------


def hole_oauth(request: Request) -> OAuthVermittler:
    return request.app.state.mcp_oauth


class OAuthStartAnfrage(BaseModel):
    server: str
    # The manual route (Google & co.): a client id created by hand at the
    # provider. Empty means: dynamic registration.
    client_id: str | None = None
    client_secret: str | None = None


class OAuthStartAntwort(BaseModel):
    url: str


class OAuthStatusAntwort(BaseModel):
    server: str
    verbunden: bool
    laeuft_ab: float | None


@router.post(
    "/tools/oauth/start",
    response_model=OAuthStartAntwort,
    summary="Browser-Anmeldung bei einem gehosteten MCP-Server beginnen",
)
async def oauth_start(
    daten: OAuthStartAnfrage,
    vermittler: OAuthVermittler = Depends(hole_oauth),
    config: Config = Depends(hole_config),
) -> OAuthStartAntwort:
    """Prepares the sign-in dance and returns the address for the browser.

    The UI does the opening — the server opens no windows.
    """
    eintraege = {
        e.name: e for e in server_lesen(config.pfad(config.mcp.servers_file))
    }
    eintrag = eintraege.get(daten.server)
    if eintrag is None or eintrag.type != "http" or not eintrag.url:
        raise HTTPException(
            404, f"'{daten.server}' ist kein eingetragener http-Server"
        )
    if eintrag.api_key_env:
        raise HTTPException(
            400,
            f"'{daten.server}' meldet sich mit einem festen Schlüssel an "
            f"({eintrag.api_key_env}) — da gibt es nichts zu verbinden",
        )
    try:
        url = await vermittler.anmelde_url(
            daten.server, eintrag.url, daten.client_id, daten.client_secret
        )
    except MCPAnmeldeFehler as fehler:
        raise HTTPException(400, str(fehler)) from None
    return OAuthStartAntwort(url=url)


def _rueckruf_seite(gelungen: bool, text: str) -> str:
    """The small page the browser lands on after signing in.

    Bilingual instead of via the catalog: it runs outside the app and
    should speak for itself even without the UI loaded.
    """
    if gelungen:
        titel = "Verbunden"
        zeile = (
            f'„{text}“ ist verbunden. Dieses Fenster kann geschlossen werden.'
            f'<br><span class="en">“{text}” is connected. You can close this window.</span>'
        )
    else:
        titel = "Nicht verbunden"
        zeile = f'{text}<br><span class="en">The sign-in did not complete.</span>'
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>{titel} — Exe AI Terminal</title>
<style>
  body {{ font: 15px/1.6 -apple-system, system-ui, sans-serif; display: grid;
         place-items: center; min-height: 90vh; margin: 0;
         background: #f6f6f4; color: #1a1a18; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #161615; color: #ececea; }} }}
  main {{ text-align: center; padding: 24px; }}
  h1 {{ font-size: 19px; margin: 0 0 8px; }}
  .en {{ opacity: 0.6; font-size: 13px; }}
</style></head>
<body><main><h1>{titel}</h1><p>{zeile}</p></main></body></html>"""


@router.get(
    "/tools/oauth/callback",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def oauth_rueckruf(
    request: Request,
    state: str = "",
    code: str = "",
    error: str = "",
    vermittler: OAuthVermittler = Depends(hole_oauth),
    config: Config = Depends(hole_config),
) -> HTMLResponse:
    """This is where the browser lands after signing in at the provider.

    Secured by the one-time, time-limited state — without it nothing is
    exchanged. After a successful exchange the tool servers restart in the
    background so the freshly connected one joins in immediately.
    """
    if error:
        return HTMLResponse(
            _rueckruf_seite(False, f"Der Anbieter meldet: {error}"), status_code=400
        )
    try:
        server = await vermittler.rueckruf(state, code)
    except MCPAnmeldeFehler as fehler:
        return HTMLResponse(_rueckruf_seite(False, str(fehler)), status_code=400)
    if config.features.mcp:
        asyncio.create_task(
            _registry_neustarten(request.app, config), name="registry-neustart"
        )
    return HTMLResponse(_rueckruf_seite(True, server))


@router.get(
    "/tools/oauth/status",
    response_model=list[OAuthStatusAntwort],
    summary="Welche gehosteten Server verbunden sind (nie die Werte)",
)
def oauth_status(
    vermittler: OAuthVermittler = Depends(hole_oauth),
) -> list[OAuthStatusAntwort]:
    return [
        OAuthStatusAntwort(server=server, **eintrag)
        for server, eintrag in sorted(vermittler.status().items())
    ]


@router.delete(
    "/tools/oauth/{server}",
    status_code=204,
    # Explicitly NO response model: FastAPI otherwise interprets the
    # "-> None" annotation as a NoneType model and refuses with 204.
    response_model=None,
    response_class=Response,
    summary="Trennen und Zugang vergessen",
)
async def oauth_vergessen(
    server: str,
    request: Request,
    vermittler: OAuthVermittler = Depends(hole_oauth),
    config: Config = Depends(hole_config),
) -> None:
    """Throws away the credentials and rebuilds the registry — the server's
    tools thereby disappear from the offering immediately."""
    vermittler.vergessen(server)
    if config.features.mcp:
        asyncio.create_task(
            _registry_neustarten(request.app, config), name="registry-neustart"
        )


async def _registry_neustarten(app, config: Config) -> None:
    """Rebuilds the registry from the freshly saved file.

    Saving means applying (A6 decision). The old registry is not stopped
    immediately: running runs hold it in hand and finish with the old
    tools — it is wound down as soon as no run is alive anymore.
    """
    async with _neustart_sperre:
        try:
            # Pick up freshly entered secrets. override, because the .env
            # is the authoritative source here — a token changed there
            # should win, not the old value in the process.
            load_dotenv(PROJEKT_WURZEL / ".env", override=True)
            neu = WerkzeugRegistry(
                server_lesen(config.pfad(config.mcp.servers_file)),
                arbeitsverzeichnis=PROJEKT_WURZEL,
                oauth=getattr(app.state, "mcp_oauth", None),
                shell_an=config.features.shell_tool,
                memory_pfad=config.pfad(config.app.memory_file),
                skills_orte=config.skillverzeichnisse,
            )
            await neu.starten()
        except Exception:  # noqa: BLE001 - a broken restart must not drag down the service
            log.exception("Registry-Neustart fehlgeschlagen — die alte bleibt im Dienst")
            return
        alt = getattr(app.state, "werkzeuge", None)
        app.state.werkzeuge = neu
        log.info(
            "Werkzeug-Registry neu aufgebaut: %d Werkzeug(e) aus %d Server(n)",
            neu.anzahl,
            len(neu.clients),
            extra={"ereignis": "registry_neustart", "werkzeuge": neu.anzahl},
        )
        if alt is not None:
            asyncio.create_task(
                _ausklingen(alt, app.state.generierungen), name="registry-ausklingen"
            )


async def _ausklingen(registry: WerkzeugRegistry, generierungen) -> None:
    """Stops the superseded registry as soon as no run is alive anymore.

    Upper bound half an hour — longer than any job restraint. After that it
    is stopped even if something is still running: a tool call to it then
    fails visibly as a failed result, not as a crash.
    """
    schleife = asyncio.get_event_loop()
    frist = schleife.time() + 30 * 60
    while generierungen.laufende() and schleife.time() < frist:
        await asyncio.sleep(10)
    await registry.stoppen()
