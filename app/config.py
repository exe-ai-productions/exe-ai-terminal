"""Load and validate the configuration.

Two sources, clearly separated:
  * config.yaml — everything non-secret, kept under version control.
  * .env        — secrets and machine-specific overrides.

The caller obtains the configuration via ``get_config()``. On the first call
it is loaded and cached afterwards.
"""

from __future__ import annotations

import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from app.configwanderung import wandern
from app.paketierung import aufloesen
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

log = logging.getLogger(__name__)

PROJEKT_WURZEL = Path(__file__).resolve().parent.parent

ReasoningFormat = Literal["native", "harmony", "think", "none"]


class Capabilities(BaseModel):
    """What an endpoint can do. The frontend shows controls accordingly."""

    streaming: bool = True
    # The same pattern applies to tool_calls, vision and thinking:
    # None = discovery detects it natively (llama.cpp /props — tools and
    # the thinking switch live in the chat template, vision in `modalities`).
    # An explicit entry here ALWAYS wins — even a "no"
    # (safety rule: Gemma's tool_calls-off must not be overruled by
    # detection).
    tool_calls: bool | None = None
    vision: bool | None = None
    thinking: bool | None = None


class EndpointConfig(BaseModel):
    id: str
    # Only a display fallback. Normally leave empty: the name comes from
    # /v1/models on the server itself so nobody has to maintain it in two
    # places. If both are missing, the id is shown.
    name: str | None = None
    # Which model this endpoint means. Leave empty for a local server: it has
    # exactly one model loaded and reports it under /v1/models, so nothing has
    # to be maintained twice.
    #
    # Cloud providers are the other case. OpenAI answers the same question
    # with its entire catalogue — embeddings, speech, image models — and the
    # first entry is whatever it happens to be. Without this field the
    # terminal picked that one and offered an embedding model to chat with.
    modell: str | None = None
    provider: str = "openai_compatible"
    base_url: str
    health_path: str = "/models"
    reasoning_format: ReasoningFormat = "none"
    # Which parameters the server knows and what it calls them.
    # "llama_cpp" for llama-server, "mlx" for mlx_lm.server, "anthropic" for
    # the Messages API, "openai" for the rest and anything unknown.
    # See app/parameter.py.
    parameter_dialect: Literal["llama_cpp", "mlx", "openai", "anthropic"] = "openai"
    # Request usage data in the stream. Without this most servers send no
    # token counts, and the context display would stay empty.
    send_usage_option: bool = True
    # How many tokens fit into the context. Leave empty: the server is then
    # asked (llama.cpp answers this via /props). Only set it when the server
    # does not reveal it itself — e.g. mlx_lm.server.
    context_tokens: int | None = None
    # Endpoints set to false are never even checked and appear nowhere.
    # Meant for switching one off without losing the entry.
    enabled: bool = True
    # Access key for cloud providers (OpenAI and anything speaking its
    # interface). This NEVER holds the value itself, only the name of the
    # environment variable — exactly like the tool servers. The value belongs
    # in .env and is never versioned and never displayed.
    #
    #     api_key_env: "OPENAI_API_KEY"
    #
    # Leave empty for local servers: llama.cpp and mlx_lm want none.
    api_key_env: str | None = None
    # Where this endpoint runs. Purely for display: the model picker and the
    # settings mask group by it, so it is obvious at a glance whether a
    # request leaves the machine.
    #   local  runs on this computer, data never leaves it
    #   cloud  a paid service, data leaves the machine
    #   extra  an OpenAI-compatible side door of a vendor whose own protocol
    #          we do not speak (Anthropic, Gemini) - works, but is not their
    #          native interface
    group: Literal["local", "cloud", "extra"] = "local"
    capabilities: Capabilities = Field(default_factory=Capabilities)

    @field_validator("base_url")
    @classmethod
    def _kein_schrägstrich_am_ende(cls, wert: str) -> str:
        return wert.rstrip("/")


