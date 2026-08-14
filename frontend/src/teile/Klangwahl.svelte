<script>
  /* The sounds in the settings: one switch, one volume, three previews.

     Its own part rather than three more rows in the appearance panel: the
     preview buttons are a control of their own, and a sound that can only
     be judged by provoking an error would never be judged at all.

     The row of previews is one group, so all three buttons are exactly the
     same size — the sound behind them differs, the button does not. */
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import Schalter from './Schalter.svelte'
  import { t } from '../lib/texte.svelte.js'
  import {
    KLAENGE, klaengeSchalten, klangwahl, pegelSetzen, probehoeren,
  } from '../lib/klaenge.svelte.js'

  /* Colour means state: done is green, waiting yellow, failed red — the
     same three the rest of the house uses. */
  const FARBEN = { fertig: 'gruen', wartet: 'gelb', fehler: 'rot' }

  /* The slider's own position. It starts from the stored level and is
     handed on from here — the stored value never drives it back while it
     is being moved. */
  let pegel = $state(klangwahl.pegel)
  let uebernommen = false
  $effect(() => {
    /* Once, when the stored level has arrived from the service. */
    if (!uebernommen && klangwahl.geladen) {
      pegel = klangwahl.pegel
      uebernommen = true
    }
  })
</script>

<div class="einstellkachel">
  <div class="zeilentext">
    {t('klaenge.titel')}
    <span class="hinweis">{t('klaenge.hinweis')}</span>
  </div>
  <Schalter
    an={!klangwahl.aus}
    beschriftung={t('klaenge.titel')}
    onschalten={(an) => klaengeSchalten(an)}
  />
</div>

<div class="einstellkachel">
  <div class="zeilentext">
    {t('klaenge.pegel')}
    <span class="hinweis">{t('klaenge.pegel_hinweis')}</span>
  </div>
  <!-- The slider owns its position while a hand is on it. Writing the
       state back into `value` on every event is what made the knob fight
       the finger. -->
  <input
    class="regler"
    type="range"
    min="0"
    max="100"
    bind:value={pegel}
    aria-label={t('klaenge.pegel')}
    oninput={() => pegelSetzen(pegel)}
    onchange={() => probehoeren('fertig')}
  />
  <span class="zahl">{pegel}</span>
</div>

<div class="einstellkachel">
  <div class="zeilentext">
    {t('klaenge.probe')}
    <span class="hinweis">{t('klaenge.probe_hinweis')}</span>
  </div>
  <div class="proben">
    {#each KLAENGE as name (name)}
      <button class="probe" onclick={() => probehoeren(name)}>
        <Leuchtpunkt farbe={FARBEN[name]} groesse={7} />
        {t(`klaenge.${name}`)}
      </button>
    {/each}
  </div>
</div>

<style>
  /* The tile shape of the settings, carried here as well: a component
     cannot borrow its parent's scoped styles, and one group of tiles has to
     look like one group. */
  .einstellkachel {
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    padding: 12px 13px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .zeilentext {
    flex: 1;
    min-width: 0;
    font-size: 13px;
  }
  .hinweis {
    display: block;
    font-size: 11.5px;
    color: var(--text-still);
    margin-top: 2px;
  }
  .zahl {
    flex: none;
    width: 30px;
    text-align: right;
    font-size: 12.5px;
    color: var(--text-still);
    font-variant-numeric: tabular-nums;
  }
  .regler {
    width: 160px;
    flex: none;
    /* The system accent is a colour with a meaning of its own here — the
       slider states a level, not a state. */
    accent-color: var(--text-leise);
  }
  .proben {
    display: flex;
    gap: 6px;
    flex: none;
  }
  /* One size for all three: the sound behind them differs, the button
     does not. */
  .probe {
    height: 30px;
    padding: 0 10px;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    cursor: pointer;
    transition: background 0.14s, color 0.14s;
  }
  .probe:hover {
    background: var(--linie);
    color: var(--text);
  }
</style>
