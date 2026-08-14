-- Exe AI Terminal — database schema (SQLite)
--
-- Timestamps are stored as ISO 8601 in UTC (text), so they are sortable
-- and independent of the server's time zone.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER NOT NULL,
    applied_at TEXT    NOT NULL
);

-- Chats -------------------------------------------------------------------
-- user_id is there from day one, so that a later login becomes an upgrade
-- and not a rebuild. Until then it holds a fixed value.
-- The title may contain anything the user types, including emoji.
-- SQLite stores text as UTF-8; composite characters like 👨‍👩‍👧‍👦 survive
-- saving, reading, and searching unchanged.
CREATE TABLE IF NOT EXISTS chats (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    title         TEXT NOT NULL,
    endpoint_id   TEXT,
    pinned        INTEGER NOT NULL DEFAULT 0,
    -- Suspends the system prompt for exactly this chat. The prompt itself
    -- lives in a file and otherwise always applies; only the "no" is here.
    prompt_aus    INTEGER NOT NULL DEFAULT 0,
    -- This chat's working folders as a JSON list: folders somewhere on the
    -- machine the model is allowed to work in — like `cd` in a real terminal.
    -- The first is the working directory commands run in, the others are
    -- additional sources; four at most. Set by the user, never by the model.
    -- NULL means: none chosen.
    working_dirs  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- Pinned first, then the most recently used.
CREATE INDEX IF NOT EXISTS idx_chats_user_updated
    ON chats (user_id, pinned DESC, updated_at DESC);

-- Settings ------------------------------------------------------------------
-- One table for every setting, instead of one column per knob. The scope says
-- how far a value reaches; the resolution goes from general to specific and
-- the last value that is actually set wins:
--
--     default (config.yaml)  →  global  →  modell:<id>  →  chat:<id>
--
-- `bereich` is 'global', 'modell:<endpoint_id>' or 'chat:<chat_id>'.
-- `schluessel` names the setting ('parameter', 'denken', 'werkzeuge_aus' …),
-- `wert_json` holds its value. Checking belongs in the code — a JSON column
-- cannot do it (for parameters: app/parameter.py).
--
-- Why one table and not one per kind: a new setting is a new row here, not a
-- schema change. And everything lives on the server, so the values are the
-- same on every device — settings kept in browser storage were a different
-- truth on each machine.
CREATE TABLE IF NOT EXISTS einstellungen (
    bereich    TEXT NOT NULL,
    schluessel TEXT NOT NULL,
    wert_json  TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (bereich, schluessel)
);

-- Chat scopes disappear with their chat.
CREATE INDEX IF NOT EXISTS idx_einstellungen_bereich
    ON einstellungen (bereich);

-- Messages ----------------------------------------------------------------
-- reasoning is kept separate from the content, because in the UI the chain
-- of thought is its own collapsible element and must not be copied along.
-- stats_json holds metrics (tokens/second, duration, token count).
CREATE TABLE IF NOT EXISTS messages (
    id         TEXT NOT NULL PRIMARY KEY,
    chat_id    TEXT NOT NULL REFERENCES chats (id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content    TEXT NOT NULL,
    reasoning  TEXT,
    stats_json TEXT,
    -- Filename of an attached image under data/bilder/ (vision).
    bild       TEXT,
    -- id of an attached document (4.1) — text and facts in documents.
    dokument   TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_created
    ON messages (chat_id, created_at);

-- Documents ---------------------------------------------------------------
-- Prepared for per-chat upload (phase 4.1). extracted_text is the already
-- extracted plain text that goes to the model as context.
CREATE TABLE IF NOT EXISTS documents (
    id             TEXT PRIMARY KEY,
    chat_id        TEXT NOT NULL REFERENCES chats (id) ON DELETE CASCADE,
    filename       TEXT NOT NULL,
    mime_type      TEXT,
    size_bytes     INTEGER,
    extracted_text TEXT,
    -- Page count (PDF only) and whether the text was truncated at the limit (4.1).
    pages          INTEGER,
    truncated      INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_chat
    ON documents (chat_id, created_at);

-- Document sections ------------------------------------------------------
-- A document past the threshold does not travel whole anymore: it is cut
-- into overlapping sections, each with its vector, and a question carries
-- only the sections that fit it. The vector is a blob of single-precision
-- floats (see app/einbettung.py) — a float per column would be 768 columns,
-- and JSON would be three times the bytes for the same numbers.
--
-- Hangs off the document, so deleting the document takes its sections with
-- it and no orphan vector is ever searched.
-- `modell` is the name of the embedding model the vector came out of. Two
-- models produce numbers that cannot be compared, and nothing in the numbers
-- themselves says so: same length, same range, similarities that sort into a
-- plausible-looking order and mean nothing. The name is the only thing that
-- can tell them apart, so it is stored beside every vector and checked before
-- anything is compared.
CREATE TABLE IF NOT EXISTS dokument_abschnitte (
    id          TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    nummer      INTEGER NOT NULL,
    text        TEXT NOT NULL,
    vektor      BLOB NOT NULL,
    modell      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_abschnitte_dokument
    ON dokument_abschnitte (document_id, nummer);

-- Jobs --------------------------------------------------------------------
-- A job is one run of an agent (phase 6). It lives alongside the chats:
-- its own list, its own states, its own log. `wartet` means: the run is
-- stopped at a confirmation prompt and remains answerable — even across a
-- restart of the service. Only `laeuft` becomes `unterbrochen` at startup,
-- because the associated background task no longer exists after a restart.
CREATE TABLE IF NOT EXISTS auftraege (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    -- Name of the agent file (prompts/agenten/<agent>.md), without extension.
    agent         TEXT NOT NULL,
    -- The job text, exactly as it was given to the agent.
    auftrag       TEXT NOT NULL,
    zustand       TEXT NOT NULL CHECK (zustand IN
                  ('laeuft', 'wartet', 'fertig', 'abgebrochen',
                   'gescheitert', 'unterbrochen')),
    -- Every ending carries a readable reason (6.4): a stable key such as
    -- 'zeitgrenze' or 'dienst_neustart', which the interface translates.
    ende_grund    TEXT,
    -- The report the agent checks in with at the end.
    ergebnis      TEXT,
    endpoint_id   TEXT,
    -- Identifier of the running in-memory run, as long as one exists. After
    -- a restart it points at nothing and is cleared during cleanup.
    generation_id TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auftraege_user_updated
    ON auftraege (user_id, updated_at DESC);

-- Steps of a job ------------------------------------------------------------
-- The log: a run always records — every step, every tool call, every
-- result — regardless of where else the agent stores things.
-- `nummer` counts from 1 per job.
CREATE TABLE IF NOT EXISTS auftrag_schritte (
    id         TEXT PRIMARY KEY,
    auftrag_id TEXT NOT NULL REFERENCES auftraege (id) ON DELETE CASCADE,
    nummer     INTEGER NOT NULL,
    typ        TEXT NOT NULL,
    inhalt     TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auftrag_schritte_auftrag
    ON auftrag_schritte (auftrag_id, nummer);
