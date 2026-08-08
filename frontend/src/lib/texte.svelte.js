/*
  Translations for the interface.

  The catalog lives on the server (`app/locales/*.json`) and is fetched once
  at startup — exactly one place for all texts, instead of a copy in the
  bundle that gets forgotten when editing. It is loaded **before** the first
  render (see `main.js`), otherwise the keys flash up for a moment.

  `katalog` is $state: when the language changes, every component that uses
  `t()` re-renders. No component has to know about it.

  The language comes from the browser's storage, otherwise from the device
  setting. If the server doesn't know it, it returns its default language
  and says in `sprache` which one that was.
*/

import { api, spracheMerken } from './api.js'

export const texte = $state({ sprache: 'de', katalog: {} })

const SPEICHER = 'sprache'

/* The desired language: storage first, then the device, German otherwise.
   `navigator.language` is "de-DE" or "en-GB" — we only care about the
   first part, because that's what the catalogs are named. */
export function gewuenschteSprache() {
  const gemerkt = localStorage.getItem(SPEICHER)
  if (gemerkt) return gemerkt
  return (navigator.language || 'de').slice(0, 2).toLowerCase()
}

export async function texteLaden(sprache = gewuenschteSprache()) {
  const daten = await api.uebersetzungen(sprache)
  texte.katalog = daten.texte
  texte.sprache = daten.sprache
  document.documentElement.lang = daten.sprache
  // Every later request says which language it speaks — the browser's own
  // header only knows the system language, not this choice.
  spracheMerken(daten.sprache)
  return daten.sprache
}

export function spracheWaehlen(sprache) {
  localStorage.setItem(SPEICHER, sprache)
  return texteLaden(sprache)
}

/* Back to "auto": storage is cleared, the device decides again. */
export function spracheZuruecksetzen() {
  localStorage.removeItem(SPEICHER)
  return texteLaden()
}

/* What the switch in the settings should display: the fixed choice from
   storage, otherwise 'auto'. */
export function gemerkteSprachwahl() {
  return localStorage.getItem(SPEICHER) || 'auto'
}

/* A text for a dot path, e.g. t('chat.neu').

   If the key is missing, the key itself comes back instead of a blank spot:
   a visible `chat.neu` in the interface shows the error immediately, an
   empty button hides it.

   Placeholders go in curly braces, same notation as in the backend:
   t('werkzeug.fertig', { name: 'websuche' }). */
export function t(pfad, werte) {
  let wert = pfad.split('.').reduce((teil, schluessel) => teil?.[schluessel], texte.katalog)
  if (typeof wert !== 'string') return pfad
  if (werte) {
    for (const [schluessel, ersatz] of Object.entries(werte)) {
      wert = wert.split(`{${schluessel}}`).join(ersatz)
    }
  }
  return wert
}
