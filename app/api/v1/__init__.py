"""Version 1 of the API.

All endpoints live under ``/api/v1/``. If a breaking change comes along later,
``/api/v2/`` is created alongside it — existing clients don't break.
"""

from fastapi import APIRouter

from app.api.v1 import (
    anbieter,
    bilder,
    dateien,
    dateisystem,
    auftraege,
    chats,
    dokumente,
    erzeugnisse,
    einstellungen,
    gedaechtnis,
    generierung,
    health,
    meta,
    modelldateien,
    modelle,
    modellsuche,
    runner,
    skills,
    systemprompt,
    werkzeuge,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(meta.router)
router.include_router(einstellungen.router)
router.include_router(modelle.router)
router.include_router(anbieter.router)
router.include_router(modellsuche.router)
router.include_router(modelldateien.router)
router.include_router(runner.router)
router.include_router(werkzeuge.router)
router.include_router(dateien.router)
router.include_router(dateisystem.router)
router.include_router(systemprompt.router)
router.include_router(gedaechtnis.router)
router.include_router(skills.router)
router.include_router(bilder.router)
router.include_router(dokumente.router)
router.include_router(erzeugnisse.router)
router.include_router(chats.router)
router.include_router(generierung.router)
router.include_router(auftraege.router)

__all__ = ["router"]
