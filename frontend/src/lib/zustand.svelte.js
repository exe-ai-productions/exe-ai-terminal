/*
  The shared state of the interface.

  Svelte 5 does this with $state: whatever lives here is reactive
  everywhere, without one component having to pass anything through to
  another. That was exactly the tedious part of the one big file — every
  change had to be written into the document by hand in three places.
*/

import { api } from './api.js'
import { t } from './texte.svelte.js'

export const zustand = $state({
  chats: [],
  modelle: [],
  nachrichten: [],
  version: '',
  aktiverChat: null,
  modellId: localStorage.getItem('modell') || '',
  suche: '',
  laeuft: null, // { abbruch, generationId } while an answer is running
  seitenleisteOffen: false,
  // Collapsed on the desktop: the sidebar goes away entirely. It used to
  // leave a narrow rail because the toggle lived inside it; the handle sits
  // on the seam now (teile/Seitengriff.svelte). Below 720 px,
  // `seitenleisteOffen` applies instead — there it slides over as a drawer.
  seitenleisteEingeklappt: localStorage.getItem('seitenleiste') === 'zu',
  // The sidebar's width in px, dragged at the seam and kept across starts.
  // While a drag runs, the width transition pauses so the edge follows the
  // hand instead of easing after it.
  seitenBreite: Number(localStorage.getItem('seitenbreite')) || 285,
  seitenZieht: false,
  werkzeuge: { aktiv: false, werkzeuge: [] },
  // Feature switches from the config (GET /meta, interface milestone C).
  // Until the answer arrives, everything counts as on — otherwise the
  // menu entries would flash away at startup and then back on.
  features: { mcp: true, image_generation: true, document_upload: true },
  // Look of the speech bubbles: filled or outline only (3.11).
  kontur: localStorage.getItem('kontur') === 'an',
  schrift: localStorage.getItem('schrift') || 'standard',
  blasenfarbe: localStorage.getItem('blasenfarbe') || '',
  // Pending confirmation before a tool runs (1.6). At most one at a time:
  // the server waits as long as it stands.
  /* The two model windows: local (what runs here) and cloud (providers).
     Windows rather than dropdowns — each carries a list and the settings of
     what is selected in it side by side, which no dropdown fits. Two entries
     in the menu bar, two modules: teile/ModelleLokal and teile/ModelleCloud. */
  lokalOffen: false,
  katalogOffen: false,
  cloudOffen: false,
  werkzeugeOffen: false,
  werkzeugfrage: null, // { generationId, aufrufId, name, argumente, chatId }
  // What the planned model-server start will roughly take — written by the
  // server form, shown in the local window's head next to the machine total.
  serverPlan: null,
  // Chats with a finished answer nobody has looked at yet — the sidebar
  // shows the pulsing dot for them.
  fertigeChats: [],
  // Which section fills the sidebar and the main area (6.5, variant A):
  // 'chats' or 'auftraege'. Deliberately not in localStorage — after
  // opening, you usually want to chat, not see yesterday's job list.
  bereich: 'chats',
  auftraege: [],
  // Job clicked in the sidebar: the main area unfolds it.
  auftragAusgewaehlt: null,
  // Search term of the job list. Unlike the chats, filtering happens in
  // the window, not on the server — the list is already there anyway.
  auftragSuche: '',
  // The start dialog lives here because its button sits in the sidebar
  // and the window next to it hangs in the main area.
  auftragStartenOffen: false,
  // The prompt/agents window likewise: it is opened from the menu bar,
  // but also from within the job dialog ("no agents yet").
  promptOffen: false,
  // Which source the editor opens with (A6): 'system' or 'tools'.
  // The settings menu has two entries pointing at the same window.
  promptStart: 'system',
  // The house's pending prompt dialog: replaces the bare
  // confirm()/prompt() boxes of the browser. At most one at a time.
  frage: null, // { text, eingabe, okSchluessel, aufloesen }
})

