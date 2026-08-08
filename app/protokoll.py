"""Logging (phase 1.7).

Without usable logs, debugging becomes tedious later — hence structure from
the start:

  * **Request id** — every request gets a short id that rides along in every
    line belonging to it. This lets you trace one operation across the log
    file, even when several run at the same time.
  * **Timing** — how long each request took.
  * **Memory usage** — the peak resident memory so far, from the standard
    library, no extra dependency.
  * **Two formats** — ``text`` reads well in the journal, ``json`` is
    machine-parseable. Switchable in ``config.yaml``.
  * **Rotation** — the file does not grow forever.

The id is passed along via a context variable: every log line in the course
of a request knows it without having to be threaded through every function
call.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import resource
import sys
import time
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from app.config import Config

# Applies to the one request currently being handled.
request_id: ContextVar[str] = ContextVar("request_id", default="-")

# These fields belong to the LogRecord itself and should not be output
# again as "extras".
_STANDARDFELDER = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}


def neue_request_id() -> str:
    """Short enough to read, long enough to be unique."""
    return uuid.uuid4().hex[:12]


def speicher_mb() -> float:
    """Peak resident memory of this process so far, in MB."""
    hoechststand = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux counts in kilobytes, macOS in bytes.
    teiler = 1024 if sys.platform != "darwin" else 1024 * 1024
    return round(hoechststand / teiler, 1)


class KennungFilter(logging.Filter):
    """Attaches the request id to every line."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


class JSONFormatter(logging.Formatter):
    """One line of JSON per log entry — for machine analysis."""

    def format(self, record: logging.LogRecord) -> str:
        eintrag: dict[str, Any] = {
            "zeit": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "stufe": record.levelname,
            "quelle": record.name,
            "meldung": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            eintrag["ausnahme"] = self.formatException(record.exc_info)

        # Everything passed via extra= goes in as well.
        for name, wert in record.__dict__.items():
            if name not in _STANDARDFELDER and name != "request_id":
                eintrag[name] = wert

        return json.dumps(eintrag, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Readable in the journal — with the id, but without a mountain of brackets."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def logging_einrichten(config: Config) -> None:
    """Sets up output to the console and to a rotating file."""
    stufe = getattr(logging, config.logging.level.upper(), logging.INFO)
    formatter = JSONFormatter() if config.logging.format == "json" else TextFormatter()
    kennung = KennungFilter()

    wurzel = logging.getLogger()
    wurzel.setLevel(stufe)
    # On a restart within the same process (tests), do not attach twice.
    for vorhandener in list(wurzel.handlers):
        wurzel.removeHandler(vorhandener)

    konsole = logging.StreamHandler()
    konsole.setFormatter(formatter)
    konsole.addFilter(kennung)
    wurzel.addHandler(konsole)

    if config.logging.file:
        verzeichnis = config.logverzeichnis
        verzeichnis.mkdir(parents=True, exist_ok=True)
        datei = logging.handlers.RotatingFileHandler(
            verzeichnis / config.logging.file,
            maxBytes=config.logging.max_bytes,
            backupCount=config.logging.file_count,
            encoding="utf-8",
        )
        datei.setFormatter(formatter)
        datei.addFilter(kennung)
        wurzel.addHandler(datei)

    # uvicorn brings its own handlers — they would output everything twice.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    # We log access ourselves, with id, duration and memory. uvicorn would
    # output the same line again without those details.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # httpx logs every single health-check request at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)


class ProtokollMiddleware:
    """Assigns the id and measures the duration — as a pure ASGI component.

    Deliberately not a BaseHTTPMiddleware: that one wedges itself between
    response and client during streaming and can swallow the cancellation.
    Exactly that must not happen here.
    """

    def __init__(self, app, ausgenommen: tuple[str, ...] = ("/health",)) -> None:
        self.app = app
        self.ausgenommen = ausgenommen
        self.log = logging.getLogger("zugriff")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        kennung = neue_request_id()
        marke = request_id.set(kennung)
        beginn = time.monotonic()
        pfad = scope.get("path", "")
        status: dict[str, int] = {}

        async def send_mit_status(nachricht):
            if nachricht["type"] == "http.response.start":
                status["code"] = nachricht["status"]
                # Send the id along so an error report can be matched up.
                kopfzeilen = list(nachricht.get("headers") or [])
                kopfzeilen.append((b"x-request-id", kennung.encode()))
                nachricht = {**nachricht, "headers": kopfzeilen}
            await send(nachricht)

        try:
            await self.app(scope, receive, send_mit_status)
        except Exception:
            self.log.exception(
                "Anfrage fehlgeschlagen",
                extra={
                    "methode": scope.get("method"),
                    "pfad": pfad,
                    "dauer_ms": round((time.monotonic() - beginn) * 1000, 1),
                },
            )
            raise
        else:
            if pfad not in self.ausgenommen:
                self.log.info(
                    "%s %s -> %s",
                    scope.get("method"),
                    pfad,
                    status.get("code", "?"),
                    extra={
                        "methode": scope.get("method"),
                        "pfad": pfad,
                        "status": status.get("code"),
                        "dauer_ms": round((time.monotonic() - beginn) * 1000, 1),
                        "speicher_mb": speicher_mb(),
                    },
                )
        finally:
            request_id.reset(marke)
