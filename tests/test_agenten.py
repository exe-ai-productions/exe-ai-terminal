"""The agent as a file (phase 6.3): read the header, survive broken files."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agenten import (
    STANDARD_MINUTEN,
    STANDARD_RUNDEN,
    AgentDateiKaputt,
    agent_lesen,
    agenten_laden,
)


def schreiben(ordner: Path, name: str, inhalt: str) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.md"
    datei.write_text(inhalt, encoding="utf-8")
    return datei


VOLLSTAENDIG = """---
model: mana
tools:
  - web_search
  - read_webpage
max_rounds: 10
max_minutes: 5
---

You are a research agent.
"""


def test_vollstaendige_datei_wird_gelesen(tmp_path):
    agent = agent_lesen(schreiben(tmp_path, "recherche", VOLLSTAENDIG))
    assert agent.name == "recherche"
    assert agent.modell == "mana"
    assert agent.werkzeuge == ["web_search", "read_webpage"]
    assert agent.runden == 10
    assert agent.minuten == 5.0
    assert agent.prompt == "You are a research agent."


def test_vorgaben_greifen_bei_schweigsamem_kopfteil(tmp_path):
    """If a limit is missing from the header, the default applies — never none at all."""
    agent = agent_lesen(
        schreiben(tmp_path, "still", "---\nmodel: mana\n---\nTu was.\n")
    )
    assert agent.runden == STANDARD_RUNDEN
    assert agent.minuten == STANDARD_MINUTEN
    assert agent.werkzeuge == []
    assert agent.modell == "mana"


def test_ohne_kopfteil_ist_die_datei_kaputt(tmp_path):
    with pytest.raises(AgentDateiKaputt, match="Kopfteil"):
        agent_lesen(schreiben(tmp_path, "roh", "Nur Prompt, kein Kopf.\n"))


def test_ohne_schliessende_striche_ist_die_datei_kaputt(tmp_path):
    with pytest.raises(AgentDateiKaputt, match="schließende"):
        agent_lesen(schreiben(tmp_path, "offen", "---\nmodel: mana\nTu was.\n"))


def test_kaputtes_yaml_ist_kaputt(tmp_path):
    with pytest.raises(AgentDateiKaputt, match="YAML"):
        agent_lesen(schreiben(tmp_path, "yaml", "---\nmodel: [ohne ende\n---\nx\n"))


def test_tools_muss_eine_liste_sein(tmp_path):
    with pytest.raises(AgentDateiKaputt, match="tools"):
        agent_lesen(schreiben(tmp_path, "t", "---\ntools: web_search\n---\nx\n"))


def test_runden_muessen_eine_zahl_ab_1_sein(tmp_path):
    with pytest.raises(AgentDateiKaputt, match="max_rounds"):
        agent_lesen(schreiben(tmp_path, "r", "---\nmax_rounds: 0\n---\nx\n"))


def test_minuten_muessen_ueber_0_liegen(tmp_path):
    with pytest.raises(AgentDateiKaputt, match="max_minutes"):
        agent_lesen(schreiben(tmp_path, "m", "---\nmax_minutes: -3\n---\nx\n"))


def test_ohne_prompt_ist_die_datei_kaputt(tmp_path):
    with pytest.raises(AgentDateiKaputt, match="kein Prompt"):
        agent_lesen(schreiben(tmp_path, "leer", "---\nmodel: mana\n---\n\n"))


def test_unbekannte_felder_stoeren_nicht(tmp_path):
    """A file from a newer program version stays readable."""
    agent = agent_lesen(
        schreiben(tmp_path, "neu", "---\nmodel: mana\nzukunft: ja\n---\nx\n")
    )
    assert agent.modell == "mana"


def test_kaputte_datei_nimmt_nur_diesen_agenten_aus_dem_spiel(tmp_path):
    """Decision from 6.3: no service outage because of one agent file."""
    schreiben(tmp_path, "gesund", VOLLSTAENDIG)
    schreiben(tmp_path, "krank", "kein kopfteil")
    agenten = agenten_laden(tmp_path)
    assert sorted(agenten) == ["gesund"]


def test_fehlender_ordner_heisst_keine_agenten(tmp_path):
    assert agenten_laden(tmp_path / "gibtsnicht") == {}