/* The windows the menu bar opens are one place each — opening one closes
   the others. Without this, a second window lands behind the first one's
   veil and the menu click looks dead. */
export function menueFensterOeffnen(name) {
  zustand.lokalOffen = name === 'lokal'
  zustand.cloudOffen = name === 'cloud'
  zustand.katalogOffen = name === 'katalog'
  zustand.werkzeugeOffen = name === 'werkzeuge'
  zustand.promptOffen = name === 'prompt'
}

/* A prompt dialog in the house style. Returns a promise:
   without an input field true/false, with an input field the text or null.

     if (!(await frage(t('chat.loeschen_frage')))) return
     const neu = await frage(t('chat.neuer_titel'), { eingabe: alt })

   The bare confirm()/prompt() boxes of the browser are off-limits from
   here on — they were the last foreign body in the interface. */
export function frage(text, { eingabe = null, okSchluessel = 'app.ok' } = {}) {
  return new Promise((aufloesen) => {
    zustand.frage = { text, eingabe, okSchluessel, aufloesen }
  })
}

export function frageBeantworten(wert) {
  const offene = zustand.frage
  if (!offene) return
  zustand.frage = null
  offene.aufloesen(wert)
}

/* Chats whose answer finished while the user was looking elsewhere. The
   sidebar marks them with the pulsing dot until they are opened. */
export function chatFertigMerken(id) {
  if (id && !zustand.fertigeChats.includes(id)) zustand.fertigeChats.push(id)
}

export function chatFertigGesehen(id) {
  if (id && zustand.fertigeChats.includes(id))
    zustand.fertigeChats = zustand.fertigeChats.filter((c) => c !== id)
}

/* A standing yes for one tool in one chat, given via the third button in
   the confirmation box. Kept in memory only: a reload starts cautious
   again, which is the right side to err on for a tool that runs
   commands. */
const werkzeugFreigaben = new Map()

export function werkzeugImmerErlaubt(chatId, name) {
  return werkzeugFreigaben.get(chatId)?.has(name) ?? false
}

export function werkzeugImmerErlauben(chatId, name) {
  if (!chatId || !name) return
  if (!werkzeugFreigaben.has(chatId)) werkzeugFreigaben.set(chatId, new Set())
  werkzeugFreigaben.get(chatId).add(name)
}

/* Yes or no to the server. The box disappears immediately — the answer
   has been given, leaving it up would invite a second click. If reporting
   it fails, the server runs into the rejection on its own after its
   timeout; hence only a notice, no restoring. */
export async function werkzeugfrageBeantworten(erlaubt, immer = false) {
  const frage = zustand.werkzeugfrage
  if (!frage) return
  zustand.werkzeugfrage = null
  if (immer && erlaubt) werkzeugImmerErlauben(frage.chatId, frage.name)
  try {
    await api.werkzeugBestaetigen(frage.generationId, frage.aufrufId, erlaubt)
  } catch {
    melde(t('werkzeug.antwort_kam_nicht_an'), 'fehler')
  }
}

export const meldungen = $state({ liste: [] })

let naechsteMeldung = 0

/* One notification system for all cases (3.8).

   Errors stay up longer than confirmations: a confirmation was expected,
   an error has to be read first.

   Kinds: hinweis, erfolg, fehler, werkzeug.

   `dauerhaft` means: stays up until someone changes or closes it. The
   tool call needs that — it reports once at the start and again when
   the result is in. */
const DAUER = { fehler: 7000, erfolg: 2400, werkzeug: 3000, hinweis: 3200 }
const uhren = new Map()

/* `werkzeug` carries the tool name (e.g. web_search) so the notification
   can show the same icon as the line in the chat — one icon, one
   language. */
export function melde(text, art = 'hinweis', { dauerhaft = false, werkzeug = '' } = {}) {
  const id = ++naechsteMeldung
  meldungen.liste.push({ id, text, art, werkzeug })
  if (meldungen.liste.length > 3) schliesseMeldung(meldungen.liste[0].id)
  if (!dauerhaft) _uhrStellen(id, DAUER[art] ?? 3200)
  return id
}

