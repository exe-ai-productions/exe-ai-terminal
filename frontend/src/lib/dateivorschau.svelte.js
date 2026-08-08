/*
  Which file is currently open in the preview window.

  Its own module for a reason that cost an hour: the window was first placed
  inside the message that owns the file, which reads well and is wrong. A
  window covers the whole program, and a `position: fixed` box only reaches
  that far if no ancestor holds it — deep inside the message list it ended up
  behind the sidebar instead of over it.

  So the file travels up here and the window hangs once at the top, like
  every other window in the program. One window, not one per message.
*/

export const vorschau = $state({
  offen: false,
  name: '',
  art: '',
  inhalt: '',
})

export function dateiZeigen({ name, art, inhalt }) {
  vorschau.name = name
  vorschau.art = art
  vorschau.inhalt = inhalt
  vorschau.offen = true
}