class AppConfig(BaseModel):
    # Loopback by schema default: a missing config file must never mean
    # "reachable by everyone on the network". Serving a whole machine or
    # LAN is a deliberate act — whoever means it writes 0.0.0.0 into
    # config.yaml themselves.
    host: str = "127.0.0.1"
    port: int = 8090
    language: str = "de"
    data_dir: str = "./data"
    log_dir: str = "./logs"
    # Where the pictures the generator draws are written. A field of its own
    # (not data_dir + "bilder" spelled out at each call site) so the storage
    # locations module (app/speicherorte.py) has one path to hand out and,
    # later, one path to let the user move. Empty means "under data_dir" — so
    # it follows a moved data folder exactly as the old datenverzeichnis/"bilder"
    # did, instead of a hardcoded path that would strand old pictures.
    bilder_verzeichnis: str = ""
    # Where the system prompt lives. Exactly one file for the whole program —
    # it is read fresh on every request and prepended to the history.
    # Deliberately a file and not a database field: the same place should
    # later also be readable by agents and the knowledge base.
    system_prompt_file: str = "./prompts/system.md"
    # The persistent memory (app/gedaechtnis.py) — a second prompt file beside
    # the first, written by the model and by hand, read fresh on every
    # request. Ships empty, like the system prompt.
    memory_file: str = "./prompts/memory.md"
    # Where the agents live (phase 6.3) — one Markdown file per agent,
    # front matter plus prompt. The folder ships empty.
    agenten_verzeichnis: str = "./prompts/agenten"
    # Skills (app/skills.py) live in two places. The shipped ones sit next to
    # the program and are replaced by every update; the user's sit next to
    # their prompts and are never touched. Same name in both: the user's wins.
    skills_mitgeliefert: str = "./skills"
    skills_verzeichnis: str = "./prompts/skills"
    # Where the model files live, and the program that runs them
    # (app/modellrunner.py). The folder is the boundary: only what lies in it
    # can be started. An empty `runner_programm` means "look for it" — in the
    # PATH first, because whoever put it somewhere of their own meant it.
    modelle_verzeichnis: str = "./data/modelle"
    runner_programm: str | None = None
    # Models that are not language models get folders of their own, and the
    # FOLDER is what says which kind a file is. Telling them apart by name
    # ("embed" somewhere in it) worked for one night and failed as soon as
    # somebody looked: an embedding model turned up in the language model's
    # picker, its start collided with the port the language server holds,
    # and "open model folder" led somewhere else than the file it was about.
    # A folder cannot be guessed wrong.
    einbettungsmodelle_verzeichnis: str = "./data/einbettungsmodelle"
    bildmodelle_verzeichnis: str = "./data/bildmodelle"
    # The embedding server is a small llama-server of its own, so it needs a
    # port of its own — the whole reason the first build collided.
    einbettung_port: int = 8081
    # Used when neither the request nor the chat specifies a response length.
    #
    # Without this value the model server's default applies, and for
    # mlx_lm.server that is 512 tokens. With a model that thinks at length,
    # those are used up before the actual answer begins — all that shows up
    # is an empty bubble.
    default_max_tokens: int = 8192
    # Time zone for the alarm clock (6.7), e.g. "Europe/Berlin". Times in the
    # agent front matter apply in this zone; if the entry is missing, the
    # server's time zone applies — on a UTC server "08:00" is then 08:00 UTC.
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _zeitzone_bekannt(cls, wert: str | None) -> str | None:
        # A single config value must never keep the program from starting. If
        # the zone cannot be resolved — a mistyped name, or a host without the
        # time-zone database — it is dropped with a warning instead of raising,
        # and the alarm clock falls back to the host zone (the same behaviour
        # as leaving the field empty).
        if wert is not None:
            from zoneinfo import ZoneInfo

            try:
                ZoneInfo(wert)
            except Exception:
                log.warning("Unknown time zone %r, falling back to host zone", wert)
                return None
        return wert

    @field_validator("port")
    @classmethod
    def _port_im_gueltigen_bereich(cls, wert: int) -> int:
        if not 1 <= wert <= 65535:
            raise ValueError(f"Port {wert} liegt außerhalb von 1-65535")
        return wert


class DatabaseConfig(BaseModel):
    backend: Literal["sqlite"] = "sqlite"
    path: str = "./data/exe-ai-terminal.db"


class FeatureFlags(BaseModel):
    mcp: bool = False
    # Beta: lock write-access settings. See app/beta.py — it also explains
    # why this is not mere cosmetics.
    #
    # Default OFF: a shipped installation must not be
    # locked out of the box, and the test suite builds its configuration
    # without config.yaml — with True as the default, 33 tests failed because
    # the latch kicked in there unintentionally. Turning it on happens
    # explicitly in config.yaml, not silently in the schema.
    beta_lock: bool = False
    document_upload: bool = False
    # The shell tool (app/tools/shell.py): lets the model run commands in the
    # folders the user shared with a chat. Shipped on, because the guard sits
    # in the tool itself: sharing a folder is the permission, without one it
    # stays shut, and any command reaching outside the share asks first.
    shell_tool: bool = True


