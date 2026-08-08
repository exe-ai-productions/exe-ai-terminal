"""Browser sign-in for hosted MCP servers (OAuth 2.1 with PKCE).

The flow as the user experiences it: click "connect", sign in with the
provider in the browser, done. Behind it are four steps:

    1. Find metadata        where do you sign in, where do you exchange
                            codes? (RFC 9728 protected resource, RFC 8414
                            provider metadata — with fallback paths for
                            older servers)
    2. Register             the program registers itself as an application
                            and gets a client id (RFC 7591). If the
                            provider can't do that (Google!), the flow
                            takes a manually entered client id.
    3. Into the browser     sign-in address with PKCE challenge and a
                            one-time state; the provider redirects back
                            to http://127.0.0.1:8090/…/oauth/callback
                            (loopback, RFC 8252 — local ONLY).
    4. Exchange & remember  exchange the code for access, stored in
                            data/mcp_auth.json (0600, git-ignored).

Renewal: silent. At startup the registry fetches a fresh access token via
``gueltiges_token`` (renewed if it would expire in under a minute); if the
access dies mid-run, ``token_erneuern`` renews once and the call is
retried. If both fail, the server loads without tools — the model is not
offered anything that is sure to fail.

Why a plain file instead of a keychain or encryption: one folder over sits
the .env with the API keys in plain text. ONE protection level for all
credentials.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

log = logging.getLogger(__name__)

CLIENT_NAME = "Exe AI Terminal"

# Whoever dawdles in the browser for more than ten minutes starts over — a
# state that is valid forever would be a standing attack path on the
# redirect.
STATE_FRIST_S = 600

# An access token counts as "about to expire" when less than a minute is
# left — better one renewal too many than a 401 in the middle of a tool call.
ABLAUF_PUFFER_S = 60


class MCPAnmeldeFehler(Exception):
    """The sign-in with the provider failed — with a reason."""


def _pkce_paar() -> tuple[str, str]:
    """Verifier and challenge (S256) for PKCE."""
    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge


class AuthSpeicher:
    """``data/mcp_auth.json`` — the rotating credentials, permissions 0600.

    Only this file knows the values. Via the status path, the UI gets to
    see nothing but connected/not connected.
    """

    def __init__(self, pfad: Path) -> None:
        self.pfad = Path(pfad)

    def _lesen(self) -> dict[str, dict[str, Any]]:
        if not self.pfad.exists():
            return {}
        try:
            return json.loads(self.pfad.read_text(encoding="utf-8"))
        except json.JSONDecodeError as fehler:
            # Don't discard silently and overwrite on the next write:
            # better to be loud, the credentials are tedious to regain.
            log.error("mcp_auth.json ist kein gültiges JSON: %s", fehler)
            return {}

    def _schreiben(self, daten: dict[str, dict[str, Any]]) -> None:
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.pfad.write_text(
            json.dumps(daten, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.chmod(self.pfad, 0o600)

    def eintrag(self, server: str) -> dict[str, Any] | None:
        return self._lesen().get(server)

    def setzen(self, server: str, **felder: Any) -> None:
        daten = self._lesen()
        daten.setdefault(server, {}).update(felder)
        self._schreiben(daten)

    def vergessen(self, server: str) -> None:
        daten = self._lesen()
        if daten.pop(server, None) is not None:
            self._schreiben(daten)

    def alle(self) -> dict[str, dict[str, Any]]:
        return self._lesen()


class OAuthVermittler:
    """Performs the sign-in dance and keeps the credentials fresh."""

    def __init__(
        self,
        speicher: AuthSpeicher,
        rueckleitung: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.speicher = speicher
        self.rueckleitung = rueckleitung
        # For tests only: an ASGITransport onto a provider in the test process.
        self._transport = transport
        # state -> ongoing flow. Lives only in memory: a restart aborts
        # open sign-ins, which is fine.
        self._laufend: dict[str, dict[str, Any]] = {}
        # Never renew twice — two simultaneous tool calls would otherwise
        # both exchange and invalidate each other's refresh token
        # (providers rotate it).
        self._sperre = asyncio.Lock()

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=20.0, transport=self._transport)

    # --- Steps 1 and 2: metadata and client id ----------------------------

    async def _metadaten(self, http: httpx.AsyncClient, mcp_url: str) -> dict[str, Any]:
        teile = urlsplit(mcp_url)
        origin = f"{teile.scheme}://{teile.netloc}"
        pfad = teile.path.rstrip("/")

        # Where does the authorization server live? First you ask the
        # resource itself (RFC 9728, with and without the path suffix) …
        anmelde_server: str | None = None
        scopes: list[str] | None = None
        for url in (
            f"{origin}/.well-known/oauth-protected-resource{pfad}",
            f"{origin}/.well-known/oauth-protected-resource",
        ):
            daten = await self._json_oder_none(http, url)
            if daten:
                server_liste = daten.get("authorization_servers") or []
                anmelde_server = server_liste[0] if server_liste else None
                scopes = daten.get("scopes_supported")
                break

        # … then ask the authorization server for its endpoints (RFC 8414;
        # OIDC as the second notation; older MCP servers carry the metadata
        # directly at their own origin).
        kandidaten: list[str] = []
        if anmelde_server:
            a = urlsplit(anmelde_server)
            a_origin = f"{a.scheme}://{a.netloc}"
            a_pfad = a.path.rstrip("/")
            kandidaten += [
                f"{a_origin}/.well-known/oauth-authorization-server{a_pfad}",
                f"{a_origin}/.well-known/openid-configuration{a_pfad}",
                f"{a_origin}{a_pfad}/.well-known/openid-configuration",
            ]
        kandidaten.append(f"{origin}/.well-known/oauth-authorization-server")

        for url in kandidaten:
            daten = await self._json_oder_none(http, url)
            if daten and daten.get("authorization_endpoint") and daten.get("token_endpoint"):
                return {
                    "authorization_endpoint": daten["authorization_endpoint"],
                    "token_endpoint": daten["token_endpoint"],
                    "registration_endpoint": daten.get("registration_endpoint"),
                    "scopes": scopes,
                    "resource": mcp_url,
                }
        raise MCPAnmeldeFehler(
            "Der Anbieter nennt keine Anmelde-Wege (keine OAuth-Metadaten gefunden)"
        )

    @staticmethod
    async def _json_oder_none(http: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
        try:
            antwort = await http.get(url)
        except httpx.HTTPError:
            return None
        if antwort.status_code != 200:
            return None
        try:
            daten = antwort.json()
        except json.JSONDecodeError:
            return None
        return daten if isinstance(daten, dict) else None

    async def _registrieren(
        self, http: httpx.AsyncClient, meta: dict[str, Any]
    ) -> tuple[str, str | None]:
        """Dynamic registration (RFC 7591) — the reason a single click is
        enough in other programs."""
        if not meta.get("registration_endpoint"):
            raise MCPAnmeldeFehler(
                "Der Anbieter kann keine automatische Registrierung — "
                "Kennung (client_id) von Hand eintragen"
            )
        antwort = await http.post(
            meta["registration_endpoint"],
            json={
                "client_name": CLIENT_NAME,
                "redirect_uris": [self.rueckleitung],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )
        if antwort.status_code >= 400:
            raise MCPAnmeldeFehler(
                f"Registrierung abgelehnt (HTTP {antwort.status_code}): "
                f"{antwort.text[:200]}"
            )
        daten = antwort.json()
        if not daten.get("client_id"):
            raise MCPAnmeldeFehler("Registrierung ohne client_id beantwortet")
        return daten["client_id"], daten.get("client_secret")

    # --- Step 3: the sign-in address --------------------------------------

    async def anmelde_url(
        self,
        server: str,
        mcp_url: str,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> str:
        """Prepares the flow and returns the address for the browser."""
        async with self._http() as http:
            meta = await self._metadaten(http, mcp_url)
            gemerkt = self.speicher.eintrag(server) or {}
            if client_id:
                # Entered by hand (the Google route) — beats everything.
                kennung, geheimnis = client_id, client_secret
            elif gemerkt.get("client_id"):
                # Already registered once: reuse the same client id.
                kennung, geheimnis = gemerkt["client_id"], gemerkt.get("client_secret")
            else:
                kennung, geheimnis = await self._registrieren(http, meta)

        verifier, challenge = _pkce_paar()
        state = secrets.token_urlsafe(32)
        self._laufend[state] = {
            "server": server,
            "mcp_url": mcp_url,
            "verifier": verifier,
            "client_id": kennung,
            "client_secret": geheimnis,
            "token_endpoint": meta["token_endpoint"],
            "resource": meta["resource"],
            "erstellt": time.monotonic(),
        }

        anfrage = {
            "response_type": "code",
            "client_id": kennung,
            "redirect_uri": self.rueckleitung,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            # RFC 8707: what the access is meant to be valid for —
            # mandatory since MCP 2025-06-18, otherwise an access token
            # might be valid for more than this one server.
            "resource": meta["resource"],
        }
        if meta.get("scopes"):
            anfrage["scope"] = " ".join(meta["scopes"])
        return f"{meta['authorization_endpoint']}?{urlencode(anfrage)}"

    # --- Step 4: callback and exchange ------------------------------------

    async def rueckruf(self, state: str, code: str) -> str:
        """The browser comes back: exchange the code for access.

        The state is one-time and time-limited — a second call with the
        same value goes nowhere. That is the entire protection of the GET
        path, and it suffices: without a valid state nothing is exchanged.
        """
        vorgang = self._laufend.pop(state, None)
        if vorgang is None or time.monotonic() - vorgang["erstellt"] > STATE_FRIST_S:
            raise MCPAnmeldeFehler(
                "Der Anmeldevorgang ist unbekannt oder abgelaufen — bitte neu beginnen"
            )

        daten = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.rueckleitung,
            "client_id": vorgang["client_id"],
            "code_verifier": vorgang["verifier"],
            "resource": vorgang["resource"],
        }
        if vorgang.get("client_secret"):
            daten["client_secret"] = vorgang["client_secret"]

        async with self._http() as http:
            antwort = await http.post(vorgang["token_endpoint"], data=daten)
        if antwort.status_code >= 400:
            raise MCPAnmeldeFehler(
                f"Der Anbieter hat den Tausch abgelehnt (HTTP {antwort.status_code}): "
                f"{antwort.text[:200]}"
            )
        zugang = antwort.json()
        if not zugang.get("access_token"):
            raise MCPAnmeldeFehler("Der Anbieter hat keinen Zugang ausgestellt")

        self.speicher.setzen(
            vorgang["server"],
            client_id=vorgang["client_id"],
            client_secret=vorgang["client_secret"],
            token_endpoint=vorgang["token_endpoint"],
            resource=vorgang["resource"],
            mcp_url=vorgang["mcp_url"],
            access_token=zugang["access_token"],
            refresh_token=zugang.get("refresh_token"),
            expires_at=time.time() + int(zugang.get("expires_in") or 3600),
            scope=zugang.get("scope"),
        )
        return vorgang["server"]

    # --- Renewal -----------------------------------------------------------

    async def gueltiges_token(self, server: str) -> str | None:
        """An access token that holds right now — renewed silently if needed."""
        async with self._sperre:
            eintrag = self.speicher.eintrag(server)
            if not eintrag or not eintrag.get("access_token"):
                return None
            if time.time() < float(eintrag.get("expires_at") or 0) - ABLAUF_PUFFER_S:
                return eintrag["access_token"]
            return await self._erneuern(server, eintrag)

    async def token_erneuern(self, server: str) -> str | None:
        """Forced renewal — for the 401 in the middle of a run."""
        async with self._sperre:
            eintrag = self.speicher.eintrag(server)
            if not eintrag:
                return None
            return await self._erneuern(server, eintrag)

    async def _erneuern(self, server: str, eintrag: dict[str, Any]) -> str | None:
        if not eintrag.get("refresh_token") or not eintrag.get("token_endpoint"):
            log.info("MCP '%s': kein Erneuerungs-Merkmal — neu anmelden nötig", server)
            return None
        daten = {
            "grant_type": "refresh_token",
            "refresh_token": eintrag["refresh_token"],
            "client_id": eintrag.get("client_id", ""),
            "resource": eintrag.get("resource", ""),
        }
        if eintrag.get("client_secret"):
            daten["client_secret"] = eintrag["client_secret"]
        try:
            async with self._http() as http:
                antwort = await http.post(eintrag["token_endpoint"], data=daten)
        except httpx.HTTPError as fehler:
            log.warning("MCP '%s': Erneuerung nicht erreichbar: %s", server, fehler)
            return None
        if antwort.status_code >= 400:
            log.info(
                "MCP '%s': Erneuerung abgelehnt (HTTP %d) — neu anmelden nötig",
                server,
                antwort.status_code,
            )
            return None
        zugang = antwort.json()
        if not zugang.get("access_token"):
            return None
        self.speicher.setzen(
            server,
            access_token=zugang["access_token"],
            # Providers may rotate the refresh token — then only the new
            # one is valid. If none comes, the old one stays valid.
            refresh_token=zugang.get("refresh_token") or eintrag["refresh_token"],
            expires_at=time.time() + int(zugang.get("expires_in") or 3600),
        )
        return zugang["access_token"]

    # --- Administration ----------------------------------------------------

    def vergessen(self, server: str) -> None:
        """"Disconnect and forget access" — the credentials are gone afterwards."""
        self.speicher.vergessen(server)

    def status(self) -> dict[str, dict[str, Any]]:
        """Connected or not — never the values themselves."""
        return {
            server: {
                "verbunden": bool(eintrag.get("access_token")),
                "laeuft_ab": eintrag.get("expires_at"),
            }
            for server, eintrag in self.speicher.alle().items()
        }
