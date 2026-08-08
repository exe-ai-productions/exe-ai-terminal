"""Create or check the database.

    python -m app.db.init_db

Creates file and schema if they are missing and reports the schema version.
If everything already exists, nothing happens — the call is safely
repeatable.
"""

from __future__ import annotations

import logging

from app.config import get_config
from app.db import datenbank_oeffnen


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = get_config()
    config.datenverzeichnis.mkdir(parents=True, exist_ok=True)

    db = datenbank_oeffnen(config)
    print(f"Datenbank : {db.pfad}")
    print(f"Schema    : Version {db.schema_version()}")

    tabellen = [
        zeile["name"]
        for zeile in db.verbindung.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
    ]
    print(f"Tabellen  : {', '.join(tabellen)}")
    db.schliessen()


if __name__ == "__main__":
    main()
