<script>
  /* A status dot: one filled disc, standing still.

     It used to wear a stroked ring and, in the chat list, three little
     performances — breathing, flashing, trading brightness with its ring.
     In the running program none of that survived the distance to the
     screen: the ring ate the disc's diameter, and the motion made the
     colour harder to read rather than easier. So the dot is now the
     simplest thing that can carry a state — a full disc in the state's own
     colour, big enough to be read at arm's length, with a fine standing
     glow and nothing that moves.

     `farbe` follows the house rule: colour means state, never decoration.

       gruen  done, ready, connected, reachable
       blau   running, active, switched on
       gelb   waiting, and caution
       rot    failed, off, unreachable, dangerous
       still  no state worth a colour — a fact, not a state
       leer   nothing to report. A small quiet disc, not an empty ring:
              it holds a row's geometry without claiming to be a state.

     `groesse` is the caller's old number and keeps its meaning for layout:
     the box around the dot stays exactly as wide as it always was, so no
     row moves. What grew is the disc inside it. */
  let { farbe = 'gruen', groesse = 8 } = $props()

  /* The box is what the layout sees, and it is unchanged from the days of
     the ring — the ring's two pixels of air simply became disc. */
  const kasten = $derived(groesse + 4)
  const mitte = $derived(kasten / 2)

  /* One step larger than before, except for the dot that says nothing: a
     row with nothing to report should not weigh as much as one that has
     something to say. */
  const scheibe = $derived(farbe === 'leer' ? groesse : groesse + 2)
</script>

<svg
  class="lp"
  data-farbe={farbe}
  width={kasten}
  height={kasten}
  viewBox="0 0 {kasten} {kasten}"
  aria-hidden="true"
>
  <circle class="scheibe" data-farbe={farbe} cx={mitte} cy={mitte} r={scheibe / 2} />
</svg>

<style>
  .lp {
    display: inline-block;
    flex: none;
    vertical-align: middle;
    /* Without this the glow never leaves the box: an SVG viewport clips its
       own content, and there is one pixel of air around the disc. */
    overflow: visible;
  }
  /* The glow hangs off the whole drawing and not off the circle inside it.
     On the circle it was clipped twice over — once by the SVG viewport and
     once by the filter region, which defaults to a tenth of the shape's own
     box and so cut a 2.5px blur down to well under a pixel. */
  .lp[data-farbe='gruen'] {
    filter: drop-shadow(0 0 2.5px color-mix(in srgb, var(--gruen) 55%, transparent));
  }
  .lp[data-farbe='blau'] {
    filter: drop-shadow(0 0 2.5px color-mix(in srgb, var(--blau) 55%, transparent));
  }
  .lp[data-farbe='gelb'] {
    filter: drop-shadow(0 0 2.5px color-mix(in srgb, var(--gelb) 55%, transparent));
  }
  .lp[data-farbe='rot'] {
    filter: drop-shadow(0 0 2.5px color-mix(in srgb, var(--rot) 55%, transparent));
  }
  .scheibe {
    /* The dot changes state more often than anything else in the bar, and a
       colour that snaps reads as a redraw rather than as a change. */
    transition: fill 0.3s;
  }
  .scheibe[data-farbe='gruen'] { fill: var(--gruen); }
  .scheibe[data-farbe='blau'] { fill: var(--blau); }
  .scheibe[data-farbe='gelb'] { fill: var(--gelb); }
  .scheibe[data-farbe='rot'] { fill: var(--rot); }
  /* A fact, not a state — and so no glow either. */
  .scheibe[data-farbe='still'] { fill: var(--text-still); }
  .scheibe[data-farbe='leer'] { fill: var(--linie-stark); }
</style>
