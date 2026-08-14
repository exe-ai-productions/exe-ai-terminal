<script>
  /* The formatting row for notes — one row for all of them, in the rail's
     head.

     Not per note, and that is deliberate: four buttons on every block would
     be a wall of controls for something people use rarely. One row, acting
     on whatever is being written; with nothing open the buttons sit still.

     Built on contenteditable and `execCommand`, not on an editor library —
     four kinds of emphasis do not justify a dependency, and everything that
     comes out is rebuilt against a whitelist on the way to disk anyway.

     THE ONE TRAP: a button must not take the focus, or the selection in the
     note is gone before the command runs. Hence `mousedown` with
     `preventDefault` — the click never reaches the focus at all. */
  import { t } from '../lib/texte.svelte.js'

  let { aktiv = false, ausfuehren = () => {} } = $props()

  /* A small, quiet palette. Highlighting is a fact about a passage, not a
     state of the program, so these are the house colours at low strength. */
  const FARBEN = ['gelb', 'blau', 'gruen']

  function greifen(ereignis, was, wert = null) {
    /* Keeps the caret where it is: without this the note loses focus and
       the command has nothing to work on. */
    ereignis.preventDefault()
    if (aktiv) ausfuehren(was, wert)
  }
</script>

<div class="werkzeuge" class:still={!aktiv}>
  <button
    class="wz fett"
    onmousedown={(e) => greifen(e, 'bold')}
    title={t('notiz.fett')}
    aria-label={t('notiz.fett')}
  >B</button>
  <button
    class="wz kursiv"
    onmousedown={(e) => greifen(e, 'italic')}
    title={t('notiz.kursiv')}
    aria-label={t('notiz.kursiv')}
  >I</button>
  <button
    class="wz unter"
    onmousedown={(e) => greifen(e, 'underline')}
    title={t('notiz.unterstrichen')}
    aria-label={t('notiz.unterstrichen')}
  >U</button>
  {#each FARBEN as farbe (farbe)}
    <button
      class="farbe {farbe}"
      onmousedown={(e) => greifen(e, 'mark', farbe)}
      title={t('notiz.markieren')}
      aria-label={t('notiz.markieren')}
    ></button>
  {/each}
</div>

<style>
  .werkzeuge {
    display: flex;
    align-items: center;
    gap: 3px;
    margin-left: auto;
  }
  /* Nothing open: the row is there but has nothing to act on, and says so
     by going quiet rather than by disappearing. */
  .werkzeuge.still {
    opacity: 0.4;
    pointer-events: none;
  }
  .wz {
    width: 26px;
    height: 24px;
    border: none;
    background: none;
    color: var(--text-leise);
    font: 12px var(--schrift);
    border-radius: 7px;
    cursor: pointer;
  }
  .wz:hover { background: var(--linie); color: var(--text); }
  .wz.fett { font-weight: 750; }
  .wz.kursiv { font-style: italic; }
  .wz.unter { text-decoration: underline; }
  .farbe {
    width: 15px;
    height: 15px;
    border-radius: 50%;
    border: 1px solid var(--linie-stark);
    cursor: pointer;
    margin-left: 3px;
    padding: 0;
  }
  .farbe.gelb { background: color-mix(in srgb, var(--gelb) 45%, var(--bg)); }
  .farbe.blau { background: color-mix(in srgb, var(--blau) 45%, var(--bg)); }
  .farbe.gruen { background: color-mix(in srgb, var(--gruen) 45%, var(--bg)); }
</style>
