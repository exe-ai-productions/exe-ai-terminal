"""Loading and writing skills.

The rules under test are the ones that were argued for, not the plumbing:
nothing here asks — the one prompt in the program is the shell reaching
outside the shared folders — and writing never lands in the shipped folder,
so a change to a shipped skill survives the next update.
"""

from __future__ import annotations

import pytest

from app import skills
from app.tools import skill


@pytest.fixture
def orte(tmp_path):
    haus = tmp_path / "haus"
    mein = tmp_path / "mein"
    haus.mkdir()
    mein.mkdir()
    return haus, mein


def _anlegen(ordner, name, beschreibung="Da", anleitung="Tu es.", auto=False):
    ziel = ordner / name
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / skills.SKILL_DATEI).write_text(
        f"---\ndescription: {beschreibung}\nauto: {str(auto).lower()}\n---\n\n{anleitung}\n",
        encoding="utf-8",
    )
    return ziel


# --- loading -----------------------------------------------------------------


async def test_laden_gibt_die_ganze_anleitung(orte):
    haus, mein = orte
    _anlegen(haus, "handoff", anleitung="Erst dies, dann das.")
    assert await skill.laden({"name": "handoff"}, haus, mein) == "Erst dies, dann das."


async def test_laden_nimmt_deine_fassung(orte):
    haus, mein = orte
    _anlegen(haus, "handoff", anleitung="Ab Werk.")
    _anlegen(mein, "handoff", anleitung="Meine.")
    assert await skill.laden({"name": "handoff"}, haus, mein) == "Meine."


async def test_ein_unbekannter_name_nennt_die_vorhandenen(orte):
    """A model that guessed the name is one line away from the right one."""
    haus, mein = orte
    _anlegen(haus, "handoff")
    with pytest.raises(skill.SkillVerboten, match="handoff"):
        await skill.laden({"name": "handof"}, haus, mein)


async def test_laden_fragt_nicht(orte):
    assert skill.braucht_bestaetigung(skill.LADEN, {"name": "handoff"}) is False


# --- writing -----------------------------------------------------------------


async def test_auch_schreiben_fragt_nicht():
    """One prompt in the whole program, and it is the shell reaching outside
    the shared folders. A written skill does nothing until it is loaded, and
    it can be switched off or deleted in the mask."""
    assert skill.braucht_bestaetigung(skill.SCHREIBEN, {"name": "x"}) is False
    assert skill.braucht_bestaetigung(skill.LADEN, {"name": "x"}) is False


async def test_schreiben_legt_die_skill_bei_dir_an(orte):
    haus, mein = orte
    antwort = await skill.schreiben(
        {"name": "release", "description": "Vor dem Ausliefern", "instruction": "Erst Tests."},
        mein,
    )
    assert "/release" in antwort
    geladen = skills.skills_laden(haus, mein)
    assert geladen["release"].anleitung == "Erst Tests."
    assert geladen["release"].eigen is True


async def test_ohne_angabe_wird_eine_neue_skill_nicht_von_selbst_geladen(orte):
    """The expensive setting is never the one you get by not deciding."""
    haus, mein = orte
    await skill.schreiben(
        {"name": "neu", "description": "Da", "instruction": "Tu es."}, mein
    )
    assert skills.skills_laden(haus, mein)["neu"].auto is False


async def test_das_modell_darf_eine_skill_selbst_freischalten(orte):
    """It costs a line of every later request — what answers that is the mask,
    where the count stands at the top and each one can be switched off."""
    haus, mein = orte
    await skill.schreiben(
        {"name": "neu", "description": "Da", "instruction": "Tu es.", "auto": True},
        mein,
    )
    assert skills.skills_laden(haus, mein)["neu"].auto is True


async def test_schreiben_geht_nie_in_den_mitgelieferten_ordner(orte):
    """Overwriting a shipped skill IS the copy that keeps the next update
    from quietly taking the change back."""
    haus, mein = orte
    _anlegen(haus, "handoff", anleitung="Ab Werk.")
    await skill.schreiben(
        {"name": "handoff", "description": "Meine", "instruction": "Meins."}, mein
    )
    assert (haus / "handoff" / skills.SKILL_DATEI).read_text().endswith("Ab Werk.\n")
    assert skills.skills_laden(haus, mein)["handoff"].anleitung == "Meins."


async def test_ein_untippbarer_name_wird_abgelehnt(orte):
    _, mein = orte
    with pytest.raises(skill.SkillVerboten):
        await skill.schreiben(
            {"name": "Mein Skill", "description": "Da", "instruction": "Tu es."}, mein
        )
    assert not any(mein.iterdir())


async def test_eine_zu_lange_anleitung_wird_abgelehnt(orte):
    _, mein = orte
    with pytest.raises(skill.SkillVerboten, match="Too long"):
        await skill.schreiben(
            {"name": "lang", "description": "Da", "instruction": "x" * (skill.MAX_ANLEITUNG + 1)},
            mein,
        )
    assert not any(mein.iterdir())


async def test_eine_abgelehnte_skill_laesst_keinen_leeren_ordner_zurueck(orte):
    _, mein = orte
    with pytest.raises(skill.SkillVerboten):
        await skill.schreiben({"name": "leer", "description": "", "instruction": "x"}, mein)
    assert not any(mein.iterdir())


async def test_der_zweite_schreibvorgang_ersetzt_statt_zu_stapeln(orte):
    haus, mein = orte
    for text in ("Erst.", "Dann."):
        await skill.schreiben(
            {"name": "wieder", "description": "Da", "instruction": text}, mein
        )
    assert skills.skills_laden(haus, mein)["wieder"].anleitung == "Dann."
