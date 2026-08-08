/*
  Which picture is currently open at full size.

  Its own module for the same reason the file preview has one: an overlay
  that covers the whole program cannot live inside a message. Fixed
  positioning reaches the whole window only when no ancestor holds it, and
  the message list holds it — the enlargement was drawn underneath the
  sidebar, which is exactly as useful as not opening at all.
*/

export const bildschau = $state({
  offen: false,
  adresse: '',
})

export function bildZeigen(adresse) {
  bildschau.adresse = adresse
  bildschau.offen = true
}