class MCPConfig(BaseModel):
    """Where the MCP servers are registered.

    A separate file instead of a section in config.yaml, because the format
    matches what other programs use as well — an existing server list can be
    adopted without rewriting it.
    """

    servers_file: str = "./mcp_servers.json"
    # The rotating OAuth credentials of the hosted servers. Separate from the
    # server list (the user edits that one, the program edits this one) and
    # separate from .env (which holds FIXED keys — refreshing would keep
    # rewriting it at runtime). Permissions 0600, git-ignored.
    auth_file: str = "./data/mcp_auth.json"


class DiscoveryConfig(BaseModel):
    interval_seconds: int = 15
    timeout_seconds: int = 3


class LoggingConfig(BaseModel):
    level: str = "INFO"
    # "text" reads well in the journal, "json" is machine-parseable.
    format: Literal["text", "json"] = "text"
    # File name in the log directory. Empty = console (journal) only.
    file: str = "exe-ai-terminal.log"
    # Rotate at this size; this many old files are kept around.
    max_bytes: int = 10 * 1024 * 1024
    file_count: int = 5


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    endpoints: list[EndpointConfig] = Field(default_factory=list)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @field_validator("endpoints")
    @classmethod
    def _kennungen_eindeutig(cls, wert: list[EndpointConfig]) -> list[EndpointConfig]:
        gesehen: set[str] = set()
        for endpunkt in wert:
            if endpunkt.id in gesehen:
                raise ValueError(f"Endpunkt-Kennung '{endpunkt.id}' ist doppelt vergeben")
            gesehen.add(endpunkt.id)
        return wert

    # --- derived paths, always absolute ---------------------------------

    def pfad(self, relativ: str) -> Path:
        """A path from the configuration that belongs to the user.

        Packaged, this is the folder beside their other application data —
        never beside the program, which is read-only, and never relative to
        the working directory, which is whatever the desktop handed over.
        """
        return aufloesen(relativ, schreibbar=True).resolve()

    def mitgeliefert(self, relativ: str) -> Path:
        """A path to something that ships with the program and is only read.

        Separate from `pfad` because the two part company as soon as the
        program is packaged: an update replaces this and must not touch the
        other.
        """
        return aufloesen(relativ).resolve()

    @property
    def datenverzeichnis(self) -> Path:
        return self.pfad(self.app.data_dir)

    @property
    def logverzeichnis(self) -> Path:
        return self.pfad(self.app.log_dir)

    @property
    def skillverzeichnisse(self) -> tuple[Path, Path]:
        """The two skill folders, shipped first, the user's second.

        Always as a pair, because they are only ever meaningful together:
        the second one overrides the first, and asking for one without the
        other would give a wrong answer about which skill is in force.
        """
        return (
            self.mitgeliefert(self.app.skills_mitgeliefert),
            self.pfad(self.app.skills_verzeichnis),
        )

    @property
    def datenbankpfad(self) -> Path:
        return self.pfad(self.database.path)

    def endpunkt(self, kennung: str) -> EndpointConfig | None:
        for endpunkt in self.endpoints:
            if endpunkt.id == kennung:
                return endpunkt
        return None

    def system_prompt_lesen(self) -> str:
        """The system prompt, fresh from disk.

        Called on every request, not cached: a change to the file should take
        effect immediately, including in existing chats. That is the whole
        point of the rework — before, a copy sat in the chat and never saw
        later changes.

        If the file is missing, there simply is no prompt. That is the
        as-shipped state: whoever installs the program finds an empty field
        and fills in what they want themselves.
        """
        datei = self.pfad(self.app.system_prompt_file)
        if not datei.exists():
            return ""
        try:
            return datei.read_text(encoding="utf-8").strip()
        except OSError as fehler:
            log.warning("System-Prompt nicht lesbar (%s): %s", datei, fehler)
            return ""

    def memory_lesen(self) -> str:
        """The memory, fresh from disk — same rules as the system prompt.

        A missing file is not an error: that is the as-shipped state, and it
        is also what a user gets who deleted everything the program had
        learned about them.
        """
        datei = self.pfad(self.app.memory_file)
        if not datei.exists():
            return ""
        try:
            return datei.read_text(encoding="utf-8").strip()
        except OSError as fehler:
            log.warning("Gedächtnis nicht lesbar (%s): %s", datei, fehler)
            return ""

    def memory_schreiben(self, text: str) -> None:
        """Writes the memory back — side file first, then rename.

        The same care as with the system prompt, and here it matters more: an
        interrupted write would leave the program having forgotten half of
        what it knew, with nothing to say so.
        """
        datei = self.pfad(self.app.memory_file)
        datei.parent.mkdir(parents=True, exist_ok=True)
        neben = datei.with_suffix(datei.suffix + ".neu")
        neben.write_text(text.strip() + ("\n" if text.strip() else ""), encoding="utf-8")
        neben.replace(datei)

    def system_prompt_schreiben(self, text: str) -> None:
        """Writes the system prompt back to the file.

        First to a side file, then rename: if the write is interrupted, the
        old version stays intact instead of being left half overwritten.
        """
        datei = self.pfad(self.app.system_prompt_file)
        datei.parent.mkdir(parents=True, exist_ok=True)
        neben = datei.with_suffix(datei.suffix + ".neu")
        neben.write_text(text.strip() + ("\n" if text.strip() else ""), encoding="utf-8")
        neben.replace(datei)


