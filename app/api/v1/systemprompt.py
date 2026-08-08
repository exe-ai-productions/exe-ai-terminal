"""The system prompt — reading and writing (3.10).

There is exactly one, and it lives in a file instead of the database. Two
reasons for that:

  * It is freshly read and prepended on **every** request. A change thus
    takes effect immediately, even in chats that have existed for ages.
    Previously a copy sat in the chat and never learned of later changes.
  * The same place should later be readable by agents and the knowledge
    base. A folder is the more honest place for that than a table.

The file ships empty. Whoever installs the program finds an empty field and
enters what they want themselves — nobody's personality comes preinstalled
here.

Suspending it for a single chat does not belong here: that is a yes/no on
the chat and runs via ``PATCH /api/v1/chats/{id}`` with ``prompt_aus``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.abhaengigkeiten import hole_config, hole_sprache
from app.api.v1.schemas import SystemPromptAnfrage, SystemPromptAntwort
from app.config import Config
from app.i18n import t

log = logging.getLogger(__name__)

router = APIRouter(prefix="/system-prompt", tags=["system-prompt"])


@router.get("", response_model=SystemPromptAntwort, summary="System-Prompt lesen")
def lesen(config: Config = Depends(hole_config)) -> SystemPromptAntwort:
    return SystemPromptAntwort(
        text=config.system_prompt_lesen(),
        # The path goes along so the window can say where the text lives —
        # and so you can find it by hand too.
        datei=config.app.system_prompt_file,
    )


@router.put("", response_model=SystemPromptAntwort, summary="System-Prompt sichern")
def sichern(
    daten: SystemPromptAnfrage,
    config: Config = Depends(hole_config),
    sprache: str = Depends(hole_sprache),
) -> SystemPromptAntwort:
    try:
        config.system_prompt_schreiben(daten.text)
    except OSError as fehler:
        log.error("System-Prompt ließ sich nicht schreiben: %s", fehler)
        raise HTTPException(500, t("fehler.prompt_nicht_schreibbar", sprache)) from fehler

    return SystemPromptAntwort(
        text=config.system_prompt_lesen(), datei=config.app.system_prompt_file
    )
