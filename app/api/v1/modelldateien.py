"""Which GGUF files a found repository actually offers.

The search answers "which repository" — this answers "which file", and only
with files the one-button download can finish alone:

* **Only ``.gguf``**, because that is what the runner starts.
* **No shards.** A model split into ``-00001-of-00003`` parts needs all of
  them; fetching one produces a file that looks like a model and is not.
* **``mmproj`` companions ride along separately.** A vision projector
  cannot start on its own, so it is never offered as a model — but the
  answer says whether the repository has one, and the download fetches it
  next to the model so its eyes arrive with it.

Smallest first, because that is the order in which the question "which one
fits my machine" gets answered.

The list is fetched on the server, same reason as the search itself: the
page would otherwise hand every user's address to a foreign host.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.abhaengigkeiten import hole_sprache
from app.i18n import t

router = APIRouter(prefix="/models", tags=["modellsuche"])

HF_BASIS = "https://huggingface.co/api/models"

# A repository is owner/name — anything else does not go into an address.
REPO = re.compile(r"^[A-Za-z0-9][\w.-]{0,95}/[\w.-]{1,96}$")

ENDUNG = ".gguf"
SHARD = re.compile(r"-\d{5}-of-\d{5}\.gguf$", re.IGNORECASE)


class Datei(BaseModel):
    datei: str
    groesse_gb: float


class Dateiliste(BaseModel):
    dateien: list[Datei]
    # The repository's vision projector, if it has one — the smallest,
    # because they only differ in precision and the small one sees the same.
    mmproj: Datei | None = None


def _brauchbar(pfad: str) -> bool:
    name = pfad.lower()
    if not name.endswith(ENDUNG):
        return False
    if SHARD.search(name):
        return False
    if "mmproj" in name:
        return False
    return True


def _ist_mmproj(pfad: str) -> bool:
    name = pfad.lower()
    return name.endswith(ENDUNG) and "mmproj" in name and not SHARD.search(name)


def _dateien_bauen(eintraege: list[Any]) -> Dateiliste:
    gueltig = [
        e for e in eintraege
        if isinstance(e, dict) and isinstance(e.get("path"), str)
    ]
    dateien = sorted(
        (
            Datei(datei=e["path"], groesse_gb=round(int(e.get("size") or 0) / 1e9, 1))
            for e in gueltig
            if _brauchbar(e["path"])
        ),
        key=lambda d: d.groesse_gb,
    )
    projektoren = sorted(
        (
            Datei(datei=e["path"], groesse_gb=round(int(e.get("size") or 0) / 1e9, 1))
            for e in gueltig
            if _ist_mmproj(e["path"])
        ),
        key=lambda d: d.groesse_gb,
    )
    return Dateiliste(dateien=dateien, mmproj=projektoren[0] if projektoren else None)


@router.get("/files", response_model=Dateiliste, summary="Dateien eines Repositories")
async def dateien(
    repo: str = Query(min_length=3, max_length=200),
    sprache: str = Depends(hole_sprache),
) -> Dateiliste:
    if not REPO.match(repo):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, t("fehler.dateiliste_repo", sprache)
        )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            antwort = await client.get(f"{HF_BASIS}/{repo}/tree/main")
            antwort.raise_for_status()
            daten = antwort.json()
    except httpx.HTTPError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, t("fehler.dateiliste_fern", sprache)
        ) from None

    if not isinstance(daten, list):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, t("fehler.dateiliste_fern", sprache)
        )

    return _dateien_bauen(daten)
