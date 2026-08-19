<script>
  /* How many pictures are still to come — the one drawing now plus any
     queued behind it. Shown only while there is at least one, so it takes no
     room when nothing is drawing: the header row reflows around it, and two
     of these (header and the working frame) always say the same number
     because they read the same count.

     The mark is the pictures module's own frame, so the badge and the rail
     button that opens the wall of pictures read as one thing. */
  import { zustand } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import Modulzeichen from './Modulzeichen.svelte'

  let { groesse = 15 } = $props()
</script>

{#if zustand.bildWarteschlange > 0}
  <span class="warteschlange" role="img"
        aria-label={t('bild.warteschlange', { zahl: zustand.bildWarteschlange })}
        title={t('bild.warteschlange', { zahl: zustand.bildWarteschlange })}>
    <span class="zahl">{zustand.bildWarteschlange}</span>
    <Modulzeichen modul="bilder" {groesse} />
  </span>
{/if}

<style>
  .warteschlange {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 1.5px 8px;
    color: var(--text-leise);
    /* The pill breathes blue while pictures are being made. A glow means
       "working right now" — here that is true, so it is honest (unlike the
       lamps, which are steady because they only report a state). */
    animation: malpuls 1.6s ease-in-out infinite;
  }
  @keyframes malpuls {
    0%, 100% {
      border-color: var(--linie-stark);
      box-shadow: 0 0 0 0 rgba(91, 141, 190, 0);
    }
    50% {
      border-color: var(--blau);
      box-shadow: 0 0 8px 1px rgba(91, 141, 190, 0.55);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .warteschlange { animation: none; border-color: var(--blau); }
  }
  .zahl {
    font-size: 12px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text);
  }
</style>
