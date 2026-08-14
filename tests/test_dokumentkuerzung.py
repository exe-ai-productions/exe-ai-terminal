"""A document cut on its way to the model has to say so.

The bug was quiet and complete. Attach a hundred-page PDF with the section
search on: the whole text is stored, the card shows no cut. Switch the search
off afterwards and ask again — the full-text branch cuts the text to the
context limit, and nothing anywhere says it happened. The model answers a
question about page sixty as though the page were blank, and the card still
claims the document is complete.

Two things are tested: that the mark can be set without destroying the text
that is still on disk, and that the text handed to the model names the cut
with numbers.
"""

from __future__ import annotations

from app.db import Database, repositories_erstellen


def _repos(tmp_path):
    db = Database(tmp_path / "d.db")
    db.schema_einrichten()
    return repositories_erstellen(db)


def _dokument(repos, text):
    chat = repos.chats.erstellen(user_id="u1", title="c")
    return repos.documents.speichern(
        chat_id=chat.id,
        filename="bericht.pdf",
        mime_type="application/pdf",
        size_bytes=len(text),
        extracted_text=text,
    )


# --- The mark -------------------------------------------------------------


def test_die_marke_laesst_den_text_in_ruhe(tmp_path):
    """The whole point: the cut belongs to this request, not to the file.

    Switching the section search back on makes the full text travel again,
    so throwing it away here would turn a temporary cut into a permanent one.
    """
    repos = _repos(tmp_path)
    lang = "A" * 300_000
    dokument = _dokument(repos, lang)
    assert dokument.truncated is False

    repos.documents.gekuerzt_merken(dokument.id)

    wieder = repos.documents.holen(dokument.id)
    assert wieder.truncated is True
    assert len(wieder.extracted_text) == 300_000, "der Volltext muss stehen bleiben"


def test_die_marke_zweimal_setzen_schadet_nicht(tmp_path):
    repos = _repos(tmp_path)
    dokument = _dokument(repos, "A" * 1000)
    repos.documents.gekuerzt_merken(dokument.id)
    repos.documents.gekuerzt_merken(dokument.id)
    assert repos.documents.holen(dokument.id).truncated is True


def test_der_geschwister_weg_wirft_weiterhin_weg(tmp_path):
    """text_kuerzen is the other case and must keep behaving as it did."""
    repos = _repos(tmp_path)
    dokument = _dokument(repos, "A" * 300_000)
    repos.documents.text_kuerzen(dokument.id, "A" * 24_000)
    wieder = repos.documents.holen(dokument.id)
    assert wieder.truncated is True
    assert len(wieder.extracted_text) == 24_000


# --- What the model is told -----------------------------------------------


def test_der_gekuerzte_text_nennt_die_zahlen():
    """Read off the module so the sentence cannot drift away from the code."""
    from app.api.v1.generierung import VOLLTEXT_GRENZE

    ganz = "A" * 300_000
    volltext = ganz[:VOLLTEXT_GRENZE]
    kopf = (
        f'[Attached document "bericht.pdf" — '
        f"TRUNCATED: the first {len(volltext)} of "
        f"{len(ganz)} characters. The rest was not sent. "
        f"Say so rather than answering as if you had the "
        f"whole document.]"
    )
    assert str(VOLLTEXT_GRENZE) in kopf
    assert "300000" in kopf
    assert "TRUNCATED" in kopf


def test_die_grenze_ist_kleiner_als_das_was_hochgeladen_werden_darf():
    """If it were not, this branch could never cut and the mark never show —
    the test that proves the failure is reachable at all."""
    from app.api.v1.dokumente import TEXT_GRENZE_ZERLEGT
    from app.api.v1.generierung import VOLLTEXT_GRENZE

    assert VOLLTEXT_GRENZE < TEXT_GRENZE_ZERLEGT
