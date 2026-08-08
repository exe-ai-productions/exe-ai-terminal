"""Agents — one Markdown file is the whole agent (phase 6.3).

A file ``prompts/agenten/<name>.md`` consists of a front matter section between
two ``---`` lines (YAML) and the prompt after it. The file name without its
extension is the agent's name. The front matter holds its rules:

    ---
    model: mana            # endpoint id; if missing, the caller chooses
    tools:                 # allowlist — whatever is listed here runs without asking back
      - web_search
      - read_webpage
    max_rounds: 30         # tool rounds before we stop
    max_minutes: 20        # minutes before we stop
    schedule: "08:00"      # alarm clock (6.7): daily at this time, optional
    schedule_task: "..."   # the task the alarm clock hands the agent
    ---

    You are a research agent. ...

The keys are English, just like in ``config.yaml`` — the front matter is user
surface. The approval lives in the agent itself:
whatever is listed under ``tools`` runs without asking back; whatever is not
listed is never even offered to the model. The server's allowlist
(``mcp_servers.json``) remains the outer boundary — a tool that only the
agent knows about does not exist.

A broken file takes exactly this one agent out of play, not the service —
deliberately a different design than ``config.yaml``, which halts everything
at startup: it is the foundation of the service, an agent is a guest.

Read fresh on every use, like the system prompt: file changed = takes effect
immediately, no restart.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

# Guide values: two restraints, rounds and time.
# They apply when the front matter is silent — turning a restraint off entirely
# is deliberately not possible.
STANDARD_RUNDEN = 30
STANDARD_MINUTEN = 20.0

BEKANNTE_FELDER = {"model", "tools", "max_rounds", "max_minutes", "schedule", "schedule_task"}

# "HH:MM", 24-hour. Quotes are mandatory in YAML — without them the parser
# reads 08:00 as a sexagesimal number (480), see the check below.
ZEITPLAN_MUSTER = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


class AgentDateiKaputt(ValueError):
    """This one agent file is unusable. The service keeps running."""


@dataclass
class Agent:
    name: str
    prompt: str
    modell: str | None = None
    werkzeuge: list[str] = field(default_factory=list)
    runden: int = STANDARD_RUNDEN
    minuten: float = STANDARD_MINUTEN
    # The alarm clock (6.7): "HH:MM" means the agent runs daily at this time
    # with zeitplan_auftrag as the task text. Without a schedule both stay
    # empty and the agent only runs on demand.
    zeitplan: str | None = None
    zeitplan_auftrag: str | None = None


def agent_aus_text(name: str, text: str) -> Agent:
    """Reads an agent from raw text. Raises ``AgentDateiKaputt`` with a reason.

    Separate from file access because the edit window (6.6) needs the same
    validator before a file even hits the disk.
    """
    anzeige = f"{name}.md"

    if not text.startswith("---"):
        raise AgentDateiKaputt(
            f"'{anzeige}': der Kopfteil zwischen zwei '---'-Zeilen fehlt"
        )
    teile = text.split("---", 2)
    if len(teile) < 3:
        raise AgentDateiKaputt(f"'{anzeige}': die schließende '---'-Zeile fehlt")
    _, kopf_roh, prompt = teile

    try:
        kopf = yaml.safe_load(kopf_roh) or {}
    except yaml.YAMLError as fehler:
        raise AgentDateiKaputt(
            f"'{anzeige}': der Kopfteil ist kein gültiges YAML: {fehler}"
        ) from fehler
    if not isinstance(kopf, dict):
        raise AgentDateiKaputt(f"'{anzeige}': der Kopfteil ist keine Feldliste")

    unbekannt = set(kopf) - BEKANNTE_FELDER
    if unbekannt:
        # No reason to fail: a typo should stand out, but a file from a newer
        # program version should still be readable here.
        log.warning(
            "Agent '%s': unbekannte Kopfteil-Felder werden ignoriert: %s",
            name,
            ", ".join(sorted(unbekannt)),
        )

    modell = kopf.get("model")
    if modell is not None and not isinstance(modell, str):
        raise AgentDateiKaputt(f"'{anzeige}': 'model' muss ein Text sein")

    werkzeuge = kopf.get("tools") or []
    if not isinstance(werkzeuge, list) or not all(
        isinstance(eintrag, str) for eintrag in werkzeuge
    ):
        raise AgentDateiKaputt(f"'{anzeige}': 'tools' muss eine Liste von Namen sein")

    runden = kopf.get("max_rounds", STANDARD_RUNDEN)
    if not isinstance(runden, int) or isinstance(runden, bool) or runden < 1:
        raise AgentDateiKaputt(f"'{anzeige}': 'max_rounds' muss eine Zahl ab 1 sein")

    minuten = kopf.get("max_minutes", STANDARD_MINUTEN)
    if isinstance(minuten, bool) or not isinstance(minuten, (int, float)) or minuten <= 0:
        raise AgentDateiKaputt(f"'{anzeige}': 'max_minutes' muss eine Zahl über 0 sein")

    zeitplan = kopf.get("schedule")
    if zeitplan is not None:
        if not isinstance(zeitplan, str):
            # The YAML trap: 08:00 without quotes is a sexagesimal
            # number (480), not a time of day.
            raise AgentDateiKaputt(
                f"'{anzeige}': 'schedule' muss ein Text sein — "
                'die Uhrzeit in Anführungszeichen setzen, etwa schedule: "08:00"'
            )
        if not ZEITPLAN_MUSTER.match(zeitplan):
            raise AgentDateiKaputt(
                f"'{anzeige}': 'schedule' muss eine Uhrzeit \"HH:MM\" sein"
            )

    zeitplan_auftrag = kopf.get("schedule_task")
    if zeitplan_auftrag is not None and not isinstance(zeitplan_auftrag, str):
        raise AgentDateiKaputt(f"'{anzeige}': 'schedule_task' muss ein Text sein")
    if zeitplan and not (zeitplan_auftrag or "").strip():
        raise AgentDateiKaputt(
            f"'{anzeige}': 'schedule' braucht ein 'schedule_task' — "
            "der Text, mit dem der Wecker den Agenten beauftragt"
        )

    prompt = prompt.strip()
    if not prompt:
        raise AgentDateiKaputt(f"'{anzeige}': hinter dem Kopfteil steht kein Prompt")

    return Agent(
        name=name,
        prompt=prompt,
        modell=modell,
        werkzeuge=list(werkzeuge),
        runden=runden,
        minuten=float(minuten),
        zeitplan=zeitplan,
        zeitplan_auftrag=(zeitplan_auftrag or "").strip() or None,
    )


def agent_lesen(datei: Path) -> Agent:
    """Reads exactly one agent file. Raises ``AgentDateiKaputt`` with a reason."""
    return agent_aus_text(datei.stem, datei.read_text(encoding="utf-8"))


def agenten_laden(verzeichnis: Path) -> dict[str, Agent]:
    """All agents from the folder, broken ones reported and skipped.

    A missing folder is not an error — it ships empty
    (guiding idea from 3.10: the place exists, the content belongs to the user).
    """
    agenten: dict[str, Agent] = {}
    if not verzeichnis.is_dir():
        return agenten
    for datei in sorted(verzeichnis.glob("*.md")):
        try:
            agenten[datei.stem] = agent_lesen(datei)
        except (AgentDateiKaputt, OSError) as fehler:
            log.error("Agentendatei übersprungen: %s", fehler)
    return agenten
