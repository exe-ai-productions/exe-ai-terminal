/*
  The three sounds: answer done, the program is waiting, something failed.

  Real recordings, not a tone generator — a balafon, one note per hit, from a
  public-domain library that travels with the program. They live in
  static/klaenge/ and not under static/app/, which is emptied on every
  frontend build.

  Three rules, and each of them is the whole reason this module exists:

    * **Only when the window is in the background.** Whoever is looking at
      the screen has already seen it. A sound for something visible is
      noise, and noise is what makes people switch sounds off.
    * **Shipped switched on.** A sound nobody finds is a sound nobody has —
      the switch and the volume live in the settings.
    * **Never twice at once.** A running sound is stopped before the next
      one starts, so a burst of errors is one knock, not a rattle.

  The preview button in the settings is the one exception to the first
  rule: pressing it means asking to hear it now.
*/

import { api } from './api.js'

const ORT = '/klaenge/'
export const KLAENGE = ['fertig', 'wartet', 'fehler']

/* One key in the settings cascade, checked on the service side by
   app/klangwahl.py. Both values live in one object on purpose: the route
   reads a falsy value as "nothing set", so a bare `false` could never
   switch the sounds off and a volume of 0 would spring back. */
export const SCHLUESSEL = 'klaenge'

export const klangwahl = $state({
  aus: false,
  /* 0 to 100 — the value the slider carries. */
  pegel: 70,
  /* The stored state has arrived; before that the slider must not adopt
     anything, or it would jump once while being dragged. */
  geladen: false,
})

const gepuffert = new Map()
let laufend = null

function datei(name) {
  if (!gepuffert.has(name)) {
    const ton = new Audio(`${ORT}${name}.wav`)
    ton.preload = 'auto'
    gepuffert.set(name, ton)
  }
  return gepuffert.get(name)
}

/* The window is "away" when it has no focus or is not visible at all —
   another program in front, another tab, a minimised window. */
function imVordergrund() {
  return document.hasFocus() && document.visibilityState === 'visible'
}

function abspielen(name) {
  const ton = datei(name)
  if (laufend && laufend !== ton) {
    laufend.pause()
    laufend.currentTime = 0
  }
  ton.volume = Math.min(1, Math.max(0, klangwahl.pegel / 100))
  ton.currentTime = 0
  laufend = ton
  /* A browser that refuses to play (no user gesture yet) is not an error
     worth a red message — the sound is a courtesy, not a result. */
  return ton.play().catch(() => {})
}

/** The ordinary way in: plays only if the window is in the background. */
export function klingen(name) {
  if (klangwahl.aus || !KLAENGE.includes(name)) return
  if (imVordergrund()) return
  abspielen(name)
}

/** The preview button: plays no matter where the window is. */
export function probehoeren(name) {
  if (!KLAENGE.includes(name)) return
  abspielen(name)
}

/* ——— The switch and the volume, stored in the settings cascade ——— */

export async function klangwahlLaden() {
  const stand = await api.einstellungAufgeloest(SCHLUESSEL).catch(() => null)
  const wert = stand?.wert
  if (!wert || typeof wert !== 'object') return
  if (typeof wert.an === 'boolean') klangwahl.aus = !wert.an
  if (typeof wert.pegel === 'number') klangwahl.pegel = wert.pegel
  klangwahl.geladen = true
}

function sichern() {
  return api
    .einstellungSetzen('global', SCHLUESSEL, {
      an: !klangwahl.aus,
      pegel: klangwahl.pegel,
    })
    .catch(() => {})
}

export async function klaengeSchalten(an) {
  klangwahl.aus = !an
  await sichern()
}

/* Dragging fires an event per pixel. Storing each one meant a dozen
   requests in flight at once, and whichever answered last wrote its value
   back into the slider — the knob jumped around under the finger.

   So: the state follows the hand immediately, and only the last position
   is stored, once the hand has come to rest. A failed write is not undone
   either; snapping the knob back mid-drag is exactly the jump this fixes. */
const SPEICHER_RUHE_MS = 300
let speicherUhr = 0

export function pegelSetzen(wert) {
  klangwahl.pegel = Math.min(100, Math.max(0, Math.round(wert)))
  clearTimeout(speicherUhr)
  speicherUhr = setTimeout(sichern, SPEICHER_RUHE_MS)
}
