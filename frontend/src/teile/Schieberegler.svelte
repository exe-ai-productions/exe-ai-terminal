<script>
  /* A value you drag instead of type.

     Nobody outside this trade knows what a context is, and fewer still know
     that it grows in powers of two. A number field asks them to know both:
     it accepts 33000 without a word and then behaves oddly, because the
     engine wanted 32768. A slider that snaps to the real steps cannot be
     answered wrongly, and the marks under it show at a glance how far along
     this machine already is.

     Two shapes, one component:

       stufen   a fixed list of values — the slider walks the list and can
                stand nowhere between two of them. This is the context.
       min/max  a plain range, every whole number allowed. This is the layer
                count, where 61 really is one more than 60.

     The marks are drawn only for the stepped shape. On a plain range they
     would be a ruler with a line every pixel. */
  let {
    wert = $bindable(0),
    stufen = null,
    min = 0,
    max = 100,
    gesperrt = false,
    id = undefined,
    beschriftung = '',
    /* How the number reads to a person. The caller knows whether its value
       is tokens, layers or gigabytes; this component only draws what comes
       back. */
    anzeige = (w) => String(w),
    /* Shown instead of the number at the far right, where the end of the
       range means "everything" rather than a quantity. */
    endtext = '',
    /* Off when a number field sits right beside the track — one value,
       written once, and the track gets the room instead. */
    mit_zahl = true,
  } = $props()

  const gestuft = $derived(Array.isArray(stufen) && stufen.length > 1)

  /* For the stepped shape the slider carries the POSITION in the list, not
     the value — that is what makes the steps evenly spaced under the hand
     instead of crowding the small ones into the first tenth of the track. */
  const platz = $derived(
    gestuft ? Math.max(0, naechsteStufe(wert)) : Number(wert),
  )

  function naechsteStufe(w) {
    let beste = 0
    let abstand = Infinity
    stufen.forEach((s, i) => {
      const d = Math.abs(s - w)
      if (d < abstand) {
        abstand = d
        beste = i
      }
    })
    return beste
  }

  function geschoben(ereignis) {
    const n = Number(ereignis.currentTarget.value)
    wert = gestuft ? stufen[n] : n
  }

  const amEnde = $derived(!gestuft && Number(wert) >= max)
  const text = $derived(amEnde && endtext ? endtext : anzeige(wert))
</script>

<div class="regler" class:gesperrt>
  <div class="bahn">
    <input
      {id}
      type="range"
      min={gestuft ? 0 : min}
      max={gestuft ? stufen.length - 1 : max}
      step="1"
      value={platz}
      disabled={gesperrt}
      aria-label={beschriftung || undefined}
      aria-valuetext={text}
      oninput={geschoben}
    />
    <!-- No marks on the track. They were drawn to say where the hand can
         come to rest, but a stepped slider snaps to those places anyway —
         and beside a field that takes any number at all, a row of ticks
         reads as a limit that is not there. -->
  </div>
  {#if mit_zahl}
    <span class="zahl">{text}</span>
  {/if}
</div>

<style>
  .regler {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }
  .regler.gesperrt {
    opacity: 0.6;
  }
  .bahn {
    position: relative;
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    /* The marks stand under the thumb, so the row needs the thumb's height
       whether a mark is drawn or not. */
    height: 22px;
  }

  input[type='range'] {
    appearance: none;
    -webkit-appearance: none;
    width: 100%;
    background: none;
    margin: 0;
    position: relative;
    z-index: 1;
    cursor: pointer;
  }
  input[type='range']:disabled {
    cursor: default;
  }
  /* A timeline, not a bar: a hairline to travel along and the house
     playhead riding above it — the same shape the mask editor and the
     picture window wear, so one kind of control looks like one kind of
     control wherever it turns up. */
  input[type='range']::-webkit-slider-runnable-track {
    height: 2px;
    border-radius: 2px;
    background: var(--text-leise);
  }
  input[type='range']::-moz-range-track {
    height: 2px;
    border-radius: 2px;
    background: var(--text-leise);
  }
  /* Point down, sitting ON the line: a mark that straddles the line would
     hide the spot it marks. */
  input[type='range']::-webkit-slider-thumb {
    appearance: none;
    -webkit-appearance: none;
    width: 12px;
    height: 8px;
    margin-top: -7px;
    background: var(--text-leise);
    clip-path: polygon(0 0, 100% 0, 50% 100%);
    border: none;
  }
  input[type='range']::-moz-range-thumb {
    width: 12px;
    height: 8px;
    background: var(--text-leise);
    clip-path: polygon(0 0, 100% 0, 50% 100%);
    border: none;
    border-radius: 0;
  }
  input[type='range']:not(:disabled):hover::-webkit-slider-thumb { background: var(--text); }
  input[type='range']:not(:disabled):hover::-moz-range-thumb { background: var(--text); }

  /* Blue is the house's colour for "switched on, in use" — a step already
     passed is exactly that, and the ones ahead stay a quiet line. */
  .marken {
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 10px;
    transform: translateY(-50%);
    pointer-events: none;
  }
  .marken i {
    position: absolute;
    top: 0;
    width: 1px;
    height: 10px;
    margin-left: -0.5px;
    background: var(--linie-stark);
  }
  .marken i.erreicht {
    background: var(--blau);
  }

  .zahl {
    flex: none;
    min-width: 6ch;
    text-align: right;
    font-family: var(--schrift-fest);
    font-size: 12px;
    color: var(--text);
    font-variant-numeric: tabular-nums;
  }
</style>
