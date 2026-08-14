/*
  Which window a window was opened from.

  The catalogue is reached from the local-models window, and once there the
  only way out used to be closing everything — which threw away the place
  the hand had come from. A window opened out of another window is a step
  further in, not a fresh start, and a step further in wants a step back.

  One entry deep on purpose. The house has no window that opens a window
  that opens a window, and a stack would invite one: what is worth having is
  the promise "the arrow takes you where you were", and that promise is kept
  by one remembered step. Anything deeper is a browser, and a settings dialog
  is not a browser.

  The trail is dropped whenever a window is opened WITHOUT a way back — the
  menu bar does that on every click. Otherwise an arrow left over from an
  earlier detour would point somewhere the hand never was.
*/

export const weg = $state({
  /* What to run to get back, or null when this window stands on its own. */
  zurueck: null,
})

/* Open a window out of the one standing now. `zurueck` closes the new window
   and reopens the old one — the caller knows both, this module knows
   neither. */
export function ausFenster(oeffnen, zurueck) {
  weg.zurueck = zurueck
  oeffnen()
}

/* Take the step back and forget it: after the arrow, the old window is the
   one standing, and it has no trail of its own. */
export function zurueckgehen() {
  const schritt = weg.zurueck
  weg.zurueck = null
  schritt?.()
}

/* A window that was not opened out of another one wipes the trail. */
export function ohneWeg() {
  weg.zurueck = null
}
