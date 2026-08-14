/*
  The guardian's findings, on the interface's side.

  Findings are not fetched on a cadence: they arrive over the answer stream
  the moment a step fails, and the suggestion follows in a second event once
  the model has written one. Polling would mean asking every few seconds a
  question that is almost always answered "nothing" — and it would be
  slower than the stream at exactly the moment it mattered.

  The list is fetched once when a chat is opened, because a run may have
  ended while that chat was closed and a finding should not disappear
  because nobody was looking.

  Findings belong to a chat, like the runs and the preview tabs. The keys
  are chat ids, so switching conversations switches the panel with them and
  nothing has to be cleared.
*/

import { api } from './api.js'

export const waechter = $state({ nach_chat: {} })

export function befundeVon(chatId) {
  return waechter.nach_chat[chatId] || []
}

/* Anything without a suggestion is still being thought about; anything
   with one is ready to send. The dot on the strip counts both — a finding
   is news either way. */
export function offeneAnzahl(chatId) {
  return befundeVon(chatId).length
}

/* One finding from the stream. The same id arrives twice — once bare when
   the step failed, once again with the model's answer — so it replaces
   rather than appends. That second event also carries an EMPTY suggestion
   when the model had nothing usable to say, which is why it is sent at
   all: without it the panel would wait for a sentence forever. */
export function befundSetzen(chatId, befund) {
  if (!chatId || !befund) return
  const liste = befundeVon(chatId)
  const stelle = liste.findIndex((b) => b.id === befund.id)
  if (stelle === -1) waechter.nach_chat[chatId] = [...liste, befund]
  else waechter.nach_chat[chatId] = liste.map((b) => (b.id === befund.id ? befund : b))
}

export async function befundeLaden(chatId) {
  if (!chatId) return
  try {
    waechter.nach_chat[chatId] = await api.befunde(chatId)
  } catch {
    /* An extra, not a load-bearing part: if the list cannot be fetched the
       panel simply stays as it was. A toast here would report a problem
       the user does not have. */
  }
}

export async function befundVerwerfen(chatId, id) {
  waechter.nach_chat[chatId] = befundeVon(chatId).filter((b) => b.id !== id)
  try {
    await api.befundVerwerfen(chatId, id)
  } catch {
    /* Already gone from the list — the server forgets its findings on
       restart anyway, so a failed delete costs nothing. */
  }
}

export function befundeVergessen(chatId) {
  delete waechter.nach_chat[chatId]
}
