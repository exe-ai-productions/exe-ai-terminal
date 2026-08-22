"""Tool registry — what is the model even allowed to touch?

The servers live in ``mcp_servers.json``. This file is the place where the
settings window will later hook in: enter, save, done.

The lockdown is the most important part of this file. Strictly:

  * Only servers from the file are started, and only those with ``enabled``.
  * If a server has ``allowed_tools``, exclusively those are offered —
    everything else the server can otherwise do stays out.
  * Tools under ``needs_confirmation`` are offered to the model but not
    simply executed: the streaming proxy stops and asks back. Without an
    explicit yes, nothing is executed.
  * What is not in the registry is not executed — even if the model asks
    for it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.paketierung import ist_eingefroren, programmpfad

# Which shipped servers the program can be itself. Same list as in
# start.py, and short on purpose: only what travels with the program.
MCP_SERVER = {"websuche", "searxng"}
import httpx

from app.tools import (
    bild_werkzeug, dateiwerkzeuge, frage_werkzeug, grenzen, memory, shell, skill,
)
from app.tools.mcp_client import MCPFehler, MCPStdioClient, MCPWerkzeug
from app.tools.mcp_http import MCPHttpClient

log = logging.getLogger(__name__)

# Both variants speak the same language (starten, stoppen, werkzeuge,
# werkzeug_aufrufen) — the registry only distinguishes during setup.
MCPClient = MCPStdioClient | MCPHttpClient


class WerkzeugVerboten(Exception):
    """The model demanded a tool that is not approved."""


@dataclass
class ServerEintrag:
    name: str
    type: str = "stdio"
    command: str = ""
    args: list[str] = None  # type: ignore[assignment]
    env: dict[str, str] = None  # type: ignore[assignment]
    enabled: bool = True
    allowed_tools: list[str] | None = None
    needs_confirmation: list[str] = None  # type: ignore[assignment]
    # The HTTP kind: address of the hosted server …
    url: str | None = None
    # … and the name of the key in the .env (never the key itself) —
    # the same pattern as with the model and image endpoints. If missing,
    # OAuth is attempted (next build step).
    api_key_env: str | None = None

    def __post_init__(self) -> None:
        self.args = self.args or []
        self.env = self.env or {}
        self.needs_confirmation = self.needs_confirmation or []


def server_lesen(pfad: Path) -> list[ServerEintrag]:
    """Reads mcp_servers.json. If the file is missing, there are simply no tools."""
    if not pfad.exists():
        log.info("Keine MCP-Konfiguration unter %s — keine Werkzeuge aktiv", pfad)
        return []

    rohdaten = json.loads(pfad.read_text(encoding="utf-8"))
    eintraege = rohdaten.get("mcpServers") or {}
    return [
        ServerEintrag(name=name, **felder)
        for name, felder in eintraege.items()
    ]



# The fields of a server entry as the editor form (A6) checks them.
# Deliberately its own list instead of derived from the dataclass: `name` is
# a field there, but in the file it is the key.
_ERLAUBTE_FELDER = {
    "type", "command", "args", "env", "enabled",
    "allowed_tools", "needs_confirmation", "url", "api_key_env",
}


def konfiguration_pruefen(text: str) -> str | None:
    """Checks raw ``mcp_servers.json`` content for the editor form (A6).

    Returns the reason if the file is no good — otherwise ``None``.
    Same approach as with the agent files: it is saved anyway, but the UI
    immediately says what needs fixing, and only what is valid gets applied
    (registry restart).
    """
    try:
        rohdaten = json.loads(text)
    except json.JSONDecodeError as fehler:
        return f"kein gültiges JSON: {fehler}"
    if not isinstance(rohdaten, dict):
        return "die oberste Ebene muss ein Objekt sein"
    eintraege = rohdaten.get("mcpServers")
    if not isinstance(eintraege, dict):
        return "'mcpServers' fehlt oder ist kein Objekt"

    for name, felder in eintraege.items():
        if not isinstance(felder, dict):
            return f"Server '{name}': der Eintrag muss ein Objekt sein"
        unbekannt = set(felder) - _ERLAUBTE_FELDER
        if unbekannt:
            return f"Server '{name}': unbekannte Felder: {', '.join(sorted(unbekannt))}"
        typ = felder.get("type", "stdio")
        if not isinstance(typ, str):
            return f"Server '{name}': 'type' muss ein Text sein"
        if typ not in ("stdio", "http"):
            # Honest instead of silent: what will never start counts as broken.
            return (
                f"Server '{name}': unbekannter Typ '{typ}' — "
                "es gibt 'stdio' und 'http'"
            )
        if not isinstance(felder.get("command", ""), str):
            return f"Server '{name}': 'command' muss ein Text sein"
        if not isinstance(felder.get("url", ""), str):
            return f"Server '{name}': 'url' muss ein Text sein"
        if not isinstance(felder.get("api_key_env", ""), str):
            return f"Server '{name}': 'api_key_env' muss ein Name sein"
        if typ == "http" and not felder.get("url"):
            return f"Server '{name}': Typ 'http' braucht eine 'url'"
        args = felder.get("args", [])
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            return f"Server '{name}': 'args' muss eine Liste von Texten sein"
        env = felder.get("env", {})
        if not isinstance(env, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in env.items()
        ):
            return f"Server '{name}': 'env' muss ein Objekt aus Texten sein"
        if not isinstance(felder.get("enabled", True), bool):
            return f"Server '{name}': 'enabled' muss true oder false sein"
        for listenfeld in ("allowed_tools", "needs_confirmation"):
            wert = felder.get(listenfeld)
            if wert is None:
                continue
            if not isinstance(wert, list) or not all(isinstance(w, str) for w in wert):
                return f"Server '{name}': '{listenfeld}' muss eine Liste von Namen sein"
    return None


class WerkzeugRegistry:
    """Holds the connections to all MCP servers and the tool list."""

    def __init__(
        self,
        eintraege: list[ServerEintrag],
        arbeitsverzeichnis: Path | None = None,
        oauth=None,
        shell_an: bool = False,
        memory_pfad: Path | None = None,
        skills_orte: tuple[Path, Path] | None = None,
        bild_zugang: tuple[str, Path] | None = None,
    ) -> None:
        self.eintraege = eintraege
        self.arbeitsverzeichnis = arbeitsverzeichnis
        # The shell tool is built in, not an MCP server (see app/tools/shell.py):
        # its working folders belong to the chat and change while the program
        # runs. It is offered like any other tool but travels a shorter path.
        self.shell_an = shell_an
        # Where the memory file lives. Built in for the same reason as the
        # shell tool: the path belongs to the program, and anything handed
        # over as an argument can be forged by the model. None means the
        # tool does not exist.
        self.memory_pfad = memory_pfad
        # The two skill folders, shipped and the user's, for the same reason
        # as the memory path. None means the two skill tools do not exist.
        self.skills_orte = skills_orte
        # This service's own API root and its picture folder, for the
        # drawing tool. Built in like the memory path: the address and the
        # folder belong to the program, never to a model's argument. None
        # means the tool does not exist.
        self.bild_zugang = bild_zugang
        # The OAuthVermittler (mcp_auth) — for hosted servers without a
        # fixed key. None means: such servers remain unconnected.
        self.oauth = oauth
        self.clients: dict[str, MCPClient] = {}
        # Tool name -> (client, tool, needs confirmation)
        self._werkzeuge: dict[str, tuple[MCPClient, MCPWerkzeug, bool]] = {}
        # Switched off by the user (app/werkzeugwahl.py). Not part of the
        # setup: the pick lives in the server entry and is fixed while the
        # registry starts, while this one changes with a click and is handed
        # in fresh per run.
        self.abgeschaltet: set[str] = set()

    # --- Setup -----------------------------------------------------------

    async def starten(self) -> None:
        for eintrag in self.eintraege:
            if not eintrag.enabled:
                continue
            client = self._client_bauen(eintrag)
            if client is None:
                continue
            # Hosted servers without a fixed key run via the browser
            # sign-in: fetch access, silently renewed if needed.
            # Without access the server does not start — the tile shows
            # "reconnect", the model is offered nothing dead.
            if (
                isinstance(client, MCPHttpClient)
                and client.api_key is None
                and not eintrag.api_key_env
            ):
                if self.oauth is None:
                    log.info(
                        "MCP-Server '%s': keine Anmeldung möglich (kein "
                        "Vermittler) — wird übersprungen",
                        eintrag.name,
                    )
                    continue
                zugang = await self.oauth.gueltiges_token(eintrag.name)
                if zugang is None:
                    log.info(
                        "MCP-Server '%s': nicht verbunden — Anmeldung über "
                        "die Einstellungen",
                        eintrag.name,
                    )
                    continue
                client.api_key = zugang
                client.token_erneuern = (
                    lambda name=eintrag.name: self.oauth.token_erneuern(name)
                )
            try:
                await client.starten()
            except (MCPFehler, OSError, asyncio.TimeoutError, httpx.HTTPError) as fehler:
                log.error("MCP-Server '%s' konnte nicht starten: %s", eintrag.name, fehler)
                continue

            self.clients[eintrag.name] = client
            self._werkzeuge_uebernehmen(eintrag, client)

        log.info(
            "Werkzeuge bereit: %d aus %d MCP-Server(n)",
            len(self._werkzeuge),
            len(self.clients),
        )

    def _client_bauen(self, eintrag: ServerEintrag) -> MCPClient | None:
        """Builds the client matching the variant — or explains why not."""
        if eintrag.type == "stdio":
            # Packaged there is no interpreter to start a script with — the
            # program is its own tool server. The entry keeps saying what it
            # says, and the translation happens here, in the one place that
            # actually starts something.
            if ist_eingefroren() and eintrag.name in MCP_SERVER:
                befehl, argumente = str(programmpfad()), ["--mcp", eintrag.name]
            else:
                befehl, argumente = eintrag.command, eintrag.args

            return MCPStdioClient(
                name=eintrag.name,
                command=befehl,
                args=argumente,
                # ${NOTION_TOKEN} and co. are resolved here — the values
                # come from the environment (.env is loaded at service start
                # and before every registry restart). A missing value stays
                # as ${…} and the server fails visibly instead of running
                # silently with an empty secret.
                env={
                    schluessel: os.path.expandvars(wert)
                    for schluessel, wert in eintrag.env.items()
                },
                arbeitsverzeichnis=str(self.arbeitsverzeichnis) if self.arbeitsverzeichnis else None,
            )

        if eintrag.type == "http":
            if not eintrag.url:
                log.error(
                    "MCP-Server '%s': Typ 'http' ohne 'url' — wird übersprungen",
                    eintrag.name,
                )
                return None
            schluessel = None
            if eintrag.api_key_env:
                schluessel = os.environ.get(eintrag.api_key_env) or None
                if schluessel is None:
                    # House rule: the model is offered nothing that is sure
                    # to fail. Without a key the server doesn't even start —
                    # the editor form shows the missing name as a red light.
                    log.error(
                        "MCP-Server '%s': Schlüssel '%s' ist nicht gesetzt (.env) "
                        "— wird übersprungen",
                        eintrag.name,
                        eintrag.api_key_env,
                    )
                    return None
            # Without api_key_env, the connection is made unauthenticated —
            # servers that demand OAuth visibly reject that with a 401 until
            # the sign-in flow (next build step) is in place.
            return MCPHttpClient(name=eintrag.name, url=eintrag.url, api_key=schluessel)

        log.warning(
            "MCP-Server '%s' hat Typ '%s' — es gibt 'stdio' und 'http', "
            "wird übersprungen",
            eintrag.name,
            eintrag.type,
        )
        return None

    def _werkzeuge_uebernehmen(self, eintrag: ServerEintrag, client: MCPClient) -> None:
        for werkzeug in client.werkzeuge:
            if eintrag.allowed_tools is not None:
                if werkzeug.name not in eintrag.allowed_tools:
                    log.info(
                        "Werkzeug '%s' von '%s' ist nicht freigegeben und wird nicht angeboten",
                        werkzeug.name,
                        eintrag.name,
                    )
                    continue
            if werkzeug.name in self._werkzeuge:
                log.warning(
                    "Werkzeugname '%s' ist doppelt vergeben — der Eintrag von '%s' gewinnt",
                    werkzeug.name,
                    self._werkzeuge[werkzeug.name][1].server,
                )
                continue
            self._werkzeuge[werkzeug.name] = (
                client,
                werkzeug,
                werkzeug.name in eintrag.needs_confirmation,
            )

    async def stoppen(self) -> None:
        for client in self.clients.values():
            await client.stoppen()
        self.clients.clear()
        self._werkzeuge.clear()

    # --- Usage -----------------------------------------------------------

    @property
    def anzahl(self) -> int:
        return len(self._werkzeuge) + (
            2 + len(dateiwerkzeuge.NAMEN) if self.shell_an else 0
        )

    def namen(self) -> list[str]:
        namen = list(self._werkzeuge)
        if self.shell_an:
            namen.append(shell.WERKZEUG_NAME)
            namen.append(frage_werkzeug.WERKZEUG_NAME)
            namen += list(dateiwerkzeuge.NAMEN)
        if self.bild_zugang is not None:
            namen.append(bild_werkzeug.WERKZEUG_NAME)
        return sorted(namen)

    def uebersicht(self) -> list[dict[str, Any]]:
        eintraege = [
            {
                "name": name,
                "beschreibung": werkzeug.beschreibung,
                "server": werkzeug.server,
                "needs_confirmation": bestaetigung,
            }
            for name, (_, werkzeug, bestaetigung) in self._werkzeuge.items()
        ]
        if self.memory_pfad is not None:
            beschreibung = memory.werkzeug_beschreibung()
            eintraege.append(
                {
                    "name": beschreibung.name,
                    "beschreibung": beschreibung.beschreibung,
                    "server": beschreibung.server,
                    "needs_confirmation": False,
                }
            )
        if self.skills_orte is not None:
            for beschreibung in skill.werkzeug_beschreibungen():
                eintraege.append(
                    {
                        "name": beschreibung.name,
                        "beschreibung": beschreibung.beschreibung,
                        "server": beschreibung.server,
                        "needs_confirmation": False,
                    }
                )
        if self.bild_zugang is not None:
            beschreibung = bild_werkzeug.werkzeug_beschreibung()
            eintraege.append(
                {
                    "name": beschreibung.name,
                    "beschreibung": beschreibung.beschreibung,
                    "server": beschreibung.server,
                    # Draws locally into the program's own folders — nothing
                    # leaves the machine and nothing of the user's is touched.
                    "needs_confirmation": False,
                }
            )
        if self.shell_an:
            beschreibung = shell.werkzeug_beschreibung()
            eintraege.append(
                {
                    "name": beschreibung.name,
                    "beschreibung": beschreibung.beschreibung,
                    "server": beschreibung.server,
                    # Not a fixed yes or no: it depends on where the command
                    # reaches. The overview can only say "sometimes", and
                    # says it as "yes" so nobody reads it as unguarded.
                    "needs_confirmation": True,
                }
            )
            for beschreibung in dateiwerkzeuge.beschreibungen():
                eintraege.append(
                    {
                        "name": beschreibung.name,
                        "beschreibung": beschreibung.beschreibung,
                        "server": beschreibung.server,
                        # Same "sometimes" as the shell: it depends on where
                        # the path reaches.
                        "needs_confirmation": True,
                    }
                )
            beschreibung = frage_werkzeug.werkzeug_beschreibung()
            eintraege.append(
                {
                    "name": beschreibung.name,
                    "beschreibung": beschreibung.beschreibung,
                    "server": beschreibung.server,
                    # It IS the question — there is nothing to confirm first.
                    "needs_confirmation": False,
                }
            )
        return sorted(eintraege, key=lambda e: e["name"])

    def als_openai_werkzeuge(self, nur: set[str] | None = None) -> list[dict[str, Any]]:
        """The tool list in the form that goes to the model.

        ``nur`` is an agent's allowlist (6.3): what is offered is the
        intersection of it and what the server approves — the registry
        remains the outer boundary. ``None`` means as before: everything
        approved.

        What the user switched off never appears, no matter who asks. A tool
        the model cannot see is one it cannot call, which is the cheapest
        enforcement there is.
        """
        liste = [
            werkzeug.als_openai_werkzeug()
            for name, (_, werkzeug, _) in self._werkzeuge.items()
            if (nur is None or name in nur) and name not in self.abgeschaltet
        ]
        if (
            self.shell_an
            and (nur is None or shell.WERKZEUG_NAME in nur)
            and shell.WERKZEUG_NAME not in self.abgeschaltet
        ):
            liste.append(shell.werkzeug_beschreibung().als_openai_werkzeug())
        if self.shell_an:
            liste += [
                b.als_openai_werkzeug()
                for b in dateiwerkzeuge.beschreibungen()
                if (nur is None or b.name in nur) and b.name not in self.abgeschaltet
            ]
        if (
            self.shell_an
            and (nur is None or frage_werkzeug.WERKZEUG_NAME in nur)
            and frage_werkzeug.WERKZEUG_NAME not in self.abgeschaltet
        ):
            liste.append(frage_werkzeug.werkzeug_beschreibung().als_openai_werkzeug())
        if (
            self.memory_pfad is not None
            and (nur is None or memory.WERKZEUG_NAME in nur)
            and memory.WERKZEUG_NAME not in self.abgeschaltet
        ):
            liste.append(memory.werkzeug_beschreibung().als_openai_werkzeug())
        if self.skills_orte is not None:
            liste += [
                b.als_openai_werkzeug()
                for b in skill.werkzeug_beschreibungen()
                if (nur is None or b.name in nur) and b.name not in self.abgeschaltet
            ]
        if (
            self.bild_zugang is not None
            and (nur is None or bild_werkzeug.WERKZEUG_NAME in nur)
            and bild_werkzeug.WERKZEUG_NAME not in self.abgeschaltet
        ):
            liste.append(bild_werkzeug.werkzeug_beschreibung().als_openai_werkzeug())
        return liste

    def server_von(self, name: str) -> str:
        """Which server offers this tool. Empty if it is unknown.

        The UI picks the tool's mark by this: the server name is fixed in
        mcp_servers.json and cannot be guessed wrong, while a tool name can
        be anything the server feels like.
        """
        if (
            name == shell.WERKZEUG_NAME
            or name == frage_werkzeug.WERKZEUG_NAME
            or name in dateiwerkzeuge.NAMEN
        ):
            return shell.SERVER_NAME if self.shell_an else ""
        if name == memory.WERKZEUG_NAME:
            return memory.SERVER_NAME if self.memory_pfad is not None else ""
        if name in (skill.LADEN, skill.SCHREIBEN):
            return skill.SERVER_NAME if self.skills_orte is not None else ""
        if name == bild_werkzeug.WERKZEUG_NAME:
            return bild_werkzeug.SERVER_NAME if self.bild_zugang is not None else ""
        eintrag = self._werkzeuge.get(name)
        return eintrag[1].server if eintrag else ""

    def bestaetigungsgrund(
        self, name: str, argumente: dict[str, Any] | None = None,
        ordner: list[str] | None = None,
    ) -> tuple[str, str, str] | None:
        """What makes THIS call need a confirmation, as (text key, field, value).

        The sentence belongs to the tool, not to whoever asks. Handing back a
        bare string meant the caller had to pick a sentence for all of them,
        and it picked the shell's: a memory rule was announced as "Reaches
        <the rule> — outside the shared folders".

        Only the shell tool has a dynamic reason: the path a command reaches
        to outside the shared folders. MCP tools are confirmed because the
        configuration says so, which is not something the prompt has to
        explain again.
        """
        if name == shell.WERKZEUG_NAME:
            grund = shell.aussenpfad(argumente or {}, ordner or []) or ""
        elif name in dateiwerkzeuge.NAMEN:
            grund = dateiwerkzeuge.aussenpfad(name, argumente or {}, ordner or []) or ""
        else:
            return None
        return (shell.GRUND_SCHLUESSEL, shell.GRUND_PLATZHALTER, grund) if grund else None

    def braucht_bestaetigung(
        self, name: str, argumente: dict[str, Any] | None = None,
        ordner: list[str] | None = None,
    ) -> bool:
        """Whether this call has to be confirmed by the user.

        For MCP tools the answer stands in the configuration and does not
        depend on the arguments. The shell tool is the exception: there the
        command itself decides — inside the shared folders it runs through,
        beyond them it asks.
        """
        if name == shell.WERKZEUG_NAME:
            return shell.braucht_bestaetigung(argumente or {}, ordner or [])
        if name in dateiwerkzeuge.NAMEN:
            return dateiwerkzeuge.aussenpfad(name, argumente or {}, ordner or []) is not None
        if name == memory.WERKZEUG_NAME:
            return memory.braucht_bestaetigung(argumente or {})
        if name in (skill.LADEN, skill.SCHREIBEN):
            return skill.braucht_bestaetigung(name, argumente or {})
        eintrag = self._werkzeuge.get(name)
        return bool(eintrag and eintrag[2])

    async def ausfuehren(
        self, name: str, argumente: dict[str, Any], bild_senke=None,
        ordner: list[str] | None = None, chat_id: str | None = None,
    ) -> str:
        """Executes a tool — but only if it is approved.

        ``bild_senke`` saves image blocks from the result (see
        ``ergebnis_zu_text``) — the chat run passes it through, jobs leave
        it out and get only the note.

        ``ordner`` are the chat's shared working folders. Only the shell tool
        uses them, and it gets them from here rather than as an argument on
        purpose: anything the model can write, the model can forge.

        ``chat_id`` for the same reason: the remembered folder, the live lines
        and a background run's report all belong to a chat, and none of that
        may come out of the model's arguments.
        """
        # The second lock on the switch. Not offering a tool already keeps an
        # honest model away from it, but a run can be older than the click and
        # carry a call for something that has since been switched off.
        if name in self.abgeschaltet:
            raise WerkzeugVerboten(f"Werkzeug '{name}' ist abgeschaltet.")

        if name == memory.WERKZEUG_NAME:
            if self.memory_pfad is None:
                raise WerkzeugVerboten(f"Werkzeug '{name}' ist nicht freigegeben.")
            try:
                return await memory.ausfuehren(argumente, self.memory_pfad)
            except memory.MemoryVerboten as fehler:
                raise WerkzeugVerboten(str(fehler)) from fehler

        if name in (skill.LADEN, skill.SCHREIBEN):
            if self.skills_orte is None:
                raise WerkzeugVerboten(f"Werkzeug '{name}' ist nicht freigegeben.")
            mitgeliefert, eigen = self.skills_orte
            try:
                if name == skill.LADEN:
                    return await skill.laden(argumente, mitgeliefert, eigen)
                return await skill.schreiben(argumente, eigen)
            except skill.SkillVerboten as fehler:
                raise WerkzeugVerboten(str(fehler)) from fehler

        if name == shell.WERKZEUG_NAME:
            if not self.shell_an:
                raise WerkzeugVerboten(
                    f"Werkzeug '{name}' ist nicht freigegeben."
                )
            try:
                return await shell.ausfuehren(argumente, ordner or [], chat_id)
            except shell.ShellVerboten as fehler:
                raise WerkzeugVerboten(str(fehler)) from fehler

        if name == frage_werkzeug.WERKZEUG_NAME:
            raise WerkzeugVerboten(
                "ask_user is answered by the user, not executed. It only works "
                "in a chat."
            )

        if name == bild_werkzeug.WERKZEUG_NAME:
            if self.bild_zugang is None:
                raise WerkzeugVerboten(f"Werkzeug '{name}' ist nicht freigegeben.")
            basis, bilderordner = self.bild_zugang
            try:
                return await bild_werkzeug.ausfuehren(
                    argumente, basis, bilderordner, bild_senke
                )
            except bild_werkzeug.BildWerkzeugFehler as fehler:
                raise WerkzeugVerboten(str(fehler)) from fehler

        if (datei_modul := dateiwerkzeuge.modul(name)) is not None:
            if not self.shell_an:
                raise WerkzeugVerboten(f"Werkzeug '{name}' ist nicht freigegeben.")
            try:
                return await datei_modul.ausfuehren(argumente, ordner or [])
            except grenzen.GrenzeVerletzt as fehler:
                raise WerkzeugVerboten(str(fehler)) from fehler

        eintrag = self._werkzeuge.get(name)
        if eintrag is None:
            raise WerkzeugVerboten(
                f"Werkzeug '{name}' ist nicht freigegeben. "
                f"Verfügbar: {', '.join(self.namen()) or 'keine'}"
            )
        client, _, _ = eintrag
        return await client.werkzeug_aufrufen(name, argumente, bild_senke)
