"""The alarm clock (phase 6.7): frontmatter, schedule logic and the three rules.

The passes are called with an explicit ``jetzt`` — the tests turn the clock
instead of waiting. Triggered runs live in a throwaway event loop
(``asyncio.run``); what is checked is the created job, not its completion —
completion belongs to the job tests (6.3/6.4).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.agenten import AgentDateiKaputt, agent_lesen
from app.wecker import Wecker, letzter_termin, wecker_pausiert
from tests.conftest import provider_setzen
from app.providers import MockProvider, mock_endpunkt


def schreiben(ordner: Path, name: str, inhalt: str) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.md"
    datei.write_text(inhalt, encoding="utf-8")
    return datei


MIT_WECKER = """---
model: test
schedule: "12:00"
schedule_task: "Collect the morning news."
---

You are the news agent.
"""


# --- Frontmatter -----------------------------------------------------------


def test_zeitplan_wird_gelesen(tmp_path):
    agent = agent_lesen(schreiben(tmp_path, "news", MIT_WECKER))
    assert agent.zeitplan == "12:00"
    assert agent.zeitplan_auftrag == "Collect the morning news."


def test_zeitplan_ohne_anfuehrungszeichen_ist_kaputt(tmp_path):
    # The YAML trap: 12:00 without quotation marks is the number 720
    # (sexagesimal). Only with a leading zero would it happen to stay a string.
    datei = schreiben(
        tmp_path,
        "news",
        '---\nschedule: 12:00\nschedule_task: "x"\n---\n\nPrompt.\n',
    )
    with pytest.raises(AgentDateiKaputt, match="Anführungszeichen"):
        agent_lesen(datei)


def test_zeitplan_muss_eine_uhrzeit_sein(tmp_path):
    datei = schreiben(
        tmp_path,
        "news",
        '---\nschedule: "25:99"\nschedule_task: "x"\n---\n\nPrompt.\n',
    )
    with pytest.raises(AgentDateiKaputt, match="HH:MM"):
        agent_lesen(datei)


def test_zeitplan_braucht_einen_auftragstext(tmp_path):
    datei = schreiben(tmp_path, "news", '---\nschedule: "08:00"\n---\n\nPrompt.\n')
    with pytest.raises(AgentDateiKaputt, match="schedule_task"):
        agent_lesen(datei)


def test_ohne_zeitplan_bleibt_alles_leer(tmp_path):
    agent = agent_lesen(schreiben(tmp_path, "still", "---\nmodel: test\n---\n\nPrompt.\n"))
    assert agent.zeitplan is None
    assert agent.zeitplan_auftrag is None


# --- Schedule logic --------------------------------------------------------


def test_letzter_termin_heute():
    jetzt = datetime(2026, 8, 4, 14, 0, tzinfo=timezone.utc)
    assert letzter_termin("12:00", jetzt) == datetime(
        2026, 8, 4, 12, 0, tzinfo=timezone.utc
    )


def test_letzter_termin_gestern():
    jetzt = datetime(2026, 8, 4, 7, 0, tzinfo=timezone.utc)
    assert letzter_termin("12:00", jetzt) == datetime(
        2026, 8, 3, 12, 0, tzinfo=timezone.utc
    )


# --- The three rules -------------------------------------------------------


def agent_anlegen(config, inhalt: str = MIT_WECKER, name: str = "news") -> None:
    schreiben(Path(config.app.agenten_verzeichnis), name, inhalt)


def pruefen(client, jetzt: datetime) -> None:
    """One alarm-clock pass at a set time."""
    asyncio.run(client.app.state.wecker.einmal_pruefen(jetzt=jetzt))


def auftraege_von(client, agent: str) -> list[dict]:
    return [a for a in client.get("/api/v1/jobs").json() if a["agent"] == agent]


MORGEN_13 = datetime.now(timezone.utc).replace(
    hour=13, minute=0, second=0, microsecond=0
) + timedelta(days=1)


def test_wecker_holt_verpassten_termin_einmal_nach(config, client):
    agent_anlegen(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test")))

    # Tomorrow 13:00: the 12:00 slot has passed, no run since it — fire.
    pruefen(client, MORGEN_13)
    assert len(auftraege_von(client, "news")) == 1

    # The same slot does not fire twice — not even after the run.
    pruefen(client, MORGEN_13)
    pruefen(client, MORGEN_13 + timedelta(minutes=30))
    assert len(auftraege_von(client, "news")) == 1


def test_lauf_seit_termin_erledigt_den_termin(config, client):
    agent_anlegen(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test")))
    # A manual run, now. The most recent past 12:00 slot lies before it —
    # the alarm clock has nothing left to do.
    client.post("/api/v1/jobs", json={"agent": "news", "task": "von Hand"})
    jetzt = datetime.now(timezone.utc) + timedelta(minutes=1)
    if letzter_termin("12:00", jetzt) > datetime.now(timezone.utc):
        pytest.skip("Terminfenster zu knapp — nur um Mitternacht UTC möglich")

    pruefen(client, jetzt)
    assert len(auftraege_von(client, "news")) == 1


def test_laufender_agent_wird_uebersprungen(config, client):
    agent_anlegen(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test")))
    repositories = client.app.state.repositories
    # A still-active run from yesterday: the slot is skipped (rule 2).
    alt = repositories.auftraege.erstellen(
        user_id="standard", agent="news", auftrag="läuft noch", zustand="laeuft"
    )
    repositories.auftraege.verbindung.execute(
        "UPDATE auftraege SET created_at = ? WHERE id = ?",
        ((MORGEN_13 - timedelta(days=1)).isoformat(), alt.id),
    )

    pruefen(client, MORGEN_13)
    assert len(auftraege_von(client, "news")) == 1  # only the old one


def test_pause_nach_drei_fehlschlaegen(config, client):
    agent_anlegen(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test")))
    repositories = client.app.state.repositories
    for _ in range(3):
        repositories.auftraege.erstellen(
            user_id="standard", agent="news", auftrag="x", zustand="gescheitert"
        )
    repositories.auftraege.verbindung.execute(
        "UPDATE auftraege SET created_at = ? WHERE agent = 'news'",
        ((MORGEN_13 - timedelta(days=1)).isoformat(),),
    )

    pruefen(client, MORGEN_13)
    assert len(auftraege_von(client, "news")) == 3  # no new one

    (eintrag,) = [a for a in client.get("/api/v1/agents").json() if a["name"] == "news"]
    assert eintrag["schedule"] == "12:00"
    assert eintrag["schedule_paused"] is True


def test_guter_lauf_beendet_die_pause(config, client):
    agent_anlegen(config)
    provider_setzen(client, MockProvider(mock_endpunkt("test")))
    repositories = client.app.state.repositories
    for zustand in ("gescheitert", "gescheitert", "gescheitert", "fertig"):
        repositories.auftraege.erstellen(
            user_id="standard", agent="news", auftrag="x", zustand=zustand
        )
    agent = agent_lesen(Path(config.app.agenten_verzeichnis) / "news.md")
    assert wecker_pausiert(repositories, agent) is False


def test_ohne_endpunkt_bleibt_der_termin_offen(config, client):
    agent_anlegen(config)
    # Shut down the discovery background loop. On entry it IMMEDIATELY
    # checks a second time (discovery.py, _schleife) and, depending on
    # chance, flipped the flag below back to True — which made the test
    # fail in about half of all runs (measured: 6 out of 12).
    #
    # Only flip the flag and cancel the task, no `asyncio.run(stoppen())`:
    # that opens a second event loop, and the task lives in the test
    # client's loop.
    discovery = client.app.state.discovery
    discovery._laeuft = False
    if discovery._aufgabe is not None:
        discovery._aufgabe.cancel()

    # Nothing is reachable — the alarm clock starts nothing, but also does
    # not mark the slot as handled.
    client.app.state.discovery.zustaende["test"].erreichbar = False
    pruefen(client, MORGEN_13)
    assert auftraege_von(client, "news") == []

    # The endpoint comes back: the next pass makes up for the slot.
    provider_setzen(client, MockProvider(mock_endpunkt("test")))
    pruefen(client, MORGEN_13 + timedelta(minutes=1))
    assert len(auftraege_von(client, "news")) == 1