/* Rewrite a running notification instead of putting a second one next to it. */
export function aktualisiereMeldung(id, { text, art, dauerhaft = false } = {}) {
  const meldung = meldungen.liste.find((m) => m.id === id)
  if (!meldung) return
  if (text !== undefined) meldung.text = text
  if (art !== undefined) meldung.art = art
  if (!dauerhaft) _uhrStellen(id, DAUER[meldung.art] ?? 3200)
}

function _uhrStellen(id, dauer) {
  clearTimeout(uhren.get(id))
  uhren.set(id, setTimeout(() => schliesseMeldung(id), dauer))
}

export function schliesseMeldung(id) {
  clearTimeout(uhren.get(id))
  uhren.delete(id)
  const stelle = meldungen.liste.findIndex((m) => m.id === id)
  if (stelle !== -1) meldungen.liste.splice(stelle, 1)
}

export function aktuellerChat() {
  return zustand.chats.find((c) => c.id === zustand.aktiverChat) || null
}
export function aktuellesModell() {
  return zustand.modelle.find((m) => m.id === zustand.modellId) || null
}

export async function featuresLaden() {
  try {
    const meta = await api.meta()
    if (meta?.features) zustand.features = meta.features
    if (meta?.version) zustand.version = meta.version
  } catch {
    /* Without an answer, the optimistic default stands — the API locks
       down disabled features itself anyway. */
  }
}

export async function modelleLaden(frisch = false) {
  try {
    zustand.modelle = await api.modelle(frisch)
    const bekannt = zustand.modelle.some((m) => m.id === zustand.modellId)
    if (!bekannt && zustand.modelle.length) modellWaehlen(zustand.modelle[0].id)
  } catch {
    melde(t('modell.nicht_geladen'), 'fehler')
  }
}

/* Outline on or off. Sits as an attribute on the root element so the rule
   applies in one place instead of being queried in every component — the
   same construction as with light and dark mode. */
export function konturSetzen(an) {
  zustand.kontur = an
  localStorage.setItem('kontur', an ? 'an' : 'aus')
  if (an) document.documentElement.setAttribute('data-blasen', 'kontur')
  else document.documentElement.removeAttribute('data-blasen')
}
konturSetzen(zustand.kontur)

/* Text size of the chat contents, three steps. The column widens with the
   letters so a line keeps its length in characters — bigger type on more
   room, not fewer words per line. Root attribute, like the mode. */
export function schriftSetzen(stufe) {
  zustand.schrift = stufe
  localStorage.setItem('schrift', stufe)
  if (stufe && stufe !== 'standard') document.documentElement.setAttribute('data-schrift', stufe)
  else document.documentElement.removeAttribute('data-schrift')
}
schriftSetzen(zustand.schrift)

/* The user's own bubble colour. Only that one surface — replies, tool
   chips and everything else keep the house palette. The text inside flips
   between the two ink colours by the luminance of the chosen ground, so
   no choice can make a bubble unreadable. */
export function blasenfarbeSetzen(farbe) {
  zustand.blasenfarbe = farbe || ''
  const wurzel = document.documentElement.style
  if (!farbe) {
    localStorage.removeItem('blasenfarbe')
    wurzel.removeProperty('--blase-eigen')
    wurzel.removeProperty('--blase-eigen-text')
    return
  }
  localStorage.setItem('blasenfarbe', farbe)
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(farbe.slice(i, i + 2), 16) / 255)
  const hell = 0.2126 * r + 0.7152 * g + 0.0722 * b
  wurzel.setProperty('--blase-eigen', farbe)
  wurzel.setProperty('--blase-eigen-text', hell > 0.45 ? '#1a1a18' : '#ecebe6')
}
blasenfarbeSetzen(zustand.blasenfarbe)

