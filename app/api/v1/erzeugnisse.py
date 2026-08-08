"""Saving what the assistant produced into a working folder.

A file in the chat is at first only text inside an answer. This is the one
place that turns it into a real file — and being the only one, the rule for
where it may land is written down exactly once.

That rule is the shell's rule: inside the folders this chat has released,
nowhere else. And a name stays a name, never a path. Whoever may choose the
folder must not be able to walk out of it in the same breath.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.abhaengigkeiten import hole_benutzer_id, hole_repositories, hole_sprache
from app.db import Repositories
from app.i18n import t
from app.tools.shell import liegt_innerhalb

router = APIRouter(prefix="/outputs", tags=["erzeugnisse"])

# Only what the program offers to produce, and only text. Extensions the
# system runs on a double click are missing on purpose: a saved file is
# meant to be looked at, not started. Nothing here is ever made executable.
ERLAUBTE_ENDUNGEN = {
    ".txt", ".md", ".markdown", ".html", ".htm", ".css", ".js",
    ".json", ".yaml", ".yml", ".csv", ".tsv", ".svg", ".xml",
    ".py", ".sh", ".sql", ".toml", ".ini", ".log",
}

MAX_ZEICHEN = 5_000_000


class Erzeugnis(BaseModel):
    chat_id: str
    name: str = Field(min_length=1, max_length=200)
    inhalt: str
    ordner: str | None = None


class Abgelegt(BaseModel):
    pfad: str


def _name_pruefen(name: str, sprache: str) -> str:
    """A file name, and nothing that could be read as a path."""
    if "/" in name or "\\" in name or name.startswith(".") or ".." in name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, t("fehler.ablage_name", sprache))
    endung = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if endung not in ERLAUBTE_ENDUNGEN:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, t("fehler.ablage_typ", sprache)
        )
    return name


@router.post("", response_model=Abgelegt, summary="Erzeugnis im Arbeitsordner ablegen")
def ablegen(
    daten: Erzeugnis,
    repositories: Repositories = Depends(hole_repositories),
    user_id: str = Depends(hole_benutzer_id),
    sprache: str = Depends(hole_sprache),
) -> Abgelegt:
    chat = repositories.chats.holen(daten.chat_id, user_id=user_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, t("fehler.chat_nicht_gefunden", sprache))

    freigegeben = [Path(o).resolve() for o in (chat.working_dirs or [])]
    if not freigegeben:
        raise HTTPException(status.HTTP_409_CONFLICT, t("fehler.ablage_kein_ordner", sprache))

    if daten.ordner is None:
        ziel_ordner = freigegeben[0]
    else:
        gewaehlt = Path(daten.ordner).resolve()
        if gewaehlt not in freigegeben:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, t("fehler.ablage_ordner_fremd", sprache)
            )
        ziel_ordner = gewaehlt

    if len(daten.inhalt) > MAX_ZEICHEN:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, t("fehler.ablage_zu_gross", sprache)
        )

    name = _name_pruefen(daten.name, sprache)
    ziel = (ziel_ordner / name).resolve()

    # Checked a second time on the finished path. The name check alone
    # trusts that nothing in it resolves outward — a symlink in the folder
    # does not care about that check.
    if not liegt_innerhalb(ziel, freigegeben):
        raise HTTPException(status.HTTP_403_FORBIDDEN, t("fehler.ablage_name", sprache))

    ziel.write_text(daten.inhalt, encoding="utf-8")
    return Abgelegt(pfad=str(ziel))
