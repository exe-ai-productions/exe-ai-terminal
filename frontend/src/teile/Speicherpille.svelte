<!-- The memory pill in the header: how much of the machine's one pool is in
     use, as "39.3 / 64 GB" with a quiet filling bar behind the figures. The
     same pill the sibling programs wear, so the whole family reads alike.
     It shows the MACHINE's memory, not this program's — the honest ceiling
     for any model plan on shared-memory hardware. -->
<script>
  import { onMount } from 'svelte'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'

  let belegt = $state(null)
  let gesamt = $state(null)
  let anteil = $state(null)

  /* Near the ceiling: where long model runs start to get killed. */
  const WARNSCHWELLE = 0.85

  async function lesen() {
    try {
      const m = await api.speicherBlick()
      belegt = m.belegt_gb
      gesamt = m.gesamt_gb
      anteil = m.anteil
    } catch {
      /* Leave the last reading standing rather than blinking to blank. */
    }
  }

  onMount(() => {
    lesen()
    const takt = setInterval(lesen, 2000)
    return () => clearInterval(takt)
  })

  const heiss = $derived(anteil != null && anteil >= WARNSCHWELLE)
  const breite = $derived(anteil != null ? `${Math.round(anteil * 100)}%` : '0%')
</script>

{#if gesamt != null}
  <div class="pille" class:heiss title={t('kopf.speicher_titel')}>
    <span class="fuellung" style={`width:${breite}`}></span>
    <span class="wert">{belegt != null ? belegt : '—'} / {gesamt} GB</span>
  </div>
{/if}

<style>
  .pille {
    position: relative;
    overflow: hidden;
    flex: none;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 4px 10px;
    font: 500 12.5px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text);
    white-space: nowrap;
  }
  .fuellung {
    position: absolute;
    inset: 0 auto 0 0;
    background: color-mix(in srgb, var(--text) 12%, transparent);
    transition: width 0.6s ease;
  }
  /* Caution, not failure: the yellow of the palette, mixed down so the
     figures stay readable on top of it. */
  .pille.heiss .fuellung {
    background: color-mix(in srgb, var(--gelb) 48%, transparent);
  }
  .wert {
    position: relative;
  }
</style>
