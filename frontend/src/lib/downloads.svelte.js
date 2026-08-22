/*
  What is being fetched, in one place.

  The service downloads ONE file at a time — that is deliberate and stays:
  two streams share the same line and the same disk, and finish later than
  two in a row. What was missing is everything around that one file: a
  second click used to earn an error, and the only way to watch a download
  was to search the model up again and stare at its card.

  So the queue lives here instead of inside the catalogue window. Whoever
  clicks fetch while something runs lines up behind it; the panel shows the
  whole row at once, and the count rides on the header button from every
  tab. Finished entries stay in the list while the window lives — proof
  that it arrived, not a message that flashes past.

  Session-only, like the picture queue: a download that was interrupted is
  restarted from the card, not resumed from a list of intentions.
*/

import { api } from './api.js'

export const downloads = $state({
  /* What the service reports right now, or null while nothing runs. */
  laufend: null,
  /* Lined up behind it, in the order they were asked for. */
  warteschlange: [],
  /* Arrived in this session, newest last. */
  fertig: [],
  /* Whether the panel is showing. */
  offen: false,
})

/* Running plus waiting — what the button's number says. Finished ones are
   not counted: they are no longer work, only a receipt. */
export function anzahlAktiv() {
  return (downloads.laufend ? 1 : 0) + downloads.warteschlange.length
}

/* The local file a job writes — what the panel shows and what makes two
   jobs the same job. Two repositories share file names, so the local name
   is the one that decides. */
export const zieldatei = (job) => job.ziel ?? job.datei

/* Rows need a key that survives a same-named file being queued twice, and
   the file name cannot give one. A plain counter can. */
let laufendeNummer = 0

/* One job, as the service takes it. Asking twice for the same file is a
   slip of the hand, not a wish for two copies — the second ask is
   dropped rather than queued. */
export function einreihen(job) {
  const ziel = zieldatei(job)
  if (downloads.laufend?.datei === ziel) return
  if (downloads.warteschlange.some((j) => zieldatei(j) === ziel)) return
  downloads.warteschlange.push({ ...job, nummer: ++laufendeNummer })
}

export function ausreihen(job) {
  const stelle = downloads.warteschlange.indexOf(job)
  if (stelle !== -1) downloads.warteschlange.splice(stelle, 1)
}

export function fertigMerken(datei, groesse) {
  if (!datei || downloads.fertig.some((f) => f.datei === datei)) return
  downloads.fertig.push({ datei, groesse })
}

/* ONE place starts downloads, and it is this one.

   Two places used to: the click and the poll that notices a finished file.
   Between the poll reading "done" and the click reading its own stale copy
   of that state, both could call the service — and the second one earned a
   409 while its job fell on the floor. Now every wish is queued and only
   this driver starts anything, guarded so two calls cannot overlap.

   Returns what the service answered for a freshly started job, or null
   when nothing was started.
*/
let treibt = false

export async function antreiben(vorhanden = []) {
  if (treibt || downloads.laufend) return null
  treibt = true
  try {
    while (
      downloads.warteschlange.length
      && vorhanden.includes(zieldatei(downloads.warteschlange[0]))
    ) {
      downloads.warteschlange.shift()
    }
    // Taken off the queue before the call, not after: a job that cannot be
    // started must not be tried again every two seconds forever. It is
    // gone, the reason is reported, and its card still offers Download.
    const job = downloads.warteschlange.shift()
    if (!job) return null
    const stand = await api.modellHolen(
      job.repo, job.datei, job.ziel ?? null, job.gehoert_zu ?? null,
      job.rolle ?? null, job.art ?? 'chat', job.unterordner ?? null,
    )
    downloads.laufend = stand
    return stand
  } finally {
    treibt = false
  }
}
