/*
Markdown rendering and syntax highlighting.

Markdown itself is still done here, by hand: nothing is fetched at runtime,
nothing leaves the machine. The syntax colouring moved out to
lib/einfaerben.js, which uses highlight.js — hand-written patterns cannot
tell a regex literal from a division, and that is where they broke.

Order matters: first the code blocks are taken out and parked, then the
rest is transformed, and at the end the blocks come back. Otherwise
Markdown inside code would be interpreted — an asterisk in a Python line
would suddenly be italic.

Everything is escaped beforehand. Untreated text never ends up in the
document.
*/

import { hervorheben } from './einfaerben.js'
import { t } from './texte.svelte.js'
import { dateiart, dateigroesse, dateiname, dateizeichen } from './dateiarten.js'


function maskieren(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/*
  For code: quotation marks stay as they are.

  Inside an element they are harmless — they only need escaping in
  attribute values. And they have to be preserved, because otherwise the
  string detection finds nothing anymore: "text" would have become
  &quot;text&quot;, and no pattern in the world searches for that.
*/
function maskierenInhalt(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/*
  The line numbers beside a block.

  Their own element, never part of the code: `user-select: none` keeps them
  out of a selection, and the copy button takes the raw source anyway. A
  number that lands in the clipboard turns pasted code into broken code.

  From two lines on. A single line has nothing to count.
*/
function nummernspalte(code) {
  const anzahl = code.split('\n').length;
  if (anzahl < 2) return '';
  let ziffern = '';
  for (let n = 1; n <= anzahl; n++) ziffern += n + '\n';
  return '<span class="code-nummern" aria-hidden="true">' + ziffern + '</span>';
}

/* ---------- Markdown ---------- */

function inline(text) {
  return text
    .replace(/`([^`]+)`/g, (_, c) => '<code>' + c + '</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/~~([^~]+)~~/g, '<del>$1</del>')
    .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

function tabelle(zeilen) {
  const zelle = (z) => z.trim().replace(/^\||\|$/g, '').split('|').map((s) => s.trim());
  const kopf = zelle(zeilen[0]);
  const koerper = zeilen.slice(2).map(zelle);
  let html = '<table><thead><tr>' + kopf.map((z) => '<th>' + inline(z) + '</th>').join('') +
    '</tr></thead><tbody>';
  koerper.forEach((reihe) => {
    html += '<tr>' + reihe.map((z) => '<td>' + inline(z) + '</td>').join('') + '</tr>';
  });
  return html + '</tbody></table>';
}

function rendern(quelltext) {
  const bloecke = [];
  let dateien = 0;

  // Take out the code blocks before anything else happens.
  let text = String(quelltext || '').replace(
    /```([\w+-]*)\n?([\s\S]*?)```/g,
    function (_, sprache, code) {
      // Both texts come from the catalog. Not escaped, because they come
      // from our own catalog and not from the model's answer.
      const kopieren = t('nachricht.kopieren');
      const roh = code.replace(/\n$/, '');
      const art = dateiart(sprache);

      // A document does not want to be read as source in the middle of an
      // answer — it wants to be looked at, kept, or put away. So it becomes
      // a closed box, and the source rides along inside it, hidden: the
      // preview window then needs no second channel to get at it.
      if (art) {
        const name = dateiname(sprache, ++dateien);
        const fakten = art.endung.toUpperCase() + ' · ' + dateigroesse(roh);
        bloecke.push(
          '<div class="dateikasten" data-art="' + maskieren(sprache.toLowerCase()) +
            '" data-name="' + maskieren(name) + '">' +
            '<button class="datei-knopf" type="button">' +
              // Our own constant markup, never anything from the answer.
              dateizeichen(sprache) +
              '<span class="datei-text">' +
                '<span class="datei-name">' + maskieren(name) + '</span>' +
                '<span class="datei-fakten">' + maskieren(fakten) + '</span>' +
              '</span>' +
              '<span class="datei-hinweis">' + maskieren(t('datei.ansehen')) + '</span>' +
            '</button>' +
            '<pre hidden><code>' + maskierenInhalt(roh) + '</code></pre>' +
          '</div>');
        return '' + (bloecke.length - 1) + '';
      }

      const kopf = sprache
        ? `<div class="code-kopf"><span>${maskieren(sprache)}</span>` +
          `<button class="code-kopieren" title="${kopieren}">${kopieren}</button></div>`
        : '';
      bloecke.push('<div class="codeblock">' + kopf + '<pre>' + nummernspalte(roh) +
        '<code>' + hervorheben(roh, sprache) + '</code></pre></div>');
      return '' + (bloecke.length - 1) + '';
    }
  );

  text = maskieren(text);

  const zeilen = text.split('\n');
  const raus = [];
  let liste = null, zitat = [], absatz = [];

  const absatzSchliessen = () => {
    if (absatz.length) { raus.push('<p>' + inline(absatz.join(' ')) + '</p>'); absatz = []; }
  };
  const listeSchliessen = () => {
    if (liste) { raus.push('</' + liste + '>'); liste = null; }
  };
  const zitatSchliessen = () => {
    if (zitat.length) {
      raus.push('<blockquote>' + inline(zitat.join(' ')) + '</blockquote>');
      zitat = [];
    }
  };
  const allesSchliessen = () => { absatzSchliessen(); listeSchliessen(); zitatSchliessen(); };

  for (let i = 0; i < zeilen.length; i++) {
    const zeile = zeilen[i];
    const roh = zeile.trim();

    if (!roh) { allesSchliessen(); continue; }

    if (/^\d+$/.test(roh)) { allesSchliessen(); raus.push(roh); continue; }

    const ueberschrift = roh.match(/^(#{1,4})\s+(.*)$/);
    if (ueberschrift) {
      allesSchliessen();
      const stufe = ueberschrift[1].length + 1;
      raus.push('<h' + stufe + '>' + inline(ueberschrift[2]) + '</h' + stufe + '>');
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(roh)) { allesSchliessen(); raus.push('<hr>'); continue; }

    if (/^&gt;\s?/.test(roh)) {
      absatzSchliessen(); listeSchliessen();
      zitat.push(roh.replace(/^&gt;\s?/, ''));
      continue;
    }

    // Table: header row plus a separator row of dashes
    if (roh.includes('|') && i + 1 < zeilen.length && /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(zeilen[i + 1])) {
      allesSchliessen();
      const block = [zeilen[i], zeilen[i + 1]];
      let j = i + 2;
      while (j < zeilen.length && zeilen[j].includes('|') && zeilen[j].trim()) { block.push(zeilen[j]); j++; }
      raus.push(tabelle(block));
      i = j - 1;
      continue;
    }

    const punkt = roh.match(/^[-*+]\s+(.*)$/);
    const nummer = roh.match(/^\d+\.\s+(.*)$/);
    if (punkt || nummer) {
      absatzSchliessen(); zitatSchliessen();
      const art = punkt ? 'ul' : 'ol';
      if (liste !== art) { listeSchliessen(); raus.push('<' + art + '>'); liste = art; }
      raus.push('<li>' + inline((punkt || nummer)[1]) + '</li>');
      continue;
    }

    listeSchliessen(); zitatSchliessen();
    absatz.push(roh);
  }
  allesSchliessen();

  return raus.join('\n').replace(/(\d+)/g, (_, i) => bloecke[i]);
}

/*
  The documents in one answer, without rendering it.

  The rail beside the chat opens a tab for each of them as they arrive, and
  it must not have to read that out of the page: the answer is the source,
  the DOM is only a picture of it. Same rule as above decides what counts as
  a document — one function, not two that drift apart.
*/
function dateienAus(quelltext) {
  const gefunden = [];
  let dateien = 0;
  String(quelltext || '').replace(
    /```([\w+-]*)\n?([\s\S]*?)```/g,
    function (_, sprache, code) {
      const art = dateiart(sprache);
      if (art) {
        gefunden.push({
          name: dateiname(sprache, ++dateien),
          art: sprache.toLowerCase(),
          inhalt: code.replace(/\n$/, ''),
        });
      }
      return '';
    },
  );
  return gefunden;
}

export { rendern, hervorheben, maskieren, dateienAus }
