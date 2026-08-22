"""The drawing tool — `draw_image`.

The bridge the image-generator skill was missing: the skill told the model
to make a picture, but no tool existed that could — the model guessed at
shell commands and failed. This one talks to the picture pipeline of this
very service over its own HTTP API, so it walks exactly the road the
picture window walks: the same queue lock, the same memory check, the same
metadata scrub.

The model does not pick the model file, the size or the steps — the stored
per-model defaults decide, exactly as the picture window's opening values
do. What the model brings is the one thing only it has: the prompt.

The finished file is handed to the run's image sink so the picture hangs
on the answer, and the pipeline's own copy is removed — one file, not two.
The folder comes from the registry, not from an argument: anything the
model can pass, the model can forge.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from app.tools.mcp_client import MCPWerkzeug

SERVER_NAME = "bild"
WERKZEUG_NAME = "draw_image"

# An SDXL picture with a detailer pass takes minutes, not seconds. The
# pipeline itself bounds the work (size and step ceilings) — this bound only
# keeps a hung server from holding the tool call open forever.
ZEITFENSTER_S = 900.0

MAX_PROMPT = 2000


class BildWerkzeugFehler(Exception):
    """The picture could not be made; the message says why."""


def werkzeug_beschreibung() -> MCPWerkzeug:
    return MCPWerkzeug(
        name=WERKZEUG_NAME,
        beschreibung=(
            "Draws a picture with the image model installed on this machine. "
            "Turn the wish into ONE dense visual sentence: subject, setting, "
            "light, mood, look — vague adjectives do nothing. The finished "
            "picture appears in your answer by itself; do not describe its "
            "contents afterwards, you have not seen it."
        ),
        schema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "What the picture shows, as one dense sentence. English works best.",
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "What must stay out of the picture. Optional.",
                },
            },
            "required": ["prompt"],
        },
        server=SERVER_NAME,
    )


async def ausfuehren(
    argumente: dict[str, Any],
    basis: str,
    bilderordner: Path,
    bild_senke=None,
) -> str:
    """Draws the picture and reports what happened.

    ``basis`` is this service's own API root. Calling ourselves over HTTP is
    deliberate: the picture endpoint holds the one-picture lock, checks the
    memory and scrubs the metadata — re-implementing that here would be a
    second, drifting copy of the rules.
    """
    prompt = str(argumente.get("prompt") or "").strip()[:MAX_PROMPT]
    if not prompt:
        raise BildWerkzeugFehler("draw_image needs a prompt.")
    negativ = str(argumente.get("negative_prompt") or "").strip()[:MAX_PROMPT]

    async with httpx.AsyncClient(timeout=ZEITFENSTER_S) as client:
        lage = (await client.get(f"{basis}/bild/modelle")).json()
        if not lage.get("programm_da"):
            return (
                "No image generator is installed. The user can fetch it in "
                "the picture window (plus menu, picture entry)."
            )
        modelle = lage.get("modelle") or []
        if not modelle:
            return (
                "No image model is installed. The user can add one in the "
                "picture window or the catalogue."
            )
        modell = modelle[0]
        vorgaben = (
            await client.get(f"{basis}/bild/vorgaben", params={"modell": modell})
        ).json()

        koerper = {
            "modell": modell,
            "prompt": prompt,
            "negativ": negativ,
            "breite": vorgaben.get("breite", 512),
            "hoehe": vorgaben.get("hoehe", 512),
            "schritte": vorgaben.get("schritte", 22),
        }
        for feld in ("sampler", "scheduler"):
            if vorgaben.get(feld):
                koerper[feld] = vorgaben[feld]

        antwort = await client.post(f"{basis}/bild", json=koerper)
        if antwort.status_code >= 400:
            try:
                grund = antwort.json().get("detail", "")
            except ValueError:
                grund = antwort.text
            return f"The picture could not be drawn: {grund}"
        daten = antwort.json()

    name = daten.get("bild", "")
    pfad = bilderordner / name
    if bild_senke is not None and name and pfad.is_file():
        # Through the sink, so the picture hangs on the answer like any
        # tool image — then the pipeline's copy goes, one file remains.
        neuer = bild_senke("image/png", base64.b64encode(pfad.read_bytes()).decode())
        pfad.unlink(missing_ok=True)
        name = neuer

    return (
        f"The picture was drawn (model {modell}, seed {daten.get('seed')}) "
        "and is attached to this answer."
    )
