<script>
  /* The working folders as pills — the view, at two spots.

     `ort="leiste"` is above the input field, where the first folder is set
     while the chat is still empty. `ort="kopf"` is the header, where they
     live from the first message onward — the header was cleared for them.

     The pills fly from one spot to the other; the flight itself is a
     crossfade from lib/arbeitsordner.svelte.js, keyed by path, so the
     framework matches departing and arriving pill. Both spots render the
     same markup on purpose: what flies has to look the same on both ends,
     or the flight ends in a jump.

     Only the folder name is shown, never the whole path — the working
     directory is known anyway; the full path is in the tooltip. */
  import { t } from '../lib/texte.svelte.js'
  import {
    HOECHSTENS, fliegen, landen, ordnerListe, ordnerName,
    ordnerLoesen, ordnerZeigen, maskeOeffnen,
  } from '../lib/arbeitsordner.svelte.js'

  let { ort = 'leiste' } = $props()

  const ordner = $derived(ordnerListe())
  const voll = $derived(ordner.length >= HOECHSTENS)
</script>

{#if ordner.length}
  <div class="reihe" class:kopf={ort === 'kopf'}>
    {#each ordner as pfad (pfad)}
      <div class="pille" in:landen={{ key: pfad }} out:fliegen={{ key: pfad }}>
        <!-- The face of the chip opens the folder, the sign at its end lets
             it go. Two jobs, two controls — a folder is a fact, so the face
             answers with brightness and never with a colour. -->
        <button class="flaeche" title={t('arbeitsordner.zeigen').replace('{pfad}', pfad)}
                onclick={() => ordnerZeigen(pfad)}>
          <svg class="zeichen" width="14" height="14" viewBox="0 0 64 64" fill="none"
               stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
               aria-hidden="true">
            <path d="M11 50 V14 H27 L32 21 H53 V50 Z" stroke-width="5" />
            <path d="M11 26 H53" stroke-width="4.5" />
          </svg>
          <span class="name">{ordnerName(pfad)}</span>
        </button>
        <button class="x" onclick={() => ordnerLoesen(pfad)}
                aria-label={t('arbeitsordner.loesen')} title={t('arbeitsordner.loesen')}>✕</button>
      </div>
    {/each}

    <!-- The plus stays put when full and says why, instead of disappearing
         and leaving the impression that something broke. -->
    <button
      class="mehr"
      class:gesperrt={voll}
      onclick={maskeOeffnen}
      title={voll
        ? t('arbeitsordner.voll').replace('{anzahl}', HOECHSTENS)
        : t('arbeitsordner.hinzufuegen')}
      aria-label={t('arbeitsordner.hinzufuegen')}
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.6" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
    </button>
  </div>
{/if}

<style>
  .reihe {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    min-width: 0;
  }
  /* Above the field in the empty start, where everything is centred — the
     mark, the field, the whole column. Left-aligned in a row of field width,
     the pill hung in mid-air with nothing under its left edge. It centres on
     the field instead.

     No margin of its own either: the zone already sets 8 px of gap, and the
     two added up to a gap twice as wide as anywhere else in the column. */
  .reihe:not(.kopf) {
    width: min(560px, 78%);
    max-width: 100%;
    justify-content: center;
  }
  @media (max-width: 720px) {
    .reihe:not(.kopf) { width: 92%; }
  }
  /* In the header: one line, never wrapping — the header has a fixed height
     of 52 px and a second row would push it apart. Four have to fit, so each
     name gets a share of the room and truncates beyond it. */
  .reihe.kopf {
    flex-wrap: nowrap;
    overflow: hidden;
  }
  .reihe.kopf .pille {
    max-width: 156px;
  }

  /* The frame is the brightest line in the house — brighter than the input
     field's, so the pill lifts off it. Blue was too loud
     for something that simply states a fact; a shared folder is not a
     warning. Thin on purpose: the tool prompt may shout, this may not.
     The folder mark carries the same colour, or the pill would read as two
     different things stuck together. */
  .pille {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    height: 28px;
    box-sizing: border-box;
    max-width: 100%;
    min-width: 0;
    border: 1px solid var(--text-leise);
    border-radius: 9px;
    background: var(--bg-erhoben);
    padding: 0 4px 0 4px;
    overflow: hidden;
  }
  /* The highlight belongs to the WHOLE chip, not to the face inside it.
     With it on the face, the remove sign stayed dark while everything left
     of it lit up — the chip read as two halves. Same mistake the fold arrow
     in the tools window had, and the same fix: put it on the container. */
  .pille:hover {
    background: var(--linie);
  }
  .flaeche {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    height: 22px;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    padding: 0 4px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.14s;
  }
  /* The face still answers on its own, a shade stronger, so it stays
     visible which half of the chip the pointer is on. */
  .flaeche:hover { background: var(--linie-stark); }
  .pille .zeichen {
    flex: none;
    color: var(--text-leise);
  }
  .name {
    font-size: 12.5px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .x {
    border: none;
    background: none;
    color: var(--text-still);
    font: inherit;
    font-size: 12px;
    padding: 2px 4px;
    border-radius: 6px;
    cursor: pointer;
    flex: none;
  }
  .x:hover {
    background: var(--linie-stark);
    color: var(--text);
  }
  /* Hovering anywhere on the chip already brightens the remove sign — it is
     part of the chip, not a separate control that has to be found. */
  .pille:hover .x { color: var(--text-leise); }
  .mehr {
    width: 28px;
    height: 28px;
    padding: 0;
    box-sizing: border-box;
    flex: none;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    background: none;
    color: var(--text-leise);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .mehr:hover {
    background: var(--linie);
    color: var(--text);
  }
  .mehr.gesperrt {
    opacity: 0.4;
    cursor: default;
  }
  .mehr.gesperrt:hover {
    background: none;
    color: var(--text-leise);
  }
</style>
