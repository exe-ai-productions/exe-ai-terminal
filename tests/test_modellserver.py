

def test_mtp_bausteine_sind_keine_modelle(tmp_path):
    # An accelerator module must never appear as a startable model.
    (tmp_path / "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf").write_bytes(b"x")
    (tmp_path / "gemma-4-12B-it-qat-mtp.gguf").write_bytes(b"x")
    from app.modellrunner import modelle_auflisten

    namen = [m.name for m in modelle_auflisten(tmp_path)]
    assert namen == ["gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"]
