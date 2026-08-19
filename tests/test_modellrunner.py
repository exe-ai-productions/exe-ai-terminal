"""The model runner.

No real model server is started here — that would need a binary and several
gigabytes. What is tested is the part that decides: which file may be loaded,
which command comes out of it, and what happens when there is no program to
run at all.

The dangerous one is the folder boundary. A name that is secretly a path
would let anything on the machine be handed to a program that runs for hours.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.modellrunner import Modellrunner, RunnerFehler, modelle_auflisten, programm_finden


@pytest.fixture
def ordner(tmp_path: Path) -> Path:
    (tmp_path / "klein.gguf").write_bytes(b"x" * 2000)
    (tmp_path / "gross.gguf").write_bytes(b"x" * 9000)
    (tmp_path / "keinmodell.txt").write_text("nein")
    return tmp_path


@pytest.fixture
def falsches_programm(tmp_path: Path) -> Path:
    """Something executable that is not a model server."""
    pfad = tmp_path / "llama-server"
    pfad.write_text("#!/bin/sh\nsleep 30\n")
    pfad.chmod(pfad.stat().st_mode | stat.S_IEXEC)
    return pfad


# --- What is in the folder ------------------------------------------------


def test_nur_gguf_zaehlt_als_modell(ordner):
    namen = [m.name for m in modelle_auflisten(ordner)]
    assert namen == ["gross.gguf", "klein.gguf"]


def test_das_groesste_steht_oben(ordner):
    assert modelle_auflisten(ordner)[0].name == "gross.gguf"


def test_ein_ordner_der_nicht_existiert_ist_leer(tmp_path):
    assert modelle_auflisten(tmp_path / "gibtsnicht") == []


# --- The program ----------------------------------------------------------


def test_eine_vorgabe_die_nicht_ausfuehrbar_ist_gilt_nicht(tmp_path):
    pfad = tmp_path / "attrappe"
    pfad.write_text("kein Programm")
    assert programm_finden(str(pfad)) is None


def test_eine_ausfuehrbare_vorgabe_gilt(falsches_programm):
    assert programm_finden(str(falsches_programm)) == falsches_programm


# --- The command ----------------------------------------------------------


def test_der_befehl_zeigt_alles_was_er_tut(ordner, falsches_programm):
    runner = Modellrunner(ordner, str(falsches_programm))
    befehl = runner.befehl("klein.gguf", 4096, 33, 8081)

    assert befehl[0] == str(falsches_programm)
    # Everything the window shows has to be in there, or the window lies.
    assert "--ctx-size" in befehl and "4096" in befehl
    assert "--n-gpu-layers" in befehl and "33" in befehl
    assert "--port" in befehl and "8081" in befehl
    # Never reachable from the network: a model server has no protection of
    # its own, and whoever reaches it can use the whole machine's memory.
    assert befehl[befehl.index("--host") + 1] == "127.0.0.1"


# --- Where it has to refuse -----------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["../draussen.gguf", "unter/tief.gguf", "/etc/passwd", "..%2Fweg.gguf"],
)
def test_ein_name_ist_nie_ein_pfad(ordner, falsches_programm, name):
    runner = Modellrunner(ordner, str(falsches_programm))
    with pytest.raises(RunnerFehler) as fehler:
        runner.starten(name)
    assert fehler.value.grund == "kein_modell"


def test_was_nicht_im_ordner_liegt_startet_nicht(ordner, falsches_programm):
    runner = Modellrunner(ordner, str(falsches_programm))
    with pytest.raises(RunnerFehler) as fehler:
        runner.starten("gibtsnicht.gguf")
    assert fehler.value.grund == "kein_modell"


def test_ohne_programm_geht_nichts(ordner):
    runner = Modellrunner(ordner, "/pfad/den/es/nicht/gibt")
    with pytest.raises(RunnerFehler) as fehler:
        runner.starten("klein.gguf")
    assert fehler.value.grund == "kein_programm"


# --- One at a time --------------------------------------------------------


def test_ein_zweiter_server_wird_abgelehnt(ordner, falsches_programm):
    runner = Modellrunner(ordner, str(falsches_programm))
    # An out-of-the-way port: the default one may be taken by a real server
    # on the developer's machine, and this test is about something else.
    runner.starten("klein.gguf", port=18101)
    try:
        assert runner.laeuft()
        with pytest.raises(RunnerFehler) as fehler:
            runner.starten("gross.gguf", port=18102)
        assert fehler.value.grund == "laeuft_schon"
    finally:
        runner.stoppen()


def test_gestartet_und_wieder_angehalten(ordner, falsches_programm):
    runner = Modellrunner(ordner, str(falsches_programm))
    lauf = runner.starten("klein.gguf", kontext=2048, schichten=10, port=8099)

    assert lauf.modell == "klein.gguf"
    assert lauf.kontext == 2048
    assert runner.lauf() is not None

    assert runner.stoppen() is True
    assert not runner.laeuft()
    assert runner.lauf() is None


def test_anhalten_ohne_lauf_ist_kein_fehler(ordner, falsches_programm):
    runner = Modellrunner(ordner, str(falsches_programm))
    assert runner.stoppen() is False


# --- Several runners side by side -----------------------------------------
#
# Three of these exist now: the chat model, the embedding server and the
# guardian. They share the class and differ in the name of the variable their
# key lives under. Anything that reads the module constant instead of the
# instance field reaches into a sibling's environment.


def test_jeder_runner_raeumt_nur_seinen_eigenen_schluessel_weg(ordner, falsches_programm):
    chat = Modellrunner(ordner, str(falsches_programm))
    waechter = Modellrunner(
        ordner, str(falsches_programm), schluessel_variable="EXE_TEST_ZWEITER_SCHLUESSEL"
    )

    chat.starten("klein.gguf", port=18111)
    waechter.starten("gross.gguf", port=18112)
    try:
        assert os.environ.get("EXE_RUNNER_API_KEY")
        assert os.environ.get("EXE_TEST_ZWEITER_SCHLUESSEL")

        # Stopping the guardian must leave the chat model able to sign its
        # requests; otherwise every answer comes back unauthorised and the
        # endpoint looks dead for a reason nobody can see.
        waechter.stoppen()

        assert os.environ.get("EXE_RUNNER_API_KEY")
        assert "EXE_TEST_ZWEITER_SCHLUESSEL" not in os.environ
    finally:
        chat.stoppen()
        waechter.stoppen()
        os.environ.pop("EXE_TEST_ZWEITER_SCHLUESSEL", None)


def test_der_letzte_runner_raeumt_seinen_schluessel_wirklich_weg(ordner, falsches_programm):
    runner = Modellrunner(ordner, str(falsches_programm))
    runner.starten("klein.gguf", port=18113)
    assert os.environ.get("EXE_RUNNER_API_KEY")
    runner.stoppen()
    assert "EXE_RUNNER_API_KEY" not in os.environ


# --- Vision companions ----------------------------------------------------


def test_ein_projektor_ist_kein_modell(tmp_path):
    ordner = tmp_path / "modelle"
    ordner.mkdir()
    (ordner / "klein.gguf").write_bytes(b"x" * 10)
    (ordner / "vision").mkdir()
    (ordner / "vision" / "klein-mmproj-Q8_0.gguf").write_bytes(b"x" * 5)
    from app.modellrunner import mmproj_auflisten

    assert [m.name for m in modelle_auflisten(ordner)] == ["klein.gguf"]
    assert mmproj_auflisten(ordner) == ["klein-mmproj-Q8_0.gguf"]


def test_der_befehl_haengt_die_passenden_augen_an(ordner, falsches_programm):
    (ordner / "vision").mkdir()
    (ordner / "vision" / "klein-mmproj-Q8_0.gguf").write_bytes(b"x" * 5)
    runner = Modellrunner(ordner, programm=str(falsches_programm))
    befehl = runner.befehl("klein.gguf", 4096, 33, 8081)
    assert "--mmproj" in befehl
    assert befehl[befehl.index("--mmproj") + 1].endswith("klein-mmproj-Q8_0.gguf")


def test_ohne_augen_kein_mmproj(ordner, falsches_programm):
    runner = Modellrunner(ordner, programm=str(falsches_programm))
    assert "--mmproj" not in runner.befehl("klein.gguf", 4096, 33, 8081)


def test_fremde_augen_bleiben_liegen(ordner, falsches_programm):
    # The shared prefix ends before the word mmproj — those are somebody
    # else's eyes, and attaching them would be worse than none.
    (ordner / "vision").mkdir()
    (ordner / "vision" / "anderes-modell-mmproj-BF16.gguf").write_bytes(b"x" * 5)
    (ordner / "vision" / "mmproj-BF16.gguf").write_bytes(b"x" * 5)
    runner = Modellrunner(ordner, programm=str(falsches_programm))
    assert "--mmproj" not in runner.befehl("klein.gguf", 4096, 33, 8081)


def test_von_zwei_paaren_gewinnt_das_laengere(ordner, falsches_programm):
    (ordner / "Qwen3.6-27B-Q4_K_M.gguf").write_bytes(b"x" * 10)
    (ordner / "vision").mkdir()
    (ordner / "vision" / "Qwen3.6-27B-mmproj-BF16.gguf").write_bytes(b"x" * 5)
    (ordner / "vision" / "Qwen3.6-35B-A3B-mmproj-BF16.gguf").write_bytes(b"x" * 5)
    runner = Modellrunner(ordner, programm=str(falsches_programm))
    befehl = runner.befehl("Qwen3.6-27B-Q4_K_M.gguf", 4096, 33, 8081)
    assert befehl[befehl.index("--mmproj") + 1].endswith("Qwen3.6-27B-mmproj-BF16.gguf")


# --- Loose companions get sorted into their own sub-folders ----------------


def test_begleiter_einsortieren_raeumt_flache_dateien_ein(ordner):
    from app.modellrunner import begleiter_einsortieren, mmproj_auflisten, mtp_auflisten

    (ordner / "gross.gguf").write_bytes(b"x" * 10)
    (ordner / "gross-mmproj-F16.gguf").write_bytes(b"x" * 5)
    (ordner / "gross-mtp-Q4.gguf").write_bytes(b"x" * 5)
    begleiter_einsortieren(ordner)

    # The model stays flat; the companions move into their own folders.
    assert (ordner / "gross.gguf").is_file()
    assert not (ordner / "gross-mmproj-F16.gguf").exists()
    assert (ordner / "vision" / "gross-mmproj-F16.gguf").is_file()
    assert (ordner / "mtp" / "gross-mtp-Q4.gguf").is_file()
    modelle = [m.name for m in modelle_auflisten(ordner)]
    assert "gross.gguf" in modelle
    assert "gross-mmproj-F16.gguf" not in modelle and "gross-mtp-Q4.gguf" not in modelle
    assert mmproj_auflisten(ordner) == ["gross-mmproj-F16.gguf"]
    assert [m.name for m in mtp_auflisten(ordner)] == ["gross-mtp-Q4.gguf"]


def test_begleiter_einsortieren_ueberschreibt_kein_belegtes_ziel(ordner):
    from app.modellrunner import begleiter_einsortieren

    (ordner / "vision").mkdir()
    (ordner / "vision" / "x-mmproj.gguf").write_bytes(b"neu")
    (ordner / "x-mmproj.gguf").write_bytes(b"alt")
    begleiter_einsortieren(ordner)

    # Target name taken → the loose file stays put, nothing is overwritten.
    assert (ordner / "x-mmproj.gguf").read_bytes() == b"alt"
    assert (ordner / "vision" / "x-mmproj.gguf").read_bytes() == b"neu"


# --- The folder manifest wins over the name heuristic ----------------------


def test_der_befehl_bevorzugt_das_manifest_gegenueber_der_heuristik(ordner, falsches_programm):
    from app import modellzuordnung

    # The heuristic would tie klein.gguf to its prefix twin; the manifest
    # names a different projector, and the manifest is the one to trust.
    (ordner / "vision").mkdir()
    (ordner / "vision" / "klein-mmproj-Q8_0.gguf").write_bytes(b"x" * 5)
    (ordner / "vision" / "spezial-mmproj.gguf").write_bytes(b"x" * 5)
    modellzuordnung.eintragen(ordner, "klein.gguf", "mmproj", "spezial-mmproj.gguf")

    runner = Modellrunner(ordner, programm=str(falsches_programm))
    befehl = runner.befehl("klein.gguf", 4096, 33, 8081)
    assert befehl[befehl.index("--mmproj") + 1].endswith("spezial-mmproj.gguf")


def test_starten_nimmt_den_mtp_aus_dem_manifest(ordner, falsches_programm, monkeypatch):
    from app import modellzuordnung
    import app.modellrunner as mr

    # A draft declared in the manifest is picked up when the caller passes
    # none, so the bond survives a restart and the command carries it.
    (ordner / "mtp").mkdir()
    (ordner / "mtp" / "klein-mtp-Q8.gguf").write_bytes(b"x" * 5)
    modellzuordnung.eintragen(ordner, "klein.gguf", "mtp", "klein-mtp-Q8.gguf")

    aufgezeichnet = {}
    echtes_popen = mr.subprocess.Popen

    def merken(befehl, *args, **kwargs):
        aufgezeichnet["befehl"] = befehl
        return echtes_popen(befehl, *args, **kwargs)

    monkeypatch.setattr(mr.subprocess, "Popen", merken)

    runner = Modellrunner(ordner, programm=str(falsches_programm))
    try:
        lauf = runner.starten("klein.gguf", port=18097)
        assert lauf.drafter == "klein-mtp-Q8.gguf"
        befehl = aufgezeichnet["befehl"]
        assert befehl[befehl.index("--model-draft") + 1].endswith("klein-mtp-Q8.gguf")
        assert befehl[befehl.index("--spec-type") + 1] == "draft-mtp"
    finally:
        runner.stoppen()


# --- The drafter riding inside the model's own file -------------------------
# The same key llama.cpp itself writes on an architecture that carries its
# own prediction layers — never a name or a repository, only the header.


def _mtp_gguf_bytes() -> bytes:
    schluessel = b"qwen35moe.nextn_predict_layers"
    kopf = bytearray(b"GGUF")
    kopf += (3).to_bytes(4, "little")  # version
    kopf += (0).to_bytes(8, "little")  # tensor count
    kopf += (1).to_bytes(8, "little")  # one metadata pair
    kopf += len(schluessel).to_bytes(8, "little") + schluessel
    kopf += (4).to_bytes(4, "little")  # value type: u32
    kopf += (1).to_bytes(4, "little")  # one embedded prediction layer
    return bytes(kopf)


def _echtes_aber_gewoehnliches_gguf_bytes() -> bytes:
    schluessel = b"general.architecture"
    wert = b"qwen35moe"
    kopf = bytearray(b"GGUF")
    kopf += (3).to_bytes(4, "little")
    kopf += (0).to_bytes(8, "little")
    kopf += (1).to_bytes(8, "little")
    kopf += len(schluessel).to_bytes(8, "little") + schluessel
    kopf += (8).to_bytes(4, "little")  # value type: string
    kopf += len(wert).to_bytes(8, "little") + wert
    return bytes(kopf)


def test_der_befehl_setzt_spec_type_fuer_eingebettetes_mtp_ohne_drafter(ordner, falsches_programm):
    (ordner / "mtp-modell.gguf").write_bytes(_mtp_gguf_bytes())
    runner = Modellrunner(ordner, str(falsches_programm))
    befehl = runner.befehl("mtp-modell.gguf", 4096, 33, 8081)
    assert befehl[befehl.index("--spec-type") + 1] == "draft-mtp"
    assert "--model-draft" not in befehl


def test_der_befehl_laesst_ein_modell_ohne_das_merkmal_unangetastet(ordner, falsches_programm):
    (ordner / "normal.gguf").write_bytes(_echtes_aber_gewoehnliches_gguf_bytes())
    runner = Modellrunner(ordner, str(falsches_programm))
    befehl = runner.befehl("normal.gguf", 4096, 33, 8081)
    assert "--spec-type" not in befehl


def test_ein_gewaehlter_drafter_gewinnt_gegen_das_eingebettete_merkmal(ordner, falsches_programm):
    # The main model's own header carries the marker too — the caller's
    # explicit choice must still be the only one that is obeyed, and the
    # flag must appear exactly once.
    (ordner / "mtp-modell.gguf").write_bytes(_mtp_gguf_bytes())
    (ordner / "mtp").mkdir()
    (ordner / "mtp" / "klein-mtp-Q8.gguf").write_bytes(b"x" * 5)
    runner = Modellrunner(ordner, str(falsches_programm))
    befehl = runner.befehl("mtp-modell.gguf", 4096, 33, 8081, drafter="klein-mtp-Q8.gguf")
    assert befehl[befehl.index("--model-draft") + 1].endswith("klein-mtp-Q8.gguf")
    assert befehl.count("--spec-type") == 1
    assert befehl[befehl.index("--spec-type") + 1] == "draft-mtp"


def test_starten_erkennt_eingebettetes_mtp_fuer_den_blitz(ordner, falsches_programm):
    (ordner / "mtp-modell.gguf").write_bytes(_mtp_gguf_bytes())
    runner = Modellrunner(ordner, programm=str(falsches_programm))
    try:
        lauf = runner.starten("mtp-modell.gguf", port=18098)
        # No companion file exists — the bolt's proof comes from the log,
        # not from a drafter name that was never there to begin with.
        assert lauf.drafter is None
        assert runner._drafter_gewuenscht is True
    finally:
        runner.stoppen()


def test_starten_ohne_das_merkmal_erwartet_keinen_drafter(ordner, falsches_programm):
    (ordner / "normal.gguf").write_bytes(_echtes_aber_gewoehnliches_gguf_bytes())
    runner = Modellrunner(ordner, programm=str(falsches_programm))
    try:
        runner.starten("normal.gguf", port=18100)
        assert runner._drafter_gewuenscht is False
    finally:
        runner.stoppen()


# --- The orphan after a service restart ------------------------------------


def test_der_start_merkt_sich_die_pid(ordner, falsches_programm):
    from app.modellrunner import PID_DATEI
    import json

    runner = Modellrunner(ordner, programm=str(falsches_programm))
    lauf = runner.starten("klein.gguf", port=18099)
    assert lauf is not None
    notiz = json.loads((ordner / PID_DATEI).read_text())
    assert notiz["pid"] == runner._prozess.pid
    runner.stoppen()
    assert not (ordner / PID_DATEI).exists()


def test_aufraeumen_beendet_nur_echte_server(ordner):
    from app.modellrunner import PID_DATEI
    import json, subprocess

    schlaefer = subprocess.Popen(["sleep", "30"], start_new_session=True)
    (ordner / PID_DATEI).write_text(json.dumps({"pid": schlaefer.pid}))
    runner = Modellrunner(ordner)

    # Somebody else's process id: the note goes, the process stays.
    assert runner.aufraeumen(ist_unserer=lambda pid: False) is False
    assert not (ordner / PID_DATEI).exists()
    assert schlaefer.poll() is None

    # Our own kind: it gets ended.
    (ordner / PID_DATEI).write_text(json.dumps({"pid": schlaefer.pid}))
    assert runner.aufraeumen(ist_unserer=lambda pid: True) is True
    schlaefer.wait(timeout=5)


def test_aufraeumen_ohne_notiz_ist_still(ordner):
    assert Modellrunner(ordner).aufraeumen() is False


def test_ein_belegter_port_faellt_sofort_auf(ordner, falsches_programm):
    import socket

    with socket.socket() as belegt:
        belegt.bind(("127.0.0.1", 0))
        belegt.listen(1)
        port = belegt.getsockname()[1]
        runner = Modellrunner(ordner, programm=str(falsches_programm))
        try:
            runner.starten("klein.gguf", port=port)
            raise AssertionError("kein Fehler")
        except RunnerFehler as fehler:
            assert fehler.grund == "port_belegt"


# --- Reading flash attention's true state off the log ----------------------


class _LaufenderProzess:
    """A stand-in for a live server process: the log-reading tests never spawn
    a real one, but the state methods now gate on ``laeuft()`` — the log flags
    survive a stopped process, the reported state must not — so a runner under
    test must count as running for its log lines to be read at all."""

    pid = 0

    def poll(self):
        return None


def test_flash_attn_zustand_ohne_protokoll_ist_unbekannt(ordner):
    assert Modellrunner(ordner).flash_attn_zustand() is None


def test_flash_attn_zustand_liest_die_eigene_zeile_des_servers(ordner):
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._zeile_aufnehmen("llama_context: n_ctx     = 32768")
    runner._zeile_aufnehmen("llama_context: flash_attn    = enabled")
    assert runner.flash_attn_zustand() is True


def test_flash_attn_zustand_nimmt_die_letzte_zeile(ordner):
    """A second load in the same process — reload, restart — must not answer
    with the first one's word once a newer line disagrees with it."""
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._zeile_aufnehmen("llama_context: flash_attn    = enabled")
    runner._zeile_aufnehmen("llama_context: flash_attn    = disabled")
    assert runner.flash_attn_zustand() is False


