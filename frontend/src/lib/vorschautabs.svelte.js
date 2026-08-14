/*
  The tabs of the preview module: which files this chat produced.

  A file the model writes used to open a window over the whole program. That
  window is fine for one look at one file, and wrong for the way people
  actually work — building a page means looking at it while the conversation
  goes on. So the file moves into the rail beside the chat, and stays there
  as a tab.

  Per chat, like everything else in the rail: switching the conversation
  switches what is open. Images keep the old window — a picture wants the
  room, not a column.
*/

import { anbieten } from './arbeitsleiste.svelte.js'

export const tabs = $state({
  /* chat id -> [{ id, name, art, inhalt }] */
  proChat: {},
  aktiv: {},
})

function schluessel(name, art) {
  return `${art}:${name}`
}

export function tabsVon(chatId) {
  return tabs.proChat[chatId] ?? []
}

export function aktiverTab(chatId) {
  const liste = tabsVon(chatId)
  return liste.find((e) => e.id === tabs.aktiv[chatId]) ?? liste[liste.length - 1] ?? null
}

/**
 * Puts a file into the rail and brings it to the front.
 *
 * A file that is already open is replaced rather than doubled: the model
 * rewriting its page is the same page, and two tabs of one name help
 * nobody.
 */
export function tabOeffnen(chatId, { name, art, inhalt }) {
  if (!chatId || !name) return
  const id = schluessel(name, art)
  const liste = [...tabsVon(chatId)]
  const stelle = liste.findIndex((e) => e.id === id)
  const eintrag = { id, name, art, inhalt }
  if (stelle >= 0) liste[stelle] = eintrag
  else liste.push(eintrag)
  tabs.proChat[chatId] = liste
  tabs.aktiv[chatId] = id
  anbieten('vorschau')
}

export function tabWaehlen(chatId, id) {
  tabs.aktiv[chatId] = id
}

export function tabSchliessen(chatId, id) {
  const liste = tabsVon(chatId).filter((e) => e.id !== id)
  tabs.proChat[chatId] = liste
  if (tabs.aktiv[chatId] === id) {
    tabs.aktiv[chatId] = liste[liste.length - 1]?.id ?? null
  }
}
