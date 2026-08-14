/*
  The message queue: what gets typed while an answer is still running.

  The input field used to lock itself for the duration of a run. That is
  the wrong side to err on — a thought arrives while the model is still
  talking, and holding it in one's head until the answer is through is
  work the program should be doing. So sending during a run no longer
  bounces: the message lines up and goes out by itself once the running
  answer has ended.

  It ends by itself only after a CLEAN end. An answer that failed or was
  stopped by hand leaves a state nobody has looked at yet; firing the next
  message into it would pile a second problem onto the first. The queue
  holds there and says so at the bubble, and one click sends it on.

  The queue belongs to the chat, not to the window: whoever queues two
  messages here and switches over there finds them again on return, and
  the other chat's list stays its own.
*/

export const warteschlange = $state({ liste: [] })

let naechsteKennung = 0

/* Put a message in line. Attachments travel as the files themselves —
   they are uploaded on sending, not on queueing, so a queued message
   behaves exactly like one typed a minute later. */
export function einreihen(chatId, auftrag) {
  const eintrag = { id: ++naechsteKennung, chatId, haelt: false, ...auftrag }
  warteschlange.liste.push(eintrag)
  return eintrag.id
}

export function entfernen(id) {
  const stelle = warteschlange.liste.findIndex((e) => e.id === id)
  if (stelle !== -1) warteschlange.liste.splice(stelle, 1)
}

export function fuerChat(chatId) {
  return warteschlange.liste.filter((e) => e.chatId === chatId)
}

/* Take the first one of this chat out of the line. Taking it out and
   sending it are one step on purpose: an entry that is on its way must
   not still be standing in the list, or a second end would send it
   twice. */
export function ausreihen(chatId) {
  const stelle = warteschlange.liste.findIndex((e) => e.chatId === chatId)
  if (stelle === -1) return null
  return warteschlange.liste.splice(stelle, 1)[0]
}

/* The line stops. Everything still waiting in this chat carries the mark,
   so the state is readable at every bubble and not only at the first. */
export function anhalten(chatId) {
  for (const eintrag of warteschlange.liste) {
    if (eintrag.chatId === chatId) eintrag.haelt = true
  }
}

export function loesen(chatId) {
  for (const eintrag of warteschlange.liste) {
    if (eintrag.chatId === chatId) eintrag.haelt = false
  }
}

export function haelt(chatId) {
  return fuerChat(chatId).some((e) => e.haelt)
}

/* A deleted chat takes its queue with it — otherwise entries would sit
   there pointing at a chat that no longer exists. */
export function leeren(chatId) {
  warteschlange.liste = warteschlange.liste.filter((e) => e.chatId !== chatId)
}
