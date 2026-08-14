/*
  The work rail on the right: which module is showing, how wide it is, and
  whether it may open by itself.

  The rail started as one window for the terminal. It is a rail with five
  modules now — terminal, CLI, preview, note, guardian — and the rule that made the
  terminal work is the rule they all follow: it opens itself when its module
  has something to show, and whoever closes it during that is not asked
  again for it.

  The signs live on a narrow strip at the right edge that is ALWAYS
  visible, panel open or shut. The first build hid them behind the seam: you
  had to hit a hairline and catch a grey button that only appeared on hover,
  which on two screens meant the pointer kept sliding onto the neighbour.
  Nobody found the CLI, and a first-time user had no way of learning the rail
  existed at all. Signs standing there solve that without a tour
  bubble.

  Everything is per chat except the note. Switching chats on the left
  switches runs, preview tabs and CLI history with it; the note belongs to
  the person, not to the conversation.
*/

/* The rail's own strip does not count towards this: 260 px is what the
   CONTENT gets at its narrowest, and a CLI line still reads at that width. */
const BREITE_MIN = 260
const BREITE_MAX = 900

export const MODULE = ['terminal', 'cli', 'vorschau', 'notiz', 'waechter']

export const leiste = $state({
  /* Open, closed and which module: remembered like the sidebar's state on
     the left. Somebody who works with the terminal open should find it open
     after a restart, not have to fetch it back every time. */
  offen: localStorage.getItem('leiste') === 'auf',
  modul: localStorage.getItem('leistenmodul') || 'terminal',
  /* The narrowest the content is allowed to be, and the width it opens at.
     Not a taste: the rail plus its strip is 312, the chat list on the left
     is 286, and at those numbers the input below the wordmark sits 13 px
     off the middle of the window — under one percent, which the eye does
     not find. The old 440 put it 103 px off, and that one the eye finds
     immediately: the conversation looked pushed aside by its own panel.
     Wider is one drag away and is remembered. */
  breite: Number(localStorage.getItem('leistenbreite')) || BREITE_MIN,
  zieht: false,
  /* Which module the user closed the rail on. It stays closed for that one
     until its next fresh occasion — a rail that pops back up is a rail
     people learn to hate. */
  nichtAufdraengen: '',
})

export function breiteSetzen(px) {
  leiste.breite = Math.round(Math.min(BREITE_MAX, Math.max(BREITE_MIN, px)))
  localStorage.setItem('leistenbreite', String(leiste.breite))
}

/**
 * A click on a module sign. Shut, it opens that module; open, a click on the
 * module already showing shuts the panel again — the sign is the switch, and
 * it is the same one either way.
 */
export function modulWaehlen(name) {
  if (!MODULE.includes(name)) return
  if (leiste.offen && leiste.modul === name) {
    schliessen()
    return
  }
  leiste.modul = name
  leiste.offen = true
  leiste.nichtAufdraengen = ''
  merken()
}

function merken() {
  localStorage.setItem('leiste', leiste.offen ? 'auf' : 'zu')
  localStorage.setItem('leistenmodul', leiste.modul)
}

/** ⌘J, the mirror of ⌘B on the left. */
export function schalten() {
  if (leiste.offen) schliessen()
  else oeffnen()
}

export function schliessen() {
  leiste.offen = false
  leiste.nichtAufdraengen = leiste.modul
  merken()
}

export function oeffnen() {
  leiste.offen = true
  leiste.nichtAufdraengen = ''
  merken()
}

/**
 * A module has something new to show. It comes to the front unless the user
 * shut the rail on exactly this module.
 */
export function anbieten(name) {
  if (!MODULE.includes(name)) return
  if (leiste.nichtAufdraengen === name && !leiste.offen) return
  leiste.modul = name
  leiste.offen = true
  merken()
}
