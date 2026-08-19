"""Version 1 of the API.

All endpoints live under ``/api/v1/``. If a breaking change comes along later,
``/api/v2/`` is created alongside it — existing clients don't break.
"""

from fastapi import APIRouter

from app.api.v1 import (
    anbieter,
    arbeitsordner,
    befehle,
    bild,
    bilder,
    bildprompt,
    dateien,
    dateisystem,
    auftraege,
    chats,
    dokumente,
    erzeugnisse,
    eewserver,
    einbettungsserver,
    einstellungen,
    gedaechtnis,
    generierung,
    health,
    hf_token,
    meta,
    modelldateien,
    modelle,
    modellsuche,
    notizen,
    runner,
    skills,
    speicherorte,
    systemprompt,
    waechter,
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
router.include_router(hf_token.router)
router.include_router(runner.router)
router.include_router(einbettungsserver.router)
router.include_router(eewserver.router)
router.include_router(werkzeuge.router)
router.include_router(dateien.router)
router.include_router(dateisystem.router)
router.include_router(speicherorte.router)
router.include_router(systemprompt.router)
router.include_router(gedaechtnis.router)
router.include_router(skills.router)
router.include_router(bilder.router)
router.include_router(bild.router)
router.include_router(bildprompt.router)
router.include_router(dokumente.router)
router.include_router(erzeugnisse.router)
router.include_router(chats.router)
router.include_router(generierung.router)
router.include_router(befehle.router)
router.include_router(arbeitsordner.router)
router.include_router(notizen.router)
router.include_router(auftraege.router)
router.include_router(waechter.router)

__all__ = ["router"]
