/*
  The server-log window: its open state and lines in one place, so the window
  itself can be drawn at the app root.

  A window that must lie over everything cannot live inside a panel that sits
  inside a scrolling, transformed window — a fixed position would be measured
  against that window, not the screen, and the popup lands clipped and off.
  So the state lives here and the drawing hangs at the root, the way the
  prompt dialog already does.
*/

let offen = $state(false)
let zeilen = $state([])
let titel = $state('')

export function protokollOffen() {
  return offen
}
export function protokollZeilen() {
  return zeilen
}
export function protokollTitel() {
  return titel
}

export function oeffneProtokoll(neuerTitel = '') {
  titel = neuerTitel
  offen = true
}

export function setzeProtokollZeilen(neu) {
  if (offen) zeilen = neu
}

export function schliesseProtokoll() {
  offen = false
}
