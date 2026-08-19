<script>
  /* The working picture stage — the house's loading mark for a picture
     being painted.

     Dust becoming a picture: grains drift aimlessly like dust in a beam of
     light, and as the painter's honest step counter climbs, one grain after
     the other eases into its place on a little sketch — horizon, mountains,
     sun — until the drawing stands. That is the run's true story told
     truthfully: order found in noise. Progress IS the settled share, so no
     figure stands in the middle any more.

     `fuellen` is the built-in mode for the chat: the stage fills whatever
     box the caller has drawn (the finished picture's own frame), bringing
     no edge of its own — two frames would be one too many. Standalone
     (without `fuellen`) it draws its old plain edge and sizes itself from
     `kante`, so it can stand alone anywhere.

     The component polls the one progress endpoint itself while mounted:
     it is only ever mounted while a picture is being painted, so mounting
     is the start and unmounting the end of the polling. When the server
     has no counter (turbo path, model still loading), no grain settles and
     the dust just drifts — honest movement without an invented number. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'

  let { breite = 1, hoehe = 1, kante = 220, fuellen = false } = $props()

  let anteil = $state(0)
  let zahlDa = $state(false)

  $effect(() => {
    let lebt = true
    const holen = async () => {
      try {
        const stand = await api.bildFortschritt()
        if (!lebt) return
        if (stand.laeuft && stand.gesamt > 0) {
          zahlDa = true
          anteil = Math.max(anteil, stand.anteil)
        }
      } catch {
        /* a missing counter is not an error — the dust just drifts */
      }
    }
    holen()
    const takt = setInterval(holen, 700)
    return () => { lebt = false; clearInterval(takt) }
  })

  const seite = $derived(hoehe / Math.max(breite, 1))
  const hoch = $derived(Math.round(kante * Math.min(Math.max(seite, 0.5), 2)))
  const prozent = $derived(Math.round(anteil * 100))

  /* The sketch the grains settle into, in its own 0..100 space: horizon,
     mountains, sun — the same little landscape the house draws elsewhere. */
  const WEGE = [
    { zug: 'M6 78 L94 78', punkte: 18 },
    { zug: 'M14 78 L38 44 L52 62 L62 50 L82 78', punkte: 26 },
    { zug: 'M74 21 a9 9 0 1 1 -0.01 0 Z', punkte: 12 },
  ]

  /* Deterministic scatter: the same constellation on every run, so the
     stage is calm instead of rolling new dice each mount. */
  function wuerfel(saat) {
    let z = saat >>> 0
    z = Math.imul(z ^ (z >>> 16), 2246822519)
    z = Math.imul(z ^ (z >>> 13), 3266489917)
    return ((z ^ (z >>> 16)) >>> 0) / 4294967296
  }

  let buehne = $state(null)
  let messSvg = $state(null)

  /* The particle field is driven imperatively: fifty-odd grains moving
     every frame would churn the reactivity for no gain. The component owns
     its stage; inside it, it draws by hand. */
  $effect(() => {
    if (!buehne || !messSvg) return

    const ziele = []
    for (const pfad of messSvg.querySelectorAll('path')) {
      const laenge = pfad.getTotalLength()
      const punkte = Number(pfad.dataset.punkte)
      for (let i = 0; i < punkte; i++) {
        const punkt = pfad.getPointAtLength((laenge * i) / (punkte - 1))
        ziele.push({ x: punkt.x, y: punkt.y })
      }
    }

    const koerner = ziele.map((ziel, i) => {
      const el = document.createElement('i')
      el.className = 'korn' + (i % 9 === 0 ? ' blau' : '')
      const d = 2.4 + wuerfel(i * 11 + 6) * 1.8
      el.style.width = d + 'px'
      el.style.height = d + 'px'
      buehne.appendChild(el)
      return {
        el, ziel,
        bx: 8 + wuerfel(i * 11 + 7) * 84,
        by: 8 + wuerfel(i * 11 + 8) * 84,
        ax: 3 + wuerfel(i * 11 + 9) * 5,
        ay: 3 + wuerfel(i * 11 + 10) * 5,
        fx: 0.4 + wuerfel(i * 11 + 11) * 0.7,
        fy: 0.35 + wuerfel(i * 11 + 12) * 0.65,
        ph: wuerfel(i * 11 + 13) * Math.PI * 2,
        fest: false, festSeit: 0, vonX: 0, vonY: 0,
      }
    })

    const ruhig = matchMedia('(prefers-reduced-motion: reduce)').matches
    let rahmen = 0
    /* The stage size is read once every ~half second, not every frame: a
       layout query per frame would fight the growing frame around it. */
    let feldB = 0, feldH = 0, messTakt = 0

    const malen = (jetzt) => {
      if (messTakt-- <= 0) {
        feldB = buehne.clientWidth
        feldH = buehne.clientHeight
        messTakt = 29
      }
      /* The sketch sits centred, scaled to the shorter side: the stage can
         have any ordered aspect, the drawing keeps its shape. */
      const zeichenSeite = Math.min(feldB, feldH) * 0.72
      const abX = (feldB - zeichenSeite) / 2
      const abY = (feldH - zeichenSeite) / 2
      const sek = jetzt / 1000

      koerner.forEach((korn, i) => {
        /* One-based: at a share of zero NOTHING has settled yet. */
        const dran = (i + 1) / koerner.length <= anteil
        if (dran && !korn.fest) {
          korn.fest = true
          korn.festSeit = jetzt
          korn.vonX = korn.bx + Math.sin(sek * korn.fx + korn.ph) * korn.ax
          korn.vonY = korn.by + Math.cos(sek * korn.fy + korn.ph) * korn.ay
          korn.el.classList.add('fest')
        }
        let x, y
        if (korn.fest) {
          const weg = ruhig ? 1 : Math.min(1, (jetzt - korn.festSeit) / 650)
          const glatt = 1 - Math.pow(1 - weg, 3)
          const zx = (korn.ziel.x / 100) * zeichenSeite + abX
          const zy = (korn.ziel.y / 100) * zeichenSeite + abY
          x = (korn.vonX / 100) * feldB + (zx - (korn.vonX / 100) * feldB) * glatt
          y = (korn.vonY / 100) * feldH + (zy - (korn.vonY / 100) * feldH) * glatt
        } else if (ruhig) {
          x = (korn.bx / 100) * feldB
          y = (korn.by / 100) * feldH
        } else {
          x = ((korn.bx + Math.sin(sek * korn.fx + korn.ph) * korn.ax) / 100) * feldB
          y = ((korn.by + Math.cos(sek * korn.fy + korn.ph) * korn.ay) / 100) * feldH
        }
        korn.el.style.transform = `translate(${x}px, ${y}px)`
      })

      /* The drift never rests while the painter works — the stage lives
         only for the painting's duration and leaves with it. */
      if (!ruhig) rahmen = requestAnimationFrame(malen)
    }

    rahmen = requestAnimationFrame(malen)
    if (ruhig) {
      /* No drift for those who ask for none: place everything once per
         share change instead of every frame. */
      const stiller = setInterval(() => malen(performance.now()), 700)
      return () => { clearInterval(stiller); cancelAnimationFrame(rahmen); koerner.forEach((k) => k.el.remove()) }
    }
    return () => { cancelAnimationFrame(rahmen); koerner.forEach((k) => k.el.remove()) }
  })