/* One toggle for three ways in: the handle on the seam, ⌘B, and the icon
   in the menu bar on a narrow screen. On the desktop the sidebar goes away
   entirely — the handle is what brings it back — on the phone it closes the
   drawer. The choice is remembered, which is why nobody flips the state by
   hand. */
export function seitenleisteSchalten() {
  zustand.seitenleisteEingeklappt = !zustand.seitenleisteEingeklappt
  zustand.seitenleisteOffen = false
  localStorage.setItem('seitenleiste', zustand.seitenleisteEingeklappt ? 'zu' : 'auf')
}

/* The sidebar is dragged, not configured: the seam clamps the hand to what
   the head row can carry (below, the section labels would clip) and to what
   still leaves the chat its room. */
const SEITEN_MIN = 220
const SEITEN_MAX = 400

export function seitenBreiteSetzen(px) {
  zustand.seitenBreite = Math.round(Math.min(SEITEN_MAX, Math.max(SEITEN_MIN, px)))
  localStorage.setItem('seitenbreite', String(zustand.seitenBreite))
}

export function modellWaehlen(id) {
  zustand.modellId = id
  localStorage.setItem('modell', id)
}

export async function chatsLaden() {
  try {
    zustand.chats = await api.chats(zustand.suche.trim())
  } catch {
    melde(t('chat.nicht_geladen'), 'fehler')
  }
}

export async function chatOeffnen(id) {
  // Without a chat there is nothing to fetch. If this guard were missing,
  // the interface would query `/chats//messages` — with a double slash,
  // because the id is empty — and catch a 404 every few seconds,
  // cluttering the log.
  if (!id) {
    zustand.aktiverChat = null
    zustand.nachrichten = []
    return
  }
  zustand.aktiverChat = id
  chatFertigGesehen(id)
  try {
    zustand.nachrichten = await api.nachrichten(id)
  } catch {
    zustand.nachrichten = []
    melde(t('chat.nicht_geoeffnet'), 'fehler')
    return
  }
  const chat = aktuellerChat()
  if (chat?.endpoint_id && zustand.modelle.some((m) => m.id === chat.endpoint_id)) {
    modellWaehlen(chat.endpoint_id)
  }
  zustand.seitenleisteOffen = false
}

export function neuerChat() {
  zustand.bereich = 'chats'
  zustand.aktiverChat = null
  zustand.nachrichten = []
}

/* Jobs (6.5). Loaded on switching over and then on a cadence as long as
   the section is open — the cadence is set by the component, not the
   state. */
export async function auftraegeLaden() {
  try {
    zustand.auftraege = await api.auftraege()
  } catch {
    melde(t('jobs.nicht_geladen'), 'fehler')
  }
}

export async function auftragLoeschen(id) {
  await api.auftragLoeschen(id)
  if (zustand.auftragAusgewaehlt === id) zustand.auftragAusgewaehlt = null
  await auftraegeLaden()
}

export function bereichWechseln(bereich) {
  zustand.bereich = bereich
  if (bereich === 'auftraege') auftraegeLaden()
}

export async function chatAendern(id, daten) {
  const geaendert = await api.chatAendern(id, daten)
  const stelle = zustand.chats.findIndex((c) => c.id === id)
  if (stelle !== -1) zustand.chats[stelle] = geaendert
  await chatsLaden()
  return geaendert
}

export async function chatLoeschen(id) {
  await api.chatLoeschen(id)
  if (zustand.aktiverChat === id) neuerChat()
  await chatsLaden()
}

/* How full is the context?

   The number comes from the usage data of the last answer, the ceiling
   from the model server. Where one of them is missing, nothing is made
   up. */
export function kontextStand() {
  const letzte = [...zustand.nachrichten]
    .reverse()
    .find((n) => n.stats?.nutzung?.total_tokens)
  const gesamt = aktuellesModell()?.context_tokens || null
  const genutzt = letzte?.stats?.nutzung?.total_tokens || 0
  return {
    genutzt,
    gesamt,
    anteil: gesamt ? Math.min(100, (genutzt / gesamt) * 100) : 0,
  }
}
