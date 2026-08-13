<p align="center">
  <img src="docs/logo.svg" width="110" alt="Exe AI Terminal mark">
</p>

<h1 align="center">Exe AI Terminal</h1>

<p align="center">
  An AI agent harness you operate entirely from its window — and all data
  stays on your PC.
</p>

<p align="center">
  <a href="https://github.com/exe-ai-productions/exe-ai-terminal/releases/latest"><b>Download the latest release</b></a>
  ·
  <a href="#quick-start">Quick start</a>
  ·
  <a href="#privacy-stance">Privacy</a>
</p>

---

Download a model, start it, talk to it, hand your agents tools and
schedules — nothing ever needs a terminal or a config file. Local models
are the normal case, not the exception; cloud providers are one key away,
and nothing leaves your machine unless you set that up yourself.

![The empty chat greeting its user by name, with the wordmark and input centred](docs/chat.png)

## What it does

- **It knows who it works for.** The first start grows a small welcome
  window straight out of the wordmark: what to call you (your system
  already suggests it), your language, light or dark. From then on the
  empty chat greets you by name and time of day — and one switch rules
  both the greeting and the single prompt line that lets your models
  address you. Off means off, everywhere.
- **Local models, end to end.** A curated catalogue of GGUF models sized
  to your machine's memory, a Hugging Face search, a one-button download
  and a built-in `llama-server` runner. Fetch, start, chat — no shell, no
  scripts.
- **Real maker marks.** Catalogue cards and every search hit carry the
  original vendor vector of their model family — Qwen, DeepSeek, Mistral,
  Meta, Microsoft, OpenAI, NVIDIA, IBM and more. Never redrawn, never
  guessed: a mark only appears when the original exists.
- **A fully integrated persistent memory.** The agent learns your working
  style over time and improves alongside you — it saves memories on its
  own and retrieves them on demand. The same applies to tools and skills.
- **Cloud providers when you want them.** Anthropic, OpenAI or any
  OpenAI-compatible endpoint. The API key goes into a local file with
  tight permissions and is never displayed again — the interface only
  ever learns *whether* a key is set.
- **Chats with history**, stored in a local SQLite database. Rename, pin,
  search, delete — it is your data, on your disk.
- **Agents and jobs.** Reusable agent files (Markdown with front matter),
  one-off or scheduled runs, with a step-by-step log and a final report.
- **Tools via MCP.** The built-in exe-websearch and a shell tool ship
  with the program; any MCP server can be added. Sources fold open and
  closed in one quiet list, and tools that reach outside ask first.
- **A shipped base prompt.** The program carries fixed operating
  instructions for the model: report only what tool calls really
  returned, treat everything a tool brings back as data rather than
  orders — a web page cannot re-instruct the assistant — and do what was
  asked, not more. Your own system prompt sits on top and shapes tone and
  character; it never has to fight the machinery.
- **Documents and images.** PDF/TXT/MD upload into the conversation,
  image input for vision models, image generation through ComfyUI or an
  OpenAI-compatible image endpoint.
- **An interface that stays out of the way.** Windows take turns instead
  of stacking, lists melt at their edges instead of cutting rows, and the
  sidebar seam drags to the width you like — and remembers it.
- **Two languages.** English and German, switchable at runtime —
  including every error message the service produces.

![The curated catalogue: fitted cards with real maker marks, plus a search across Hugging Face](docs/katalog.png)

![The tools window: sources folded into one quiet list, one unfolded](docs/werkzeuge.png)

## Privacy stance

The service binds to `127.0.0.1`. Chats, settings, keys and models live in
local files and a local database. The optional memory feature sends its
content to cloud providers only if you switch that on, and the same
honesty applies to your name: it sits in the local settings store, and the
one switch that shares it with your models says so in plain words. Model
downloads talk to `huggingface.co` directly; the model search runs through
the service so your browser never contacts a third party.

## Quick start

### Packaged (macOS)

Grab the `.dmg` from the
[latest release](https://github.com/exe-ai-productions/exe-ai-terminal/releases/latest),
drag the app into `Applications`, open it. The service starts with the
window and everything above applies out of the box.

### From source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.example.yaml config.yaml   # optional: port, language, endpoints
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8090
```

Then open `http://127.0.0.1:8090/app/`.

To run local models, install [llama.cpp](https://github.com/ggml-org/llama.cpp)
(`brew install llama.cpp` on macOS, prebuilt releases exist for Windows and
Linux). The interface finds `llama-server` on its own.

### Self-contained build

`deploy/exe-ai-terminal.spec` builds a single self-contained file with
PyInstaller — no Python required on the target machine:

```bash
.venv/bin/pyinstaller deploy/exe-ai-terminal.spec
```

Double-clicking the result starts the service and opens the browser; a
second start just brings the window back.

### Docker

```bash
docker compose up
```

## Configuration

`config.example.yaml` is version-controlled and serves as the template:
copy it to `config.yaml` — your personal, unversioned copy — and adjust
port, language, feature flags and candidate endpoints there. Secrets
belong in `.env`, which never ends up in the repository. Everything else —
providers, models, tools, agents — can be set up from the interface.

Which endpoints are actually reachable is decided at runtime by a health
check; the list in the file is only the set of candidates.

## API

The frontend talks to a plain HTTP API, which you can use directly.

| Address | Purpose |
|---|---|
| `/health` | Service status (fixed address for monitoring) |
| `/api/v1/meta` | Features, languages, version |
| `/api/v1/models` | Reachable endpoints with their reported model names |
| `/api/v1/chats` | Create, list, rename, delete chats |
| `/api/v1/chat/completions` | Generate a response (Server-Sent Events) |
| `/api/v1/tools` | Available tools (MCP) |
| `/api/v1/agents`, `/api/v1/jobs` | Agents and their runs |
| `/docs` | Interactive API documentation |

## Project layout

```
app/          FastAPI service: providers, discovery, tools, agents, db
app/locales/  Translation catalogs (EN is the source, DE the translation)
frontend/     Svelte 5 source of the interface (Vite)
static/       Served files, including the built frontend
mcp/          Bundled MCP servers (web search)
deploy/       PyInstaller spec and systemd unit
tests/        pytest suite — run with .venv/bin/pytest
```

## Tests

```bash
.venv/bin/pytest
```

## License

[PolyForm Noncommercial 1.0.0](LICENSE.md) — in plain words: use it, change
it and share it freely for anything personal, educational or otherwise
noncommercial. Using it commercially — in a company, for paid work — needs
a commercial license: write to dev@exe-hq.net.
