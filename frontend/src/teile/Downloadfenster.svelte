<!-- What is being fetched, as one list.

     It hangs off the header button and covers the catalogue's content while
     it is open — reachable from every tab and from a model's detail page,
     because a download does not belong to the tab it was started on.

     Four rows stand; the rest scrolls under the mouse, with the house's
     melting edge instead of a bar. Finished entries stay while the window
     lives: a receipt, not a message that flashes past. -->
<script>
  import { fly } from 'svelte/transition'
  import { rollfade } from '../lib/rollfade.js'
  import { downloads, ausreihen, zieldatei } from '../lib/downloads.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  let { stand = null, tempo = '', onAbbrechen } = $props()

  const gb = (bytes) => (bytes / 1e9).toFixed(1)
  const laeuft = $derived(Boolean(stand) && !stand.fertig && !stand.fehler)
  const anteil = $derived(Math.round((stand?.anteil ?? 0) * 100))
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div
  class="fenster"
  transition:fly={{ y: -8, duration: 160 }}
  onclick={(e) => e.stopPropagation()}
>
  {#if !laeuft && !downloads.warteschlange.length && !downloads.fertig.length}
    <p class="leer">{t('downloads.leer')}</p>
  {:else}
    <div class="liste" use:rollfade>
      {#if laeuft}
        <div class="kachel">
          <div class="zeile">
            <span class="punkt blau"></span>
            <span class="datei">{stand.datei}</span>
            <span class="rechts">
              <button class="abbrechen" onclick={onAbbrechen}>{t('katalog.abbrechen')}</button>
            </span>
          </div>
          <div class="balken"><i style="width:{anteil}%"></i></div>
          <div class="zahlen">
            <span>{gb(stand.geladen)} / {gb(stand.gesamt)} GB · {anteil} %</span>
            {#if tempo}<span class="tempo">{tempo}</span>{/if}
          </div>
        </div>
      {/if}

      {#each downloads.warteschlange as job (job.nummer)}
        <div class="kachel wartet">
          <div class="zeile">
            <span class="punkt still"></span>
            <span class="datei">{zieldatei(job)}</span>
            <span class="rechts">
              <span class="marke">{t('downloads.wartet')}</span>
              <button class="abbrechen" onclick={() => ausreihen(job)}>
                {t('katalog.abbrechen')}
              </button>
            </span>
          </div>
        </div>
      {/each}

      {#each downloads.fertig as eintrag (eintrag.datei)}
        <div class="kachel">
          <div class="zeile">
            <span class="punkt gruen"></span>
            <span class="datei">{eintrag.datei}</span>
            <span class="rechts">
              <span class="zahlen">
                {#if eintrag.groesse}{gb(eintrag.groesse)} GB · {/if}{t('downloads.fertig')}
              </span>
            </span>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .fenster {
    position: absolute;
    top: 46px;
    right: 0;
    z-index: 6;
    width: min(460px, calc(100vw - 60px));
    background: var(--bg-erhoben);
    border-radius: 16px;
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--fensterring, var(--text)) 70%, transparent),
      0 24px 60px rgba(0, 0, 0, 0.3);
    padding: 12px;
  }
  /* Four rows stand, the rest scrolls — the melting edge says there is
     more, so no bar has to. */
  .liste {
    max-height: 372px;
    overflow-y: auto;
  }
  .kachel {
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg);
    padding: 11px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .kachel + .kachel {
    margin-top: 8px;
  }
  .kachel.wartet {
    opacity: 0.62;
  }
  .zeile {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .datei {
    font: 500 13px var(--schrift-fest);
    color: var(--text);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rechts {
    margin-left: auto;
    flex: none;
    display: flex;
    align-items: center;
    gap: 9px;
  }
  /* Filled discs, the house's states: blue runs, green arrived, and a
     waiting one is a fact rather than a state — brightness only. */
  .punkt {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }
  .punkt.blau {
    background: var(--blau);
    box-shadow: 0 0 5px color-mix(in srgb, var(--blau) 60%, transparent);
  }
  .punkt.gruen {
    background: var(--gruen);
    box-shadow: 0 0 5px color-mix(in srgb, var(--gruen) 55%, transparent);
  }
  .punkt.still {
    background: var(--linie-stark);
  }
  .balken {
    position: relative;
    height: 6px;
    border-radius: 99px;
    background: var(--linie);
    overflow: hidden;
  }
  .balken i {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: 99px;
    background: var(--blau);
    box-shadow: 0 0 8px color-mix(in srgb, var(--blau) 55%, transparent);
    transition: width 0.4s ease;
  }
  .zahlen {
    display: flex;
    gap: 14px;
    font: 500 11.5px var(--schrift-fest);
    color: var(--text-leise);
  }
  .tempo {
    color: var(--text-still);
  }
  .marke {
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 2px 9px;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.05em;
    color: var(--text-still);
    white-space: nowrap;
  }
  .abbrechen {
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 11.5px;
    padding: 3px 11px;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .abbrechen:hover {
    background: var(--linie);
    color: var(--text);
  }
  .leer {
    margin: 0;
    padding: 10px 4px;
    font-size: 12.5px;
    color: var(--text-still);
  }
</style>