</script>

<div class="rahmen" class:fuellt={fuellen}
     style={fuellen ? undefined : `width:${kante}px;height:${hoch}px`}
     role="img" aria-label={zahlDa ? t('bild.fortschritt_prozent', { zahl: prozent }) : t('nachricht.bild_laeuft')}>
  <div class="staub" bind:this={buehne}></div>
  <!-- Only for measuring the sketch: never shown, but it must be rendered
       (display:none would make the path lengths unreadable). -->
  <svg class="mass" viewBox="0 0 100 100" aria-hidden="true" bind:this={messSvg}>
    {#each WEGE as weg}
      <path d={weg.zug} data-punkte={weg.punkte} />
    {/each}
  </svg>
</div>

<style>
  /* Standing alone, the stage draws its own plain edge. */
  .rahmen {
    position: relative;
    border: 2px solid var(--linie-stark);
    border-radius: 0;
    overflow: hidden;
    background: var(--bg-erhoben);
  }
  /* Built into a caller's frame: fill it, bring no edge of your own. */
  .rahmen.fuellt {
    width: 100%;
    height: 100%;
    border: none;
    border-radius: 0;
  }
  .staub { position: absolute; inset: 0; }
  .mass { position: absolute; width: 0; height: 0; visibility: hidden; }
  .mass path { fill: none; }

  .staub :global(.korn) {
    position: absolute;
    left: 0;
    top: 0;
    border-radius: 99px;
    background: var(--text-still);
    will-change: transform;
  }
  .staub :global(.korn.fest) {
    background: var(--text-leise);
    box-shadow: 0 0 6px color-mix(in srgb, var(--blau) 35%, transparent);
  }
  .staub :global(.korn.blau) { background: var(--blau); }
</style>
