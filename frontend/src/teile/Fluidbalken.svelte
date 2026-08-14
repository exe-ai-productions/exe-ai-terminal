<script>
  /* A tube filling up with the measurement, its surface rolling.

     This was the speed display of the input bar. It has been replaced there
     by the beat strokes (`Tempoanzeige.svelte`), which say the same thing
     faster to the eye — a rhythm is felt, a fill level has to be read.

     It is kept, not deleted. The drawing is sound and the one hard part of
     it is solved: the wave front is a repeating path column rolling by CSS
     transform, because WebKit could not do the SMIL path morph the first
     build used and the bar simply looked dead. Whoever needs a "how full is
     it" anywhere in this house should start here and not from nothing.

     `anteil` is 0 to 1. Empty means: pushed all the way out of the clip. */

  let { anteil = 0, beschriftung = '' } = $props()

  // How far the fill has to travel to be flush right. The tube is 140 units
  // wide in its own coordinates; 128 is that minus the round caps.
  const WEG = 128
</script>

<svg class="fluid" width="56" height="10" viewBox="0 0 140 24" role="img" aria-label={beschriftung}>
  <defs><clipPath id="fluidschnitt"><rect x="1" y="1" width="138" height="22" rx="11" /></clipPath></defs>
  <g clip-path="url(#fluidschnitt)">
    <g class="fuellung"
       style="transform: translateX({anteil > 0 ? Math.round(-WEG * (1 - anteil)) : -150}px)">
      <rect x="-140" y="0" width="268" height="24" fill="currentColor" />
      <path class="welle" fill="currentColor"
            d="M128 -20 q8 5 0 10 q-8 5 0 10 q8 5 0 10 q-8 5 0 10 q8 5 0 10 q-8 5 0 10 L122 40 L122 -20 Z" />
    </g>
  </g>
  <rect class="huelse" x="1" y="1" width="138" height="22" rx="11" stroke-width="3" />
</svg>

<style>
  .fluid {
    display: block;
    color: var(--text-still);
  }
  .fluid .huelse {
    stroke: var(--linie-stark);
    fill: none;
  }
  .fluid .fuellung {
    transition: transform 0.45s ease;
  }
  /* The front rolls endlessly downward: the wave pattern repeats every
     20 units — shift by 20 once and seamlessly start over. */
  .fluid .welle {
    animation: wogen 1.15s linear infinite;
  }
  @keyframes wogen {
    to { transform: translateY(20px); }
  }
  @media (prefers-reduced-motion: reduce) {
    .fluid .welle { animation: none; }
  }
</style>
