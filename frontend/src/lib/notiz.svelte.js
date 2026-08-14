/*
  The note in the work rail.

  Deliberately the one thing in the rail that does NOT belong to a chat: it
  is the pad beside the keyboard. A note tied to a conversation would be
  gone the moment the conversation is, which is exactly when people still
  need what they wrote down.

  localStorage is enough for a first version — it is the user's own text on
  the user's own machine, and it costs no round trip while typing.
*/

const SPEICHER = 'randnotiz'

export const notiz = $state({
  text: localStorage.getItem(SPEICHER) || '',
})

export function notizSetzen(text) {
  notiz.text = text
  if (text) localStorage.setItem(SPEICHER, text)
  else localStorage.removeItem(SPEICHER)
}
