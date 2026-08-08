"""Shared dependencies for the API routes.

FastAPI passes these functions into the routes via ``Depends``. That way no
route hangs directly off a global object, and tests can replace each
dependency individually.
"""

from __future__ import annotations

from fastapi import Header, Request

from app.config import Config
from app.db import Repositories
from app.i18n import STANDARDSPRACHE, verfuegbare_sprachen

# As long as there is no login, everything belongs to this user. The user_id
# column exists from day one so that adding login later is an upgrade.
STANDARD_BENUTZER = "standard"


def hole_config(request: Request) -> Config:
    return request.app.state.config


def hole_repositories(request: Request) -> Repositories:
    return request.app.state.repositories


def hole_benutzer_id(request: Request) -> str:
    return getattr(request.app.state, "standard_benutzer", STANDARD_BENUTZER)


def hole_sprache(
    request: Request,
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
) -> str:
    """Language from the request header, otherwise the one from the config."""
    bekannt = verfuegbare_sprachen()
    if accept_language:
        for eintrag in accept_language.split(","):
            kennung = eintrag.split(";")[0].strip().lower()[:2]
            if kennung in bekannt:
                return kennung
    konfiguriert = request.app.state.config.app.language
    return konfiguriert if konfiguriert in bekannt else STANDARDSPRACHE
