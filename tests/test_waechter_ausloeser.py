"""The guardian's trigger catalogue — the half that runs without a model.

Two kinds of mistake matter here and both are quiet: a trigger that never
fires leaves the guardian mute, and one that fires too eagerly turns a
working run into a stream of suggestions nobody asked for. So both
directions are tested — what must fire, and what must stay silent.
"""

from __future__ import annotations

from app import waechter_ausloeser as ausloeser


def test_ein_befehl_mit_exit_code_ungleich_null_loest_aus():
    befund = ausloeser.pruefen(
        name="run_command",
        ergebnis="stderr:\nnpm ERR! missing script: baun\n[exit code 1]",
        argumente={"command": "npm run baun"},
        auftrag="Bau bitte das Frontend.",
    )
    assert befund is not None
    assert befund.art == ausloeser.BEFEHL_GESCHEITERT
    assert befund.werkzeug == "run_command"
    assert befund.auftrag == "Bau bitte das Frontend."
    assert befund.argumente == {"command": "npm run baun"}


def test_exit_code_null_loest_nicht_aus():
    """A command that worked is not a case, however loudly it printed."""
    assert (
        ausloeser.pruefen(name="run_command", ergebnis="alles gut\n[exit code 0]") is None
    )
    assert ausloeser.pruefen(name="run_command", ergebnis="(done, no output)") is None


def test_eine_zeitueberschreitung_loest_aus_und_nicht_als_exit_code():
    # The full two-line text as the tool really returns it: the advice line
    # after the stop sentence is what a $-anchored pattern chokes on.
    befund = ausloeser.pruefen(
        name="run_command",
        ergebnis=(
            "Stopped after 120 seconds — the command was still running.\n"
            "If it is supposed to run that long, start it with background set to true."
        ),
    )
    assert befund is not None
    assert befund.art == ausloeser.ZEIT_ABGELAUFEN


def test_ein_abgelehnter_aufruf_loest_aus_egal_was_im_text_steht():
    """The refusal text is translated — the flag decides, not the wording."""
    befund = ausloeser.pruefen(
        name="run_command",
        ergebnis="Der Benutzer hat „run_command“ nicht erlaubt. Nicht ausgeführt.",
        fehlgeschlagen=True,
        abgelehnt=True,
    )
    assert befund is not None
    assert befund.art == ausloeser.AUFRUF_ABGELEHNT


def test_der_grund_reist_mit_und_wird_gedeckelt():
    """Why a call was refused is kept on the finding, bounded like the rest —
    the model reads it, and something the caller renders has no length this
    code knows."""
    befund = ausloeser.pruefen(
        name="write_file",
        ergebnis="not allowed",
        abgelehnt=True,
        grund="Reaches /etc/hosts — outside the shared folders",
    )
    assert befund.grund == "Reaches /etc/hosts — outside the shared folders"

    lang = ausloeser.pruefen(
        name="write_file", ergebnis="not allowed", abgelehnt=True, grund="p" * 500
    )
    assert len(lang.grund) == ausloeser.GRUND_GRENZE


def test_eine_verfehlte_aenderung_loest_aus():
    for text in (
        "old_text was not found in 'app/main.py'. Read the file and copy the passage",
        "old_text appears 3 times in 'app/main.py'. Give more of the surrounding lines",
    ):
        befund = ausloeser.pruefen(name="edit_file", ergebnis=text, fehlgeschlagen=True)
        assert befund is not None and befund.art == ausloeser.AENDERUNG_VERFEHLT


def test_eine_unlesbare_datei_loest_aus():
    for text in (
        "'bild.png' is a binary file, use run_command with a suitable tool instead.",
        "'app/fehlt.py' does not exist.",
    ):
        befund = ausloeser.pruefen(name="read_file", ergebnis=text, fehlgeschlagen=True)
        assert befund is not None and befund.art == ausloeser.DATEI_UNLESBAR


def test_derselbe_satz_in_einer_gelesenen_datei_loest_nicht_aus():
    """A file that talks about binary files is not a failed read."""
    assert (
        ausloeser.pruefen(
            name="read_file",
            ergebnis="Zeile 1: whoever writes 'is a binary file' into a doc is fine",
            fehlgeschlagen=False,
        )
        is None
    )


