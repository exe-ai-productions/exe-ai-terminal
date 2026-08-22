/*
  The start/stop action of the shown server panel, kept in one place so a
  single full-width button can stand at the base of the rail instead of in
  each panel's own foot.

  The panel that is on screen writes its action here while it lives; the rail
  reads it to draw the button. One truth for a control drawn in a different
  column than the logic that feeds it.
*/

// { text, punkt, gesperrt, onTat } while a server panel is shown, else null.
let aktion = $state(null)

export function startAktion() {
  return aktion
}

export function setzeStartAktion(neu) {
  aktion = neu
}

export function loescheStartAktion() {
  aktion = null
}
