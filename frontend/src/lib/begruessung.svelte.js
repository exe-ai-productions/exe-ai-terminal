/*
  The greeting and the name behind it.

  One setting drives two things: the corner greeting on the empty chat and
  the one line in the system prompt that names the user. The switch and the
  name live in the settings store; this module keeps the loaded copy and
  the little clock that decides between morning, day and evening.
*/

import { api } from './api.js'

export const begruessung = $state({
  name: '',
  an: true,
  geladen: false,
  // The first name the operating system suggests for the first start.
  vorschlag: '',
})

export async function begruessungLaden() {
  try {
    const [stand, meta] = await Promise.all([
      api.einstellungAufgeloest('anrede'),
      api.meta(),
    ])
    const wert = stand?.wert || {}
    begruessung.name = String(wert.name || '')
    begruessung.an = wert.an !== false
    begruessung.vorschlag = String(meta?.system_name || '')
  } catch {
    // The service could not say — the greeting simply stays quiet.
  }
  begruessung.geladen = true
}

export async function anredeSpeichern(name, an) {
  begruessung.name = String(name || '').trim()
  begruessung.an = Boolean(an)
  await api.einstellungSetzen('global', 'anrede', {
    name: begruessung.name,
    an: begruessung.an,
  })
}

/** The greeting key for this hour — morning, day or evening. */
export function grussSchluessel(frage = false) {
  const stunde = new Date().getHours()
  const teil = stunde >= 5 && stunde < 11 ? 'morgen' : stunde >= 11 && stunde < 18 ? 'tag' : 'abend'
  return frage ? `gruss.frage_${teil}` : `gruss.${teil}`
}

/* The first start is a one-time act per installation: once the window was
   answered — or a name exists — it never comes back. */
export function erststartNoetig() {
  return begruessung.geladen && !begruessung.name && !localStorage.getItem('erststart')
}

export function erststartErledigt() {
  localStorage.setItem('erststart', 'gezeigt')
}