def test_ein_zitierter_exit_code_loest_nicht_aus():
    """A log that mentions an exit code is not a command that failed.

    `cat build.log` comes back successful, with somebody else's exit code
    somewhere in the middle of it. Read loosely, that used to fire the
    guardian, burn one of the two allowances for the request, and cost a
    model call for a step that worked.
    """
    protokoll = "npm run build\n[exit code 1]\nnpm run build\nfertig\n[exit code 0]"
    assert ausloeser.pruefen(name="run_command", ergebnis=protokoll) is None
    # And the same words out of a tool that is not the shell stay silent
    # whatever they say.
    assert (
        ausloeser.pruefen(name="read_file", ergebnis="…\n[exit code 1]", fehlgeschlagen=False)
        is None
    )
    assert (
        ausloeser.pruefen(
            name="read_file", ergebnis="Stopped after 5 seconds — quoted", fehlgeschlagen=False
        )
        is None
    )


def test_ein_gewoehnliches_ergebnis_bleibt_stumm():
    assert ausloeser.pruefen(name="web_search", ergebnis="Keine Treffer.") is None
    assert ausloeser.pruefen(name="read_file", ergebnis="") is None


def test_ein_langes_ergebnis_wird_gekuerzt():
    """A wall of build output must not push the request out of the prompt."""
    befund = ausloeser.pruefen(
        name="run_command", ergebnis="x" * 5000 + "\n[exit code 2]"
    )
    assert befund is not None
    assert len(befund.ergebnis) == ausloeser.ERGEBNIS_GRENZE


def test_ein_langer_werkzeugname_wird_gekuerzt():
    """The name comes out of the model's call, not out of our registry."""
    befund = ausloeser.pruefen(
        name="n" * 400, ergebnis="'x' does not exist.", fehlgeschlagen=True
    )
    assert befund is not None
    assert len(befund.werkzeug) == ausloeser.WERKZEUG_GRENZE


# --- Arguments: every value, not just the ones that happen to be strings ----


def _argumente(werte: dict) -> dict:
    befund = ausloeser.pruefen(
        name="edit_file",
        ergebnis="old_text was not found in 'app/main.py'.",
        fehlgeschlagen=True,
        argumente=werte,
    )
    assert befund is not None
    return befund.argumente


def test_ein_langer_text_wird_gekuerzt():
    gekuerzt = _argumente({"old_text": "z" * 5000})["old_text"]
    assert len(gekuerzt) == ausloeser.ARGUMENT_GRENZE + 1
    assert gekuerzt.endswith("…")


def test_auch_listen_und_objekte_werden_gekuerzt():
    """The first build cut strings and only strings — a list of two thousand
    paths is not a `str` and went into the prompt whole."""
    for wert in (
        ["/ein/pfad/" + "p" * 40 for _ in range(200)],
        {f"schluessel{n}": "w" * 100 for n in range(100)},
        int("9" * 2000),
    ):
        gekuerzt = _argumente({"wert": wert})["wert"]
        assert isinstance(gekuerzt, str)
        assert len(gekuerzt) == ausloeser.ARGUMENT_GRENZE + 1


def test_was_passt_behaelt_seinen_typ():
    """A number that fits reads as a number; only a cut value becomes text."""
    behalten = _argumente({"zeilen": 12, "an": True, "pfad": "app/main.py"})
    assert behalten == {"zeilen": 12, "an": True, "pfad": "app/main.py"}


def test_die_summe_aller_argumente_ist_begrenzt():
    """Twenty short values must not add up past the window either."""
    gekuerzt = _argumente({f"nummer_{n}": "w" * 300 for n in range(30)})
    assert len(str(gekuerzt)) <= ausloeser.ARGUMENTE_GRENZE
    # And the report says that something is missing rather than quietly
    # showing a shorter call than the one that was made.
    assert ausloeser.UEBERZAEHLIG in gekuerzt


def test_auch_lange_namen_werden_gekuerzt():
    gekuerzt = _argumente({"n" * 400: "kurz"})
    assert list(gekuerzt) == ["n" * ausloeser.SCHLUESSEL_GRENZE]


def test_ohne_argumente_bleibt_es_leer():
    assert _argumente({}) == {}
