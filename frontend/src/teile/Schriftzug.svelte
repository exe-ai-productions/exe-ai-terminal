<script>
  /* A drawn lettering: large headings of the
     settings gallery are not text but capitals from the house stroke
     font — round-capped, strong, not bold.

     The letterings live generated in lib/schriftzuege.js (skill
     "exe-vektoren"); here we only pick by language and draw. For screen
     readers, the surrounding box carries the actual word. */
  import { SCHRIFTZUEGE } from '../lib/schriftzuege.js'
  import { texte } from '../lib/texte.svelte.js'

  let { zug, hoehe = 13 } = $props()

  const wahl = $derived(SCHRIFTZUEGE[zug]?.[texte.sprache] || SCHRIFTZUEGE[zug]?.en)
</script>

{#if wahl}
  <svg
    viewBox="-2 -2 {wahl.breite + 4} 18"
    height={hoehe}
    fill="none"
    stroke="currentColor"
    stroke-width="2.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    {@html wahl.markup}
  </svg>
{/if}

<style>
  svg {
    display: block;
  }
</style>
