/*
  Which fenced block is a file, and what can be done with it — the catalogue.

  Its own module because three places ask the same question and must get the
  same answer: the renderer that turns a block into a file box, the preview
  window that has to decide how to show it, and the save button that needs a
  name and an extension.

  The dividing line is not "is this code" but "is this a document". A shell
  snippet in an answer is meant to be read in place; an HTML page is meant to
  be looked at, kept, or opened. Only the second kind becomes a file.

  `zeigen` says what the preview can do with it:

      gerendert   the browser draws it — HTML and SVG, in a sealed frame
      tabelle     rows and columns, read from the text itself
      text        monospace, exactly as written

  Everything can be downloaded and saved, no matter how it is shown.
*/

/*
  The marks. One sheet with a folded corner carries all of them — the file
  the user hands in and the file the assistant hands back are the same kind
  of thing, so they wear the same body. Only what stands on the sheet
  changes: lines for prose, a grid for a table, brackets for markup, braces
  for data, a horizon for a picture.

  Drawn in the house measurements (64 grid, main stroke 5, secondary 4.5,
  round ends) and standing still — a mark that says what something IS does
  not animate; only a running tool call does.
*/
const BLATT = '<path d="M16 8 H38 L48 18 V56 H16 Z" stroke-width="5" />' +
  '<path d="M38 8 V18 H48" stroke-width="4.5" />'

const ZEICHEN = {
  zeilen: BLATT + '<path d="M24 32 H40 M24 42 H40" stroke-width="4.5" />',
  gitter: BLATT +
    '<path d="M23 30 H41 M23 40 H41 M32 26 V46" stroke-width="4.5" />',
  klammern: BLATT +
    '<path d="M29 32 L24 38 L29 44 M35 32 L40 38 L35 44" stroke-width="4.5" />',
  geschweift: BLATT +
    '<path d="M29 30 C26 30 27 37 24 37 C27 37 26 45 29 45" stroke-width="4.5" />' +
    '<path d="M35 30 C38 30 37 37 40 37 C37 37 38 45 35 45" stroke-width="4.5" />',
  bild: BLATT +
    '<path d="M23 45 L29 37 L34 43 L38 39 L41 45 Z" stroke-width="4.5" />',
}

const ARTEN = {
  html: { endung: 'html', typ: 'text/html', zeigen: 'gerendert', zeichen: 'klammern' },
  svg: { endung: 'svg', typ: 'image/svg+xml', zeigen: 'gerendert', zeichen: 'bild' },
  csv: { endung: 'csv', typ: 'text/csv', zeigen: 'tabelle', zeichen: 'gitter' },
  tsv: { endung: 'tsv', typ: 'text/tab-separated-values', zeigen: 'tabelle', zeichen: 'gitter' },
  markdown: { endung: 'md', typ: 'text/markdown', zeigen: 'text', zeichen: 'zeilen' },
  md: { endung: 'md', typ: 'text/markdown', zeigen: 'text', zeichen: 'zeilen' },
  json: { endung: 'json', typ: 'application/json', zeigen: 'text', zeichen: 'geschweift' },
  yaml: { endung: 'yaml', typ: 'application/yaml', zeigen: 'text', zeichen: 'geschweift' },
  yml: { endung: 'yaml', typ: 'application/yaml', zeigen: 'text', zeichen: 'geschweift' },
  xml: { endung: 'xml', typ: 'application/xml', zeigen: 'text', zeichen: 'klammern' },
}

/** The finished mark for a fence language, ready to drop into markup. */
export function dateizeichen(sprache, groesse = 22) {
  const art = dateiart(sprache)
  if (!art) return ''
  return `<svg class="datei-zeichen" width="${groesse}" height="${groesse}" ` +
    'viewBox="0 0 64 64" fill="none" stroke="currentColor" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    ZEICHEN[art.zeichen] + '</svg>'
}

/**
 * How much a file weighs, in the shortest honest form.
 *
 * A fact, not a state — so it is told in plain text and carries no colour.
 */
export function dateigroesse(inhalt) {
  const bytes = new Blob([inhalt ?? '']).size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** The catalogue entry for a fence language, or null if it is not a document. */
export function dateiart(sprache) {
  return ARTEN[String(sprache || '').toLowerCase().trim()] || null
}

/**
 * A file name for a block.
 *
 * The model rarely gives one, so one is made up — and it has to be stable
 * within a message, otherwise the same file is called something else after
 * every keystroke while the answer is still streaming in.
 */
export function dateiname(sprache, nummer) {
  const art = dateiart(sprache)
  if (!art) return null
  return `${sprache.toLowerCase()}-${nummer}.${art.endung}`
}

/** Rows and columns out of a separated text, quoted fields included. */
export function tabelleLesen(text, trenner = ',') {
  const zeilen = []
  let feld = '', reihe = [], inAnfuehrung = false

  for (let i = 0; i < text.length; i++) {
    const z = text[i]
    if (inAnfuehrung) {
      if (z === '"' && text[i + 1] === '"') { feld += '"'; i++ }
      else if (z === '"') inAnfuehrung = false
      else feld += z
    } else if (z === '"') {
      inAnfuehrung = true
    } else if (z === trenner) {
      reihe.push(feld); feld = ''
    } else if (z === '\n') {
      reihe.push(feld); zeilen.push(reihe); reihe = []; feld = ''
    } else if (z !== '\r') {
      feld += z
    }
  }
  if (feld || reihe.length) { reihe.push(feld); zeilen.push(reihe) }

  return zeilen.filter((r) => r.some((f) => f !== ''))
}
