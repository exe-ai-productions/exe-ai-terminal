"""Browser sign-in for hosted MCP servers (OAuth 2.1 with PKCE).

The proof runs against a real, tiny provider inside the test process
(ASGITransport): metadata, registration, code exchange with PKCE
verification, refresh. Only the browser step itself is shortcut — the test
plays the provider that issues the code after sign-in.
"""

from __future__ import annotations

import base64
import hashlib
import json
import stat
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from app.tools.mcp_auth import (
    AuthSpeicher,
    MCPAnmeldeFehler,
    OAuthVermittler,
    _pkce_paar,
)

RUECKLEITUNG = "http://127.0.0.1:8090/api/v1/tools/oauth/callback"


class Anbieter:
    """A provider with metadata, registration and token issuance.

    It actually verifies the PKCE checksum — an exchange with the wrong
    verifier is caught, just like with a real provider.
    """

    def __init__(self, mit_registrierung: bool = True) -> None:
        self.mit_registrierung = mit_registrierung
        self.registrierungen = 0
        self.ausgestellter_code: str | None = None
        self.erwartete_challenge: str | None = None
        self.erneuerungen = 0

    def app(self) -> Starlette:
        routen = [
            Route("/.well-known/oauth-protected-resource/mcp", self.ressource),
            Route("/.well-known/oauth-authorization-server", self.metadaten),
            Route("/token", self.token, methods=["POST"]),
        ]
        if self.mit_registrierung:
            routen.append(Route("/register", self.registrieren, methods=["POST"]))
        return Starlette(routes=routen)

    async def ressource(self, request: Request) -> Response:
        return JSONResponse(
            {
                "resource": "http://testserver/mcp",
                "authorization_servers": ["http://testserver"],
                "scopes_supported": ["lesen", "schreiben"],
            }
        )

    async def metadaten(self, request: Request) -> Response:
        daten = {
            "issuer": "http://testserver",
            "authorization_endpoint": "http://testserver/authorize",
            "token_endpoint": "http://testserver/token",
        }
        if self.mit_registrierung:
            daten["registration_endpoint"] = "http://testserver/register"
        return JSONResponse(daten)

    async def registrieren(self, request: Request) -> Response:
        self.registrierungen += 1
        anfrage = json.loads(await request.body())
        assert RUECKLEITUNG in anfrage["redirect_uris"]
        return JSONResponse({"client_id": "dyn-123"}, status_code=201)

    def code_ausstellen(self, anmelde_url: str) -> tuple[str, str]:
        """The shortcut browser step: reads the authorization URL and
        issues a code, bound to the PKCE checksum."""
        anfrage = parse_qs(urlsplit(anmelde_url).query)
        assert anfrage["response_type"] == ["code"]
        assert anfrage["code_challenge_method"] == ["S256"]
        assert anfrage["redirect_uri"] == [RUECKLEITUNG]
        assert anfrage["resource"] == ["http://testserver/mcp"]
        self.erwartete_challenge = anfrage["code_challenge"][0]
        self.ausgestellter_code = "code-abc"
        return anfrage["state"][0], self.ausgestellter_code

    async def token(self, request: Request) -> Response:
        felder = parse_qs((await request.body()).decode("utf-8"))
        art = felder["grant_type"][0]
        if art == "authorization_code":
            if felder["code"][0] != self.ausgestellter_code:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            pruefsumme = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(felder["code_verifier"][0].encode()).digest()
                )
                .rstrip(b"=")
                .decode()
            )
            if pruefsumme != self.erwartete_challenge:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            return JSONResponse(
                {
                    "access_token": "zugang-1",
                    "refresh_token": "erneuer-1",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                }
            )
        if art == "refresh_token":
            if felder["refresh_token"][0] != "erneuer-1":
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            self.erneuerungen += 1
            return JSONResponse(
                {
                    "access_token": f"zugang-{1 + self.erneuerungen}",
                    "refresh_token": "erneuer-1",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                }
            )
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


def vermittler(anbieter: Anbieter, tmp_path) -> OAuthVermittler:
    return OAuthVermittler(
        AuthSpeicher(tmp_path / "mcp_auth.json"),
        rueckleitung=RUECKLEITUNG,
        transport=httpx.ASGITransport(app=anbieter.app()),
    )


