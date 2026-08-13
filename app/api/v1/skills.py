"""The skill list — what the slash list in the input bar offers.

Names and one line each, nothing more. The instruction itself is not sent
here on purpose: this route answers on every keystroke that opens the list,
and nobody needs the full text to pick from it.

Where a skill comes from is not in the answer either. At picking time it does
not matter whether it shipped with the program or the user wrote it — that
distinction belongs in the settings mask, where it decides what editing does.
"""

from __future__ import annotations

import shutil

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import skills

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillEintrag(BaseModel):
    name: str
    beschreibung: str
    auto: bool


class SkillZeile(SkillEintrag):
    """The mask needs two things the picker does not: where the skill comes
    from, because it decides what editing does, and whether a shipped one has
    been taken over, because that is what can be undone."""

    eigen: bool
    mitgeliefert: bool


class AutoSetzen(BaseModel):
    auto: bool


class NeuerSkill(BaseModel):
    """The raw ``SKILL.md`` a user writes in the editor: the front matter and
    the body in one string, saved exactly as typed so it reads back the same.

    The length bound is a guardrail against a runaway paste, not a budget — a
    skill is an instruction, and one that long is a mistake either way.
    """

    name: str
    inhalt: str = Field(max_length=100_000)


def _orte(request: Request) -> tuple:
    return request.app.state.config.skillverzeichnisse


def _geprueft(name: str) -> str:
    """The name comes out of the URL and is about to become a path.

    Without this check a name like ``../../etc`` would reach straight out of
    the skill folder. The pattern is the same one a skill file has to satisfy,
    so nothing legitimate is turned away by it.
    """
    if not skills.NAME_MUSTER.match(name):
        raise HTTPException(400, f"'{name}' ist kein gültiger Skill-Name")
    return name


@router.get("", response_model=list[SkillEintrag])
def liste(request: Request) -> list[SkillEintrag]:
    """Every usable skill, sorted by name, the user's copy winning."""
    vorhanden = skills.skills_laden(*_orte(request))
    return [
        SkillEintrag(name=s.name, beschreibung=s.beschreibung, auto=s.auto)
        for s in vorhanden.values()
    ]


@router.get("/verwaltung", response_model=list[SkillZeile])
def verwaltung(request: Request) -> list[SkillZeile]:
    """The same list for the settings mask, with where each one comes from."""
    mitgeliefert, eigen = _orte(request)
    ab_werk = set(skills.aus_verzeichnis(mitgeliefert, eigen=False))
    return [
        SkillZeile(
            name=s.name,
            beschreibung=s.beschreibung,
            auto=s.auto,
            eigen=s.eigen,
            mitgeliefert=s.name in ab_werk,
        )
        for s in skills.skills_laden(mitgeliefert, eigen).values()
    ]


@router.post("", response_model=SkillZeile, status_code=201)
def anlegen(daten: NeuerSkill, request: Request) -> SkillZeile:
    """Writes a user's own skill and hands back how it now reads.

    The file lands in the user's folder, where it shadows a shipped one of the
    same name — the same copy-on-write the settings mask uses, so the next
    update walks past it. Content that does not parse is taken back off the
    disk and answered with the reason, so a broken skill never lingers.
    """
    name = _geprueft(daten.name)
    if not daten.inhalt.strip():
        raise HTTPException(400, "Der Skill-Inhalt ist leer")

    mitgeliefert, eigen = _orte(request)
    ordner = eigen / name
    frisch = not ordner.exists()
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / skills.SKILL_DATEI
    datei.write_text(daten.inhalt, encoding="utf-8")

    try:
        skills.skill_lesen(ordner, eigen=True)
    except skills.SkillKaputt as fehler:
        # A file that will not load back must not be left behind. Remove only
        # what this call put there: the whole folder when it was created here,
        # otherwise just the file that was overwritten.
        if frisch:
            shutil.rmtree(ordner, ignore_errors=True)
        else:
            datei.unlink(missing_ok=True)
        raise HTTPException(400, str(fehler)) from fehler

    geladen = skills.skills_laden(mitgeliefert, eigen)[name]
    ab_werk = set(skills.aus_verzeichnis(mitgeliefert, eigen=False))
    return SkillZeile(
        name=name,
        beschreibung=geladen.beschreibung,
        auto=geladen.auto,
        eigen=True,
        mitgeliefert=name in ab_werk,
    )


@router.patch("/{name}", response_model=SkillZeile)
def auto_setzen(name: str, daten: AutoSetzen, request: Request) -> SkillZeile:
    """Switches a skill between being offered on its own and being named.

    On a shipped skill this quietly makes the user's copy first — the same
    copy-on-edit that keeps the next update from taking the change back.
    """
    name = _geprueft(name)
    mitgeliefert, eigen = _orte(request)
    vorhanden = skills.skills_laden(mitgeliefert, eigen)
    skill = vorhanden.get(name)
    if skill is None:
        raise HTTPException(404, f"Keine Skill namens '{name}'")

    ziel = eigen / name
    if not skill.eigen:
        shutil.copytree(skill.ordner, ziel)
    datei = ziel / skills.SKILL_DATEI
    datei.write_text(
        f"---\ndescription: {skill.beschreibung}\nauto: {str(daten.auto).lower()}\n"
        f"---\n\n{skill.anleitung}\n",
        encoding="utf-8",
    )
    ab_werk = set(skills.aus_verzeichnis(mitgeliefert, eigen=False))
    return SkillZeile(
        name=name,
        beschreibung=skill.beschreibung,
        auto=daten.auto,
        eigen=True,
        mitgeliefert=name in ab_werk,
    )


@router.delete("/{name}", status_code=204, response_class=Response)
def zuruecksetzen(name: str, request: Request) -> Response:
    """Removes the user's copy. A shipped skill reappears in its own version;
    one the user wrote themselves is gone."""
    name = _geprueft(name)
    _, eigen = _orte(request)
    ziel = eigen / name
    if not (ziel / skills.SKILL_DATEI).is_file():
        raise HTTPException(404, f"Keine eigene Fassung von '{name}'")
    shutil.rmtree(ziel)
    return Response(status_code=204)
