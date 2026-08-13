"""Information about the running service for the frontend.

The frontend asks here which features are switched on and which languages
exist — instead of hard-coding such things. Secrets and internal addresses
are deliberately not shipped along.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import __version__
from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.config import Config
from app.i18n import STANDARDSPRACHE, verfuegbare_sprachen

router = APIRouter(tags=["meta"])


class MetaAntwort(BaseModel):
    name: str
    version: str
    sprache: str
    standardsprache: str
    verfuegbare_sprachen: list[str]
    features: dict[str, bool]
    # The first name the operating system knows — the address suggestion
    # for the first start. Empty when the system offers none.
    system_name: str = ""


def _systemname() -> str:
    """The user's first name as the system knows it, or an empty string."""
    import os

    voll = ""
    try:
        import pwd

        voll = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].strip()
    except Exception:
        voll = ""
    kurz = voll.split()[0] if voll else ""
    return kurz or os.environ.get("USER") or os.environ.get("USERNAME") or ""


@router.get("/meta", response_model=MetaAntwort, summary="Funktionen und Sprachen")
def meta(
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> MetaAntwort:
    return MetaAntwort(
        system_name=_systemname(),
        name="Exe AI Terminal",
        version=__version__,
        sprache=sprache,
        standardsprache=STANDARDSPRACHE,
        verfuegbare_sprachen=verfuegbare_sprachen(),
        features=config.features.model_dump(),
    )


@router.get("/translations/{sprache}", summary="Übersetzungskatalog")
def uebersetzungen(sprache: str) -> dict:
    """Delivers the complete catalog of a language to the frontend."""
    from app.i18n import _katalog  # deliberately local: internal access, not part of the API

    katalog = _katalog(sprache)
    if not katalog:
        katalog = _katalog(STANDARDSPRACHE)
        sprache = STANDARDSPRACHE
    return {"sprache": sprache, "texte": katalog}
