<script>
  /* The Image-Turbo mark: a speedometer. It replaced the bolt, which said
     "MTP" (the blue speed module) everywhere else and so meant two things at
     once. The gauge is this switch's alone.

     Unlike the Hauszeichen signs it is NOT a static signpost: switched on,
     the needle sweeps once from zero (lower left) all the way round to the
     stop (lower right), hits it, rebounds and settles — colour running from
     green through gold to red as it goes. That is why it lives in its own
     file and not in Hauszeichen, whose contract is "static, one colour": a
     drawn, animated, multi-colour mark would break it.

       an = false   grey, at rest at zero — the switch is off.
       an = true    the coloured gauge; the sweep plays once on turn-on and
                    the needle then holds at the red stop.

     The needle turns with SVG transforms (rotate with an explicit pivot),
     never with CSS transform-origin: a pixel origin on a scaled SVG is
     resolved differently by every engine and threw the needle clean out of
     the dial. The pivot named inside rotate() cannot be misresolved.

     The run-up accelerates INTO the stop (no braking before the hit) so the
     rebound reads as a real impact; the settling wobble eases out after. */
  let { an = false, groesse = 15 } = $props()

  /* The sweep, as a native SVG animation with the pivot in every keyframe.
     Started by hand on each turn-on: an animation element mounted later
     would count its begin time from page load and skip straight to the end. */
  let sweep = $state(null)
  const bewegungReduziert =
    typeof matchMedia === 'function' &&
    matchMedia('(prefers-reduced-motion: reduce)').matches

  /* Start the sweep only on a real turn-ON, never on mount: a pill that
     remounts while turbo has long been on would otherwise replay the whole
     run-up and misreport a state change that did not happen. */
  let vorherAn = an
  $effect(() => {
    if (an && sweep && !bewegungReduziert && !vorherAn) sweep.beginElement()
    vorherAn = an
  })
</script>

<svg class="tacho" class:an viewBox="0 0 64 64" width={groesse} height={groesse}
     fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <defs>
    <linearGradient id="turbotachoVerlauf" x1="9" y1="0" x2="55" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#57a55f" />
      <stop offset="0.5" stop-color="#d8b23a" />
      <stop offset="1" stop-color="#d15448" />
    </linearGradient>
  </defs>
  <!-- The dial: a 270° horseshoe open at the bottom. Grey off, the gradient
       on. -->
  <path class="skala" d="M16.4 48.6 A22 22 0 1 1 47.6 48.6" stroke-width="5" />
  <!-- The needle, ending exactly at the hub — nothing juts past it. At rest
       it stands at zero (lower left); switched on it holds at the red stop,
       and the one-shot sweep below carries it there.

       Keyed on the switch: a frozen sweep (fill="freeze") outlives any
       change to the base transform, so switching off would leave the grey
       needle pinned at the red stop. Rebuilding the group on every toggle
       clears the frozen animation with it. -->
  {#key an}
  <g class="nadel" transform="rotate({an ? 135 : -135} 32 33)">
    <animateTransform
      bind:this={sweep}
      attributeName="transform"
      type="rotate"
      begin="indefinite"
      dur="3.4s"
      fill="freeze"
      calcMode="spline"
      values="-135 32 33; 135 32 33; 159 32 33; 119 32 33; 142 32 33; 132 32 33; 135 32 33"
      keyTimes="0; 0.4; 0.49; 0.6; 0.7; 0.8; 1"
      keySplines="0.42 0 0.92 0.5; 0 0 0.58 1; 0.42 0 0.58 1; 0.42 0 0.58 1; 0 0 0.58 1; 0 0 1 1"
    />
    <line x1="32" y1="33" x2="32" y2="14" stroke-width="5" />
  </g>
  {/key}
  <circle cx="32" cy="33" r="3.2" class="nabe" />
</svg>

<style>
  svg { flex: none; display: block; }

  /* Off: everything grey, needle resting at zero (lower left). */
  .skala { stroke: var(--linie-stark); }
  .nadel { stroke: var(--linie-stark); }
  .nabe { fill: var(--linie-stark); stroke: none; }

  /* On: the gradient dial, the hub in the text colour, and the needle's
     colour rides the sweep from green through gold to red. */
  .tacho.an .skala { stroke: url(#turbotachoVerlauf); }
  .tacho.an .nabe { fill: var(--text-leise); }
  .tacho.an .nadel line {
    animation: turbofarbe 3.4s linear forwards;
  }
  @keyframes turbofarbe {
    0%, 13% { stroke: #57a55f; }
    38%     { stroke: #d8b23a; }
    66%, 100% { stroke: #d15448; }
  }

  /* No motion for those who ask for none: the sweep is never started, the
     markup already holds the needle at the red stop, and the colour stands
     still too. */
  @media (prefers-reduced-motion: reduce) {
    .tacho.an .nadel line { animation: none; stroke: #d15448; }
  }
</style>
