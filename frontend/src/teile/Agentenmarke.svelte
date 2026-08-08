<script>
  /* The agent mark for the jobs section.

     Counterpart to the wordmark: there the terminal frame with the input
     arrow, here the torso with a hat. Both share the same chevron — in
     the wordmark once and directed, as a command prompt; here twice and
     mirrored, as a pair of eyes.

     Mirrored, because a face has an axis and no direction: two chevrons
     pointing the same way read as a fast-forward button at small sizes,
     the mirrored ones immediately as eyes. In the tab at 15 px, that is
     exactly the difference between recognizable and a smudge.

     No face outline — only the eyes sit under the brim. That is the
     agent gaze, and it saves the strokes that would clog up small
     anyway.

     The stroke widths depend on the size: below 20 px the fine strokes
     clog up, so they are raised there. Same logic by which the favicon
     is drawn bolder than the large mark.

     The color is inherited, so it flips along by itself on mode change. */
  import { t } from '../lib/texte.svelte.js'

  let { groesse = 26, beschriftung = null } = $props()

  const klein = $derived(groesse < 20)
  const kraeftig = $derived(klein ? 4.6 : 3.6)
  const fein = $derived(klein ? 4.2 : 3.2)
  /* At small sizes the eye tips move outward: with a thicker stroke the
     round cap would otherwise eat up the bend and the arrow turns into a
     bar. */
  const augeLinks = $derived(klein ? 'M23 29.5 L27.5 33 L23 36.5' : 'M23 30 L27 33 L23 36')
  const augeRechts = $derived(klein ? 'M41 29.5 L36.5 33 L41 36.5' : 'M41 30 L37 33 L41 36')
</script>

<span class="marke" role="img" aria-label={beschriftung ?? t('jobs.bereich_jobs')}>
  <svg viewBox="0 0 64 64" width={groesse} height={groesse}
       fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
       aria-hidden="true">
    <path d="M6 24 Q32 30 58 24" stroke-width={kraeftig} />
    <path d="M18 24 V15 Q18 8 32 8 Q46 8 46 15 V24" stroke-width={kraeftig} />
    <path d={augeLinks} stroke-width={fein} />
    <path d={augeRechts} stroke-width={fein} />
    <path d="M8 60 V51 Q8 42 19 39.5 L32 47 L45 39.5 Q56 42 56 51 V60" stroke-width={kraeftig} />
  </svg>
  {#if beschriftung}<span class="text">{beschriftung}</span>{/if}
</span>

<style>
  .marke {
    display: inline-flex;
    align-items: center;
    gap: 0.5em;
    color: inherit;
    line-height: 1;
    white-space: nowrap;
    user-select: none;
  }
  svg {
    flex: none;
    display: block;
  }
  .text {
    font-family: var(--schrift);
    font-weight: 600;
    letter-spacing: -0.02em;
  }
</style>
