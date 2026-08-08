"""Event system: delivery, decoupling, fault tolerance."""

from __future__ import annotations

import pytest

from app.events import Ereignisse, EventBus


@pytest.mark.asyncio
async def test_handler_wird_aufgerufen():
    bus = EventBus()
    empfangen = []

    async def handler(**daten):
        empfangen.append(daten)

    bus.abonnieren(Ereignisse.CHAT_ERSTELLT, handler)
    await bus.veroeffentlichen(Ereignisse.CHAT_ERSTELLT, chat_id="abc")

    assert empfangen == [{"chat_id": "abc"}]


@pytest.mark.asyncio
async def test_synchroner_handler_funktioniert_auch():
    bus = EventBus()
    empfangen = []

    def handler(**daten):
        empfangen.append(daten)

    bus.abonnieren("test", handler)
    await bus.veroeffentlichen("test", wert=1)

    assert empfangen == [{"wert": 1}]


@pytest.mark.asyncio
async def test_mehrere_abonnenten_bekommen_alle_das_ereignis():
    bus = EventBus()
    zaehler = []

    for nummer in range(3):
        bus.abonnieren("test", lambda nummer=nummer, **_: zaehler.append(nummer))

    await bus.veroeffentlichen("test")
    assert sorted(zaehler) == [0, 1, 2]


@pytest.mark.asyncio
async def test_defekter_handler_blockiert_die_anderen_nicht():
    bus = EventBus()
    erfolgreich = []

    def kaputt(**_):
        raise RuntimeError("absichtlich")

    bus.abonnieren("test", kaputt)
    bus.abonnieren("test", lambda **_: erfolgreich.append(True))

    await bus.veroeffentlichen("test")  # must not raise
    assert erfolgreich == [True]


@pytest.mark.asyncio
async def test_abbestellen_wirkt():
    bus = EventBus()
    empfangen = []

    def handler(**_):
        empfangen.append(True)

    bus.abonnieren("test", handler)
    bus.abbestellen("test", handler)
    await bus.veroeffentlichen("test")

    assert empfangen == []


@pytest.mark.asyncio
async def test_ereignis_ohne_abonnenten_ist_harmlos():
    bus = EventBus()
    await bus.veroeffentlichen("niemand_hoert_zu", wert=1)
