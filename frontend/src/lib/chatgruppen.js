/*
  The chat list, cut into days.

  One heading, "Recent", used to stand over everything that was not
  pinned — and under it a run of thirty titles that said nothing about
  when any of them happened. Whoever was looking for "the thing from
  Tuesday" had to open chats to find out which one Tuesday was.

  So the list gets the same headings a calendar would give it: PINNED,
  TODAY, YESTERDAY, and from there one heading per day with its date.
  Nothing is re-sorted — the order is the server's, newest first, and
  cutting it into days only ever draws lines between rows that are already
  neighbours.

  No imports on purpose: this is a pure function of a list and a moment,
  which makes it readable in one piece and runnable in a test without the
  interface around it. The heading TEXTS are not decided here — a group
  carries either a catalogue key or a date, and the sidebar turns that
  into words in whatever language is set.
*/

/* Midnight of the day a moment falls on, in local time. Days are what a
   person sees on their own wall calendar, not what UTC says. */
function tagesbeginn(zeitpunkt) {
  const tag = new Date(zeitpunkt)
  tag.setHours(0, 0, 0, 0)
  return tag
}

/* Which timestamp a chat is filed under: when it last had something to
   say. Filing by creation date would drop a conversation carried on for
   a week under the day it started, where nobody looks for it. */
function stempel(chat) {
  const wert = chat.updated_at || chat.created_at
  const zeit = wert ? new Date(wert).getTime() : NaN
  return Number.isNaN(zeit) ? null : zeit
}

/* The groups, in the order they are shown.

   Each group is `{ schluessel, datum, chats }`: `schluessel` is a
   catalogue key for the three named groups and null for a dated one,
   `datum` the other way round. Empty groups are not returned — a heading
   over nothing is noise.

   `jetzt` is a parameter rather than a call to the clock inside, so the
   boundaries can be tested at all. */
export function chatgruppen(chats, jetzt = Date.now()) {
  const angeheftet = []
  const uebrige = []
  for (const chat of chats || []) (chat.pinned ? angeheftet : uebrige).push(chat)

  const heute = tagesbeginn(jetzt).getTime()
  const gestern = heute - 86400000

  const gruppen = []
  if (angeheftet.length)
    gruppen.push({ schluessel: 'chat.angeheftet', datum: null, chats: angeheftet })

  /* Built by walking the list once: a new group starts wherever the day
     changes. That is why the incoming order survives untouched. */
  let laufend = null
  for (const chat of uebrige) {
    const zeit = stempel(chat)
    /* A chat without a usable date cannot be filed by day. It joins
       whatever group is open rather than starting one of its own — a
       heading reading "Invalid Date" would be worse than a row sitting a
       line too high. */
    if (zeit === null && laufend) {
      laufend.chats.push(chat)
      continue
    }
    /* Anything dated today or later belongs to today — and is FILED under
       today, not merely labelled that way. Labelling alone would put a
       chat stamped after midnight and one stamped this afternoon under two
       separate groups carrying the same heading, and two groups with one
       key is an error Svelte raises rather than survives. The case is not
       hypothetical: the clock here ticks once a minute, so for up to a
       minute after midnight `heute` is still yesterday. */
    const roh = zeit === null ? heute : tagesbeginn(zeit).getTime()
    const tag = roh > heute ? heute : roh
    const schluessel = tag === heute ? 'chat.heute' : tag === gestern ? 'chat.gestern' : null
    if (!laufend || laufend.tag !== tag) {
      laufend = { schluessel, datum: schluessel ? null : new Date(tag), tag, chats: [] }
      gruppen.push(laufend)
    }
    laufend.chats.push(chat)
  }
  return gruppen.map(({ schluessel, datum, chats: liste }) => ({
    schluessel,
    datum,
    chats: liste,
  }))
}

/* A dated heading in the language of the interface: "July 7" in English,
   "7. Juli" in German — the order of day and month is the language's
   business, not ours, so it comes from Intl rather than from a format
   string in the catalogue.

   The year appears only when it is not the current one. Within the year it
   would be noise on every heading; across years its absence would be a
   riddle. */
export function gruppenDatum(datum, sprache, jetzt = Date.now()) {
  const gleichesJahr = datum.getFullYear() === new Date(jetzt).getFullYear()
  return new Intl.DateTimeFormat(sprache || 'en', {
    day: 'numeric',
    month: 'long',
    ...(gleichesJahr ? {} : { year: 'numeric' }),
  }).format(datum)
}
