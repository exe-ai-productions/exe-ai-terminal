"""Data objects of the application.

Deliberately plain dataclasses instead of database rows: the application
logic works with these objects and does not know whether SQLite or something
else is behind them.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chat:
    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    prompt_aus: bool = False
    endpoint_id: str | None = None
    pinned: bool = False
    # The folders the model may work in for this chat (shell tool). The first
    # is the working directory commands run in, the others are additional
    # sources; four at most. Empty: none chosen. Set by the user, never by
    # the model.
    working_dirs: list[str] = field(default_factory=list)

    @classmethod
    def aus_zeile(cls, zeile: sqlite3.Row) -> "Chat":
        return cls(
            id=zeile["id"],
            user_id=zeile["user_id"],
            title=zeile["title"],
            created_at=zeile["created_at"],
            updated_at=zeile["updated_at"],
            prompt_aus=bool(zeile["prompt_aus"]),
            endpoint_id=zeile["endpoint_id"],
            pinned=bool(zeile["pinned"]),
            working_dirs=json.loads(zeile["working_dirs"]) if zeile["working_dirs"] else [],
        )


@dataclass
class Message:
    id: str
    chat_id: str
    role: str
    content: str
    created_at: str
    reasoning: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
    # File name of an attached image under data/bilder/ (vision, 4.x).
    bild: str | None = None
    # id of an attached document (4.1) — text and facts in documents.
    dokument: str | None = None

    @classmethod
    def aus_zeile(cls, zeile: sqlite3.Row) -> "Message":
        rohe_stats = zeile["stats_json"]
        return cls(
            id=zeile["id"],
            chat_id=zeile["chat_id"],
            role=zeile["role"],
            content=zeile["content"],
            created_at=zeile["created_at"],
            reasoning=zeile["reasoning"],
            stats=json.loads(rohe_stats) if rohe_stats else {},
            bild=zeile["bild"] if "bild" in zeile.keys() else None,
            dokument=zeile["dokument"] if "dokument" in zeile.keys() else None,
        )


@dataclass
class Auftrag:
    """One run of an agent (phase 6) — lives alongside the chats."""

    id: str
    user_id: str
    agent: str
    auftrag: str
    zustand: str
    created_at: str
    updated_at: str
    ende_grund: str | None = None
    ergebnis: str | None = None
    endpoint_id: str | None = None
    generation_id: str | None = None

    @classmethod
    def aus_zeile(cls, zeile: sqlite3.Row) -> "Auftrag":
        return cls(
            id=zeile["id"],
            user_id=zeile["user_id"],
            agent=zeile["agent"],
            auftrag=zeile["auftrag"],
            zustand=zeile["zustand"],
            created_at=zeile["created_at"],
            updated_at=zeile["updated_at"],
            ende_grund=zeile["ende_grund"],
            ergebnis=zeile["ergebnis"],
            endpoint_id=zeile["endpoint_id"],
            generation_id=zeile["generation_id"],
        )


@dataclass
class AuftragSchritt:
    """One line in a job's transcript. A run always keeps a record."""

    id: str
    auftrag_id: str
    nummer: int
    typ: str
    inhalt: str
    created_at: str

    @classmethod
    def aus_zeile(cls, zeile: sqlite3.Row) -> "AuftragSchritt":
        return cls(
            id=zeile["id"],
            auftrag_id=zeile["auftrag_id"],
            nummer=zeile["nummer"],
            typ=zeile["typ"],
            inhalt=zeile["inhalt"],
            created_at=zeile["created_at"],
        )


@dataclass
class Document:
    id: str
    chat_id: str
    filename: str
    created_at: str
    mime_type: str | None = None
    size_bytes: int | None = None
    extracted_text: str | None = None
    # Page count (PDF only) and whether it was truncated at the limit (4.1).
    pages: int | None = None
    truncated: bool = False

    @classmethod
    def aus_zeile(cls, zeile: sqlite3.Row) -> "Document":
        return cls(
            id=zeile["id"],
            chat_id=zeile["chat_id"],
            filename=zeile["filename"],
            created_at=zeile["created_at"],
            mime_type=zeile["mime_type"],
            size_bytes=zeile["size_bytes"],
            extracted_text=zeile["extracted_text"],
            pages=zeile["pages"] if "pages" in zeile.keys() else None,
            truncated=bool(zeile["truncated"]) if "truncated" in zeile.keys() else False,
        )