def test_flash_attn_zustand_ignoriert_fremde_zeilen(ordner):
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._zeile_aufnehmen("srv  params_from_: some other line entirely")
    assert runner.flash_attn_zustand() is None


def test_flash_attn_zustand_ueberlebt_den_vollen_ringpuffer(ordner):
    """The load-time line is written once; a busy server then pushes it out
    of the 400-line ring buffer. The answer must survive that."""
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._zeile_aufnehmen("llama_context: flash_attn    = enabled")
    for n in range(500):
        runner._zeile_aufnehmen(f"srv  log: request {n}")
    assert runner.flash_attn_zustand() is True


def test_flash_attn_zustand_ist_none_wenn_server_aus(ordner):
    """The load-time line stays in the buffer after the process dies; the
    reported state must not. A server that is no longer running answers
    "unknown", not the word it printed while it was up."""
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._zeile_aufnehmen("llama_context: flash_attn    = enabled")
    assert runner.flash_attn_zustand() is True
    runner._prozess = None
    assert runner.flash_attn_zustand() is None


# --- The drafter's honest state (MTP), read off the same log --------------
# The two lines below are the real ones a llama-server (build 10310) prints:
# the speculative-init line comes BEFORE "model loaded", so a "model loaded"
# without it means the drafter was set but never engaged.
_MTP_ZEILE = "0.00.886 I common_speculative_init_result: loading draft model 'm.gguf'"
_BEREIT_ZEILE = "0.01.084 I srv  llama_server: model loaded"


