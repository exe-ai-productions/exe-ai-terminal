/*
  Everything this chat has had done for it, in one list.

  The terminal module started as a window on shell commands, and it kept
  that view long after the program had grown five file tools, a question
  tool, a memory and a whole shelf of MCP servers. A conversation spent
  reading and writing files reported "no command has run yet" — empty and
  wrong, because the module was looking into one drawer of a cupboard.

  So the list is built from both places a call can be:

    * the RUNS — commands with live output, which have their own stream and
      keep writing after the answer is over. They stay the big entries.
    * the calls recorded on the messages — every tool, whatever its source,
      built in or from a server. They become one quiet line each.

  A shell command is both by nature: a run AND a recorded call. It appears
  once, as its run — the big entry says everything the quiet line would and
  carries the output besides.

  The ORDER is taken from the messages, and the runs are threaded into it
  at the calls that started them. Sorting by a timestamp was not possible:
  a run knows its number, a call knows only its place in the conversation,
  and there is no clock both of them read.

  No imports on purpose: this is a pure function of two lists, which makes
  it readable in one piece and runnable in a test without the interface
  standing up around it.
*/

/* Tools whose story a run already tells. */
const ALS_LAUF = new Set(['run_command'])

/* How much of an argument stands in the line. Enough to recognise WHICH
   call it was, not enough to wrap: the line is a record, not a transcript.
   The full arguments are in the chat, on the message itself. */
const ARGUMENT_LAENGE = 60

/* One readable word for what a call was about.

   The first argument that carries something is the right one often enough
   to be worth it: a path for the file tools, a query for a search, a
   command for the shell. A tool whose arguments say nothing gets no
   subtitle rather than an invented one. */
export function kurzargument(argumente) {
  if (!argumente || typeof argumente !== 'object') return ''
  for (const wert of Object.values(argumente)) {
    if (typeof wert === 'string' && wert.trim()) {
      const knapp = wert.trim().replace(/\s+/g, ' ')
      return knapp.length > ARGUMENT_LAENGE ? knapp.slice(0, ARGUMENT_LAENGE) + '…' : knapp
    }
    if (typeof wert === 'number' || typeof wert === 'boolean') return String(wert)
  }
  return ''
}

/* The calls one message recorded.

   While an answer streams, they hang on the message object itself; once it
   is stored they live in its stats. Both are read, the live one wins —
   during a run it is the more complete of the two. */
function aufrufeVon(nachricht) {
  return nachricht.werkzeuge?.length ? nachricht.werkzeuge : nachricht.stats?.werkzeuge || []
}

function alsZeile(aufruf) {
  return {
    art: 'aufruf',
    name: aufruf.name,
    server: aufruf.server || '',
    kurz: kurzargument(aufruf.argumente),
    fehlgeschlagen: Boolean(aufruf.fehlgeschlagen),
  }
}

/* Runs and calls in the order they happened.

   The messages carry the order; the runs are handed out in theirs, one per
   shell call, as those calls come along. A run left over at the end —
   started from the CLI module, or belonging to a message that is no longer
   loaded — is appended rather than dropped: it happened, so it is shown.

   A shell call with no run left to claim falls back to a quiet line. That
   is the honest picture of a service that was restarted: the call is in
   the conversation, its output is not in memory anymore. */
export function historie(nachrichten, laeufe) {
  const alle = [...(laeufe || [])]
  /* Only command runs are handed to a shell call. A drawing job has no tool
     call behind it at all — it comes from the picture window — so letting a
     shell call claim one would file the picture under a command that never
     drew it, and leave the command that really ran without its output. */
  const offen = alle.filter((lauf) => (lauf.art || 'befehl') === 'befehl')
  const vergeben = new Set()
  const eintraege = []
  for (const nachricht of nachrichten || []) {
    for (const aufruf of aufrufeVon(nachricht)) {
      if (!ALS_LAUF.has(aufruf.name)) {
        eintraege.push(alsZeile(aufruf))
        continue
      }
      const lauf = offen.shift()
      if (lauf) vergeben.add(lauf)
      eintraege.push(lauf ? { art: 'lauf', lauf } : alsZeile(aufruf))
    }
  }
  /* Everything nobody claimed, in the order it happened: runs started from
     the CLI module, drawing jobs, and runs whose message is no longer
     loaded. Walked over the original list rather than the filtered one, so
     the order between the two kinds is the order they really came in. */
  for (const lauf of alle) {
    if (!vergeben.has(lauf)) eintraege.push({ art: 'lauf', lauf })
  }
  return eintraege
}

/* Is there anything at all to show?

   Asked before the empty notice: "no command has run yet" is only true
   when nothing of either kind is there. That sentence over a chat full of
   file work was the whole reason for this module. */
export function leer(nachrichten, laeufe) {
  return historie(nachrichten, laeufe).length === 0
}
