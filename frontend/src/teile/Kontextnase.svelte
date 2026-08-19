<script>
  /* The context bar, as a nose on the seam between header and chat.

     It used to sit in the foot of the sidebar, where it shared a narrow
     column with the model picker and had room for neither. Up here it has
     the width of the window and one job: how full the context is.

     It appears only with a model loaded — nothing to measure, nothing to
     show. The entrance runs once, on arrival: the nose drops out of the
     seam, settles, and only then does the level run in. Both at once and
     neither reads. Afterwards a changing level moves the fill alone, or the
     nose would hop at every answer. */
  import { kontextStand, zustand } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  const kontext = $derived(kontextStand())
  const sichtbar = $derived(Boolean(zustand.modellId && kontext.gesamt))

  /* The entrance belongs to the arrival of a model, not to every render.
     `frisch` carries it for exactly one appearance. */
  let frisch = $state(false)
  let letztesModell = $state(null)

  $effect(() => {
    if (sichtbar && zustand.modellId !== letztesModell) {
      letztesModell = zustand.modellId
      frisch = false
      requestAnimationFrame(() => (frisch = true))
    }
    if (!sichtbar) letztesModell = null
  })

  function kurz(zahl) {
    if (!zahl) return '0'
    return zahl >= 1000 ? Math.round(zahl / 1000) + 'k' : String(zahl)
  }
</script>

{#if sichtbar}
  <div
    class="nase"
    class:frisch
    title={t('kontext.auslastung', { genutzt: kurz(kontext.genutzt), gesamt: kurz(kontext.gesamt) })}
    role="img"
    aria-label={t('kontext.auslastung', { genutzt: kurz(kontext.genutzt), gesamt: kurz(kontext.gesamt) })}
  >
    <div class="rohr">
      <!-- The gradient sits in the tube at full width and the fill is only
           a window onto it. Carried in the fill instead, every level would
           end in red and the colour would say nothing. -->
      <div class="fuellung" style="width:{kontext.anteil}%">
        <div class="verlauf"></div>
      </div>
    </div>
  </div>
{/if}

<style>
  .nase {
    /* Anchored in the chat column, not in the window: the header runs the
       full width, the chat does not, and a nose centred on the window would
       sit half a sidebar to the left of the input field it belongs to.
       `main` is the anchor, so it moves with the column when either rail
       folds away. */
    position: absolute;
    left: 50%;
    top: 0;
    /* Two pixels of it stay above the seam so it grows out of the edge
       rather than floating below it; the rest hangs in the chat field,
       which is what makes it read as a nose and not as a tab. */
    transform: translate(-50%, -2px);
    z-index: 4;

    display: flex;
    align-items: center;
    height: 35px;
    padding: 0 13px;
    background: var(--bg-leiste, var(--bg));
    border: 1px solid var(--linie);
    border-top: none;
    border-radius: 0 0 10px 10px;
    box-shadow: 0 6px 18px -6px rgba(0, 0, 0, 0.35);
    pointer-events: none;
  }

  .rohr {
    position: relative;
    width: 176px;
    height: 7px;
    border-radius: 99px;
    background: color-mix(in srgb, var(--text-still) 22%, transparent);
    overflow: hidden;
  }

  .fuellung {
    position: absolute;
    inset: 0 auto 0 0;
    overflow: hidden;
    transition: width 0.5s cubic-bezier(0.3, 0.9, 0.3, 1);
  }

  .verlauf {
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: 176px;
    background: linear-gradient(
      90deg,
      var(--gruen) 0%,
      var(--gruen) 34%,
      var(--gelb) 68%,
      var(--rot) 100%
    );
  }

  /* The entrance: the nose drops, squashes as it lands, rocks out. The fill
     waits until that is over — 1.01 s in, measured against the drop. */
  .nase.frisch {
    animation: fallen 1.2s cubic-bezier(0.34, 1.4, 0.5, 1) both;
  }
  .nase.frisch .fuellung {
    animation: einlaufen 1.33s 1.01s cubic-bezier(0.3, 0.9, 0.3, 1) both;
  }

  @keyframes fallen {
    from { transform: translate(-50%, -37px) scaleY(0.4) scaleX(1.25); opacity: 0; }
    45%  { transform: translate(-50%, 6px) scaleY(1.16) scaleX(0.9); opacity: 1; }
    72%  { transform: translate(-50%, -5px) scaleY(0.94) scaleX(1.05); }
    to   { transform: translate(-50%, -2px) scaleY(1) scaleX(1); }
  }

  @keyframes einlaufen {
    from { width: 0; }
  }

  @media (prefers-reduced-motion: reduce) {
    .nase.frisch, .nase.frisch .fuellung, .fuellung { animation: none; transition: none; }
  }
</style>
