/* The skill list behind the slash list in the input bar.
 *
 * Held once rather than fetched per keystroke: opening the list must feel
 * instant, and the list only changes when somebody edits a skill.
 *
 * The name a user types is matched against this list before it is sent. A
 * slash that hits nothing is just a slash — the message goes out as written
 * rather than being refused over something the user only added on top. */

import { api } from './api.js'

/* Lower case, digits, hyphens — the same shape the backend enforces on a
 * folder name, because this is what has to be typeable. */
const AM_ANFANG = /^\/([a-z0-9][a-z0-9-]*)(\s|$)/

export const skills = $state({ liste: [], geladen: false })

export async function skillsLaden() {
  try {
    skills.liste = await api.skills()
    skills.geladen = true
  } catch {
    /* No list is not an error worth a red line: the slash list simply stays
       empty, and everything else in the program carries on. */
    skills.liste = []
  }
}

/** The skill a line starts with, or null. Matched against what exists. */
export function skillAmAnfang(text) {
  const treffer = AM_ANFANG.exec(text || '')
  if (!treffer) return null
  return skills.liste.find((s) => s.name === treffer[1]) ?? null
}

/** Entries whose name contains the filter, those starting with it first.
 *
 * Substring rather than prefix so "generator" still finds
 * "image-generator"; sorted so a prefix match never hides behind one. */
export function gefiltert(filter) {
  const suche = (filter || '').toLowerCase()
  if (!suche) return skills.liste
  const treffer = skills.liste.filter((s) => s.name.toLowerCase().includes(suche))
  return treffer.sort((a, b) => {
    const va = a.name.toLowerCase().startsWith(suche) ? 0 : 1
    const vb = b.name.toLowerCase().startsWith(suche) ? 0 : 1
    return va - vb
  })
}
