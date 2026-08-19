/*
  All access to the API in one place.

  No component talks to the server on its own. That keeps error handling
  uniform and makes it easy to hook something in later — say, authentication
  once login arrives.
*/

const BASIS = '/api/v1'

/* The language the interface runs in. The browser's own header says the
   system language — whoever switched the app in the settings would get
   answers in the wrong one. Set once when the catalogue loads; a plain
   variable instead of an import, because the text module imports this one. */
let sprache = null

export function spracheMerken(neue) {
  sprache = neue
}

export class ApiFehler extends Error {
  constructor(nachricht, status) {
    super(nachricht)
    this.status = status
  }
}

async function ruf(pfad, optionen = {}) {
  const antwort = await fetch(BASIS + pfad, {
    headers: {
      ...(optionen.body ? { 'Content-Type': 'application/json' } : {}),
      ...(sprache ? { 'Accept-Language': sprache } : {}),
    },
    ...optionen,
  })
  if (!antwort.ok) {
    const daten = await antwort.json().catch(() => ({}))
    /* A validation error (422) carries `detail` as an array of objects —
       anything but a plain string would surface as "[object Object]". */
    let meldung = daten.detail
    if (Array.isArray(meldung)) meldung = meldung.map((f) => f?.msg ?? '').filter(Boolean).join('; ')
    if (typeof meldung !== 'string' || !meldung) meldung = `Fehler ${antwort.status}`
    throw new ApiFehler(meldung, antwort.status)
  }
  return antwort.status === 204 ? null : antwort.json()
}

const alsText = (wert) => JSON.stringify(wert)

/* The storage-location list is read by every folder row — the pictures
   module and the three server panels — which mount together. Share one
   in-flight request so their near-simultaneous reads collapse into a single
   call; it clears the moment it resolves, so a read after a change is always
   fresh, never a stale cache. */
let orteLauf = null

