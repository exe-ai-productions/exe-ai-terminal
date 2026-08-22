<!-- The way into the download panel, beside the memory figure in the
     catalogue header — so it stands on every tab and on a model's detail
     page alike. The number counts what is running plus what waits; it
     glows blue because a download is something in motion, and it is a
     steady light rather than a pulse (a filled disc, never a ring). -->
<script>
  import { downloads, anzahlAktiv } from '../lib/downloads.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  const aktiv = $derived(anzahlAktiv())
</script>

<button
  class="knopf"
  onclick={(e) => {
    e.stopPropagation()
    downloads.offen = !downloads.offen
  }}
  aria-label={t('downloads.titel')}
  title={t('downloads.titel')}
>
  <!-- The house's filing arrow: something coming down and landing. -->
  <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"
       stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M12 4 V15" />
    <path d="M7 11 L12 16 L17 11" />
    <path d="M4 20 H20" />
  </svg>
  {#if aktiv}
    <span class="zahl">{aktiv}</span>
  {/if}
</button>

<style>
  .knopf {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    flex: none;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 5px 12px 5px 10px;
    background: none;
    color: var(--text-leise);
    font: inherit;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .knopf:hover {
    background: var(--linie);
    color: var(--text);
  }
  .zahl {
    font: 600 12.5px var(--schrift-fest);
    font-variant-numeric: tabular-nums;
    color: var(--blau);
    text-shadow: 0 0 6px color-mix(in srgb, var(--blau) 65%, transparent);
  }
</style>
