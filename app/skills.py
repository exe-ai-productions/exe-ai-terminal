"""Skills — an instruction handed to the model in the middle of a conversation.

A skill is a folder. ``<name>/SKILL.md`` holds a front matter section between
two ``---`` lines and the instruction after it; anything else in the folder
belongs to the skill and can be pointed at from the instruction:

    ---
    description: Sums this conversation up as a handover
    auto: false            # may the model reach for it on its own?
    ---

    Go through the whole conversation and collect ...

The folder name is the skill's name, and it is what the user types after a
slash — so it is restricted to what can be typed and read back without
guessing: lower case, digits, hyphens.

**A skill is not an agent.** It carries no ``model:`` and no ``tools:``. An
agent is a separate run with its own head; it starts empty and cannot
summarise a conversation it was never part of. A skill is an instruction for
the head that is already here and already knows the conversation. Whatever a
skill is allowed to do is exactly what the chat is allowed to do.

Two places hold skills, and the user's wins:

* the shipped folder next to the program — replaced by every update
* the user's folder next to their prompts — never touched

Editing a shipped skill quietly copies it to the user's folder, so an update
walks past it. That is the same layering the settings use (default → global →
model → chat) and the same the prompt uses (shipped → the user's own): what
the house delivers is the floor, what the user writes lies on top.

A broken skill takes itself out of play and nothing else — like an agent
file, and unlike ``config.yaml``, which stops the service. The service is the
foundation, a skill is a guest.

Read fresh on every use: an edited file takes effect at once, no restart.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

SKILL_DATEI = "SKILL.md"

BEKANNTE_FELDER = {"description", "auto"}

# What an agent has and a skill deliberately does not. Named separately so the
# warning can say where that belongs instead of just calling it unknown.
AGENTENFELDER = {"model", "tools", "max_rounds", "max_minutes", "schedule"}

# The name is typed after a slash and read back from a list. Spaces, capitals
# and umlauts all survive on disk and then cannot be typed reliably.
NAME_MUSTER = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# The description of an automatic skill rides in the system prompt on every
# single request. One line is the whole budget.
MAX_BESCHREIBUNG = 120


class SkillKaputt(ValueError):
    """This one skill is unusable. The service keeps running."""


@dataclass
class Skill:
    name: str
    beschreibung: str
    anleitung: str
    ordner: Path
    # May the model load it without being asked? Costs a line of the system
    # prompt on every request, which is why it is off unless somebody decides
    # otherwise — in the mask, or through the tool, which asks either way.
    auto: bool = False
    # From the user's folder rather than the shipped one. Decides whether
    # editing writes straight through or makes a copy first.
    eigen: bool = False


def skill_aus_text(name: str, text: str, *, ordner: Path, eigen: bool = False) -> Skill:
    """Reads a skill from raw text. Raises ``SkillKaputt`` with a reason.

    Separate from file access so the editing mask can check the same way
    before anything reaches the disk.
    """
    anzeige = f"{name}/{SKILL_DATEI}"

    if not NAME_MUSTER.match(name):
        raise SkillKaputt(
            f"'{name}': der Name wird hinter einem Schrägstrich getippt und darf "
            "deshalb nur Kleinbuchstaben, Ziffern und Bindestriche enthalten"
        )

    if not text.startswith("---"):
        raise SkillKaputt(f"'{anzeige}': der Kopfteil zwischen zwei '---'-Zeilen fehlt")
    teile = text.split("---", 2)
    if len(teile) < 3:
        raise SkillKaputt(f"'{anzeige}': die schließende '---'-Zeile fehlt")
    _, kopf_roh, anleitung = teile

    try:
        kopf = yaml.safe_load(kopf_roh) or {}
    except yaml.YAMLError as fehler:
        raise SkillKaputt(
            f"'{anzeige}': der Kopfteil ist kein gültiges YAML: {fehler}"
        ) from fehler
    if not isinstance(kopf, dict):
        raise SkillKaputt(f"'{anzeige}': der Kopfteil ist keine Feldliste")

    verirrt = set(kopf) & AGENTENFELDER
    if verirrt:
        log.warning(
            "Skill '%s': %s gehört zu einem Agenten, nicht zu einer Skill, "
            "und wird übergangen",
            name,
            ", ".join(sorted(verirrt)),
        )
    unbekannt = set(kopf) - BEKANNTE_FELDER - AGENTENFELDER
    if unbekannt:
        # Not a reason to fail: a typo should stand out, but a file from a
        # newer program version should still be readable here.
        log.warning(
            "Skill '%s': unbekannte Kopfteil-Felder werden ignoriert: %s",
            name,
            ", ".join(sorted(unbekannt)),
        )

    beschreibung = kopf.get("description")
    if not isinstance(beschreibung, str) or not beschreibung.strip():
        raise SkillKaputt(
            f"'{anzeige}': 'description' fehlt — der eine Satz, der in der Liste "
            "steht und an dem das Modell erkennt, wofür die Skill da ist"
        )
    beschreibung = " ".join(beschreibung.split())
    if len(beschreibung) > MAX_BESCHREIBUNG:
        raise SkillKaputt(
            f"'{anzeige}': 'description' ist länger als {MAX_BESCHREIBUNG} Zeichen — "
            "sie steht bei jeder Anfrage im Prompt und muss ein Satz bleiben"
        )

    auto = kopf.get("auto", False)
    if not isinstance(auto, bool):
        raise SkillKaputt(f"'{anzeige}': 'auto' muss true oder false sein")

    anleitung = anleitung.strip()
    if not anleitung:
        raise SkillKaputt(f"'{anzeige}': hinter dem Kopfteil steht keine Anleitung")

    return Skill(
        name=name,
        beschreibung=beschreibung,
        anleitung=anleitung,
        ordner=ordner,
        auto=auto,
        eigen=eigen,
    )


def skill_lesen(ordner: Path, *, eigen: bool = False) -> Skill:
    """Reads exactly one skill folder. Raises ``SkillKaputt`` with a reason."""
    datei = ordner / SKILL_DATEI
    return skill_aus_text(
        ordner.name, datei.read_text(encoding="utf-8"), ordner=ordner, eigen=eigen
    )


def aus_verzeichnis(verzeichnis: Path, *, eigen: bool) -> dict[str, Skill]:
    """Everything usable in ONE of the two places.

    Public because the settings mask has to tell the two apart: what came with
    the program can be reset, what the user wrote themselves cannot.
    """
    gefunden: dict[str, Skill] = {}
    if not verzeichnis.is_dir():
        # Not an error: the place exists, the content belongs to the user.
        return gefunden
    for ordner in sorted(p for p in verzeichnis.iterdir() if p.is_dir()):
        if not (ordner / SKILL_DATEI).is_file():
            continue
        try:
            gefunden[ordner.name] = skill_lesen(ordner, eigen=eigen)
        except (SkillKaputt, OSError) as fehler:
            log.error("Skill übersprungen: %s", fehler)
    return gefunden


def skills_laden(mitgeliefert: Path, eigen: Path) -> dict[str, Skill]:
    """Every usable skill, the user's copy winning over the shipped one.

    Sorted by name so the list reads the same way every time — the order in
    which folders come off the disk is not something anyone should have to
    think about.
    """
    zusammen = aus_verzeichnis(mitgeliefert, eigen=False)
    zusammen.update(aus_verzeichnis(eigen, eigen=True))
    return dict(sorted(zusammen.items()))


# What the model is told before a picked instruction. Without a sentence like
# this it reads as part of the conversation rather than as the thing to do.
EINLEITUNG = (
    "The user picked this written-down instruction for this message. Follow "
    "it for this task. Their message follows it and says what to apply it to."
)


def anhaengen(system_prompt: str, skill: Skill | None) -> str:
    """Puts the picked instruction into the ONE system message, last.

    Last on purpose: it is the most immediate thing to do, and the layers
    before it — how the machine works, who the user is, what is known about
    them — are the context it acts in, not competition for it.

    It rides along with this request and is not stored. What should outlast
    the request is the answer, not the instruction that produced it; a
    handover, once written, does not need the rule for writing handovers to
    stay in the conversation.
    """
    if skill is None:
        return system_prompt
    block = f"{EINLEITUNG}\n\n## {skill.name}\n\n{skill.anleitung}"
    system_prompt = (system_prompt or "").strip()
    return f"{system_prompt}\n\n{block}" if system_prompt else block


def automatische(skills: dict[str, Skill]) -> list[Skill]:
    """Only those the model may reach for on its own.

    Everything here costs a line in the system prompt on every request; the
    rest costs nothing at all and is still available by typing its name.
    """
    return [s for s in skills.values() if s.auto]
