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
      <div class="unter">{unter}</div>
    </div>
    <Standpille farbe={standfarbe}>{standtext}</Standpille>
  </div>

  {#if wofuer}
    <p class="wofuer">{wofuer}</p>
  {/if}

  {#if modelle.length}
    <div class="feld">
      <span>{modellBeschriftung}</span>
      <Auswahlfeld
        bind:wert={gewaehlt}
        eintraege={modelle}
        gesperrt={modellGesperrt}
        beschriftung={modellBeschriftung}
        gewaehlt={modellGeaendert}
      />
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

  {#if speicherort}
    <!-- The folder as a full row: seen, opened and moved from one place. -->
    <div class="ortzeile">
      <Speicherortzeile name={speicherort} onaendern={onOrtGeaendert} />
    </div>
  {/if}

  <div class="fuss">
    {#if !speicherort && ordnerOeffnen}
      <button class="still" onclick={ordnerOeffnen}>
        <Hauszeichen zeichen="ordner" groesse="klein" />
        {t('modell.ordner_oeffnen')}
      </button>
    {/if}
    <button class="tat" disabled={tatGesperrt} onclick={onTat}>
      <Leuchtpunkt farbe={tatPunkt} groesse={7} />
      {tatText}
    </button>
  </div>

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
  .min {
    min-width: 0;
  }
  .gross {
    font-size: 15px;
  }
  .unter {
    font-size: 12.5px;
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
  .feld > span {
    font-size: 12px;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--text-still);
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
