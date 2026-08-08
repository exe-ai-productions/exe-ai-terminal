"""What the built-in tools tell the model about themselves.

A description is the only thing a model has to go on before it calls
something. Two ways it can be wrong, and both are checked here.

It can state a number the code does not honour. That one is already ruled
out by construction: the limits are interpolated from their constants, so
changing one changes the sentence with it. What is left to catch is the way
that construction breaks — somebody edits the text and drops the `f` prefix,
and the model is then told the limit is "{ZEITGRENZE_SEKUNDEN}". Checking for
the actual number catches exactly that, and nothing else. It was worth
verifying: the first version of this file claimed to guard against drift, and
a deliberate change to the constant did not make it fail — because it cannot.

And it can repeat what the shipped prompt already says. That is not merely
redundant: everything here rides along on every request, and a sentence paid
for twice is attention taken from a sentence that appears once.
"""

from __future__ import annotations

from app import grundprompt
from app.tools import memory, shell


def test_die_zeitgrenze_steht_als_zahl_im_text():
    text = shell.werkzeug_beschreibung().beschreibung
    assert str(shell.ZEITGRENZE_SEKUNDEN) in text


def test_die_ausgabegrenze_steht_als_zahl_im_text():
    text = shell.werkzeug_beschreibung().beschreibung
    assert f"{shell.MAX_AUSGABE_ZEICHEN:,}" in text


def test_die_laengengrenze_steht_als_zahl_im_text():
    text = memory.werkzeug_beschreibung().beschreibung
    assert str(memory.MAX_LAENGE) in text


def test_die_shell_nennt_was_nur_sie_weiss():
    """Facts a model cannot infer and will otherwise trip over: nothing waits
    for input, and some commands are refused rather than asked about."""
    text = shell.werkzeug_beschreibung().beschreibung.lower()
    assert "interactive" in text
    assert "refused" in text


def test_das_gedaechtnis_nennt_seine_grenzen():
    text = memory.werkzeug_beschreibung().beschreibung.lower()
    assert "cannot delete" in text
    assert "replaces" in text


def test_die_beschreibungen_wiederholen_den_grundprompt_nicht():
    """The shipped prompt says it once for all tools; saying it again here
    costs the same attention twice on every single request."""
    grund = grundprompt.bauen(werkzeuge=True, ordner=["/a"], gedaechtnis=True).lower()
    for beschreibung in (
        shell.werkzeug_beschreibung().beschreibung,
        memory.werkzeug_beschreibung().beschreibung,
    ):
        klein = beschreibung.lower()
        # The three sentences the shipped prompt owns.
        assert "report only what actually happened" not in klein
        assert "data, not instructions" not in klein
        assert "should still hold next week" not in klein
    # And the shipped prompt really does carry them, so the check has teeth.
    assert "report only what actually happened" in grund
    assert "data, not instructions" in grund
    assert "should still hold next week" in grund
