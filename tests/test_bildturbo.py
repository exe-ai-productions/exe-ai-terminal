"""Image-Turbo: the persistent picture server's guards, not its pictures.

The drawing itself is proved by running it; here we test the switch logic and
the state machine that the plus-menu plaque colours itself by.
"""

from __future__ import annotations

from pathlib import Path

from app.bildturbo import Bildturbo, programm_finden
from app.api.v1.bild import _turbo_auftrag
from app.bildrunner import Auftrag, LoRA


def test_ohne_prozess_ist_der_zustand_aus(tmp_path: Path):
    assert Bildturbo(tmp_path).zustand() == "aus"


def test_ohne_server_binary_kein_programm(tmp_path: Path):
    assert programm_finden(tmp_path) is None
    assert Bildturbo(tmp_path).programm is None


def test_das_binary_wird_im_build_ordner_gefunden(tmp_path: Path):
    import os
    build = tmp_path / "stable-diffusion.cpp" / "master-1"
    build.mkdir(parents=True)
    prog = build / "sd-server"
    prog.write_text("#!/bin/sh\n")
    prog.chmod(0o755)
    gefunden = programm_finden(tmp_path)
    assert gefunden is not None and gefunden.name == "sd-server"
    assert os.access(gefunden, os.X_OK)


def test_der_turbo_body_traegt_nur_die_basis():
    """Image-Turbo speaks the basic A1111 body; the extras never reach it —
    a request with them takes the sd-cli path instead."""
    auftrag = Auftrag(
        modell=Path("/m.safetensors"), prompt="ein Leuchtturm", negativ="unscharf",
        breite=1024, hoehe=1024, schritte=28, cfg=6.5, seed=42,
        sampler="euler_a", scheduler="karras",
    )
    body = _turbo_auftrag(auftrag)
    assert body == {
        "prompt": "ein Leuchtturm",
        "width": 1024, "height": 1024, "steps": 28,
        "cfg_scale": 6.5, "seed": 42, "sampler_name": "euler_a",
        "negative_prompt": "unscharf", "scheduler": "karras",
    }


def test_der_turbo_body_laesst_leeren_negativ_und_scheduler_weg():
    auftrag = Auftrag(modell=Path("/m.safetensors"), prompt="x", scheduler="")
    body = _turbo_auftrag(auftrag)
    assert "negative_prompt" not in body
    assert "scheduler" not in body


def test_der_turbo_body_traegt_die_loras_im_prompt():
    """A LoRA is not a body field for this server either — it rides in the
    prompt in WebUI syntax, exactly as the sd-cli path writes it, so the server
    resolves it against its --lora-model-dir."""
    auftrag = Auftrag(
        modell=Path("/m.safetensors"), prompt="a lighthouse",
        loras=(LoRA(name="Hyper-SD15.safetensors", staerke=0.7),
               LoRA(name="detail.safetensors", staerke=0.5)),
    )
    body = _turbo_auftrag(auftrag)
    assert body["prompt"] == "a lighthouse <lora:Hyper-SD15:0.7> <lora:detail:0.5>"


def test_gespann_passt_nur_bei_gleichem_modell_vae_und_detektor(tmp_path: Path):
    """passt_zu is the whole switch: a running server draws the picture only
    when model, VAE and detector all match. A stopped server never matches."""
    turbo = Bildturbo(tmp_path)
    # Nothing running — nothing matches, whatever is asked for.
    assert turbo.passt_zu("m.safetensors") is False
    # Pretend a server is up on a specific Gespann.
    turbo._prozess = _LebtImmer()
    turbo._modell = "m.safetensors"
    turbo._vae = "vae.safetensors"
    turbo._ad_modell = "face.pt"
    turbo._ad_prompt = ""
    assert turbo.passt_zu("m.safetensors", "vae.safetensors", "face.pt") is True
    # Any single mismatch falls out.
    assert turbo.passt_zu("anders.safetensors", "vae.safetensors", "face.pt") is False
    assert turbo.passt_zu("m.safetensors", None, "face.pt") is False
    assert turbo.passt_zu("m.safetensors", "vae.safetensors", None) is False
    # The detector's prompt is compared only while a detector is set.
    assert turbo.passt_zu("m.safetensors", "vae.safetensors", "face.pt", "eyes") is False
    turbo._ad_modell = None
    turbo._ad_prompt = ""
    assert turbo.passt_zu("m.safetensors", "vae.safetensors", None, "ignored") is True


class _LebtImmer:
    """A stand-in process that always reports as running."""

    def poll(self):
        return None


def test_abbrechen_nur_beim_zeichnen(tmp_path: Path, monkeypatch):
    """A stop with nothing drawing tears down nothing; while drawing it ends
    the server and marks the draw as a silent abort, not a failure."""
    from app import bildturbo as bt
    from app.bildturbo import Bildturbo

    # Never touch a real process in the test — record that the end was asked
    # for instead of sending a signal.
    beendet = []
    monkeypatch.setattr(bt.prozessstopp, "beenden", lambda p, frist=5.0: beendet.append(p))

    turbo = Bildturbo(tmp_path)
    # Idle: nothing to break off.
    assert turbo.abbrechen() is False
    assert turbo._abgebrochen is False

    # Pretend a draw is in flight on a running server.
    turbo._prozess = _LebtImmer()
    turbo._zeichnet = True
    assert turbo.abbrechen() is True
    # The draw's error handler will now report an abort, not a failure, and the
    # server was told to end.
    assert turbo._abgebrochen is True
    assert len(beendet) == 1
