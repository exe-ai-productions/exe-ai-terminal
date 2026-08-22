<script>
  /* One shape for every server panel.

     There are three of them — the model server, the embedding server and
     the picture generator — and they used to be three different layouts:
     head cards of different heights, one page with a dropdown and one with
     a fixed line of text, the action button sometimes in the head and
     sometimes at the foot. Read one after the other they looked like three
     programs rather than three rooms of one.

     So the shape lives here, once, and the panels only fill it in:

       1  the head card — name and one line about it on the left, the state
          on the right
       2  one quiet sentence about what the thing is for
       3  the model, always as a dropdown. A generator with exactly one
          model shows a dropdown with one entry: what the control IS must
          not depend on how much happens to be installed, or the eye has to
          learn the page anew every time the folder changes.
       4  whatever else this particular server needs
       5  the foot — the model folder on the left, the one action on the
          right, in the same place on all three

     `modelle` is a list of {wert, text}: the panel decides what a model is
     called here, the shell only draws it. */
  import Auswahlfeld from './Auswahlfeld.svelte'
  import Hauszeichen from './Hauszeichen.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import Standpille from './Standpille.svelte'
  import Speicherortzeile from './Speicherortzeile.svelte'
  import { t } from '../lib/texte.svelte.js'

  let {
    titel = '',
    unter = '',
    standfarbe = 'still',
    standtext = '',
    wofuer = '',
    modelle = [],
    gewaehlt = $bindable(''),
    modellBeschriftung = '',
    modellGesperrt = false,
    modellGeaendert = null,
    leerText = '',
    /* Where a model for this panel is to be had: opens the catalogue on
       this panel's own tab. Shown only while the folder is empty — the one
       moment the panel cannot help itself. */
    katalogTat = null,
    ordnerOeffnen = null,
    /* The storage location this panel keeps its models in ('bildmodelle',
       'modelle', 'einbettung'). When given, the foot shows the shared folder
       row — path, open, move — in place of the plain open-folder button, so
       a folder can be moved from the same spot it was only opened before. */
    speicherort = null,
    onOrtGeaendert = null,
    tatText = '',
    tatPunkt = 'still',
    tatGesperrt = false,
    onTat = null,
    mitte = null,
    unten = null,
  } = $props()
</script>

