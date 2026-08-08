"""Foundation of all repositories.

A repository encapsulates access to exactly one kind of data. The application
logic calls methods like ``erstellen`` or ``auflisten`` and never sees SQL.
This is the point where PostgreSQL can later step in without routes,
streaming proxy or frontend noticing anything.
"""

from __future__ import annotations

import uuid

from app.db.connection import Database, jetzt_iso


def neue_id() -> str:
    """Ids are UUIDs without hyphens — short enough for URLs."""
    return uuid.uuid4().hex


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @property
    def verbindung(self):
        return self.db.verbindung

    @staticmethod
    def zeitstempel() -> str:
        return jetzt_iso()
