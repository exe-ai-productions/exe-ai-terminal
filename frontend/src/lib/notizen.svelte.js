/*
  The notes and the document dock — state and actions in one place.

  Both live in the data folder, not in the browser: a note with a heading and
  formatting is work, and work belongs where the rest of it is kept. It
  survives a cleared cache and a different browser, and it travels with a
  backup.

  What is edited right now is held here too, because the toolbar sits in the
  rail's head while the note being formatted sits in the panel below — the
  two have to agree on which note the buttons act on.
*/

import { api } from './api.js'
import { melde } from './zustand.svelte.js'

export const notizen = $state({
  liste: [],
  /* The note currently open for editing: an id, or 'neu' for the one being
     written, or null when nothing is. */
  offen: null,
  entwurf: { ueberschrift: '', inhalt: '' },
  geladen: false,
})

export const dock = $state({
  liste: [],
  plaetze: 4,
})

export async function notizenLaden() {
  try {
    notizen.liste = await api.notizen()
  } catch {
    notizen.liste = []
  }
  notizen.geladen = true
}

export async function dockLaden() {
  try {
    dock.liste = await api.dockAlle()
  } catch {
    dock.liste = []
  }
}

/* ——— Writing ——— */

export function neueNotiz() {
  notizen.offen = 'neu'
  notizen.entwurf = { ueberschrift: '', inhalt: '' }
}

export function notizOeffnen(notiz) {
  notizen.offen = notiz.id
  notizen.entwurf = { ueberschrift: notiz.ueberschrift, inhalt: notiz.inhalt }
}

export function schliessen() {
  notizen.offen = null
  notizen.entwurf = { ueberschrift: '', inhalt: '' }
}

/** The tick: an empty note is simply dropped rather than stored empty. */
export async function sichern() {
  const { ueberschrift, inhalt } = notizen.entwurf
  const leer = !ueberschrift.trim() && !inhalt.replace(/<[^>]*>/g, '').trim()
  if (leer) return schliessen()
  try {
    if (notizen.offen === 'neu') {
      const neu = await api.notizAnlegen({ ueberschrift, inhalt })
      notizen.liste = [...notizen.liste, neu]
    } else {
      const geaendert = await api.notizAendern(notizen.offen, { ueberschrift, inhalt })
      notizen.liste = notizen.liste.map((n) => (n.id === geaendert.id ? geaendert : n))
    }
    schliessen()
  } catch (fehler) {
    melde(fehler.message, 'fehler')
  }
}

export async function loeschen(id) {
  try {
    await api.notizLoeschen(id)
    notizen.liste = notizen.liste.filter((n) => n.id !== id)
    if (notizen.offen === id) schliessen()
  } catch (fehler) {
    melde(fehler.message, 'fehler')
  }
}

/* ——— The dock ——— */

export async function dockAblegen(datei) {
  if (dock.liste.length >= dock.plaetze) return
  try {
    const eintrag = await api.dockAblegen(datei)
    dock.liste = [...dock.liste, eintrag]
  } catch (fehler) {
    melde(fehler.message, 'fehler')
  }
}

export async function dockEntfernen(id) {
  try {
    await api.dockEntfernen(id)
    dock.liste = dock.liste.filter((e) => e.id !== id)
  } catch (fehler) {
    melde(fehler.message, 'fehler')
  }
}

/**
 * A docked file as a real File, so it can travel the ordinary attachment
 * path into the chat — the input field does not need to know the dock
 * exists.
 */
export async function dockDatei(eintrag) {
  const antwort = await fetch(api.dockAdresse(eintrag.id))
  const blob = await antwort.blob()
  return new File([blob], eintrag.name, { type: eintrag.typ || blob.type })
}
