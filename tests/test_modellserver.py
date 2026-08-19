

import os


def test_mtp_bausteine_sind_keine_modelle(tmp_path):
    # An accelerator module must never appear as a startable model.
    (tmp_path / "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf").write_bytes(b"x")
    (tmp_path / "gemma-4-12B-it-qat-mtp.gguf").write_bytes(b"x")
    from app.modellrunner import modelle_auflisten

    namen = [m.name for m in modelle_auflisten(tmp_path)]
    assert namen == ["gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"]


def test_mtp_bausteine_sind_eigene_liste(tmp_path):
    # The modules show up in their own list, with sizes, and a vision
    # projector does not sneak in even when its name carries the marker.
    (tmp_path / "mtp").mkdir()
    (tmp_path / "mtp" / "mtp-gemma-4-12B-it.gguf").write_bytes(b"x" * 2048)
    (tmp_path / "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf").write_bytes(b"x")
    # A projector that carries the mtp marker still must not sneak into the
    # draft list, even lying in the mtp folder.
    (tmp_path / "mtp" / "mtp-gemma-4-12B-mmproj-F16.gguf").write_bytes(b"x")
    from app.modellrunner import mtp_auflisten

    module = mtp_auflisten(tmp_path)
    assert [m.name for m in module] == ["mtp-gemma-4-12B-it.gguf"]
    assert module[0].groesse_gb == 0.0


def test_mtp_drafter_bekommt_eigenen_modus(tmp_path):
    # A prediction module needs --spec-type draft-mtp; a sibling model
    # must stay on the plain draft path.
    from app.modellrunner import Modellrunner

    runner = Modellrunner(tmp_path)
    mit_modul = runner.befehl(
        "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf", 8192, 99, 8080,
        drafter="mtp-gemma-4-12B-it.gguf",
    )
    assert "--spec-type" in mit_modul
    assert mit_modul[mit_modul.index("--spec-type") + 1] == "draft-mtp"

    mit_geschwister = runner.befehl(
        "Bonsai-27B-Q1_0.gguf", 8192, 99, 8080,
        drafter="Bonsai-1.7B-Q1_0.gguf",
    )
    assert "--spec-type" not in mit_geschwister
    assert "--model-draft" in mit_geschwister


def test_start_gibt_dem_server_einen_schluessel(tmp_path, monkeypatch):
    # The started server gets a fresh key via environment; the service
    # keeps the same key where the provider reads it. The shown command
    # stays clean — no secret in the process list.
    import subprocess
    from app import modellrunner as mr

    (tmp_path / "modell.gguf").write_bytes(b"x")
    aufrufe = {}

    class StummerProzess:
        pid = 4711
        stdout = None
        def poll(self):
            return None

    def fake_popen(befehl, **wie):
        aufrufe["befehl"] = befehl
        aufrufe["env"] = wie.get("env") or {}
        return StummerProzess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(mr, "programm_finden", lambda vorgabe=None: tmp_path / "llama-server")

    runner = mr.Modellrunner(tmp_path)
    runner.starten("modell.gguf", port=18099)

    schluessel = aufrufe["env"].get("LLAMA_API_KEY")
    assert schluessel and len(schluessel) >= 24
    assert os.environ.get(mr.SCHLUESSEL_VARIABLE) == schluessel
    assert "--api-key" not in aufrufe["befehl"]
    assert schluessel not in " ".join(aufrufe["befehl"])

    runner._prozess = None
    os.environ.pop(mr.SCHLUESSEL_VARIABLE, None)
