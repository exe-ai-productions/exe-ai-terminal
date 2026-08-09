"""The Hugging Face token, set from the window instead of a text editor.

Optional on purpose: everything public works without one. With one, the
catalogue lifts its rate limits and opens gated models — the very models
somebody signs an agreement for. Same handling as the provider keys: into
``.env`` with tight permissions and into the running environment, handed
back out never — the window only learns whether one is there.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_config
from app.config import Config
from app.env_datei import env_schreiben

router = APIRouter(prefix="/models", tags=["modellsuche"])

NAME = "HF_TOKEN"


class TokenStand(BaseModel):
    gesetzt: bool


class NeuesToken(BaseModel):
    token: str = Field(min_length=8, max_length=400)


def token() -> str | None:
    wert = os.environ.get(NAME, "").strip()
    return wert or None


@router.get("/token", response_model=TokenStand, summary="Ist ein Token da")
def stand() -> TokenStand:
    return TokenStand(gesetzt=token() is not None)


@router.post("/token", response_model=TokenStand, summary="Hugging-Face-Token setzen")
def setzen(daten: NeuesToken, config: Config = Depends(hole_config)) -> TokenStand:
    wert = daten.token.strip()
    env_schreiben(config.pfad("./.env"), NAME, wert)
    os.environ[NAME] = wert
    return TokenStand(gesetzt=True)
