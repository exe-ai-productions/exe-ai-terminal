"""Settings across their scopes.

Every setting is reachable under the scope it belongs to — `global`,
`modell:<endpoint_id>` or `chat:<chat_id>` — and the resolved route gives back
what actually applies, together with where each value comes from.

That last part matters: a cascade without provenance is a black box. You see a
number and cannot tell whether it is yours, the model's, or the default.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_repositories
from app.db import Repositories
from app.db.repositories.einstellungen import GLOBAL
from app.gedaechtnis import SCHLUESSEL as GEDAECHTNIS
from app.gedaechtnis import schalter_pruefen
from app.modellwahl import aus_pruefen, wahl_pruefen
from app.parameter import pruefen
from app.skillwahl import SCHLUESSEL as SKILLS_AUTO
from app.skillwahl import schalter_pruefen as skills_auto_pruefen
from app.werkzeugwahl import SCHLUESSEL as WERKZEUGE_AUS
from app.werkzeugwahl import aus_pruefen as werkzeuge_aus_pruefen

router = APIRouter(prefix="/settings", tags=["settings"])

# Which settings may be written through this route, and how each is checked.
# A setting nobody vouches for does not get in — the JSON column cannot check
# anything by itself.
PRUEFER = {
    "parameter": pruefen,
    "modelle_aus": aus_pruefen,
    "katalog_wahl": wahl_pruefen,
    WERKZEUGE_AUS: werkzeuge_aus_pruefen,
    GEDAECHTNIS: schalter_pruefen,
    SKILLS_AUTO: skills_auto_pruefen,
}


class WertSetzen(BaseModel):
    wert: Any = None


class WertAntwort(BaseModel):
    bereich: str
    schluessel: str
    wert: Any = None


class AufgeloesteAntwort(BaseModel):
    schluessel: str
    # Usually a set of values merged key by key. A setting that cannot be
    # taken apart — a list, say — travels whole from the most specific scope
    # that set it.
    wert: Any = Field(default_factory=dict)
    # Per value: which scope it came from. The UI shows it, so nobody has to
    # guess why a number is what it is.
    herkunft: dict[str, str] = Field(default_factory=dict)


def _bereich_pruefen(bereich: str) -> str:
    if bereich == GLOBAL or bereich.startswith(("modell:", "chat:")):
        return bereich
    raise HTTPException(
        400, "Bereich muss 'global', 'modell:<id>' oder 'chat:<id>' sein"
    )


@router.get(
    "/resolved/{schluessel}",
    response_model=AufgeloesteAntwort,
    summary="Was hier tatsächlich gilt",
)
def aufgeloest(
    schluessel: str,
    modell: str | None = None,
    chat: str | None = None,
    repositories: Repositories = Depends(hole_repositories),
) -> AufgeloesteAntwort:
    return AufgeloesteAntwort(
        schluessel=schluessel,
        wert=repositories.einstellungen.zusammengefuehrt(
            schluessel, modell=modell, chat=chat
        ),
        herkunft=repositories.einstellungen.herkunft(schluessel, modell=modell, chat=chat),
    )


@router.get(
    "/{bereich}/{schluessel}",
    response_model=WertAntwort,
    summary="Was in genau diesem Bereich steht",
)
def holen(
    bereich: str,
    schluessel: str,
    repositories: Repositories = Depends(hole_repositories),
) -> WertAntwort:
    _bereich_pruefen(bereich)
    return WertAntwort(
        bereich=bereich,
        schluessel=schluessel,
        wert=repositories.einstellungen.holen(bereich, schluessel),
    )


@router.put(
    "/{bereich}/{schluessel}",
    response_model=WertAntwort,
    summary="Wert eines Bereichs setzen",
)
def setzen(
    bereich: str,
    schluessel: str,
    daten: WertSetzen,
    repositories: Repositories = Depends(hole_repositories),
) -> WertAntwort:
    """Stores a value. `null` removes it and lets the scope above take over."""
    _bereich_pruefen(bereich)
    if schluessel not in PRUEFER:
        raise HTTPException(400, f"Unbekannte Einstellung '{schluessel}'")

    wert = daten.wert
    if wert is not None:
        wert = PRUEFER[schluessel](wert)
        # Everything discarded by the check means: nothing was set. Storing an
        # empty set would shadow the scope above it with emptiness.
        if not wert:
            wert = None

    repositories.einstellungen.setzen(bereich, schluessel, wert)
    return WertAntwort(
        bereich=bereich,
        schluessel=schluessel,
        wert=repositories.einstellungen.holen(bereich, schluessel),
    )
