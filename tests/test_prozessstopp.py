"""Ending a process together with everything it spawned.

Two things are tested here that a single machine cannot show on its own: that
the POSIX path really reaches the whole group, and that the Windows path is
taken at all. The second one matters most — the Windows branch used to be
missing entirely, and reaching for `os.killpg` there raises AttributeError, so
the stop button did nothing while the process kept running.
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from app import prozessstopp


@pytest.fixture
def schlaefer():
    """A process that will not end on its own within the test."""
    prozess = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
    )
    yield prozess
    if prozess.poll() is None:
        prozess.kill()
        prozess.wait(timeout=5)


# --- The living process ---------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX groups")
def test_ein_laufender_prozess_wird_beendet(schlaefer):
    prozessstopp.beenden(schlaefer, frist=5)
    assert schlaefer.poll() is not None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX groups")
def test_die_kinder_gehen_mit(tmp_path):
    """A signal to the parent alone would leave the child holding the port."""
    marke = tmp_path / "kind.pid"
    eltern = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess, sys, pathlib; "
            f"k = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
            f"pathlib.Path({str(marke)!r}).write_text(str(k.pid)); "
            "import time; time.sleep(30)",
        ],
        start_new_session=True,
    )
    for _ in range(50):
        if marke.exists():
            break
        time.sleep(0.1)
    kind_pid = int(marke.read_text())

    prozessstopp.beenden(eltern, frist=5)

    # The child is gone too, or at least no longer signalable as itself.
    time.sleep(0.3)
    with pytest.raises(OSError):
        import os

        os.kill(kind_pid, 0)


def test_ein_toter_prozess_ist_kein_fehler(schlaefer):
    schlaefer.kill()
    schlaefer.wait(timeout=5)
    prozessstopp.beenden(schlaefer, frist=1)


def test_eine_unbekannte_nummer_meldet_sich_ehrlich():
    # An id that cannot belong to anything: the call says no, it does not raise.
    assert prozessstopp.beenden_nach_pid(2**31 - 1) is False


# --- The Windows path -----------------------------------------------------
#
# It cannot be run here, but it can be shown that it is taken, and that the
# old code would have crashed instead.


def test_unter_windows_wird_taskkill_genommen(monkeypatch):
    gerufen = {}

    def falsches_run(befehl, **kwargs):
        gerufen["befehl"] = befehl

        class Ergebnis:
            returncode = 0

        return Ergebnis()

    monkeypatch.setattr(prozessstopp, "WINDOWS", True)
    monkeypatch.setattr(prozessstopp.subprocess, "run", falsches_run)

    assert prozessstopp.beenden_nach_pid(4242) is True
    assert gerufen["befehl"][0] == "taskkill"
    # /T is the part that walks the children — without it this is the same
    # half-stop the POSIX path avoids with its group.
    assert "/T" in gerufen["befehl"]
    assert "4242" in gerufen["befehl"]


def test_unter_windows_meldet_ein_leerer_treffer_kein_erfolg(monkeypatch):
    def falsches_run(befehl, **kwargs):
        class Ergebnis:
            returncode = 128

        return Ergebnis()

    monkeypatch.setattr(prozessstopp, "WINDOWS", True)
    monkeypatch.setattr(prozessstopp.subprocess, "run", falsches_run)

    assert prozessstopp.beenden_nach_pid(4242) is False


def test_unter_windows_faellt_der_stopp_nicht_um(monkeypatch):
    """The regression: os.killpg does not exist there and used to raise."""

    def falsches_run(befehl, **kwargs):
        class Ergebnis:
            returncode = 0

        return Ergebnis()

    monkeypatch.setattr(prozessstopp, "WINDOWS", True)
    monkeypatch.setattr(prozessstopp.subprocess, "run", falsches_run)

    class Lebt:
        pid = 4242

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    prozessstopp.beenden(Lebt(), frist=1)
