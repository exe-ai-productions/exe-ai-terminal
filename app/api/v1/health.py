"""Health check of the service.

Two paths, deliberately:
  * ``/health``        — unversioned, for Uptime Kuma and systemd. This
                         address must never change.
  * ``/api/v1/health`` — the same information within the versioned API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import __version__
from app.api.abhaengigkeiten import hole_config, hole_repositories
from app.config import Config
from app.db import Repositories

router = APIRouter(tags=["health"])


class DatenbankStatus(BaseModel):
    erreichbar: bool
    schema_version: int | None = None
    fehler: str | None = None


class HealthAntwort(BaseModel):
    status: str
    version: str
    datenbank: DatenbankStatus


def _health_ermitteln(config: Config, repositories: Repositories) -> HealthAntwort:
    try:
        version = repositories.db.schema_version()
        datenbank = DatenbankStatus(erreichbar=True, schema_version=version)
    except Exception as fehler:  # noqa: BLE001 - health must never crash itself
        datenbank = DatenbankStatus(erreichbar=False, fehler=str(fehler))

    return HealthAntwort(
        status="ok" if datenbank.erreichbar else "degraded",
        version=__version__,
        datenbank=datenbank,
    )


@router.get("/health", response_model=HealthAntwort, summary="Zustand des Dienstes")
def health(
    config: Config = Depends(hole_config),
    repositories: Repositories = Depends(hole_repositories),
) -> HealthAntwort:
    return _health_ermitteln(config, repositories)
