/*
  The terminal module's state: which commands ran in this chat, and what
  they wrote while they ran.

  Its own module for the same reason the tools have one — the window draws,
  it does not decide. What it shows comes from one stream per chat
  (`/laeufe/{chat}/stream`), and that stream is deliberately NOT the answer
  stream: a background command outlives the answer that started it, and its
  lines have to keep arriving after the model has stopped talking.

  Two habits are worth naming, because both were decided against something:

    * The rail comes forward by itself when a command starts. Whoever closed
      it on this module is not asked again — a panel that pops back up is a
      panel people learn to hate.
    * The view sticks to the end while nobody scrolls. The moment somebody
      scrolls up, it stops following: reading beats watching.
*/

import { api } from './api.js'
import { anbieten } from './arbeitsleiste.svelte.js'
import { chatOeffnen, zustand } from './zustand.svelte.js'

export const terminal = $state({
  /* The runs of the open chat, oldest first. */
  laeufe: [],
  /* Follow the last line, or stay where the reader put us. */
  klebt: true,
})

function lauf(nummer) {
  return terminal.laeufe.find((l) => l.lauf === nummer) ?? null
}

/* ——— The stream ——— */

let quelle = null
let verbundenerChat = null

export async function verbinden(chatId) {
  if (chatId === verbundenerChat) return
  trennen()
  verbundenerChat = chatId ?? null
  terminal.laeufe = []
  if (!chatId) return

  /* What already ran comes through the ordinary route — the stream only
     carries what happens from now on. This is what makes a chat switch
     harmless: coming back fetches the chat's runs again, output included,
     instead of showing only what happens from the moment of reconnecting.

     The honest limit: those runs live in the service's memory, not in the
     database. They survive switching chats, closing the panel and reloading
     the window; they do not survive a restart of the service. A chat opened
     the next morning shows its tool calls (those are on the messages) but
     not the output of yesterday's commands. */
  try {
    terminal.laeufe = await api.laeufe(chatId)
  } catch {
    terminal.laeufe = []
  }

  quelle = new EventSource(api.laeufeStrom(chatId))
  quelle.onmessage = (nachricht) => {
    let ereignis
    try {
      ereignis = JSON.parse(nachricht.data)
    } catch {
      return
    }
    aufnehmen(ereignis)
  }
  /* A dropped stream is not worth a red message: the browser reconnects by
     itself, and what was missed is one run's lines, not the result. */
  quelle.onerror = () => {}
}

export function trennen() {
  quelle?.close()
  quelle = null
  verbundenerChat = null
}

function aufnehmen(ereignis) {
  if (ereignis.typ === 'lauf_start') {
    terminal.laeufe = [
      ...terminal.laeufe,
      {
        lauf: ereignis.lauf,
        befehl: ereignis.befehl,
        hintergrund: Boolean(ereignis.hintergrund),
        /* What kind of work this was. Older entries and anything the server
           does not label are commands — that is what the list held before
           pictures joined it. */
        art: ereignis.art || 'befehl',
        zustand: 'laeuft',
        code: null,
        dauer_sekunden: null,
        ausgabe: '',
      },
    ]
    /* Shipped switched on: a command that runs is a thing to watch. The
       rail decides whether it may come forward — it knows whether the user
       just closed it on this module. */
    terminal.klebt = true
    anbieten('terminal')
    return
  }
  const eintrag = lauf(ereignis.lauf)
  if (!eintrag) return
  if (ereignis.typ === 'lauf_zeile') {
    eintrag.ausgabe = eintrag.ausgabe ? `${eintrag.ausgabe}\n${ereignis.text}` : ereignis.text
    return
  }
  if (ereignis.typ === 'lauf_ende') {
    eintrag.zustand = ereignis.zustand
    eintrag.code = ereignis.code
    eintrag.dauer_sekunden = ereignis.dauer_sekunden ?? null
    /* A background run leaves a message behind. Fetch the chat again so it
       appears without anybody having to click. */
    if (ereignis.hintergrund && zustand.aktiverChat === verbundenerChat) {
      chatOeffnen(verbundenerChat)
    }
  }
}