def test_mtp_ohne_drafter_ist_nichts(ordner):
    """No drafter asked for → nothing to show, whatever the log says."""
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._zeile_aufnehmen(_BEREIT_ZEILE)
    assert runner.mtp_zustand() is None


def test_mtp_aktiv_wenn_die_speculative_zeile_kam(ordner):
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._drafter_gewuenscht = True
    runner._zeile_aufnehmen(_MTP_ZEILE)
    runner._zeile_aufnehmen(_BEREIT_ZEILE)
    assert runner.mtp_zustand() == "aktiv"


def test_mtp_fehler_wenn_server_hochkam_ohne_die_zeile(ordner):
    """Drafter configured, server reached "model loaded", but the speculative
    line never appeared — the pairing did not take."""
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._drafter_gewuenscht = True
    runner._zeile_aufnehmen(_BEREIT_ZEILE)
    assert runner.mtp_zustand() == "fehler"


def test_mtp_laedt_noch_ist_nichts(ordner):
    """Drafter configured but the server has not reached ready yet: grey, not
    a premature red."""
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._drafter_gewuenscht = True
    assert runner.mtp_zustand() is None


def test_mtp_zustand_ueberlebt_den_vollen_ringpuffer(ordner):
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._drafter_gewuenscht = True
    runner._zeile_aufnehmen(_MTP_ZEILE)
    runner._zeile_aufnehmen(_BEREIT_ZEILE)
    for n in range(500):
        runner._zeile_aufnehmen(f"srv  log: request {n}")
    assert runner.mtp_zustand() == "aktiv"


def test_mtp_zustand_ist_none_wenn_server_aus(ordner):
    """The same liveness rule for the drafter: once the process is gone the
    bolt goes grey, even though the speculative line is still in the buffer."""
    runner = Modellrunner(ordner)
    runner._prozess = _LaufenderProzess()
    runner._drafter_gewuenscht = True
    runner._zeile_aufnehmen(_MTP_ZEILE)
    runner._zeile_aufnehmen(_BEREIT_ZEILE)
    assert runner.mtp_zustand() == "aktiv"
    runner._prozess = None
    assert runner.mtp_zustand() is None
