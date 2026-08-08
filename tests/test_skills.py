"""Reading skills: two places, the user's wins, a broken one drops out alone.

The rules being guarded here are decisions, not implementation details. A
skill carries no model and no tool list — that is what separates it from an
agent, and the separation is the reason both exist. Its name is typed after a
slash, so it has to survive being typed. And its description rides in the
system prompt on every request when the skill is automatic, which is why
there is a limit on it at all.
"""

from __future__ import annotations

import pytest

from app import skills


def _schreiben(ordner, name, text, *, beilage=None):
    ziel = ordner / name
    ziel.mkdir(parents=True)
    (ziel / skills.SKILL_DATEI).write_text(text, encoding="utf-8")
    if beilage:
        (ziel / beilage).write_text("egal", encoding="utf-8")
    return ziel


GUT = """---
description: Sums this conversation up as a handover
auto: true
---

Go through the whole conversation and collect what matters.
"""


def test_eine_gute_skill_wird_gelesen(tmp_path):
    ordner = _schreiben(tmp_path, "handoff", GUT)
    skill = skills.skill_lesen(ordner)
    assert skill.name == "handoff"
    assert skill.beschreibung == "Sums this conversation up as a handover"
    assert skill.anleitung.startswith("Go through")
    assert skill.auto is True


def test_auto_ist_ohne_angabe_aus(tmp_path):
    """The expensive setting is never the one you get by not deciding."""
    ordner = _schreiben(tmp_path, "still", "---\ndescription: Does a thing\n---\n\nDo it.\n")
    assert skills.skill_lesen(ordner).auto is False


def test_der_ordner_gehoert_zur_skill(tmp_path):
    """An instruction that points at a script beside it needs to know where
    it stands. Two of the three skills this was modelled on carry one."""
    ordner = _schreiben(tmp_path, "vektoren", GUT, beilage="generator.py")
    skill = skills.skill_lesen(ordner)
    assert skill.ordner == ordner
    assert (skill.ordner / "generator.py").is_file()


@pytest.mark.parametrize("name", ["Handoff", "mein skill", "über", "-vorn", "a_b"])
def test_ein_name_der_sich_nicht_tippen_laesst_faellt_durch(tmp_path, name):
    with pytest.raises(skills.SkillKaputt):
        skills.skill_aus_text(name, GUT, ordner=tmp_path)


def test_ohne_beschreibung_faellt_sie_durch(tmp_path):
    """Without it there is nothing to put in the list and nothing the model
    could recognise the skill by."""
    with pytest.raises(skills.SkillKaputt, match="description"):
        skills.skill_aus_text("x", "---\nauto: true\n---\n\nText.\n", ordner=tmp_path)


def test_eine_zu_lange_beschreibung_faellt_durch(tmp_path):
    lang = "w " * 200
    with pytest.raises(skills.SkillKaputt, match="description"):
        skills.skill_aus_text(
            "x", f"---\ndescription: {lang}\n---\n\nText.\n", ordner=tmp_path
        )


def test_ohne_anleitung_faellt_sie_durch(tmp_path):
    with pytest.raises(skills.SkillKaputt):
        skills.skill_aus_text("x", "---\ndescription: Da\n---\n\n   \n", ordner=tmp_path)


def test_agentenfelder_werden_uebergangen_statt_befolgt(tmp_path, caplog):
    """A skill has no model and no tool list. Writing them anyway is a
    misunderstanding worth a word, not a reason to throw the skill away."""
    text = "---\ndescription: Da\nmodel: qwen-mac\ntools:\n  - run_command\n---\n\nText.\n"
    skill = skills.skill_aus_text("x", text, ordner=tmp_path)
    assert skill.beschreibung == "Da"
    assert not hasattr(skill, "modell")
    assert "Agenten" in caplog.text


# --- the two places ----------------------------------------------------------


def test_deine_fassung_schlaegt_die_mitgelieferte(tmp_path):
    haus = tmp_path / "haus"
    mein = tmp_path / "mein"
    _schreiben(haus, "handoff", "---\ndescription: Ab Werk\n---\n\nWerk.\n")
    _schreiben(mein, "handoff", "---\ndescription: Meine\n---\n\nMeins.\n")

    geladen = skills.skills_laden(haus, mein)
    assert len(geladen) == 1
    assert geladen["handoff"].beschreibung == "Meine"
    assert geladen["handoff"].eigen is True


def test_beide_orte_kommen_zusammen(tmp_path):
    haus = tmp_path / "haus"
    mein = tmp_path / "mein"
    _schreiben(haus, "handoff", GUT)
    _schreiben(mein, "eigenes", GUT)

    geladen = skills.skills_laden(haus, mein)
    assert sorted(geladen) == ["eigenes", "handoff"]
    assert geladen["handoff"].eigen is False


def test_fehlende_ordner_sind_kein_fehler(tmp_path):
    """It ships empty — the place exists, the content belongs to the user."""
    assert skills.skills_laden(tmp_path / "weg", tmp_path / "auch-weg") == {}


def test_eine_kaputte_skill_nimmt_die_anderen_nicht_mit(tmp_path):
    mein = tmp_path / "mein"
    _schreiben(mein, "heil", GUT)
    _schreiben(mein, "kaputt", "hier fehlt der Kopfteil")

    geladen = skills.skills_laden(tmp_path / "haus", mein)
    assert sorted(geladen) == ["heil"]


def test_ein_ordner_ohne_skill_datei_wird_uebergangen(tmp_path):
    mein = tmp_path / "mein"
    (mein / "nur-ein-ordner").mkdir(parents=True)
    _schreiben(mein, "heil", GUT)
    assert sorted(skills.skills_laden(tmp_path / "haus", mein)) == ["heil"]


def test_nur_automatische_kosten_platz_im_prompt(tmp_path):
    mein = tmp_path / "mein"
    _schreiben(mein, "selbst", "---\ndescription: Da\nauto: true\n---\n\nText.\n")
    _schreiben(mein, "getippt", "---\ndescription: Da\n---\n\nText.\n")

    geladen = skills.skills_laden(tmp_path / "haus", mein)
    assert [s.name for s in skills.automatische(geladen)] == ["selbst"]
