"""The embedding server's own start line."""

from __future__ import annotations
def test_das_fenster_steht_nur_einmal_in_der_zeile():
    """The runner writes `--ctx-size` itself. A second one from the flag list
    made a command line that carried it twice — it worked by accident, because
    llama.cpp takes the last one.

    Same guard as the Extended-Workflow server's, and for the same reason:
    what a command line says has to be what somebody meant to say.
    """
    from pathlib import Path

    from app import einbettungsserver

    assert "--ctx-size" not in einbettungsserver.FLAGS
    runner = einbettungsserver.runner_bauen(Path("/tmp"), "llama-server", 8081)
    zeile = " ".join(runner.befehl("m.gguf", einbettungsserver.STAPEL, 99, 8081))
    assert zeile.count("--ctx-size") == 1
    assert f"--ctx-size {einbettungsserver.STAPEL}" in zeile