export const api = {
  /* `frisch` asks the server to knock on every candidate first — for the
     moment right after something was started or added, when the regular
     check has not come around yet. */
  modelle: (frisch = false) => ruf(frisch ? '/models?jetzt_pruefen=true' : '/models'),
  meta: () => ruf('/meta'),
  uebersetzungen: (sprache) => ruf(`/translations/${sprache}`),
  werkzeuge: () => ruf('/tools'),
  /* The command runs of a chat, and the stream that keeps them current. */
  laeufe: (chatId) => ruf(`/laeufe/${chatId}`),
  /* The notes and the document dock — the user's own pad beside the chat.
     Both live in the data folder, so they outlive a cleared browser. */
  /* The offline picture generator. `bildmodelle` looks at the data folder,
     `bildZeichnen` blocks for as long as the picture takes — half a minute
     is normal, so no caller may treat a slow answer as a hang. */
  bildmodelle: () => ruf('/bild/modelle'),
  /* The starting values a model opens on — class-aware, so an SDXL model
     comes back at 1024/28 and an SD-1.5 at 512/22. Asked whenever the
     chosen model changes. */
  bildVorgaben: (modell) => ruf(`/bild/vorgaben${modell ? `?modell=${encodeURIComponent(modell)}` : ''}`),
  bildordnerOeffnen: () => ruf('/bild/folder', { method: 'POST' }),
  bildZeichnenStoppen: () => ruf('/bild/stop', { method: 'POST' }),
  /* Open a companion sub-folder in the file manager so a hand-picked file can
     be dropped in. The picture side (vae/lora/adetailer) and the chat side
     (mtp/vision) each have their own whitelisted route. */
  bildBegleiterOrdner: (unter) => ruf(`/bild/begleiter-folder/${unter}`, { method: 'POST' }),
  chatBegleiterOrdner: (unter) => ruf(`/runner/begleiter-folder/${unter}`, { method: 'POST' }),
  /* The generator program itself — fetched once on machines without one. */
  bildProgrammHolen: () => ruf('/bild/programm', { method: 'POST' }),
  bildProgrammStand: () => ruf('/bild/programm'),
  /* Asks the loaded LANGUAGE model to rewrite a picture prompt in English.
     Nothing to do with the generator — it only happens to serve the same
     window. */
  /* The running picture's honest step counter — feeds the filling frame. */
  bildFortschritt: () => ruf('/bild/fortschritt'),

  bildPromptVerbessern: (prompt, negativ, endpointId) =>
    ruf('/bild/prompt', { method: 'POST', body: alsText({ prompt, negativ: negativ || '', endpoint_id: endpointId || null }) }),

  /* The embedding server: its own port, its own folder, its own buttons.
     Started and stopped independently of the language model's server —
     sharing either was the whole reason the first build collided. */
  einbettungAuskunft: () => ruf('/einbettungsserver'),
  einbettungProtokoll: () => ruf('/einbettungsserver/log'),
  einbettungStarten: (modell, port) =>
    ruf('/einbettungsserver/start', { method: 'POST', body: alsText({ modell, port: port ?? null }) }),
  einbettungStoppen: () => ruf('/einbettungsserver/stop', { method: 'POST' }),
  einbettungOrdnerOeffnen: () => ruf('/einbettungsserver/folder', { method: 'POST' }),

  /* The assets view: the saved pictures, and the storage locations behind
     them — one place to see what was drawn and to move where it is kept. */
  bilderListe: () => ruf('/bilder'),
  speicherorteLesen: () => {
    if (!orteLauf) orteLauf = ruf('/speicherorte').finally(() => { orteLauf = null })
    return orteLauf
  },
  // A change drops the shared in-flight read, so the very next read starts
  // fresh instead of joining a request begun before the change and handing
  // back the pre-change list.
  speicherortSetzen: (name, pfad) => {
    orteLauf = null
    return ruf(`/speicherorte/${name}`, { method: 'PUT', body: alsText({ pfad }) })
  },
  speicherortZuruecksetzen: (name) => {
    orteLauf = null
    return ruf(`/speicherorte/${name}`, { method: 'DELETE' })
  },
  speicherortOeffnen: (name) => ruf(`/speicherorte/${name}/folder`, { method: 'POST' }),

  /* Extended Workflow: the guardian's own small model. Its own routes for
     the same reason the embedding server has its own — two servers that
     must start independently. */
  eewAuskunft: () => ruf('/eew'),
  eewStarten: (modell) => ruf('/eew/start', { method: 'POST', body: alsText({ modell }) }),
  eewStoppen: () => ruf('/eew/stop', { method: 'POST' }),
  bildZeichnen: (daten) => ruf('/bild', { method: 'POST', body: alsText(daten) }),

  /* The guardian's findings for one chat. Nothing is created through
     here — findings arise in the run and arrive over the stream; this only
     fetches what is standing and throws one away. */
  befunde: (chatId) => ruf(`/guardian/${chatId}`),
  befundVerwerfen: (chatId, id) => ruf(`/guardian/${chatId}/${id}`, { method: 'DELETE' }),
  notizen: () => ruf('/notizen'),
  notizAnlegen: (daten) => ruf('/notizen', { method: 'POST', body: alsText(daten) }),
  notizAendern: (id, daten) => ruf(`/notizen/${id}`, { method: 'PUT', body: alsText(daten) }),
  notizLoeschen: (id) => ruf(`/notizen/${id}`, { method: 'DELETE' }),
  dockAlle: () => ruf('/notizen/dock/alle'),
  /* Raw bytes with the name as a parameter — same shape as the image and
     document uploads. */
  dockAblegen: (datei) =>
    ruf(`/notizen/dock?name=${encodeURIComponent(datei.name)}`, {
      method: 'POST',
      headers: { 'Content-Type': datei.type || 'application/octet-stream' },
      body: datei,
    }),
  dockEntfernen: (id) => ruf(`/notizen/dock/${id}`, { method: 'DELETE' }),
  dockAdresse: (id) => `${BASIS}/notizen/dock/${id}`,

  /* Shows a shared working folder in the file manager. */
  ordnerOeffnen: (chatId, pfad) =>
    ruf('/ordner/oeffnen', { method: 'POST', body: alsText({ chat_id: chatId, pfad }) }),
  laeufeStrom: (chatId) => `${BASIS}/laeufe/${chatId}/stream`,
  /* One command from the CLI module — same runner, folders and limits as
     the model's. */
  befehlAusfuehren: (chatId, command) =>
    ruf(`/laeufe/${chatId}/befehl`, { method: 'POST', body: alsText({ command }) }),
  skills: () => ruf('/skills'),
  skillsVerwaltung: () => ruf('/skills/verwaltung'),
  skillSchreiben: (name, inhalt) =>
    ruf('/skills', { method: 'POST', body: alsText({ name, inhalt }) }),
  skillAuto: (name, auto) =>
    ruf(`/skills/${encodeURIComponent(name)}`, { method: 'PATCH', body: alsText({ auto }) }),
  skillZuruecksetzen: (name) =>
    ruf(`/skills/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  // config.yaml and .env, editable in the settings mask.
  datei: (kennung) => ruf(`/dateien/${kennung}`),
  dateiSichern: (kennung, inhalt) =>
    ruf(`/dateien/${kennung}`, { method: 'PUT', body: alsText({ inhalt }) }),
  /* Raw bytes instead of multipart — the server wants it exactly this way. */
  bildHochladen: (datei) =>
    ruf('/images', { method: 'POST', headers: { 'Content-Type': datei.type }, body: datei }),
  /* Documents (4.1): raw bytes as well; the name travels along as a
     parameter because the server needs the extension — the type isn't
     reliably present in the Content-Type. */
  /* Adds a cloud provider: key into .env, endpoint into config.yaml. */
  anbieterHinzufuegen: (daten) =>
    ruf('/providers', { method: 'POST', body: alsText(daten) }),

  /* The model server on this machine: what is there, what runs, what it says.
     Fetching a model goes the same way — one button, no command. */
  runnerAuskunft: () => ruf('/runner'),
  runnerProtokoll: () => ruf('/runner/log'),
  runnerStarten: (daten) => ruf('/runner/start', { method: 'POST', body: alsText(daten) }),
  runnerStoppen: () => ruf('/runner/stop', { method: 'POST' }),
  /* A companion (mmproj/mtp) carries which model it belongs to and its
     role, so the service records the association in a manifest and the
     runner attaches it later without guessing from file names. */
  modellHolen: (
    repo, datei, ziel = null, gehoert_zu = null, rolle = null, art = 'chat',
    unterordner = null,
  ) =>
    ruf('/runner/download', {
      method: 'POST',
      body: alsText({ repo, datei, ziel, gehoert_zu, rolle, art, unterordner }),
    }),
  modellHolenStand: () => ruf('/runner/download'),
  modellHolenAbbrechen: () => ruf('/runner/download', { method: 'DELETE' }),

  /* Searches the model catalogue. Runs on our server, never in the page.
     `art` is one of the catalogue's three tabs — chat, einbettung, bild —
     and scopes the search to that kind alone. */
  modellSuche: (q, art, anzahl = 12) =>
    ruf(`/models/search?q=${encodeURIComponent(q)}&art=${art}&anzahl=${anzahl}`),
  /* The GGUF files of one found repository — what the download can finish. */
  modellDateien: (repo) => ruf(`/models/files?repo=${encodeURIComponent(repo)}`),
  /* The Hugging Face token: set once, never handed back out. */
  hfTokenStand: () => ruf('/models/token'),
  hfTokenSetzen: (token) => ruf('/models/token', { method: 'POST', body: alsText({ token }) }),
  /* Shows the model folder in the file manager. Always that one folder. */
  modellordnerOeffnen: () => ruf('/runner/folder', { method: 'POST' }),
  /* The model server itself — fetched once on machines without one. */
  serverProgrammHolen: () => ruf('/runner/programm', { method: 'POST' }),
  serverProgrammStand: () => ruf('/runner/programm'),

  /* Turns a file from the chat into a real file in a released folder. */
  erzeugnisAblegen: (daten) =>
    ruf('/outputs', { method: 'POST', body: alsText(daten) }),

  dokumentHochladen: (chatId, datei) =>
    ruf(
      `/documents?chat_id=${encodeURIComponent(chatId)}&name=${encodeURIComponent(datei.name)}`,
      { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: datei },
    ),
  bildAdresse: (name) => `${BASIS}/images/${name}`,
  /* Image-Turbo: the optional persistent picture server. Off by default;
     switched on from the plus menu, which then keeps the model loaded so
     every picture after the first skips the load. */
  turboStand: () => ruf('/bild/turbo'),
  turboStarten: (modell) => ruf('/bild/turbo/start', { method: 'POST', body: alsText({ modell }) }),
  turboStoppen: () => ruf('/bild/turbo/stop', { method: 'POST' }),
  werkzeugKonfiguration: () => ruf('/tools/config'),
  werkzeugKonfigurationSichern: (content) =>
    ruf('/tools/config', { method: 'PUT', body: alsText({ content }) }),

  /* The tile gallery: server entries in structured form, plus the browser
     sign-in. Same source of truth as the raw text field. */
  serverUebersicht: () => ruf('/tools/servers'),
  serverSchreiben: (name, daten) =>
    ruf(`/tools/servers/${encodeURIComponent(name)}`, { method: 'PUT', body: alsText(daten) }),
  serverEntfernen: (name) =>
    ruf(`/tools/servers/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  oauthStart: (daten) =>
    ruf('/tools/oauth/start', { method: 'POST', body: alsText(daten) }),
  oauthStatus: () => ruf('/tools/oauth/status'),
  oauthVergessen: (server) =>
    ruf(`/tools/oauth/${encodeURIComponent(server)}`, { method: 'DELETE' }),

  systemPrompt: () => ruf('/system-prompt'),
  systemPromptSichern: (text) =>
    ruf('/system-prompt', { method: 'PUT', body: alsText({ text }) }),
  /* The memory (app/gedaechtnis.py) — a second prompt file, same shape. */
  gedaechtnis: () => ruf('/memory'),
  gedaechtnisSichern: (text) =>
    ruf('/memory', { method: 'PUT', body: alsText({ text }) }),

  /* The system's folder dialog. The browser never hands
     out a real path — the service opens Finder or Explorer instead and
     returns one. `pfad: null` in the answer means the user cancelled; the
     UI treats that as nothing happening, not as an error. */
  ordnerDialogAuskunft: () => ruf('/filesystem/folder-dialog'),
  ordnerDialogOeffnen: (titel, start) =>
    ruf('/filesystem/choose-folder', { method: 'POST', body: alsText({ titel, start }) }),

  /* Settings across their scopes. `aufgeloest` gives what actually applies
     plus where each value comes from; `setzen` writes one scope. `null` as a
     value removes the entry and lets the scope above take over. */
  einstellungAufgeloest: (schluessel, { modell, chat } = {}) => {
    const frage = new URLSearchParams()
    if (modell) frage.set('modell', modell)
    if (chat) frage.set('chat', chat)
    const anhang = frage.toString()
    return ruf(`/settings/resolved/${schluessel}` + (anhang ? `?${anhang}` : ''))
  },
  einstellungSetzen: (bereich, schluessel, wert) =>
    ruf(`/settings/${encodeURIComponent(bereich)}/${schluessel}`, {
      method: 'PUT',
      body: alsText({ wert }),
    }),

  chats: (suche) => ruf('/chats' + (suche ? `?suche=${encodeURIComponent(suche)}` : '')),
  chatAnlegen: (daten) => ruf('/chats', { method: 'POST', body: alsText(daten) }),
  chatAendern: (id, daten) => ruf(`/chats/${id}`, { method: 'PATCH', body: alsText(daten) }),
  chatLoeschen: (id) => ruf(`/chats/${id}`, { method: 'DELETE' }),

  nachrichten: (id) => ruf(`/chats/${id}/messages`),
  nachrichtLoeschen: (chatId, id) => ruf(`/chats/${chatId}/messages/${id}`, { method: 'DELETE' }),

  abbrechen: (generationId) =>
    ruf('/chat/stop', { method: 'POST', body: alsText({ generation_id: generationId }) }),

  /* Answer to the confirmation prompt before a tool runs. Goes over its own
     connection — the event stream is one-way only, nothing can be sent back
     through it. */
  /* Answers a waiting tool call: the yes or no before a tool runs, or —
     with `antwort` — what the user replied to the model's own question. */
  werkzeugBestaetigen: (generationId, aufrufId, erlaubt, antwort = null) =>
    ruf('/chat/confirm', {
      method: 'POST',
      body: alsText({
        generation_id: generationId,
        aufruf_id: aufrufId,
        erlaubt,
        ...(antwort === null ? {} : { antwort }),
      }),
    }),

  /* Agents and jobs (6.5/6.6). `agentDateien` also lists broken ones —
     a file that shows up nowhere could never be repaired. */
  agenten: () => ruf('/agents'),
  agentDateien: () => ruf('/agent-files'),
  agentDatei: (name) => ruf(`/agents/${encodeURIComponent(name)}`),
  agentSichern: (name, content) =>
    ruf(`/agents/${encodeURIComponent(name)}`, { method: 'PUT', body: alsText({ content }) }),
  agentLoeschen: (name) => ruf(`/agents/${encodeURIComponent(name)}`, { method: 'DELETE' }),

  auftraege: () => ruf('/jobs'),
  auftragStarten: (daten) => ruf('/jobs', { method: 'POST', body: alsText(daten) }),
  auftrag: (id) => ruf(`/jobs/${id}`),
  auftragAbbrechen: (id) => ruf(`/jobs/${id}/cancel`, { method: 'POST' }),
  auftragLoeschen: (id) => ruf(`/jobs/${id}`, { method: 'DELETE' }),
}

/*
  Fetch the answer and deliver it piece by piece.

  Returns an asynchronous stream of events, just as the server sends them:
  start, reasoning, content, tool_call, tool_result, stats, error, done.
  The caller decides what to display from it.

  The AbortController is handed in from outside so the stop button can
  really close the connection — that's what makes the model server stop
  computing.
*/
export async function* antwortStrom(koerper, signal) {
  const antwort = await fetch(`${BASIS}/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: alsText(koerper),
    signal,
  })
  if (!antwort.ok) {
    const daten = await antwort.json().catch(() => ({}))
    /* A validation error (422) carries `detail` as an array of objects —
       anything but a plain string would surface as "[object Object]". */
    let meldung = daten.detail
    if (Array.isArray(meldung)) meldung = meldung.map((f) => f?.msg ?? '').filter(Boolean).join('; ')
    if (typeof meldung !== 'string' || !meldung) meldung = `Fehler ${antwort.status}`
    throw new ApiFehler(meldung, antwort.status)
  }

  const leser = antwort.body.getReader()
  const dekoder = new TextDecoder()
  let rest = ''

  while (true) {
    const { done, value } = await leser.read()
    if (done) break
    rest += dekoder.decode(value, { stream: true })
    const teile = rest.split('\n\n')
    rest = teile.pop()
    for (const roh of teile) {
      if (!roh.startsWith('data:')) continue
      try {
        yield JSON.parse(roh.slice(5))
      } catch {
        // A broken packet must not tear down the stream.
      }
    }
  }
}
