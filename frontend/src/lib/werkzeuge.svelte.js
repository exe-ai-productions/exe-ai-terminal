/*
  The tools: which ones a source offers, which of them were picked, and which
  of those are switched on right now.

  Its own module for the same reason the models have one: the window is not
  the place to decide what a tool is, and the connections gallery has no
  business knowing it at all.

  Two separate things live here, and they are stored in two different places
  on purpose:

    gewaehlt  WHICH of a server's tools exist for us. Stored in
              mcp_servers.json as `allowed_tools`, because the registry has to
              hold that line while it is starting — long before a window is
              open. One server reports nineteen tools; nobody ordered that.

    an / aus  Which of the picked ones go to the model right now. Stored in
              the settings cascade as `werkzeuge_aus` — the negative again, so
              a tool a server newly offers is simply there instead of hiding
              until somebody remembers to allow it.

  Keeping them apart is what lets a tool be silenced for an afternoon without
  losing the pick behind it.

  The built-in tool is its own source. It has no catalogue to pick from — it
  is either there or the feature is off — but it takes the switch like every
  other, and the registry refuses it just the same.
*/

import { api } from './api.js'
import { serverTitel } from './serverkatalog.js'

/* What is switched OFF. Same key the server checks — app/werkzeugwahl.py. */
const SCHLUESSEL_AUS = 'werkzeuge_aus'

/* The built-in tools name their own source: `shell`, `memory`. Anything
   whose source is not among the MCP servers is one of them — asking that way
   round means a third built-in shows up by itself instead of vanishing,
   which is exactly what happened when this said `=== 'shell'`.

   The label comes from the catalogue where we have a word for it; otherwise
   the raw name stands, because inventing one would be guessing. */
export const EINGEBAUTE_NAMEN = {
  shell: 'werkzeuge.eingebaut',
  memory: 'gedaechtnis.quelle',
  skills: 'skills.quelle',
}

export const werkzeugwahl = $state({
  aus: [],
  /* GET /tools — what the registry currently approves, with descriptions. */
  freigegeben: [],
  /* GET /tools/servers — the entries with their full catalogue. */
  server: [],
  geladen: false,
})

export async function werkzeugeLaden() {
  const [uebersicht, server, aus] = await Promise.all([
    api.werkzeuge().catch(() => null),
    api.serverUebersicht().catch(() => []),
    api.einstellungAufgeloest(SCHLUESSEL_AUS).catch(() => null),
  ])
  werkzeugwahl.freigegeben = uebersicht?.werkzeuge ?? []
  werkzeugwahl.server = Array.isArray(server) ? server : []
  werkzeugwahl.aus = Array.isArray(aus?.wert) ? aus.wert : []
  werkzeugwahl.geladen = true
}

/* ——— The catalogue: what exists for us at all ——— */

/** Is this tool of the server's picked at all? `null` means: all of them. */
export function istGewaehlt(server, name) {
  return server.allowed_tools === null || server.allowed_tools.includes(name)
}

export async function katalogSchalten(server, name, gewaehlt) {
  const alle = (server.alle_werkzeuge ?? []).map((w) => w.name)
  const bisher = server.allowed_tools === null ? alle : server.allowed_tools
  const neu = gewaehlt
    ? [...new Set([...bisher, name])]
    : bisher.filter((n) => n !== name)
  await katalogSichern(server, neu)
}

/** The "pick all" of a catalogue — and its counterpart, with an empty list. */
export async function katalogAlle(server, alle) {
  await katalogSichern(server, alle ? (server.alle_werkzeuge ?? []).map((w) => w.name) : [])
}

async function katalogSichern(server, namen) {
  /* Always write the explicit list — only whoever never unpicked keeps
     "everything". That way a provider cannot quietly deliver more later. */
  await api.serverSchreiben(server.name, { allowed_tools: namen })
  await werkzeugeLaden()
}

/* ——— The switch: which of them travel right now ——— */

export function istAn(name) {
  return !werkzeugwahl.aus.includes(name)
}

export async function schalten(name, an) {
  const vorher = werkzeugwahl.aus
  const neu = an
    ? vorher.filter((n) => n !== name)
    : [...new Set([...vorher, name])]
  werkzeugwahl.aus = neu
  try {
    await api.einstellungSetzen('global', SCHLUESSEL_AUS, neu.length ? neu : null)
  } catch {
    /* Put it back rather than showing a state that was never stored. */
    werkzeugwahl.aus = vorher
  }
}

/* ——— Who delivers what ——— */

/** What the registry knows about one tool: description and confirmation. */
function freigabe(name) {
  return werkzeugwahl.freigegeben.find((w) => w.name === name) ?? null
}

/**
 * The sources, each with the tools picked from it.
 *
 * Built-in first: it is the one that works without anybody connecting
 * anything. Then the servers in the order the API reports them, which is by
 * name — a gallery sorts by state, a list of names does not need to.
 */
export function quellen() {
  const liste = []

  /* Grouped by source, and every source the MCP list does not know is a
     built-in one. Built-in sources come first: they are the ones that work
     without anybody connecting anything. */
  const vonServern = new Set(werkzeugwahl.server.map((s) => s.name))
  const eigene = new Map()
  for (const werkzeug of werkzeugwahl.freigegeben) {
    if (vonServern.has(werkzeug.server)) continue
    if (!eigene.has(werkzeug.server)) eigene.set(werkzeug.server, [])
    eigene.get(werkzeug.server).push({ ...werkzeug, quelle: werkzeug.server })
  }
  for (const [quelle, werkzeuge] of eigene) {
    liste.push({
      id: quelle,
      name: quelle,        // the window translates it where we have a word
      eingebaut: true,
      laeuft: true,
      katalog: [],         // nothing to pick from: it is there or it is not
      werkzeuge,
    })
  }

  for (const server of werkzeugwahl.server) {
    const alle = server.alle_werkzeuge ?? []
    liste.push({
      id: server.name,
      name: serverTitel(server.name),
      eingebaut: false,
      laeuft: server.laeuft,
      enabled: server.enabled,
      eintrag: server,
      katalog: alle.map((w) => ({ id: w.name, name: w.name, beschreibung: w.beschreibung })),
      werkzeuge: alle
        .filter((w) => istGewaehlt(server, w.name))
        .map((w) => ({
          name: w.name,
          beschreibung: w.beschreibung,
          quelle: server.name,
          needs_confirmation: freigabe(w.name)?.needs_confirmation ?? false,
        })),
    })
  }

  return liste
}

/** How many tools actually reach the model — the number under the title. */
export function anzahlAn() {
  return quellen()
    .filter((q) => q.laeuft)
    .reduce((summe, q) => summe + q.werkzeuge.filter((w) => istAn(w.name)).length, 0)
}
