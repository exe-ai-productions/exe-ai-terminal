<script>
  /* How fast the model is speaking, right now.

     Five strokes standing on one line, only their top edges moving. The
     wave runs through them because each starts a fifth of a beat after its
     neighbour — one animation, five delays, no timers and nothing to keep
     in step by hand.

     The BEAT carries the number: sluggish when the model crawls, lively at
     a normal local speed, shimmering when it races. That is the whole point
     of the thing — the height of a bar would have to be read, a rhythm is
     felt. The exact figure stands beside it for whoever wants it.

     At rest it does not disappear — it freezes. The last measured figure
     stays standing, quietly, with the strokes still: a display that vanishes
     takes its answer with it, and "how fast was that one" is a question
     asked after the answer, not during it. Before the first run of a
     conversation there is nothing to freeze, and then it really is absent.

     The old fluid bar sat here and measured the same thing. It was well
     built; it simply is not what the eye reads fastest in this spot. */

  import { t } from '../lib/texte.svelte.js'

  let { wert = null, laeuft = false } = $props()

  /* The last figure that was really measured. The bar reports `null` again
     the moment a run is over, so the display has to remember for itself
     what it is meant to keep showing.

     It is deliberately not reset here when a run ends. It is cleared by the
     input bar re-creating this component for a different conversation —
     the memory belongs to the chat, and a chat that has never run anything
     shows nothing at all. */
  let letzterWert = $state(null)
  $effect(() => {
    if (wert != null) letzterWert = wert
  })

  /* Five strokes. More would be a graph, fewer would be a blinking light. */
  const STRICHE = 5

  /* How long one wobble takes, from the measurement.

     Inversely proportional, then clamped: at 40 TPS this lands on the 0.55 s
     of the approved template, 5 TPS runs into the slow end, 90 into the
     fast one. The clamps matter more than the curve — without them a first
     chunk measured at 200 would make the strokes flicker, and a stalled
     stream would freeze them. */
  const TAKT_BEI_40 = 22
  const LANGSAMSTE = 1.6
  const SCHNELLSTE = 0.24

  const dauer = $derived(
    Math.min(LANGSAMSTE, Math.max(SCHNELLSTE, TAKT_BEI_40 / Math.max(1, wert ?? 0))),
  )
  /* Each stroke starts a fifth of a beat earlier than the next — that
     offset IS the wave. Negative, so the run is already under way at the
     first frame instead of starting flat. */
  const versatz = $derived(dauer / STRICHE)

  /* Moving only while something is really running AND a figure has arrived.
     Between the two there is a moment where the run has started and nothing
     has been measured yet; strokes wobbling to a made-up beat would be the
     one thing this display must never do. */
  const aktiv = $derived(laeuft && Boolean(wert))
  const gezeigt = $derived(wert ?? letzterWert)
  const sichtbar = $derived(gezeigt != null)

  /* Whole numbers only. The decimal changed the width of the figure on every
     measurement and shoved the row sideways; a tenth of a token per second
     is below what anybody reads anyway. */
  const zahl = $derived(gezeigt == null ? '' : Math.round(gezeigt))
</script>

{#if sichtbar}
  <span class="tempo" class:ruht={!aktiv} aria-label={`${zahl} ${t('eingabe.tps_einheit')}`}>
    <span class="striche" aria-hidden="true">
      {#each Array(STRICHE) as _, i}
        <i style="animation-duration: {dauer}s; animation-delay: {-versatz * (STRICHE - 1 - i)}s"></i>
      {/each}
    </span>
    <span class="wert"><b>{zahl}</b> {t('eingabe.tps_einheit')}</span>
  </span>
{/if}

<style>
  .tempo {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    flex: none;
  }
  .striche {
    display: inline-flex;
    align-items: flex-end;
    gap: 3.5px;
    /* The floor the strokes stand on. Fixed, because a row of bars that
       also moved at the bottom would read as noise instead of a beat. */
    height: 14px;
  }
  .striche i {
    width: 4px;
    height: 100%;
    border-radius: 2px;
    background: var(--text-leise);
    transform-origin: bottom;
    animation-name: wippen;
    animation-timing-function: ease-in-out;
    animation-iteration-count: infinite;
  }
  @keyframes wippen {
    0%, 100% { transform: scaleY(0.3); opacity: 0.65; }
    50% { transform: scaleY(1); opacity: 1; }
  }
  .wert {
    font-family: var(--schrift-fest);
    font-size: 11.5px;
    color: var(--text-leise);
    /* The digits keep their box, so the row does not twitch sideways every
       time the figure changes. */
    font-variant-numeric: tabular-nums;
  }
  /* Room for three digits, right-aligned, held whether the figure needs it
     or not: tabular figures keep ONE digit the same width as another, but a
     two-digit number is still narrower than a three-digit one, and that
     difference was enough to push the row about. */
  .wert b {
    display: inline-block;
    min-width: 3ch;
    text-align: right;
    color: var(--text);
    font-weight: 600;
  }

  /* At rest: the same display, a step back. Nothing moves, everything goes
     quiet, and the figure stays readable for whoever wants it. */
  .tempo.ruht {
    opacity: 0.55;
  }
  .tempo.ruht .striche i {
    animation: none;
    /* Mid-height, so the row of strokes reads as a display at rest and not
       as one that has bottomed out. */
    transform: scaleY(0.55);
    opacity: 1;
  }
  .tempo.ruht .wert b {
    color: var(--text-still);
    font-weight: 500;
  }
  /* Whoever asked for less motion gets the figure, standing still. */
  @media (prefers-reduced-motion: reduce) {
    .striche i {
      animation: none;
      transform: scaleY(0.7);
    }
  }
</style>
