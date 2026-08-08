"""6.1 — the run outlives the request.

Two kinds of test, deliberately separated:

* The **manager** on its own, without HTTP. That's where we can check what
  happens in memory — catch-up reads, live streaming, two watchers, the
  read counter.
* The **whole chain** against a real uvicorn. Only there can we verify that
  a run really survives a dropped connection; the ASGI test transport
  collects the entire response first and never sees a disconnect at all.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.generationen import Generierungsverwaltung
from app.providers import MockProvider, mock_endpunkt


# --- The manager on its own ----------------------------------------------


@pytest.mark.asyncio
async def test_lauf_laeuft_ohne_zuschauer_zu_ende():
    """The heart of 6.1: nobody is watching, yet it happens anyway."""
    verwaltung = Generierungsverwaltung()

    async def arbeit(lauf):
        for i in range(3):
            lauf.melden(f"zeile{i}")
            await asyncio.sleep(0)

    lauf = verwaltung.starten(
        chat_id="c", endpoint_id="e", arbeit=arbeit, an_verbindung_gebunden=False
    )
    await asyncio.wait_for(lauf.fertig.wait(), timeout=2)
    assert lauf.ereignisse == ["zeile0", "zeile1", "zeile2"]


@pytest.mark.asyncio
async def test_spaeter_zuschauer_bekommt_erst_das_versaeumte_dann_live():
    verwaltung = Generierungsverwaltung()
    weiter = asyncio.Event()

    async def arbeit(lauf):
        lauf.melden("a")
        lauf.melden("b")
        await weiter.wait()
        lauf.melden("c")

    lauf = verwaltung.starten(chat_id="c", endpoint_id="e", arbeit=arbeit)
    # Wait until the first two are actually in.
    while len(lauf.ereignisse) < 2:
        await asyncio.sleep(0)

    gelesen: list[str] = []

    async def zusehen():
        async for zeile in lauf.zuschauen():
            gelesen.append(zeile)

    beobachter = asyncio.create_task(zusehen())
    await asyncio.sleep(0)
    # The missed events arrive before anything new happens at all.
    assert gelesen == ["a", "b"]

    weiter.set()
    await asyncio.wait_for(beobachter, timeout=2)
    assert gelesen == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_zaehlstand_ueberspringt_was_schon_gelesen_wurde():
    """Whoever lost the connection picks up right where they left off."""
    verwaltung = Generierungsverwaltung()

    async def arbeit(lauf):
        for i in range(4):
            lauf.melden(f"z{i}")

    lauf = verwaltung.starten(chat_id="c", endpoint_id="e", arbeit=arbeit)
    await asyncio.wait_for(lauf.fertig.wait(), timeout=2)

    gelesen = [zeile async for zeile in lauf.zuschauen(ab=2)]
    assert gelesen == ["z2", "z3"]


@pytest.mark.asyncio
async def test_zwei_zuschauer_sehen_dasselbe():
    verwaltung = Generierungsverwaltung()
    weiter = asyncio.Event()

    async def arbeit(lauf):
        lauf.melden("eins")
        await weiter.wait()
        lauf.melden("zwei")

    lauf = verwaltung.starten(chat_id="c", endpoint_id="e", arbeit=arbeit)
    while not lauf.ereignisse:
        await asyncio.sleep(0)

    async def sammeln():
        return [zeile async for zeile in lauf.zuschauen()]

    a = asyncio.create_task(sammeln())
    b = asyncio.create_task(sammeln())
    await asyncio.sleep(0)
    weiter.set()

    assert await asyncio.wait_for(a, timeout=2) == ["eins", "zwei"]
    assert await asyncio.wait_for(b, timeout=2) == ["eins", "zwei"]


@pytest.mark.asyncio
async def test_fertiger_lauf_bleibt_eine_weile_nachlesbar():
    """Whoever looks only shortly after the end still sees the whole thing."""
    verwaltung = Generierungsverwaltung()

    async def arbeit(lauf):
        lauf.melden("fertig geworden")

    lauf = verwaltung.starten(chat_id="c", endpoint_id="e", arbeit=arbeit)
    await asyncio.wait_for(lauf.fertig.wait(), timeout=2)
    verwaltung.abmelden(lauf.id)

    wiedergefunden = verwaltung.holen(lauf.id)
    assert wiedergefunden is not None
    assert [z async for z in wiedergefunden.zuschauen()] == ["fertig geworden"]


@pytest.mark.asyncio
async def test_ein_gescheiterter_lauf_reisst_den_dienst_nicht_mit():
    verwaltung = Generierungsverwaltung()

    async def arbeit(lauf):
        lauf.melden("bis hierhin")
        raise RuntimeError("kaputt")

    lauf = verwaltung.starten(chat_id="c", endpoint_id="e", arbeit=arbeit)
    await asyncio.wait_for(lauf.fertig.wait(), timeout=2)
    assert lauf.ereignisse == ["bis hierhin"]
    # The task finished cleanly and was not left dangling.
    assert lauf.aufgabe.done() and lauf.aufgabe.exception() is None


# --- The whole chain against a real server -------------------------------


def _ereignisse(zeilen: list[str]) -> list[dict]:
    return [json.loads(z[5:].strip()) for z in zeilen if z.startswith("data:")]


@pytest.mark.asyncio
async def test_ein_zuschauer_sieht_einer_laufenden_antwort_zu(laufender_server):
    """The second connection: attach, read along, and break nothing."""
    import httpx

    app, basis = laufender_server
    zustand = app.state.discovery.zustaende["test"]
    zustand.provider = MockProvider(
        mock_endpunkt("test"), haeppchen=[f"T{i} " for i in range(20)], verzoegerung=0.05
    )
    zustand.erreichbar = True

    async with httpx.AsyncClient(base_url=basis, timeout=30) as client:
        chat_id = (await client.post("/api/v1/chats", json={"title": "Zusehen"})).json()["id"]

        vom_besitzer: list[str] = []
        vom_zuschauer: list[str] = []
        generation_id = None

        async def zuschauen(kennung: str):
            async with client.stream("GET", f"/api/v1/chat/stream/{kennung}") as antwort:
                assert antwort.status_code == 200
                async for zeile in antwort.aiter_lines():
                    vom_zuschauer.append(zeile)

        beobachter = None
        async with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json={"chat_id": chat_id, "endpoint_id": "test", "content": "Los"},
        ) as antwort:
            async for zeile in antwort.aiter_lines():
                vom_besitzer.append(zeile)
                if not zeile.startswith("data:"):
                    continue
                ereignis = json.loads(zeile[5:].strip())
                if ereignis["typ"] == "start" and beobachter is None:
                    generation_id = ereignis["generation_id"]
                    beobachter = asyncio.create_task(zuschauen(generation_id))

        await asyncio.wait_for(beobachter, timeout=10)

    besitzer = _ereignisse(vom_besitzer)
    zuschauer = _ereignisse(vom_zuschauer)

    # The watcher read from the start — including what happened before it joined.
    assert zuschauer[0]["typ"] == "start"
    assert zuschauer[-1]["typ"] == "done"
    # And it saw exactly the same thing as the owner.
    assert zuschauer == besitzer
    # The watcher cancelled nothing.
    assert besitzer[-1]["abgebrochen"] is False


@pytest.mark.asyncio
async def test_ungebundener_lauf_ueberlebt_die_weggefallene_verbindung(laufender_server):
    """The actual proof for 6.1.

    A chat is cancelled when the browser closes — that should stay that way
    and is checked further down. A job must not be. Here a run is started
    without a binding, the watcher leaves in the middle, and the run still
    has to finish.
    """
    import httpx

    app, basis = laufender_server
    verwaltung = app.state.generierungen
    schritte = 12

    async def arbeit(lauf):
        for i in range(schritte):
            lauf.melden(f'data: {{"typ": "content", "text": "S{i}"}}\n\n')
            await asyncio.sleep(0.05)

    lauf = verwaltung.starten(
        chat_id="egal", endpoint_id="test", arbeit=arbeit, an_verbindung_gebunden=False
    )

    # Watch and drop out in the middle — just like a closing browser does.
    gesehen = 0
    async with httpx.AsyncClient(base_url=basis, timeout=30) as client:
        async with client.stream("GET", f"/api/v1/chat/stream/{lauf.id}") as antwort:
            async for _ in antwort.aiter_lines():
                gesehen += 1
                if gesehen >= 4:
                    break

    assert gesehen < schritte, "zu früh fertig, der Test würde nichts zeigen"
    assert not lauf.fertig.is_set(), "Lauf war schon durch, bevor die Verbindung fiel"

    # And now the crucial part: it keeps going without a watcher.
    await asyncio.wait_for(lauf.fertig.wait(), timeout=10)
    assert len(lauf.ereignisse) == schritte

    # Attaching afterwards delivers the full state.
    async with httpx.AsyncClient(base_url=basis, timeout=30) as client:
        antwort = await client.get(f"/api/v1/chat/stream/{lauf.id}")
        assert antwort.text.count("data:") == schritte


@pytest.mark.asyncio
async def test_chat_bricht_weiter_ab_wenn_der_browser_zugeht(laufender_server):
    """The old behavior must stay: no GPU heating without a watcher."""
    import httpx

    app, basis = laufender_server
    provider = MockProvider(
        mock_endpunkt("test"), haeppchen=[f"T{i} " for i in range(60)], verzoegerung=0.05
    )
    zustand = app.state.discovery.zustaende["test"]
    zustand.provider = provider
    zustand.erreichbar = True

    async with httpx.AsyncClient(base_url=basis, timeout=30) as client:
        chat_id = (await client.post("/api/v1/chats", json={"title": "Zu"})).json()["id"]

        gelesen = 0
        async with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json={"chat_id": chat_id, "endpoint_id": "test", "content": "Los"},
        ) as antwort:
            async for zeile in antwort.aiter_lines():
                if zeile.startswith("data:"):
                    gelesen += 1
                if gelesen >= 4:
                    break

        # The watchdog checks every half second — give it time.
        for _ in range(40):
            if provider.abgebrochen:
                break
            await asyncio.sleep(0.1)

    assert provider.abgebrochen is True, "der Lauf lief ohne Zuschauer weiter"
    assert provider.ausgegebene_haeppchen < 60


@pytest.mark.asyncio
async def test_unbekannter_lauf_gibt_404(laufender_server):
    import httpx

    _, basis = laufender_server
    async with httpx.AsyncClient(base_url=basis, timeout=10) as client:
        assert (await client.get("/api/v1/chat/stream/gibtesnicht")).status_code == 404
