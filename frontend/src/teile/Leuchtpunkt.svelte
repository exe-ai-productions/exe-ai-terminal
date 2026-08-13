<script>
  /* A status dot with a ring — the house's one glowing point.

     Drawn as a vector: a filled disc for the state, a stroked circle for
     the ring around it. A real stroke, not a box-shadow — at these small
     sizes a shadow ring cants and frays on a sharp screen; a vector stroke
     stays clean and sits in its own box, so it never bleeds into a
     neighbour or drops a row out of line. The stroke reaches a hair inside
     the disc so no dark seam shows between the two.

     `farbe` follows the house rule: colour means state, never decoration.

       gruen  done, ready, connected, reachable
       blau   running, active, switched on
       gelb   waiting, and caution
       rot    failed, off, unreachable, dangerous
       still  no state worth a colour — a fact, not a state

     `an` lets the dot breathe while something is truly live, the same
     pulse the menu-bar lamp wears. `groesse` is the disc diameter in px;
     the ring adds two pixels around it. */
  let { farbe = 'gruen', an = false, groesse = 8 } = $props()

  const kasten = $derived(groesse + 4)
  const mitte = $derived(kasten / 2)
  const rScheibe = $derived(groesse / 2)
  // The stroke centre sits so its inner edge falls just inside the disc —
  // flush, with no seam — and its outer edge stays inside the box.
  const rRing = $derived(groesse / 2 + 0.35)
</script>

<svg
  class="lp"
  class:an
  width={kasten}
  height={kasten}
  viewBox="0 0 {kasten} {kasten}"
  aria-hidden="true"
>
  <circle class="scheibe" data-farbe={farbe} cx={mitte} cy={mitte} r={rScheibe} />
  <circle cx={mitte} cy={mitte} r={rRing} fill="none" stroke="var(--text)" stroke-width="1.4" />
</svg>

<style>
  .lp {
    display: inline-block;
    flex: none;
    vertical-align: middle;
  }
  .scheibe[data-farbe='gruen'] { fill: var(--gruen); }
  .scheibe[data-farbe='blau'] { fill: var(--blau); }
  .scheibe[data-farbe='gelb'] { fill: var(--gelb); }
  .scheibe[data-farbe='rot'] { fill: var(--rot); }
  .scheibe[data-farbe='still'] { fill: var(--text-still); }

  /* Breathes only while something actually runs — the same timing as the
     menu-bar lamp, so the two never tick against one another. */
  .lp.an {
    transform-origin: center;
    animation: lppuls 1.6s ease-in-out infinite;
  }
  @keyframes lppuls {
    50% { opacity: 0.5; transform: scale(0.85); }
  }
  @media (prefers-reduced-motion: reduce) {
    .lp.an { animation: none; }
  }
</style>
