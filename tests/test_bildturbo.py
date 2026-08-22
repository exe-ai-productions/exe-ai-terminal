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
    """Without extras the body stays the bare basics — nothing is invented."""
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


# --- The extras that used to force the slow path -----------------------------


def test_startbild_und_maske_reisen_als_base64(tmp_path: Path):
    """A starting picture and its mask travel in the body, base64, with the
    strength beside them. Both were kept from this path for a long time on
    the belief that the server had no fields for them."""
    import base64

    start = tmp_path / "start.png"
    start.write_bytes(b"START-BYTES")
    maske = tmp_path / "maske.png"
    maske.write_bytes(b"MASKE-BYTES")

    auftrag = Auftrag(
        modell=Path("/m.safetensors"), prompt="x",
        startbild=start, maske=maske, staerke=0.42,
    )
    body = _turbo_auftrag(auftrag)
    assert body["init_images"] == [base64.b64encode(b"START-BYTES").decode()]
    assert body["mask"] == base64.b64encode(b"MASKE-BYTES").decode()
    assert body["denoising_strength"] == 0.42
    # The mask keeps the polarity the rest of the program uses; the server was
    # measured to read it the same way, so nothing is flipped here.
    assert "inpainting_mask_invert" not in body


def test_ohne_startbild_keine_staerke_und_keine_maske(tmp_path: Path):
    """No starting picture, no strength — a denoising figure without a picture
    to act on would be a number about nothing."""
    auftrag = Auftrag(modell=Path("/m.safetensors"), prompt="x", staerke=0.5)
    body = _turbo_auftrag(auftrag)
    assert "init_images" not in body
    assert "denoising_strength" not in body
    assert "mask" not in body


def test_hires_und_clipskip_reisen_mit():
    auftrag = Auftrag(
        modell=Path("/m.safetensors"), prompt="x",
        hires=True, hires_scale=2.0, clip_skip=2,
    )
    body = _turbo_auftrag(auftrag)
    assert body["enable_hr"] is True
    assert body["hr_scale"] == 2.0
    assert body["clip_skip"] == 2


def test_ohne_hires_und_ohne_clipskip_steht_nichts_im_body():
    auftrag = Auftrag(modell=Path("/m.safetensors"), prompt="x", clip_skip=-1)
    body = _turbo_auftrag(auftrag)
    assert "enable_hr" not in body
    assert "hr_scale" not in body
    assert "clip_skip" not in body


def test_die_paesse_zaehlen_wie_beim_langsamen_weg():
    """Both paths count the same passes, or the same picture would be drawn
    behind two different bars."""
    from app.api.v1.bild import _erwartete_paesse

    schlicht = Auftrag(modell=Path("/m.safetensors"), prompt="x")
    assert _erwartete_paesse(schlicht) == 1

    mit_hires = Auftrag(modell=Path("/m.safetensors"), prompt="x", hires=True)
    assert _erwartete_paesse(mit_hires) == 2

    mit_beidem = Auftrag(
        modell=Path("/m.safetensors"), prompt="x",
        hires=True, ad_modell=Path("/face.safetensors"),
    )
    assert _erwartete_paesse(mit_beidem) == 3


def test_ein_startbild_geht_an_den_anderen_eingang(tmp_path: Path, monkeypatch):
    """A body with a starting picture belongs at img2img, one without at
    txt2img. The module itself never looks into the body to decide."""
    import app.bildturbo as bt

    gerufen: list[str] = []

    class _Antwort:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            import base64
            return {"images": [base64.b64encode(b"PNG").decode()]}

    def _post(url, json=None, timeout=None):
        gerufen.append(url)
        return _Antwort()

    monkeypatch.setattr(bt.httpx, "post", _post)

    turbo = Bildturbo(tmp_path)
    turbo._prozess = object()          # laeuft() sagt ja
    monkeypatch.setattr(turbo, "laeuft", lambda: True)

    turbo.zeichnen({"prompt": "x", "steps": 8}, weg="img2img")
    turbo.zeichnen({"prompt": "x", "steps": 8})

    assert gerufen[0].endswith("/sdapi/v1/img2img")
    assert gerufen[1].endswith("/sdapi/v1/txt2img")


def test_die_paesse_kommen_vom_aufrufer(tmp_path: Path, monkeypatch):
    """The caller knows about highres; the module only takes the number."""
    import app.bildturbo as bt

    class _Antwort:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            import base64
            return {"images": [base64.b64encode(b"PNG").decode()]}

    gesehen = {}

    def _post(url, json=None, timeout=None):
        # The counting stands while the call is in flight.
        gesehen.update(turbo._zaehl or {})
        return _Antwort()

    monkeypatch.setattr(bt.httpx, "post", _post)
    turbo = Bildturbo(tmp_path)
    turbo._prozess = object()
    monkeypatch.setattr(turbo, "laeuft", lambda: True)

    turbo.zeichnen({"prompt": "x", "steps": 8}, paesse=3)
    assert gesehen["paesse"] == 3


def test_die_weiche_schickt_ein_startbild_ueber_den_turbo(tmp_path: Path, monkeypatch):
    """The switch: while the turbo runs, a request with a starting picture
    takes it too. It used to fall back to sd-cli on the belief that this
    server had no fields for one."""
    from app.api.v1 import bild as bildapi

    start = tmp_path / "start.png"
    start.write_bytes(b"START")

    auftrag = Auftrag(modell=Path("/m.safetensors"), prompt="x", startbild=start,
                      staerke=0.5)
    koerper = bildapi._turbo_auftrag(auftrag)

    # Exactly the decision the endpoint makes.
    assert "init_images" in koerper
    weg = "img2img" if "init_images" in koerper else "txt2img"
    assert weg == "img2img"

    # And without one it stays the ordinary entrance.
    ohne = bildapi._turbo_auftrag(Auftrag(modell=Path("/m.safetensors"), prompt="x"))
    assert ("img2img" if "init_images" in ohne else "txt2img") == "txt2img"


def test_maske_ohne_startbild_erreicht_den_body_nicht(tmp_path: Path):
    """The old rule stands: a mask without a picture to mask has nothing to
    act on, and the endpoint drops it before the body is built."""
    maske = tmp_path / "m.png"
    maske.write_bytes(b"MASKE")
    auftrag = Auftrag(modell=Path("/m.safetensors"), prompt="x", maske=maske)
    body = _turbo_auftrag(auftrag)
    assert "mask" not in body
