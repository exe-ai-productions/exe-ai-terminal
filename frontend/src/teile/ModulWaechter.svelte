<script>
  /* The guardian's panel: one tile per failed step.

     A tile says three things in the order one wants them: WHAT went wrong,
     WHAT to do about it, and then the raw result for whoever wants to see
     it — folded away, because a wall of build output at the top of the tile
     would bury the suggestion under the problem.

     The two buttons are deliberately unequal. Sending is what the tile is
     for and looks like it; discarding is quiet, because a finding one does
     not want should cost a click, not attention. */
  import { t } from '../lib/texte.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'
  import { befundVerwerfen, befundeVon } from '../lib/waechter.svelte.js'

  let { senden } = $props()

  const liste = $derived(befundeVon(zustand.aktiverChat))

  const ARTEN = {
    befehl_gescheitert: 'waechter.befehl_gescheitert',
    aufruf_abgelehnt: 'waechter.aufruf_abgelehnt',
    zeit_abgelaufen: 'waechter.zeit_abgelaufen',
    aenderung_verfehlt: 'waechter.aenderung_verfehlt',
    datei_unlesbar: 'waechter.datei_unlesbar',
  }
</script>

<div class="modul">
  {#if !liste.length}
    <p class="leer">{t('waechter.leer')}</p>
  {/if}
  {#each liste as befund (befund.id)}
    <div class="kachel">
      <div class="kopf">
        <span class="art">{t(ARTEN[befund.art] ?? 'waechter.befehl_gescheitert')}</span>
        <span class="werkzeug">{befund.werkzeug}</span>
      </div>

      {#if befund.vorschlag}
        <p class="vorschlag">{befund.vorschlag}</p>
        <div class="taten">
          <button class="schicken" onclick={() => senden(befund)}>
            {t('waechter.senden')}
          </button>
          <button class="still" onclick={() => befundVerwerfen(zustand.aktiverChat, befund.id)}>
            {t('waechter.verwerfen')}
          </button>
        </div>
      {:else}
        <!-- Two quiet states, and they must not look alike: null means the
             model has not answered yet, "" means it answered with nothing
             usable. A spinner that never ends would be the worse of the
             two lies. -->
        <p class="denkt">
          {befund.vorschlag === null ? t('waechter.denkt') : t('waechter.kein_vorschlag')}
        </p>
        <div class="taten">
          <button class="still" onclick={() => befundVerwerfen(zustand.aktiverChat, befund.id)}>
            {t('waechter.verwerfen')}
          </button>
        </div>
      {/if}

      <details class="roh">
        <summary>{t('waechter.rohes_ergebnis')}</summary>
        <pre>{befund.ergebnis}</pre>
      </details>
    </div>
  {/each}
</div>

<style>
  /* The rail gives every panel the same box and hides what runs out of it.
     Without a height of its own a panel grows past that box instead of
     scrolling inside it, and everything below the edge — findings, and the
     buttons that answer them — becomes unreachable. The three lines the
     sibling panels carry, for the same reason. */
  .modul {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
  .leer {
    margin: 0;
    padding: 14px 2px;
    color: var(--text-still);
    font-size: 13px;
  }
  /* One group, one size: every tile is built the same way, and only its
     content decides how tall it stands. */
  .kachel {
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 10px 12px;
    background: var(--bg-leiste);
  }
  .kopf {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 6px;
  }
  .art {
    font-size: 12px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    /* Yellow is the house's colour for "waiting, and caution" — which is
       exactly what an unanswered finding is. */
    color: var(--gelb);
  }
  .werkzeug {
    font-family: var(--mono, ui-monospace, monospace);
    font-size: 12px;
    color: var(--text-still);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .vorschlag {
    margin: 0 0 8px;
    font-size: 13.5px;
    line-height: 1.5;
    overflow-wrap: anywhere;
  }
  .denkt {
    margin: 0 0 8px;
    font-size: 13px;
    color: var(--text-still);
  }
  .taten {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .schicken,
  .still {
    font: inherit;
    font-size: 12.5px;
    border-radius: 9px;
    padding: 4px 10px;
    cursor: pointer;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
  }
  .schicken {
    background: var(--linie-stark);
  }
  .still {
    border-color: transparent;
    color: var(--text-still);
  }
  .schicken:hover {
    background: var(--linie);
  }
  .still:hover {
    color: var(--text);
    background: var(--linie);
  }
  .roh {
    margin-top: 8px;
    font-size: 12px;
    color: var(--text-still);
  }
  .roh summary {
    cursor: pointer;
  }
  .roh pre {
    margin: 6px 0 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font-family: var(--mono, ui-monospace, monospace);
    font-size: 11.5px;
    max-height: 220px;
    overflow: auto;
  }
</style>
