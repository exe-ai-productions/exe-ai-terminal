/*
  The command line as a module in the window.

  It was a separate program once. That program is gone: it duplicated the
  service's whole surface for a second front end that nobody could see, and
  its input line was where it broke. This one is a panel in the rail — it
  speaks the same HTTP API the rest of the interface speaks, so there is one
  service and one truth about it.

  It is deliberately NOT a terminal emulator. No PTY, no vim, no REPL. Those
  belong in the system's terminal, and the help text says so. What it is: a
  fast way to switch models, look at state, and fire one shell command
  without dictating it to a model first.

  Independent of the model on purpose: every command here is its own request
  to the service, so `/modelle` answers while an answer is still streaming.
*/

import { api } from './api.js'
import { t } from './texte.svelte.js'
import { modellWaehlen, zustand } from './zustand.svelte.js'

export const cli = $state({
  /* [{ art: 'eingabe' | 'ausgabe' | 'fehler', text }] */
  proChat: {},
  /* What was typed before, newest last — arrow up walks back through it. */
  verlauf: [],
  laeuft: false,
})

export function zeilenVon(chatId) {
  return cli.proChat[chatId] ?? []
}

function schreiben(chatId, art, text) {
  const liste = [...zeilenVon(chatId), { art, text: String(text ?? '') }]
  /* A CLI panel is not an archive: what scrolled far enough out of sight is
     not worth the memory. */
  cli.proChat[chatId] = liste.slice(-300)
}

/* ——— The commands ——— */

const BEFEHLE = {
  async hilfe() {
    return t('cli.hilfe_text')
  },

  async modelle() {
    const liste = await api.modelle()
    if (!liste.length) return t('cli.keine_modelle')
    return liste
      .map((m) => {
        const marke = m.id === zustand.modellId ? '*' : ' '
        const stand = m.erreichbar ? t('cli.bereit') : t('cli.offline')
        return `${marke} ${m.id}  —  ${stand}`
      })
      .join('\n')
  },

  async modell(rest) {
    const kennung = rest.trim()
    if (!kennung) return t('cli.modell_fehlt')
    const liste = await api.modelle()
    const treffer = liste.find((m) => m.id === kennung)
      || liste.find((m) => m.id.includes(kennung))
    if (!treffer) return t('cli.modell_unbekannt', { name: kennung })
    modellWaehlen(treffer.id)
    return t('cli.modell_gewaehlt', { name: treffer.id })
  },

  async server(rest) {
    const was = rest.trim()
    if (was === 'stop') {
      await api.runnerStoppen()
      return t('cli.server_gestoppt')
    }
    if (was === 'start') {
      const auskunft = await api.runnerAuskunft()
      const modell = auskunft?.modelle?.[0]?.datei
      if (!modell) return t('cli.kein_lokales_modell')
      await api.runnerStarten({ datei: modell })
      return t('cli.server_gestartet', { name: modell })
    }
    const auskunft = await api.runnerAuskunft()
    return auskunft?.laeuft
      ? t('cli.server_laeuft', { name: auskunft.modell || '?' })
      : t('cli.server_aus')
  },

  async werkzeuge(rest) {
    const teile = rest.trim().split(/\s+/).filter(Boolean)
    const uebersicht = await api.werkzeuge()
    const alle = uebersicht?.werkzeuge ?? []
    if (!teile.length) {
      if (!alle.length) return t('cli.keine_werkzeuge')
      const aus = (await api.einstellungAufgeloest('werkzeuge_aus').catch(() => null))?.wert ?? []
      return alle
        .map((w) => `${aus.includes(w.name) ? ' ' : '*'} ${w.name}  —  ${w.server}`)
        .join('\n')
    }
    const [schalter, name] = teile
    if (!name || !['an', 'aus', 'on', 'off'].includes(schalter)) return t('cli.werkzeug_syntax')
    const an = schalter === 'an' || schalter === 'on'
    const aus = (await api.einstellungAufgeloest('werkzeuge_aus').catch(() => null))?.wert ?? []
    const neu = an ? aus.filter((n) => n !== name) : [...new Set([...aus, name])]
    await api.einstellungSetzen('global', 'werkzeuge_aus', neu.length ? neu : null)
    return t(an ? 'cli.werkzeug_an' : 'cli.werkzeug_aus', { name })
  },

  async status() {
    const [auskunft, uebersicht] = await Promise.all([
      api.runnerAuskunft().catch(() => null),
      api.werkzeuge().catch(() => null),
    ])
    const zeilen = [
      `${t('cli.status_modell')}: ${zustand.modellId || '—'}`,
      `${t('cli.status_server')}: ${t(auskunft?.laeuft ? 'cli.server_an' : 'cli.server_nicht_an')}`,
      `${t('cli.status_werkzeuge')}: ${uebersicht?.werkzeuge?.length ?? 0}`,
      `${t('cli.status_chat')}: ${zustand.aktiverChat || '—'}`,
    ]
    return zeilen.join('\n')
  },

  async neu() {
    const chat = await api.chatAnlegen({ endpoint_id: zustand.modellId })
    zustand.aktiverChat = chat.id
    zustand.nachrichten = []
    return t('cli.chat_neu')
  },

  async chat(rest) {
    const suche = rest.trim().toLowerCase()
    if (!suche) return t('cli.chat_fehlt')
    const treffer = zustand.chats.find((c) => (c.title || '').toLowerCase().includes(suche))
    if (!treffer) return t('cli.chat_unbekannt', { name: rest.trim() })
    const { chatOeffnen } = await import('./zustand.svelte.js')
    await chatOeffnen(treffer.id)
    return t('cli.chat_gewechselt', { name: treffer.title })
  },

  async sh(rest, chatId) {
    const befehl = rest.trim()
    if (!befehl) return t('cli.sh_fehlt')
    if (!chatId) return t('cli.sh_ohne_chat')
    const antwort = await api.befehlAusfuehren(chatId, befehl)
    return antwort?.text || ''
  },
}

/* English names, German aliases: the program speaks both, and so does its
   command line. */
const ALIASE = {
  help: 'hilfe', '?': 'hilfe',
  models: 'modelle', model: 'modell',
  tools: 'werkzeuge',
  new: 'neu',
}

/** Runs one line. Everything it produces lands in the chat's own history. */
export async function ausfuehren(chatId, eingabe) {
  const zeile = String(eingabe ?? '').trim()
  if (!zeile) return
  schreiben(chatId, 'eingabe', zeile)
  cli.verlauf = [...cli.verlauf.filter((z) => z !== zeile), zeile].slice(-100)

  if (!zeile.startsWith('/')) {
    schreiben(chatId, 'fehler', t('cli.kein_befehl'))
    return
  }

  const [roh, ...rest] = zeile.slice(1).split(/\s+/)
  const name = ALIASE[roh.toLowerCase()] || roh.toLowerCase()
  const befehl = BEFEHLE[name]
  if (!befehl) {
    schreiben(chatId, 'fehler', t('cli.unbekannt', { name: roh }))
    return
  }

  cli.laeuft = true
  try {
    const text = await befehl(rest.join(' '), chatId)
    schreiben(chatId, 'ausgabe', text)
  } catch (fehler) {
    schreiben(chatId, 'fehler', fehler?.message || String(fehler))
  } finally {
    cli.laeuft = false
  }
}
