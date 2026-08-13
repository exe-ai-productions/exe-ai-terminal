/*
  Which mark belongs to which tool — the catalogue.

  Its own module, because the answer must be the same everywhere it is asked
  (chat row, job log, tool overview) and because the rule is data, not markup.

  Three steps, from certain to uncertain:

  1. THE TOOL BY NAME. An exact entry always wins. This is where a tool goes
     that deserves its own mark regardless of where it comes from.

  2. THE SERVER. Every tool the registry offers knows which server it came
     from, and that name is fixed in mcp_servers.json — it cannot be guessed
     wrong. A tool of the Notion server gets the Notion mark, whatever it is
     called. This is the step that makes the catalogue reliable instead of
     clever: a new server tool that nobody has seen yet still lands right.

  3. THE NAME PATTERN. Only for what arrives without a known server — a tool
     from a server someone registered by hand. Order matters here, because
     `search_repositories` and `model_search` both contain "search".

  Whatever survives all three keeps the gray chevron. That is the honest
  answer, not a placeholder to be forgotten: an unknown tool should look
  unknown.
*/

/* Step 1 — by tool name. */
const NACH_WERKZEUG = {
  web_search: 'globus',
  read_webpage: 'globus',
  run_command: 'eingabe',
  generate_image: 'bild',
  image_to_image: 'bild',
  inpaint_image: 'bild',
  remove_background: 'freistellen',
  memory_save: 'wolke',
}

/* Step 2 — by server, the name from mcp_servers.json. The one entry a new
   server needs; without it its tools fall through to the patterns. */
const NACH_SERVER = {
  shell: 'eingabe',
  memory: 'wolke',
  skills: 'buch',
  websuche: 'globus',
  searxng: 'globus',
  notion: 'seite',
  recraft: 'bild',
  github: 'verzweigung',
  gmail: 'brief',
  figma: 'flaechen',
  huggingface: 'paket',
}

/* Step 3 — by name pattern, for tools whose server we do not know. */
const NACH_MUSTER = [
  [/^(API-|notion-)/, 'seite'],
  [/^(gmail|.*_(email|draft))|(^|_)(send_message|messages?_(send|list|get)|threads?_)/, 'brief'],
  [/(repo|issue|pull_request|commit|branch|gist|workflow|fork)/, 'verzweigung'],
  [/(figma|design_context|node|frame)/, 'flaechen'],
  [/(model|dataset|paper|space)_?(search|detail|info|list)/, 'paket'],
]

export const RUECKFALL = 'winkel'

/**
 * The mark for a tool.
 *
 * `server` is what makes this dependable — pass it whenever it is known.
 * Without it the catalogue still answers, just with less certainty.
 */
export function zeichenFuer(name = '', server = '') {
  if (NACH_WERKZEUG[name]) return NACH_WERKZEUG[name]
  if (server && NACH_SERVER[server]) return NACH_SERVER[server]
  for (const [muster, zeichen] of NACH_MUSTER) {
    if (muster.test(name)) return zeichen
  }
  return RUECKFALL
}

/** Which servers the catalogue knows — for the preview page and for tests. */
export function bekannteServer() {
  return Object.keys(NACH_SERVER)
}
