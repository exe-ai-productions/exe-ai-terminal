"""What a command leaves behind: a folder, live lines, a background result.

Three promises are checked here, and each of them broke something real when
it was missing:

* a `cd` reaches the next call — but only inside the shared folders, because
  otherwise a chat could walk itself out of its permission,
* every line is announced while the command runs, not at the end,
* a background call returns at once and its result finds its way back.
"""

from __future__ import annotations

import asyncio

import pytest

from app.tools import hintergrund, ordnergedaechtnis, shell


@pytest.fixture(autouse=True)
def sauber():
    ordnergedaechtnis.vergessen()
    hintergrund.laeufe._laeufe.clear()
    hintergrund.laeufe.abschluss = None
    yield
    ordnergedaechtnis.vergessen()
    hintergrund.laeufe._laeufe.clear()
    hintergrund.laeufe.abschluss = None


@pytest.fixture()
def ordner(tmp_path):
    (tmp_path / "unterordner").mkdir()
    return [str(tmp_path)]


# --- The remembered folder -------------------------------------------------


@pytest.mark.asyncio
async def test_ein_cd_wirkt_im_naechsten_aufruf(ordner, tmp_path):
    await shell.ausfuehren({"command": "cd unterordner"}, ordner, "chat-1")
    antwort = await shell.ausfuehren({"command": "pwd"}, ordner, "chat-1")
    assert str((tmp_path / "unterordner").resolve()) in antwort


@pytest.mark.asyncio
async def test_ein_cd_gehoert_nur_seinem_chat(ordner, tmp_path):
    await shell.ausfuehren({"command": "cd unterordner"}, ordner, "chat-1")
    antwort = await shell.ausfuehren({"command": "pwd"}, ordner, "chat-2")
    assert antwort.strip().endswith(str(tmp_path.resolve()))


@pytest.mark.asyncio
async def test_ein_cd_nach_draussen_wird_nicht_gemerkt(ordner, tmp_path):
    await shell.ausfuehren({"command": "cd /tmp"}, ordner, "chat-1")
    antwort = await shell.ausfuehren({"command": "pwd"}, ordner, "chat-1")
    assert antwort.strip().endswith(str(tmp_path.resolve()))


@pytest.mark.asyncio
async def test_die_ordnermarke_steht_nicht_in_der_ausgabe(ordner):
    antwort = await shell.ausfuehren({"command": "echo hallo"}, ordner, "chat-1")
    assert antwort == "hallo"
    assert shell.MARKE not in antwort


# --- Live output -----------------------------------------------------------


@pytest.mark.asyncio
async def test_jede_zeile_wird_gemeldet(ordner):
    gesehen = []

    async def zuschauen():
        async for ereignis in hintergrund.laeufe.zuschauen("chat-1"):
            gesehen.append(ereignis)

    zuschauer = asyncio.ensure_future(zuschauen())
    await asyncio.sleep(0)
    await shell.ausfuehren({"command": "printf 'eins\\nzwei\\n'"}, ordner, "chat-1")
    await asyncio.sleep(0.05)
    zuschauer.cancel()

    arten = [e["typ"] for e in gesehen]
    assert arten[0] == "lauf_start"
    assert arten[-1] == "lauf_ende"
    assert [e["text"] for e in gesehen if e["typ"] == "lauf_zeile"] == ["eins", "zwei"]


@pytest.mark.asyncio
async def test_der_lauf_kennt_seinen_ausgang(ordner):
    await shell.ausfuehren({"command": "exit 3"}, ordner, "chat-1")
    lauf = hintergrund.laeufe.holen("chat-1", 1)
    assert lauf.zustand == hintergrund.FEHLER
    assert lauf.code == 3


# --- Background ------------------------------------------------------------


@pytest.mark.asyncio
async def test_hintergrund_kehrt_sofort_zurueck_und_meldet_sich_spaeter(ordner, tmp_path):
    fertig: list[tuple] = []
    hintergrund.laeufe.abschluss = lambda lauf, antwort: fertig.append((lauf, antwort))

    antwort = await shell.ausfuehren(
        {"command": "sleep 0.2 ; echo spaet", "background": True}, ordner, "chat-1"
    )
    assert "run #1" in antwort
    assert "spaet" not in antwort

    for _ in range(60):
        if fertig:
            break
        await asyncio.sleep(0.05)
    assert fertig, "der Hintergrundlauf hat sich nie gemeldet"
    lauf, ergebnis = fertig[0]
    assert lauf.hintergrund is True
    assert "spaet" in ergebnis


@pytest.mark.asyncio
async def test_alles_wird_beim_herunterfahren_getoetet(ordner):
    await shell.ausfuehren({"command": "sleep 30", "background": True}, ordner, "chat-1")
    assert hintergrund.laeufe.alle_toeten() == 1
    assert hintergrund.laeufe.holen("chat-1", 1).zustand == hintergrund.FEHLER
    # Let the killed run finish tidying up before the loop goes away.
    await asyncio.sleep(0.1)


# --- The window's route ----------------------------------------------------


def test_die_laeufe_eines_chats_stehen_im_netz(client):
    """The window asks once for what already ran; the stream carries only
    what happens from then on."""
    lauf = hintergrund.laeufe.anlegen("chat-9", "echo hallo")
    hintergrund.laeufe.zeile(lauf, "hallo")
    hintergrund.laeufe.beenden(lauf, 0)

    antwort = client.get("/api/v1/laeufe/chat-9")
    assert antwort.status_code == 200
    eintraege = antwort.json()
    assert len(eintraege) == 1
    # The duration is measured, so it is checked for being there rather than
    # for being a particular number.
    dauer = eintraege[0].pop("dauer_sekunden")
    assert dauer is not None and dauer >= 0
    assert eintraege == [
        {
            "lauf": 1,
            "befehl": "echo hallo",
            "hintergrund": False,
            "zustand": "fertig",
            "code": 0,
            "ausgabe": "hallo",
            "art": "befehl",
        }
    ]


# --- The buffer ------------------------------------------------------------


def test_der_puffer_behaelt_beide_enden():
    lauf = hintergrund.Lauf(nummer=1, chat_id="chat-1", befehl="x")
    zeile = "y" * 1000
    for nummer in range(400):
        lauf.anhaengen(f"{nummer:04} {zeile}")
    text = lauf.ausgabe
    assert len(text) <= hintergrund.MAX_PUFFER_ZEICHEN + 200
    assert text.startswith("0000 ")
    assert text.rstrip().endswith(f"0399 {zeile}")
    assert "cut out of the middle" in text
