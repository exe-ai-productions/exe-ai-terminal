/*
  What a chat row has to say about itself, in one dot.

  A list of chats used to report exactly one thing: an answer had finished
  somewhere. Everything else — that a run is going on over there, that
  something is standing still waiting for a decision, that a run fell over —
  was only visible by opening the chat. With more than one conversation in
  flight at a time that is the wrong way round: the list is where one looks
  to decide WHICH chat to open.

  So every row carries the house's status dot, and the five states it can
  wear are the five things worth walking over for:

    gelb   somebody is waiting for you — a question, a confirmation
    blau   an answer is running here
    rot    a run failed and nobody has looked at it
    gruen  an answer finished and nobody has looked at it
    leer   nothing to report; a small quiet disc keeps the rows in line

  Only one dot per row — two would make the row a dashboard, and a list of
  thirty chats cannot afford that. Which of them wins when several are true
  is decided in `ringfarbe.js`; this file only gathers the four facts the
  decision needs.
*/

import { ringAus } from './ringfarbe.js'
import { zustand } from './zustand.svelte.js'

/* Chats whose last run failed, until somebody opens them. The sibling of
   `fertigeChats`, and deliberately memory only: after a restart there is
   no run to point at anymore, so the mark would be a claim without a
   subject. */
export const fehlerChats = $state({ liste: [] })

export function chatFehlerMerken(id) {
  if (id && !fehlerChats.liste.includes(id)) fehlerChats.liste.push(id)
}

export function chatFehlerGesehen(id) {
  if (id && fehlerChats.liste.includes(id))
    fehlerChats.liste = fehlerChats.liste.filter((c) => c !== id)
}

/* Is this chat the one holding a question? Both pending boxes carry the
   chat they belong to, so a question in one conversation cannot light up
   the row of another. */
function fragtNach(chatId) {
  return (
    zustand.werkzeugfrage?.chatId === chatId || zustand.benutzerfrage?.chatId === chatId
  )
}

export function ringFarbe(chatId) {
  if (!chatId) return 'leer'
  return ringAus({
    fragt: fragtNach(chatId),
    laeuft: zustand.laeuft?.chatId === chatId,
    fehler: fehlerChats.liste.includes(chatId),
    fertig: zustand.fertigeChats.includes(chatId),
  })
}
