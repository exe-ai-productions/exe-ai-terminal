"""Adding a cloud provider from the window instead of from a text editor.

The cloud window used to be a dead end: it said no provider was set up and
offered no way to set one up. The only way in was `.env` and `config.yaml`,
opened by hand — the one thing this program is supposed to spare people.

Two files change when a provider arrives, and both are the user's:

* the key goes into `.env`, where only the service reads it, and it is never
  handed back out — the window only ever learns *whether* one is there;
* the endpoint goes into `config.yaml`, in the same shape somebody would
  have typed by hand.

Three kinds are offered, and the third is the reason this stays small: for
anything OpenAI-compatible only the address differs, so a server in one's own
network costs no extra code.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.config import Config, EndpointConfig
from app.env_datei import env_schreiben
from app.i18n import t

router = APIRouter(prefix="/providers", tags=["anbieter"])

# What a known provider needs. Everything here would otherwise have to be
# typed correctly by hand — the address most of all.
BEKANNT = {
    "anthropic": {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "parameter_dialect": "anthropic",
    },
    "openai": {
        "provider": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "parameter_dialect": "openai",
    },
}

# An id becomes a key name in .env and a section in config.yaml, so it stays
# in the alphabet both of them can carry.
KENNUNG = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")


class NeuerAnbieter(BaseModel):
    art: str = Field(description="anthropic, openai oder eigen")
    schluessel: str = Field(min_length=8, max_length=400)
    # Only for `eigen`: everything else is known.
    kennung: str | None = None
    url: str | None = None


class Angelegt(BaseModel):
    id: str
    api_key_env: str


@router.post("", response_model=Angelegt, summary="Cloud-Anbieter hinzufügen")
async def hinzufuegen(
    daten: NeuerAnbieter,
    request: Request,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> Angelegt:
    if daten.art in BEKANNT:
        kennung = daten.art
        vorlage = dict(BEKANNT[daten.art])
    elif daten.art == "eigen":
        kennung = (daten.kennung or "").strip().lower()
        if not KENNUNG.match(kennung):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, t("fehler.anbieter_kennung", sprache)
            )
        if not (daten.url or "").startswith(("http://", "https://")):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, t("fehler.anbieter_adresse", sprache)
            )
        vorlage = {
            "provider": "openai_compatible",
            "base_url": daten.url.rstrip("/"),
            "api_key_env": f"{kennung.upper().replace('-', '_')}_API_KEY",
            "parameter_dialect": "openai",
        }
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, t("fehler.anbieter_art", sprache))

    konfig_datei = config.pfad("./config.yaml")
    rohdaten = yaml.safe_load(konfig_datei.read_text(encoding="utf-8")) or {}
    endpunkte = rohdaten.setdefault("endpoints", [])

    if any(e.get("id") == kennung for e in endpunkte):
        raise HTTPException(status.HTTP_409_CONFLICT, t("fehler.anbieter_doppelt", sprache))

    endpunkte.append({"id": kennung, "group": "cloud", **vorlage})
    konfig_datei.write_text(
        yaml.safe_dump(rohdaten, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    # The key last: an entry without a key shows a red lamp and can be
    # repaired, a key without an entry belongs to nothing and is only lying
    # around.
    env_schreiben(config.pfad("./.env"), vorlage["api_key_env"], daten.schluessel.strip())

    # The file serves the next start; the running service reads its
    # environment. Without this line the provider stays red until a restart —
    # a working key that looks broken.
    os.environ[vorlage["api_key_env"]] = daten.schluessel.strip()

    # And the provider joins the model list right away, same route as the
    # model server: the window that just added it is looking at that list.
    endpunkt = EndpointConfig(id=kennung, group="cloud", **vorlage)
    config.endpoints.append(endpunkt)
    await request.app.state.discovery.anmelden(endpunkt)

    return Angelegt(id=kennung, api_key_env=vorlage["api_key_env"])
