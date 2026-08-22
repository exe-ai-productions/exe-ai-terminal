/*
  Extended Workflow: on or off, and what that costs.

  The switch exists twice — once in the module's own head, where the hand is
  when it wants the thing, and once in the settings, where somebody goes to
  find every switch in one place. Two switches for one fact is fine; two
  copies of the fact are not. So the fact lives here, and both only draw it.

  Switching on means two things at once, and that is the whole point of
  having a switch rather than a checkbox: the triggers go live AND the
  guardian's own small model loads. Switching off unloads it again. A model
  kept warm for a feature nobody switched on is a gigabyte nobody agreed to.

  The model load is deliberately NOT awaited by the switch. It takes seconds,
  and a switch that stays half-pressed while a file is read from disk reads
  as a program that hung. The state says "loading" until the server answers.
*/

import { api } from './api.js'

export const eew = $state({
  /* What the user decided. This is the setting; everything else follows. */
  an: true,
  /* Whether the guardian's own model is up. Not the same question: the
     switch can be on while the model is still coming. */
  laeuft: false,
  laedt: false,
  /* A start that was tried and did not work. Kept apart from `laeuft`
     because "not up yet" and "will not come up" are different facts and the
     dot owes the user the difference. */
  fehler: false,
  /* Which model it uses. The server names its own default; the dropdown on
     the model server page writes this. */
  modell: '',
  /* Whether that choice was actually made rather than merely absent: an
     empty model is a valid answer, and without this flag the server's
     default would fill it back in on the next load. */
  gewaehlt: false,
  vorgabe: '',
})

const SCHLUESSEL = 'waechter'

/* What the switch means for the rail's status dot.
   Off is still. On is blue — the house word for switched on and working —
   whether the model is already up or still coming; green once it can
   actually answer; red when a start was tried and failed.
   Yellow is deliberately NOT in here: the rail paints a waiting finding
   yellow, and a dot that is yellow from the moment the program starts can
   never carry that message. */
export function punktfarbe() {
  if (!eew.an) return 'still'
  if (eew.fehler) return 'rot'
  if (eew.laeuft) return 'gruen'
  return 'blau'
}

export async function standLaden() {
  try {
    const stand = await api.einstellungAufgeloest(SCHLUESSEL)
    if (stand?.wert && typeof stand.wert.an === 'boolean') eew.an = stand.wert.an
    /* A stored empty string is a deliberate "none", not a missing value —
       tested by kind, because a falsy test would throw exactly that choice
       away and the server's default would take its place on every load. */
    if (typeof stand?.wert?.modell === 'string') {
      eew.modell = stand.wert.modell
      eew.gewaehlt = true
    }
  } catch {
    /* Leaves the default standing — shipped on. */
  }
  await serverStandLaden()
}

export async function serverStandLaden() {
  try {
    const a = await api.eewAuskunft()
    eew.laeuft = Boolean(a.laeuft)
    eew.vorgabe = a.vorgabe || ''
    if (!eew.modell && !eew.gewaehlt) eew.modell = a.modell || a.vorgabe || ''
  } catch {
    eew.laeuft = false
  }
}

/* One at a time.

   The switch starts and stops a process, and a hand can click faster than a
   model loads. Two calls in flight meant two start commands for one port:
   the second came back 409, its catch set `laeuft` to false, and the switch
   then said "not running" about a server that was running perfectly well.
   Off-then-on was worse — the stop could land after the start.

   So every operation joins a queue instead of racing. What the user last
   asked for is what the last operation in the queue does, because the state
   is read when the operation runs, not when it was queued. */
let schlange = Promise.resolve()

function nacheinander(arbeit) {
  const naechste = schlange.then(arbeit, arbeit)
  /* The queue itself must never hold on to a rejection, or one failed
     switch would poison every switch after it. The caller still gets it. */
  schlange = naechste.then(
    () => {},
    () => {}
  )
  return naechste
}

/* The switch. Writes the setting first — that is what the user actually
   decided — and then brings the model into line with it. */
export function schalten(an) {
  return nacheinander(async () => {
    const vorher = eew.an
    eew.an = an
    try {
      await api.einstellungSetzen('global', SCHLUESSEL, { an, modell: eew.modell })
    } catch {
      eew.an = vorher
      throw new Error('einstellung')
    }
    await modellNachziehen()
  })
}

/* Which small model the guardian uses. Changing it while the thing runs
   means restarting it — a running server holds the old file. */
export function modellWaehlen(name) {
  return nacheinander(async () => {
    eew.modell = name
    eew.gewaehlt = true
    try {
      await api.einstellungSetzen('global', SCHLUESSEL, { an: eew.an, modell: name })
    } catch {
      /* The setting failing is not worth undoing the choice in front of the
         user; the next switch writes it again. */
    }
    if (eew.an && eew.laeuft) {
      await api.eewStoppen().catch(() => {})
      eew.laeuft = false
      await modellNachziehen()
    }
  })
}

async function modellNachziehen() {
  if (!eew.an) {
    eew.laedt = false
    eew.fehler = false
    try {
      await api.eewStoppen()
    } catch {
      /* Nothing running is the state we wanted anyway. */
    }
    eew.laeuft = false
    return
  }
  const name = eew.modell || eew.vorgabe
  if (!name) return
  eew.laedt = true
  eew.fehler = false
  try {
    const a = await api.eewStarten(name)
    eew.laeuft = Boolean(a.laeuft)
  } catch {
    /* A refused start says nothing reliable about what is running. It can
       mean the server is already up (a second click on the same switch) or
       that something else holds the port — 409 for both, and the sentence
       that comes back is a translation, not a key to branch on.

       So the state is not guessed from the error: the server is asked. What
       it says is the truth about the process, which is the whole question
       here. Only if it says nothing is running was this a real failure. */
    await serverStandLaden()
    eew.fehler = !eew.laeuft
  } finally {
    eew.laedt = false
  }
}
