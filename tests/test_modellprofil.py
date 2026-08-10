"""The start flags a model file gets: --jinja always, family lore on top."""

from app.modellprofil import startflags


def test_jinja_ist_immer_dabei():
    assert "--jinja" in startflags("irgendein-modell.gguf")


def test_gemma_bekommt_seine_werte():
    flags = startflags("gemma-4-31B-it-Q4_K_M.gguf")
    assert flags[0] == "--jinja"
    assert "--top-k" in flags


def test_glm_bekommt_repeat_penalty_eins():
    flags = startflags("GLM-4.7-Flash-UD-Q4_K_XL.gguf")
    stelle = flags.index("--repeat-penalty")
    assert flags[stelle + 1] == "1.0"


def test_unbekannte_familie_bekommt_nur_jinja():
    assert startflags("Bonsai-27B-Q1_0.gguf") == ["--jinja"]


def test_gross_klein_egal():
    assert "--top-k" in startflags("GEMMA-4-12B-IT-Q6_K.GGUF")