# --- PKCE ------------------------------------------------------------------


def test_pkce_pruefsumme_ist_s256():
    verifier, challenge = _pkce_paar()
    assert 43 <= len(verifier) <= 128
    erwartet = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == erwartet


# --- The dance -------------------------------------------------------------


async def test_anmelde_url_registriert_und_traegt_alles(tmp_path):
    anbieter = Anbieter()
    v = vermittler(anbieter, tmp_path)
    url = await v.anmelde_url("recraft", "http://testserver/mcp")

    assert anbieter.registrierungen == 1
    anfrage = parse_qs(urlsplit(url).query)
    assert anfrage["client_id"] == ["dyn-123"]
    assert anfrage["scope"] == ["lesen schreiben"]
    assert url.startswith("http://testserver/authorize?")


async def test_rueckruf_tauscht_speichert_und_schuetzt(tmp_path):
    anbieter = Anbieter()
    v = vermittler(anbieter, tmp_path)
    url = await v.anmelde_url("recraft", "http://testserver/mcp")
    state, code = anbieter.code_ausstellen(url)

    server = await v.rueckruf(state, code)
    assert server == "recraft"

    eintrag = v.speicher.eintrag("recraft")
    assert eintrag["access_token"] == "zugang-1"
    assert eintrag["refresh_token"] == "erneuer-1"
    assert eintrag["client_id"] == "dyn-123"
    assert eintrag["expires_at"] > time.time()

    # Permissions 0600 — the file belongs to the user account alone.
    rechte = stat.S_IMODE((tmp_path / "mcp_auth.json").stat().st_mode)
    assert rechte == 0o600

    # The state is single-use: the same callback goes nowhere.
    with pytest.raises(MCPAnmeldeFehler, match="unbekannt oder abgelaufen"):
        await v.rueckruf(state, code)


async def test_falscher_state_tauscht_nichts(tmp_path):
    v = vermittler(Anbieter(), tmp_path)
    with pytest.raises(MCPAnmeldeFehler, match="unbekannt oder abgelaufen"):
        await v.rueckruf("erfunden", "code-abc")
    assert v.speicher.alle() == {}


async def test_handkennung_ueberspringt_registrierung(tmp_path):
    anbieter = Anbieter(mit_registrierung=False)
    v = vermittler(anbieter, tmp_path)
    url = await v.anmelde_url(
        "gmail", "http://testserver/mcp", client_id="meine-kennung"
    )
    assert anbieter.registrierungen == 0
    assert parse_qs(urlsplit(url).query)["client_id"] == ["meine-kennung"]


async def test_ohne_registrierung_und_ohne_kennung_klare_meldung(tmp_path):
    v = vermittler(Anbieter(mit_registrierung=False), tmp_path)
    with pytest.raises(MCPAnmeldeFehler, match="Kennung"):
        await v.anmelde_url("gmail", "http://testserver/mcp")


# --- Refresh ---------------------------------------------------------------


async def test_abgelaufener_zugang_wird_still_erneuert(tmp_path):
    anbieter = Anbieter()
    v = vermittler(anbieter, tmp_path)
    v.speicher.setzen(
        "recraft",
        access_token="zugang-1",
        refresh_token="erneuer-1",
        token_endpoint="http://testserver/token",
        client_id="dyn-123",
        resource="http://testserver/mcp",
        expires_at=time.time() - 10,
    )
    zugang = await v.gueltiges_token("recraft")
    assert zugang == "zugang-2"
    assert anbieter.erneuerungen == 1
    assert v.speicher.eintrag("recraft")["access_token"] == "zugang-2"


async def test_frischer_zugang_wird_nicht_angefasst(tmp_path):
    anbieter = Anbieter()
    v = vermittler(anbieter, tmp_path)
    v.speicher.setzen(
        "recraft",
        access_token="zugang-1",
        refresh_token="erneuer-1",
        token_endpoint="http://testserver/token",
        expires_at=time.time() + 3600,
    )
    assert await v.gueltiges_token("recraft") == "zugang-1"
    assert anbieter.erneuerungen == 0


