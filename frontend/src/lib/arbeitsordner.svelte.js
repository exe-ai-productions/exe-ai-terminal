/*
  The working folders of a chat — state and actions in one place.

  Split out of the component because the folders now live in two spots: above
  the input field while a chat is still empty, and in the header once it is
  running. Two views, one truth — the alternative would
  have been to keep the same logic twice and watch the two drift apart.

  The flight from one spot to the other is a Svelte crossfade. Both views ask
  for it here, so both use the same pair — a crossfade only works between
  elements that share one transition.
*/

import { crossfade } from 'svelte/transition'
import { cubicOut } from 'svelte/easing'

import { api } from './api.js'
import { t } from './texte.svelte.js'
import { zustand, aktuellerChat, chatsLaden, melde } from './zustand.svelte.js'

/* Four at most. The API enforces the same number —
   this here is only the polite half, so the plus can lock before someone
   runs into an error message. */
export const HOECHSTENS = 4

/* The flight: the pill leaves one spot and arrives at the other, and the
   framework works out the path. `fliegen` and `landen` are handed to the two
   views as out: and in: — matched up by the folder path as key. */
export const [landen, fliegen] = crossfade({
  duration: 420,
  easing: cubicOut,
  fallback: (knoten) => ({
    duration: 200,
    easing: cubicOut,
    css: (t) => `opacity: ${t}; transform: scale(${0.96 + 0.04 * t})`,
  }),
})

export const ordnerZustand = $state({
  /* Whether this machine has a folder dialog at all. Asked once at startup;
     without one, only the path field remains in the window. */
  dialogDa: false,
  maskeOffen: false,
  laeuft: false,
})

export function ordnerListe() {
  return aktuellerChat()?.working_dirs ?? []
}

/* Only the folder name, not the whole path — the working directory is known
   anyway. The full path stays in the tooltip, so the short form never has to
   lie about where something is. */
export function ordnerName(pfad) {
  const teile = String(pfad).split('/').filter(Boolean)
  return teile[teile.length - 1] || '/'
}

export async function dialogPruefen() {
  try {
    const auskunft = await api.ordnerDialogAuskunft()
    ordnerZustand.dialogDa = Boolean(auskunft?.verfuegbar)
  } catch {
    ordnerZustand.dialogDa = false
  }
}

export function maskeOeffnen() {
  if (ordnerListe().length >= HOECHSTENS) {
    melde(t('arbeitsordner.voll').replace('{anzahl}', HOECHSTENS), 'hinweis')
    return
  }
  ordnerZustand.maskeOffen = true
}

/* The flow: new chat → plus → set the working folder → write the first
   message. So in the empty start there is no chat row yet — we create one
   here rather than refusing. It stays untitled; the first message gives it
   its name (see App.svelte). */
async function chatSichern() {
  const vorhandener = aktuellerChat()
  if (vorhandener) return vorhandener
  const neuer = await api.chatAnlegen({
    title: t('chat.unbenannt'),
    endpoint_id: zustand.modellId,
  })
  zustand.aktiverChat = neuer.id
  zustand.nachrichten = []
  await chatsLaden()
  return aktuellerChat()
}

async function sichern(liste) {
  try {
    const chat = await chatSichern()
    if (!chat) return
    const geaendert = await api.chatAendern(chat.id, { working_dirs: liste })
    // Write back into the list the state holds, so every view that reads the
    // chat sees the new folders — not just the one that changed them.
    chat.working_dirs = geaendert.working_dirs
  } catch (fehler) {
    melde(fehler.message || t('fehler.allgemein'), 'fehler')
  }
}

export async function ordnerHinzufuegen(pfad) {
  if (!pfad) return
  if (ordnerListe().includes(pfad)) {
    ordnerZustand.maskeOffen = false
    return
  }
  await sichern([...ordnerListe(), pfad])
  ordnerZustand.maskeOffen = false
}

export async function ordnerLoesen(pfad) {
  await sichern(ordnerListe().filter((eintrag) => eintrag !== pfad))
}

/* The system dialog blocks as long as it is open — the service answers only
   once it is closed. `laeuft` keeps a second click out meanwhile. */
export async function systemdialog() {
  if (ordnerZustand.laeuft) return
  ordnerZustand.laeuft = true
  try {
    const liste = ordnerListe()
    const antwort = await api.ordnerDialogOeffnen(
      t('arbeitsordner.dialog_titel'),
      liste[liste.length - 1] || null,
    )
    // No path means cancelled. Nothing happened — say nothing.
    if (antwort?.pfad) await ordnerHinzufuegen(antwort.pfad)
  } catch (fehler) {
    melde(fehler.message || t('fehler.allgemein'), 'fehler')
  } finally {
    ordnerZustand.laeuft = false
  }
}
