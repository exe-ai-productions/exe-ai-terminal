/*
  ANSI colour codes into house classes.

  npm, vite, git and half the tools people run send colour escapes. Shown
  raw they are noise (`[32m`), stripped they lose the one thing that made
  the output readable — which line is the error.

  About forty lines instead of a library: only SGR codes are understood,
  everything else is swallowed. An unknown code shows nothing rather than
  showing garbage, and no escape ever reaches the document as text.
*/

const FARBEN = {
  30: 'schwarz', 31: 'rot', 32: 'gruen', 33: 'gelb',
  34: 'blau', 35: 'lila', 36: 'cyan', 37: 'weiss',
  90: 'grau', 91: 'rot', 92: 'gruen', 93: 'gelb',
  94: 'blau', 95: 'lila', 96: 'cyan', 97: 'weiss',
}

/* Every escape sequence, not just the colour ones: what is not understood
   still has to disappear. */
const ESCAPES = /\[[0-9;?]*[a-zA-Z]/g
const SGR = /^\[([0-9;]*)m$/

function maskieren(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** One line of program output as HTML, colours kept, escapes gone. */
export function ansiZuHtml(zeile) {
  const text = String(zeile ?? '')
  let raus = ''
  let offen = 0
  let zuletzt = 0
  let treffer

  const klasse = (farbe, fett) =>
    `<span class="ansi-${farbe}${fett ? ' ansi-fett' : ''}">`

  ESCAPES.lastIndex = 0
  while ((treffer = ESCAPES.exec(text)) !== null) {
    raus += maskieren(text.slice(zuletzt, treffer.index))
    zuletzt = treffer.index + treffer[0].length
    const sgr = treffer[0].match(SGR)
    if (!sgr) continue // cursor moves and the like: swallowed
    let fett = false
    for (const roh of sgr[1].split(';')) {
      const code = Number(roh || '0')
      if (code === 0) {
        raus += '</span>'.repeat(offen)
        offen = 0
      } else if (code === 1) {
        fett = true
      } else if (FARBEN[code]) {
        raus += klasse(FARBEN[code], fett)
        offen++
      }
    }
  }
  raus += maskieren(text.slice(zuletzt))
  return raus + '</span>'.repeat(offen)
}
