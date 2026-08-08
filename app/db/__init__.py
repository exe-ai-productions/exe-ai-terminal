"""Database layer — the only place in the project where SQL occurs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Config
from app.db.connection import Database
from app.db.repositories.auftraege import AuftragRepository
from app.db.repositories.chats import ChatRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.einstellungen import EinstellungenRepository
from app.db.repositories.messages import MessageRepository


@dataclass
class Repositories:
    """Binder: one access point to all repositories."""

    db: Database
    chats: ChatRepository
    messages: MessageRepository
    documents: DocumentRepository
    auftraege: AuftragRepository
    einstellungen: EinstellungenRepository


def repositories_erstellen(db: Database) -> Repositories:
    return Repositories(
        db=db,
        chats=ChatRepository(db),
        messages=MessageRepository(db),
        documents=DocumentRepository(db),
        auftraege=AuftragRepository(db),
        einstellungen=EinstellungenRepository(db),
    )


def datenbank_oeffnen(config: Config | None = None, pfad: str | Path | None = None) -> Database:
    """Opens the database and sets up the schema when needed."""
    if pfad is None:
        if config is None:
            raise ValueError("Entweder 'config' oder 'pfad' muss angegeben werden")
        if config.database.backend != "sqlite":
            raise NotImplementedError(
                f"Backend '{config.database.backend}' ist noch nicht umgesetzt. "
                "Das Repository-Pattern erlaubt es, hier ein weiteres zu ergänzen."
            )
        pfad = config.datenbankpfad

    db = Database(pfad)
    db.schema_einrichten()
    return db


__all__ = [
    "Database",
    "Repositories",
    "datenbank_oeffnen",
    "repositories_erstellen",
    "AuftragRepository",
    "ChatRepository",
    "MessageRepository",
    "DocumentRepository",
]