async def test_ohne_erneuerungs_merkmal_kommt_none(tmp_path):
    v = vermittler(Anbieter(), tmp_path)
    v.speicher.setzen(
        "recraft", access_token="zugang-1", expires_at=time.time() - 10
    )
    assert await v.gueltiges_token("recraft") is None


async def test_unbekannter_server_kommt_none(tmp_path):
    v = vermittler(Anbieter(), tmp_path)
    assert await v.gueltiges_token("nie-gesehen") is None


async def test_vergessen_wirft_die_merkmale_weg(tmp_path):
    v = vermittler(Anbieter(), tmp_path)
    v.speicher.setzen("recraft", access_token="zugang-1")
    v.vergessen("recraft")
    assert v.speicher.eintrag("recraft") is None
    assert v.status() == {}


# --- Via the API -----------------------------------------------------------


@pytest.fixture
def http_serverdatei(config, tmp_path):
    """A registered http server without a fixed key — the OAuth case."""
    pfad = tmp_path / "mcp_servers.json"
    pfad.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "recraft": {
                        "type": "http",
                        "url": "http://testserver/mcp",
                        "enabled": True,
                    },
                    "github": {
                        "type": "http",
                        "url": "http://testserver/mcp",
                        "api_key_env": "GITHUB_TOKEN",
                        "enabled": True,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    config.mcp.servers_file = str(pfad)
    return pfad


async def test_api_voller_tanz(client, http_serverdatei, tmp_path):
    anbieter = Anbieter()
    client.app.state.mcp_oauth = vermittler(anbieter, tmp_path)

    antwort = client.post("/api/v1/tools/oauth/start", json={"server": "recraft"})
    assert antwort.status_code == 200
    url = antwort.json()["url"]

    state, code = anbieter.code_ausstellen(url)
    rueckruf = client.get(
        "/api/v1/tools/oauth/callback", params={"state": state, "code": code}
    )
    assert rueckruf.status_code == 200
    assert "Verbunden" in rueckruf.text and "recraft" in rueckruf.text

    status = client.get("/api/v1/tools/oauth/status").json()
    assert status == [
        {
            "server": "recraft",
            "verbunden": True,
            "laeuft_ab": pytest.approx(time.time() + 3600, abs=30),
        }
    ]


async def test_api_unbekannter_server_ist_404(client, http_serverdatei, tmp_path):
    client.app.state.mcp_oauth = vermittler(Anbieter(), tmp_path)
    antwort = client.post("/api/v1/tools/oauth/start", json={"server": "erfunden"})
    assert antwort.status_code == 404


async def test_api_fester_schluessel_hat_nichts_zu_verbinden(
    client, http_serverdatei, tmp_path
):
    client.app.state.mcp_oauth = vermittler(Anbieter(), tmp_path)
    antwort = client.post("/api/v1/tools/oauth/start", json={"server": "github"})
    assert antwort.status_code == 400
    assert "GITHUB_TOKEN" in antwort.json()["detail"]


async def test_api_kaputter_rueckruf_zeigt_fehlerseite(client, tmp_path):
    client.app.state.mcp_oauth = vermittler(Anbieter(), tmp_path)
    antwort = client.get(
        "/api/v1/tools/oauth/callback", params={"state": "erfunden", "code": "x"}
    )
    assert antwort.status_code == 400
    assert "Nicht verbunden" in antwort.text


async def test_api_anbieter_lehnt_ab_zeigt_fehlerseite(client, tmp_path):
    client.app.state.mcp_oauth = vermittler(Anbieter(), tmp_path)
    antwort = client.get(
        "/api/v1/tools/oauth/callback", params={"error": "access_denied"}
    )
    assert antwort.status_code == 400
    assert "access_denied" in antwort.text


async def test_api_vergessen(client, http_serverdatei, tmp_path):
    v = vermittler(Anbieter(), tmp_path)
    v.speicher.setzen("recraft", access_token="zugang-1")
    client.app.state.mcp_oauth = v
    antwort = client.delete("/api/v1/tools/oauth/recraft")
    assert antwort.status_code == 204
    assert v.speicher.eintrag("recraft") is None
