"""What a finished background run leaves behind in the chat.

The run itself lives in ``app/tools/hintergrund.py`` and knows nothing about
the database — a tool that writes messages would be a tool that can write
anything. The service hangs this handler in at startup, and it does the one
thing the run cannot: put the result where both the user and the model will
see it.

Both at once, on purpose. A note only the window shows would be invisible to
the model at the next question, and a result only the model sees would look
to the user as if nothing had happened.
"""

from __future__ import annotations

import logging

from app.db import Repositories
from app.tools.hintergrund import Lauf, laeufe

log = logging.getLogger(__name__)

# As much as a tool result carries in the message log — beyond that nobody
# reads it and the context pays for it.
MAX_ZEICHEN = 2_000


def _text(lauf: Lauf, antwort: str) -> str:
    ausgang = "finished" if lauf.code == 0 else f"failed with exit code {lauf.code}"
    return (
        f"[background run #{lauf.nummer} {ausgang}: {lauf.befehl}]\n\n"
        f"{antwort[:MAX_ZEICHEN]}"
    )


def anmelden(repositories: Repositories) -> None:
    """From now on every finished background run reports into its chat."""

    def fertig(lauf: Lauf, antwort: str) -> None:
        try:
            repositories.messages.speichern(
                chat_id=lauf.chat_id,
                role="assistant",
                content=_text(lauf, antwort),
                stats={
                    "werkzeuge": [
                        {
                            "name": "run_command",
                            "server": "shell",
                            "argumente": {"command": lauf.befehl, "background": True},
                            "fehlgeschlagen": lauf.code != 0,
                            "ergebnis": antwort[:MAX_ZEICHEN],
                        }
                    ]
                },
            )
        except Exception:  # noqa: BLE001 - a lost note must not take the service with it
            log.exception("Ergebnis eines Hintergrundlaufs konnte nicht abgelegt werden")

    laeufe.abschluss = fertig