def _umgebung_anwenden(rohdaten: dict) -> dict:
    """Allows targeted overrides from the environment (EXE_AI_*)."""
    app = rohdaten.setdefault("app", {})
    if port := os.getenv("EXE_AI_PORT"):
        app["port"] = int(port)
    if host := os.getenv("EXE_AI_HOST"):
        app["host"] = host
    if sprache := os.getenv("EXE_AI_LANGUAGE"):
        app["language"] = sprache
    if datenbank := os.getenv("EXE_AI_DB_PATH"):
        rohdaten.setdefault("database", {})["path"] = datenbank
    return rohdaten


def _erststart_kopie(ziel: Path, vorlage: Path) -> None:
    """Puts a shipped file into the user's folder, once.

    Files like the server list start as ours and become theirs the moment
    they edit one. Packaged, ours lies in a folder that an update replaces,
    so a copy has to move across before anybody writes into it — otherwise
    the first edit is gone with the next version.
    """
    if ziel.exists() or not vorlage.exists() or ziel == vorlage:
        return
    ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vorlage, ziel)
    log.info("Erststart: %s angelegt", ziel.name)


def config_laden(pfad: str | Path | None = None) -> Config:
    """Reads config.yaml (+ .env) and returns a validated configuration."""
    load_dotenv(PROJEKT_WURZEL / ".env", override=False)
    # Packaged, the user's .env lives in the writable folder next to
    # config.yaml — the project root inside the bundle is an ephemeral
    # extraction dir, so a key saved at runtime would vanish from the
    # environment on every restart if only the line above ran.
    load_dotenv(aufloesen(".env", schreibbar=True), override=False)

    # The configuration belongs to the user, so packaged it lives next to
    # their data and not inside the program, which is read-only.
    quelle = Path(pfad or os.getenv("EXE_AI_CONFIG") or aufloesen("config.yaml", schreibbar=True))

    # First start: config.yaml does not exist yet because it is not shipped -
    # it holds personal addresses and is git-ignored. What IS shipped is
    # config.example.yaml with commented examples. Copy it once, then the
    # file belongs to the user and is never touched again.
    # Only for the default location. If someone names a file explicitly and
    # it is missing, that is an error and must stay one - silently creating
    # a file at a path the caller chose would hide their typo.
    ausdruecklich = pfad is not None or os.getenv("EXE_AI_CONFIG")
    if not quelle.exists() and not ausdruecklich:
        vorlage = aufloesen("config.example.yaml")
        if vorlage.exists():
            shutil.copy2(vorlage, quelle)
            log.info("Erststart: %s aus %s angelegt", quelle.name, vorlage.name)

    _erststart_kopie(aufloesen("mcp_servers.json", schreibbar=True),
                     aufloesen("mcp_servers.json"))

    if not quelle.exists():
        raise FileNotFoundError(
            f"Konfigurationsdatei nicht gefunden: {quelle}. "
            "Vorlage liegt als config.example.yaml im Projektverzeichnis."
        )

    # Then the other direction: an existing file gets whatever the program
    # has learned since it was written. A setting only the schema knows about
    # is a setting nobody can find - see app/configwanderung.py. Runs before
    # the file is read, so the additions take effect the same start; it never
    # changes a value that is already there and never raises.
    wandern(quelle, aufloesen("config.example.yaml"), Config)

    rohdaten = yaml.safe_load(quelle.read_text(encoding="utf-8")) or {}
    return Config.model_validate(_umgebung_anwenden(rohdaten))


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Cached configuration for the running process."""
    return config_laden()

