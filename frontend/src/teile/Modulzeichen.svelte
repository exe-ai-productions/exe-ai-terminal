<script>
  /* The module signs, drawn in one place.

     The strip and the rail's head both show them, and they have to be the
     same stroke: two copies of one drawing drift apart at the first change,
     and a head that shows a slightly different mark than the button beside
     it reads as two different things. */
  let { modul = 'terminal', groesse = 16 } = $props()
</script>

{#if modul === 'terminal'}
  <svg width={groesse} height={groesse} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m4 17 6-6-6-6" /><path d="M12 19h8" /></svg>
{:else if modul === 'cli'}
  <svg width={groesse} height={groesse} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" /><path d="m7 9 3 3-3 3" /></svg>
{:else if modul === 'vorschau'}
  <svg width={groesse} height={groesse} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18" /></svg>
{:else}
  <svg width={groesse} height={groesse} viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></svg>
{/if}