<div class="tafel">
  <div class="kopfkarte">
    <div class="min">
      <div class="gross">{titel}</div>
      <!-- Only when there is something to report: an empty line would hold
           the card open around nothing. -->
      {#if unter}
        <div class="unter">{unter}</div>
      {/if}
    </div>
    <Standpille farbe={standfarbe}>{standtext}</Standpille>
  </div>

  {#if wofuer}
    <p class="wofuer">{wofuer}</p>
  {/if}

  {#if modelle.length}
    <div class="feld">
      <span>
        <!-- The house cube: a model is a package, and the picture window's
             model row already wears it. -->
        <svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
             stroke-linejoin="round" aria-hidden="true">
          <path d="M12 3 L20.5 7.5 L12 12 L3.5 7.5 Z" />
          <path d="M3.5 7.5 V16 L12 20.5 L20.5 16 V7.5" />
          <path d="M12 12 V20.5" />
        </svg>{modellBeschriftung}</span>
      <!-- The picker and the way to more of them, on one line: choosing a
           model and fetching one are the same errand, and the catalogue had
           no business being a tile of its own in the rail beside four
           services that run. The button is square and exactly as tall as the
           field, so the row reads as one control with a door at its end. -->
      <div class="feldkasten">
      <div class="modellzeile">
        <Auswahlfeld
          bind:wert={gewaehlt}
          eintraege={modelle}
          gesperrt={modellGesperrt}
          beschriftung={modellBeschriftung}
          gewaehlt={modellGeaendert}
        />
        {#if katalogTat}
          <!-- The way from the list to where more of them come from. Quiet,
               and not a control of its own: it points, it is not pressed. -->
          <svg class="weiter" width="15" height="15" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.1" stroke-linecap="round"
               stroke-linejoin="round" aria-hidden="true">
            <path d="M5 12H19M12 5l7 7-7 7" />
          </svg>
          <button class="katalogtuer" onclick={katalogTat}
                  title={t('modell.zum_katalog')} aria-label={t('modell.zum_katalog')}>
            <Hauszeichen zeichen="raster" groesse="mittel" />
          </button>
        {/if}
      </div>
      {#if speicherort}
        <!-- The folder the list is read from, right under the list: seeing
             which model is chosen and seeing where they lie is one question
             asked twice, and the answer stood at the far end of the panel. -->
        <Speicherortzeile name={speicherort} onaendern={onOrtGeaendert} />
      {/if}
      </div>
    </div>
  {:else if leerText}
    <p class="leer">{leerText}</p>
    {#if katalogTat}
      <button class="zumkatalog" onclick={katalogTat}>
        {t('modell.zum_katalog')}
      </button>
    {/if}
  {/if}

  {@render mitte?.()}

  {#if (!speicherort && ordnerOeffnen) || onTat}
    <div class="fuss">
      {#if !speicherort && ordnerOeffnen}
        <button class="still" onclick={ordnerOeffnen}
                title={t('modell.ordner_oeffnen')} aria-label={t('modell.ordner_oeffnen')}>
          <Hauszeichen zeichen="ordner" groesse="klein" />
        </button>
      {/if}
      {#if onTat}
        <button class="tat" disabled={tatGesperrt} onclick={onTat}>
          <Leuchtpunkt farbe={tatPunkt} groesse={7} />
          {tatText}
        </button>
      {/if}
    </div>
  {/if}

  {@render unten?.()}
</div>

<style>
  .tafel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 2px;
  }
  /* The one tile all three wear, to the pixel: same radius, same padding,
     and a height that comes from the same two lines everywhere. */
  .kopfkarte {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 12px 14px;
  }
  /* Name and file are two lines, not one wrapped one — they need the seam
     that says so. */
  .min {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .gross {
    font-size: 15px;
    line-height: 1.25;
  }
  .unter {
    font-size: 12.5px;
    line-height: 1.3;
    color: var(--text-still);
  }
  .wofuer,
  .leer {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-still);
  }
  .feld {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  /* The same heading the groups inside the panel wear — model, tempo,
     memory and network are sections of one list, and one of them set in a
     different hand reads as a different kind of thing. */
  .feld > span {
    font: 600 11px var(--schrift);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-leise);
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .feldzeichen {
    flex: none;
  }
  .modellzeile {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  /* The picker takes the whole line but for the door at its end. Written
     against every child except the button, because the picker brings its own
     wrapper and a :first-child rule reached the wrong element. */
  .modellzeile > :global(:not(.katalogtuer):not(.weiter)) {
    flex: 1 1 auto;
    min-width: 0;
    /* Pulled back so the picker's right edge lands exactly above the left
       edge of the folder button in the row below — the arrow and the
       catalogue door keep their place. */
    margin-right: 7px;
  }
  /* The same brightness the headings stand at — it belongs to the label
     above it, not to the field it points away from. */
  .weiter {
    flex: none;
    color: var(--text-leise);
    /* Nudged left so its centre sits exactly above the folder button below,
       a visual shift only — the picker and the door keep their places. */
    transform: translateX(-4.5px);
  }
  /* Square, and exactly the field's height — measured from the same value
     the fields stand at, so the two end on one line. */
  .katalogtuer {
    flex: none;
    width: 36px;
    height: 36px;
    box-sizing: border-box;
    display: grid;
    place-items: center;
    padding: 0;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg-erhoben);
    color: var(--text-leise);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .katalogtuer:hover {
    background: var(--linie-stark);
    color: var(--text);
  }
  .feld > span::after {
    content: '';
    flex: 1;
    border-top: 1px solid var(--linie);
  }
  /* Clear of the head card above it: without the sentence that used to
     stand between them, the two were pressed together. */
  .feld {
    margin-top: 6px;
  }
  /* Picker and folder in one frame — the same box the groups below wear. */
  .feld > .modellzeile {
    margin-bottom: 10px;
  }
  .feldkasten {
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 12px 14px;
  }
  /* A hair of air between the picker row and the folder row below it, so the
     folder tools do not touch the catalogue door that sits above them. */
  .feldkasten > :global(.zeile) {
    margin-top: 2px;
  }
  /* Centered on its own line: the empty panel's one way forward, same
     button family as the foot, radius 9 like every control. */
  .zumkatalog {
    align-self: center;
    font: inherit;
    font-size: 13px;
    border-radius: 9px;
    padding: 7px 14px;
    cursor: pointer;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
  }
  .zumkatalog:hover {
    background: var(--linie);
  }
  /* The folder row sits in a tile of its own, above the action, so a long
     path never crowds the button that starts the server. */
  .ortzeile {
    border: 1px solid var(--linie);
    border-radius: 10px;
    padding: 9px 12px;
  }
  .fuss {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: flex-end;
  }
  .tat,
  .still {
    font: inherit;
    font-size: 13px;
    border-radius: 9px;
    padding: 7px 14px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
  }
  .tat {
    background: var(--linie-stark);
  }
  .still {
    border-color: transparent;
    color: var(--text-still);
    margin-right: auto;
  }
  .tat:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .tat:not(:disabled):hover,
  .still:hover {
    background: var(--linie);
    color: var(--text);
  }
</style>
