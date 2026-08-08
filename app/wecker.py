"""The alarm clock (phase 6.7) — starts agents on a schedule.

Modeled on the endpoint check (``discovery.py``): a background loop in the
same process, started and stopped by the lifecycle. An agent gets its
schedule in the front matter (``schedule: "08:00"`` plus ``schedule_task``),
read fresh on every pass — file changed = takes effect immediately, as
everywhere with agents.

The three rules:

1. **Catch up once.** Only the most recent past due time counts. If the
   agent has not run since then, it is started — even if the service was off
   at the scheduled time. Older missed due times lapse. A manually started
   run counts toward the due time: the report in question exists then, after
   all.
2. **Skip instead of stacking.** If a run of the agent is still running (or
   waiting), the due time is dropped — noted in the log, not made up.
3. **Pause after three consecutive failures.** If the agent's three most
   recent runs all failed, the alarm clock suspends until any run ends well
   again. ``GET /agents`` reports the pause to the UI.

Times apply in ``app.timezone`` from ``config.yaml`` — if the entry is
missing, in the server's time zone.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.agenten import Agent, agenten_laden

log = logging.getLogger(__name__)

PRUEF_ABSTAND_SEKUNDEN = 30
PAUSE_NACH_FEHLSCHLAEGEN = 3


def wecker_pausiert(repositories, agent: Agent) -> bool:
    """Whether the alarm clock is currently leaving this agent alone (rule 3)."""
    if not agent.zeitplan:
        return False
    zustaende = repositories.auftraege.letzte_zustaende(
        agent=agent.name, anzahl=PAUSE_NACH_FEHLSCHLAEGEN
    )
    return len(zustaende) == PAUSE_NACH_FEHLSCHLAEGEN and all(
        zustand == "gescheitert" for zustand in zustaende
    )


def letzter_termin(zeitplan: str, jetzt: datetime) -> datetime:
    """The most recent past due time — today, or yesterday if today's
    time has not been reached yet."""
    stunde, minute = (int(teil) for teil in zeitplan.split(":"))
    termin = jetzt.replace(hour=stunde, minute=minute, second=0, microsecond=0)
    if termin > jetzt:
        termin -= timedelta(days=1)
    return termin


def _als_aware(iso: str) -> datetime:
    """Make timestamps from the database (``jetzt_iso``, UTC) comparable."""
    wert = datetime.fromisoformat(iso)
    return wert if wert.tzinfo else wert.replace(tzinfo=timezone.utc)


class Wecker:
    """Continuously checks whether an agent is due per its schedule."""

    def __init__(self, app) -> None:
        # Only the app is held on to — configuration, repositories and
        # discovery are read fresh from ``app.state`` on every pass, just
        # like the agent files from disk.
        self.app = app
        # Per agent, the most recently handled due time: triggered OR
        # deliberately skipped. Intentionally in memory only — after a
        # restart the database answers the question anew (rule 1).
        self._behandelt: dict[str, datetime] = {}
        self._aufgabe: asyncio.Task | None = None
        self._laeuft = False

    def _jetzt(self) -> datetime:
        name = self.app.state.config.app.timezone
        if name:
            return datetime.now(ZoneInfo(name))
        return datetime.now().astimezone()

    async def einmal_pruefen(self, jetzt: datetime | None = None) -> None:
        """One pass over all agents with a schedule."""
        config = self.app.state.config
        repositories = self.app.state.repositories
        jetzt = jetzt or self._jetzt()

        verzeichnis = config.pfad(config.app.agenten_verzeichnis)
        for agent in agenten_laden(verzeichnis).values():
            if not agent.zeitplan:
                continue
            termin = letzter_termin(agent.zeitplan, jetzt)
            if self._behandelt.get(agent.name) == termin:
                continue

            start = repositories.auftraege.letzter_start(agent=agent.name)
            if start is not None and _als_aware(start) >= termin:
                # Something already ran since the due time — done (rule 1).
                self._behandelt[agent.name] = termin
                continue

            if repositories.auftraege.laeuft_gerade(agent=agent.name):
                log.info(
                    "Wecker: Termin von '%s' übersprungen — ein Lauf ist noch aktiv",
                    agent.name,
                    extra={"ereignis": "wecker_uebersprungen", "agent": agent.name},
                )
                self._behandelt[agent.name] = termin
                continue

            if wecker_pausiert(repositories, agent):
                log.warning(
                    "Wecker: '%s' pausiert — die letzten %d Läufe sind gescheitert",
                    agent.name,
                    PAUSE_NACH_FEHLSCHLAEGEN,
                    extra={"ereignis": "wecker_pausiert", "agent": agent.name},
                )
                self._behandelt[agent.name] = termin
                continue

            await self._ausloesen(agent, termin)

    async def _ausloesen(self, agent: Agent, termin: datetime) -> None:
        # The import sits here instead of at the top because ``auftraege.py``
        # in turn needs ``wecker_pausiert`` — at the top it would be a cycle.
        from fastapi import HTTPException

        from app.api.abhaengigkeiten import STANDARD_BENUTZER
        from app.api.v1.auftraege import auftrag_anstossen

        config = self.app.state.config
        try:
            auftrag = auftrag_anstossen(
                config=config,
                repositories=self.app.state.repositories,
                discovery=self.app.state.discovery,
                generierungen=self.app.state.generierungen,
                registry=getattr(self.app.state, "werkzeuge", None),
                agent=agent,
                task=agent.zeitplan_auftrag,
                endpoint_id=None,
                user_id=getattr(self.app.state, "standard_benutzer", STANDARD_BENUTZER),
                sprache=config.app.language,
            )
        except HTTPException as fehler:
            # No endpoint available: the due time stays unhandled, the next
            # pass tries again — until the due time is done or superseded
            # by the next one.
            log.warning(
                "Wecker: '%s' nicht gestartet: %s",
                agent.name,
                fehler.detail,
                extra={"ereignis": "wecker_fehlgeschlagen", "agent": agent.name},
            )
            return

        self._behandelt[agent.name] = termin
        log.info(
            "Wecker: '%s' gestartet — Auftrag %s",
            agent.name,
            auftrag.id,
            extra={
                "ereignis": "wecker_gestartet",
                "agent": agent.name,
                "auftrag": auftrag.id,
            },
        )

    # --- Background loop -------------------------------------------------

    async def _schleife(self) -> None:
        while self._laeuft:
            try:
                await self.einmal_pruefen()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - the loop must never die
                log.exception("Wecker-Durchlauf fehlgeschlagen")
            try:
                await asyncio.sleep(PRUEF_ABSTAND_SEKUNDEN)
            except asyncio.CancelledError:
                raise

    async def starten(self) -> None:
        if self._aufgabe is not None:
            return
        self._laeuft = True
        # A first pass right away — that is the catching-up after a
        # restart (rule 1).
        await self.einmal_pruefen()
        self._aufgabe = asyncio.create_task(self._schleife(), name="wecker")
        log.info("Wecker gestartet")

    async def stoppen(self) -> None:
        self._laeuft = False
        if self._aufgabe is None:
            return
        self._aufgabe.cancel()
        try:
            await self._aufgabe
        except asyncio.CancelledError:
            pass
        finally:
            self._aufgabe = None
