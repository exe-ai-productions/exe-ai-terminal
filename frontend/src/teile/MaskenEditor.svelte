<script>
  /* Painting the part of a picture that should be drawn again.

     The starting picture lies underneath, what gets painted lies over it as
     a translucent house colour. Translucent on purpose: a mask you cannot
     see through is a mask you cannot aim, and aiming is the entire job
     here.

     Aiming needs more than a brush once the picture is larger than the
     window: the view zooms and drags, the history takes a wrong stroke
     back, and a handful of whole-mask operations save painting work that a
     brush should never have to do. What leaves here is still black and
     white (lib/maske.js); the colour is for the eye only. */
  import Fenster from './Fenster.svelte'
  import MaskenZeichen from './MaskenZeichen.svelte'
  import Maskenmarke from './Maskenmarke.svelte'
  import Schriftzug from './Schriftzug.svelte'
  import { t } from '../lib/texte.svelte.js'
  /* The two skins that carry a field on the main page carry it in here too,
     so the room does not fall back to a flat panel the moment it opens. */
  import himmelfeldUrl from '../lib/himmelfeld.svg'
  import materiefeldUrl from '../lib/materiefeld.svg'
  import {
    alsDatei,
    aufFlaeche,
    bemalt,
    leeren,
    malflaeche,
    strich,
    umkehren,
  } from '../lib/maske.js'

  let { offen = $bindable(false), bildUrl = '', fertig } = $props()

  let anzeige = $state(null)
  let buehne = $state(null)

  /* The sliders run exactly as wide as the picture is shown and end flush with
     it — a slider wider than the picture it belongs to reads as belonging to
     something else. The width is the picture's own laid-out width (the zoom is
     a transform on top and leaves that box unchanged), watched so it follows
     every resize and every newly loaded picture. */
  let bildBreite = $state(0)
  $effect(() => {
    if (!anzeige) return
    const messen = () => (bildBreite = anzeige.offsetWidth)
    const beobachter = new ResizeObserver(messen)
    beobachter.observe(anzeige)
    messen()
    return () => beobachter.disconnect()
  })

  let flaeche = null
  let stift = $state(null)
  let groesse = $state(48)
  let radiert = $state(false)
  let etwasGemalt = $state(false)
  // Where the brush hovers, in stage pixels — feeds the dashed circle that
  // shows WHERE and HOW BIG the next stroke will land. Null while the
  // pointer is off the picture: no phantom circle in a corner.
  let zeiger = $state(null)
  let massstab = $state(1)

  /* The view: how far in, and where. The transform sits on the box that
     carries picture and mask together, so both move as one and every
     measurement taken from the picture stays true (see maske.js). */
  const TIEFSTE = 1 // "everything visible" — the picture never shrinks below it
  const HOECHSTE = 8
  let zoom = $state(1)
  let versatz = $state({ x: 0, y: 0 })
  let handModus = $state(false)
  let raumTaste = $state(false)
  let schiebt = $state(false)
  const schiebend = $derived(handModus || raumTaste)

  /* What the eye sees of the mask: shown or hidden, and how strongly tinted.
     Hiding is not erasing — it is a look underneath while the mask waits. */
  let maskeSichtbar = $state(true)
  let toenung = $state(0.5)

  /* The history keeps INTENTIONS, not pictures: a stroke is its points, a
     whole-mask operation is its name. Replaying them rebuilds any state
     exactly, which costs a few kilobytes for an unlimited history instead of
     megabytes per step for a stack of canvas copies. */
  let verlauf = $state([])
  let zukunft = $state([])
  let laufenderStrich = null
  const kannZurueck = $derived(verlauf.length > 0)
  const kannVor = $derived(zukunft.length > 0)

  /* The mask is created at the STARTING PICTURE's size, not at the size it
     is shown in. The window scales to fit; the strokes belong to the
     picture's own pixels, so nothing is lost and the export needs no second
     resampling. */
  function bildGeladen(ereignis) {
    const bild = ereignis.currentTarget
    flaeche = malflaeche(bild.naturalWidth, bild.naturalHeight)
    verlauf = []
    zukunft = []
    etwasGemalt = false
    ansichtZurueck()
    zeichnenAufSicht()
  }

  /* What the eye sees: the painted layer, tinted, on top of the picture.

     The tint is painted HERE and not left to a CSS filter: the layer is
     white, and no filter turns white into a chosen colour reliably. The
     mask is drawn first and then filled through itself (`source-in`), which
     colours exactly what was painted and nothing else. */
  const TINTE = 'rgba(90, 150, 255, 1)'

  function zeichnenAufSicht() {
    if (!stift || !flaeche) return
    if (stift.width !== flaeche.width) stift.width = flaeche.width
    if (stift.height !== flaeche.height) stift.height = flaeche.height
    const sicht = stift.getContext('2d')
    sicht.clearRect(0, 0, stift.width, stift.height)
    sicht.drawImage(flaeche, 0, 0)
    sicht.save()
    sicht.globalCompositeOperation = 'source-in'
    sicht.fillStyle = TINTE
    sicht.fillRect(0, 0, stift.width, stift.height)
    sicht.restore()
  }

  // --- History ---------------------------------------------------------

  function anwenden(schritt) {
    if (schritt.art === 'strich') {
      const p = schritt.punkte
      strich(flaeche, p[0], p[0], schritt.groesse, schritt.radiert)
      for (let i = 1; i < p.length; i += 1) {
        strich(flaeche, p[i - 1], p[i], schritt.groesse, schritt.radiert)
      }
    } else if (schritt.art === 'umkehren') {
      umkehren(flaeche)
    } else if (schritt.art === 'leeren') {
      leeren(flaeche)
    }
  }

  function neuZeichnen() {
    if (!flaeche) return
    leeren(flaeche)
    for (const schritt of verlauf) anwenden(schritt)
    etwasGemalt = bemalt(flaeche)
    zeichnenAufSicht()
  }

  /* A finished step closes the door on the redone-away ones: continuing from
     an undone state makes the branch that was skipped unreachable, and
     keeping it would let a later Redo overwrite work that came after. */
  function merken(schritt) {
    verlauf.push(schritt)
    zukunft = []
  }

  function zurueck() {
    if (!kannZurueck) return
    zukunft.push(verlauf.pop())
    neuZeichnen()
  }

  function vor() {
    if (!kannVor) return
    verlauf.push(zukunft.pop())
    neuZeichnen()
  }

  // --- Whole-mask operations -------------------------------------------

  /* One button covers filling too: inverting an empty mask marks the whole
     picture, and pressing it again gives back what was there before — a
     toggle, not two separate tools. */
  function allesUmkehren() {
    if (!flaeche) return
    const schritt = { art: 'umkehren' }
    anwenden(schritt)
    merken(schritt)
    etwasGemalt = bemalt(flaeche)
    zeichnenAufSicht()
  }

  function allesWeg() {
    if (!flaeche) return
    const schritt = { art: 'leeren' }
    anwenden(schritt)
    merken(schritt)
    etwasGemalt = false
    zeichnenAufSicht()
  }

  // --- View -------------------------------------------------------------

  function ansichtZurueck() {
    zoom = TIEFSTE
    versatz = { x: 0, y: 0 }
  }

  /* The picture always covers the stage: the offset is held inside the slack
     the zoom created. Without it the picture could be dragged off to the
     side, leaving an empty stage and nothing to aim at. */
  function begrenzen() {
    if (!buehne) return
    // The inner width, without the border: that is the area the picture has
    // to cover, and the area the offset is measured in.
    versatz = {
      x: Math.min(0, Math.max(buehne.clientWidth * (1 - zoom), versatz.x)),
      y: Math.min(0, Math.max(buehne.clientHeight * (1 - zoom), versatz.y)),
    }
  }

  /* Zoom towards the pointer, not towards the middle: the spot under the
     cursor is the spot being aimed at, and a zoom that walks away from it
     loses exactly what the zoom was for. Keeping it fixed means solving for
     the offset that maps the same picture point back under the pointer. */
  function radeln(ereignis) {
    if (!flaeche || !buehne) return
    ereignis.preventDefault()
    const { x, y } = zeigerImKasten(ereignis)
    const alt = zoom
    const neu = Math.min(HOECHSTE, Math.max(TIEFSTE, alt * Math.exp(-ereignis.deltaY * 0.0016)))
    if (neu === alt) return
    versatz = {
      x: x - ((x - versatz.x) / alt) * neu,
      y: y - ((y - versatz.y) / alt) * neu,
    }
    zoom = neu
    begrenzen()
  }

  // --- Pointer ----------------------------------------------------------

  function fassen(ereignis) {
    if (!flaeche || ereignis.button !== 0) return
    ereignis.currentTarget.setPointerCapture(ereignis.pointerId)
    if (schiebend) {
      schiebt = true
      return
    }
    const punkt = aufFlaeche(ereignis, anzeige, flaeche)
    laufenderStrich = { art: 'strich', punkte: [punkt], groesse, radiert }
    // A click without a drag should leave a dot, not nothing.
    strich(flaeche, punkt, punkt, groesse, radiert)
    // Painting proves there is something; only taking away can leave nothing,
    // and that answer waits until the stroke is finished. Reading back the
    // whole layer is the expensive part of a stroke, so it is asked only when
    // the answer is genuinely unknown.
    if (!radiert) etwasGemalt = true
    zeichnenAufSicht()
  }

  function ziehen(ereignis) {
    zeigerFolgen(ereignis)
    const gefasst = ereignis.currentTarget.hasPointerCapture?.(ereignis.pointerId)
    if (!gefasst) return
    if (schiebt) {
      versatz = {
        x: versatz.x + ereignis.movementX,
        y: versatz.y + ereignis.movementY,
      }
      begrenzen()
      return
    }
    if (!laufenderStrich) return
    const jetzt = aufFlaeche(ereignis, anzeige, flaeche)
    const punkte = laufenderStrich.punkte
    strich(flaeche, punkte[punkte.length - 1], jetzt, groesse, radiert)
    punkte.push(jetzt)
    zeichnenAufSicht()
  }

  /* One step is one finished stroke — pointer down to pointer up — because
     that is what a person did, not the dozens of positions the mouse
     reported on the way. */
  function loslassen(ereignis) {
    if (ereignis.currentTarget.hasPointerCapture?.(ereignis.pointerId)) {
      ereignis.currentTarget.releasePointerCapture(ereignis.pointerId)
    }
    schiebt = false
    if (laufenderStrich) {
      const nahmWeg = laufenderStrich.radiert
      merken(laufenderStrich)
      laufenderStrich = null
      if (nahmWeg) etwasGemalt = bemalt(flaeche)
    }
  }

  /* The dashed circle rides on the pointer at the brush's true size: the
     stroke is measured in the PICTURE's pixels, the circle in the shown
     ones, so the display scale is read from the picture each move — which
     also carries the zoom, because a measured rectangle is post-transform.
     The circle itself is placed against the STAGE, the box that does not
     move, so it stays under the pointer while the picture slides beneath. */
  function zeigerFolgen(ereignis) {
    if (!flaeche || !anzeige || !buehne) return
    massstab = anzeige.getBoundingClientRect().width / flaeche.width
    zeiger = zeigerImKasten(ereignis)
  }

  /* A pointer position inside the stage, in the coordinates an absolutely
     placed child uses. A measured rectangle starts at the OUTER edge, a
     placed child at the inner one — subtracting the border (`clientLeft`)
     is what keeps the ring exactly under the pointer instead of a border's
     width beside it. Also what the wheel needs, for the same reason. */
  function zeigerImKasten(ereignis) {
    const kasten = buehne.getBoundingClientRect()
    return {
      x: ereignis.clientX - kasten.left - buehne.clientLeft,
      y: ereignis.clientY - kasten.top - buehne.clientTop,
    }
  }

  /* Space is the borrowed hand: held down it moves the picture without
     giving up the brush, and the moment it is released the brush is back.
     Ignored while something is being typed, so a space in a text field
     stays a space. */
  function tasteRunter(ereignis) {
    if (!offen) return
    const ziel = ereignis.target
    const tippt = ziel instanceof HTMLElement &&
      (ziel.tagName === 'INPUT' || ziel.tagName === 'TEXTAREA' || ziel.isContentEditable)
    if (ereignis.code === 'Space' && !tippt) {
      ereignis.preventDefault()
      raumTaste = true
      return
    }
    if ((ereignis.metaKey || ereignis.ctrlKey) && ereignis.key.toLowerCase() === 'z') {
      ereignis.preventDefault()
      if (ereignis.shiftKey) vor()
      else zurueck()
    }
  }

  function tasteHoch(ereignis) {
    if (ereignis.code === 'Space') raumTaste = false
  }

  async function uebernehmen() {
    if (!flaeche || !etwasGemalt) return
    fertig(await alsDatei(flaeche))
    offen = false
  }
</script>

<svelte:window onkeydown={tasteRunter} onkeyup={tasteHoch} />

<!-- No plain title: the body carries its own drawn heading (mark + lettering),
     and a text title above it would say the same thing twice. -->
<Fenster bind:offen titel="" art="werk">
  <!-- The size of the brush belongs where the eye starts, at the top edge of
       the frame — not in the row of tools, which is about what a tool does. -->
  <!-- The room's own heading: its mark and its name, both drawn — the house
       agent painting, beside the drawn lettering. The box carries the word
       for a reader that cannot see the strokes. -->
  <!-- The skin's own field, filling the window behind everything in it. Only
       the two skins that carry one paint it; the others keep their plain
       ground. -->
  <div class="feldgrund" aria-hidden="true"
       style={`--himmelfeld:url(${himmelfeldUrl});--materiefeld:url(${materiefeldUrl})`}></div>

  <div class="ueberschrift" aria-label={t('maske.editor')}>
    <!-- Mark and lettering share ONE plaque: the window's own ground, the
         frame the stage wears, the corner the foot button wears. It straddles
         the heading's top edge — half above, half below — so it reads as laid
         onto the window rather than placed inside it. -->
    <span class="markenplakette">
      <Maskenmarke groesse={30} />
      <Schriftzug zug="maske" hoehe={18} />
    </span>
  </div>

  <div class="arbeit">
    <!-- Left: the picture as large as the room allows, its two sliders under
         it. The picture keeps its own shape — the drawing area is not a fixed
         box, so a portrait and a landscape each fill it their own way. -->
    <div class="mitte">
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
      <div
        class="buehne"
        class:hand={schiebend}
        class:greift={schiebt}
        bind:this={buehne}
        onwheel={radeln}
        ondblclick={ansichtZurueck}
        role="presentation"
      >
        <!-- Picture and painted layer lie exactly on top of each other and
             are zoomed and dragged as ONE box; the layer takes the strokes,
             the picture only shows what they are aimed at. -->
        <div class="leinwand" style={`transform: translate(${versatz.x}px, ${versatz.y}px) scale(${zoom})`}>
          <img src={bildUrl} alt={t('bild.startbild')} bind:this={anzeige} onload={bildGeladen} />
          <canvas
            bind:this={stift}
            class="maske"
            style={`opacity:${maskeSichtbar ? toenung : 0}`}
            onpointerdown={fassen}
            onpointermove={ziehen}
            onpointerup={loslassen}
            onpointercancel={loslassen}
            onpointerenter={zeigerFolgen}
            onpointerleave={() => (zeiger = null)}
          ></canvas>
        </div>

        <!-- The brush shown before it lands: a dashed ring at the true
             stroke size, two-toned so it reads on any ground. -->
        {#if zeiger && !schiebend}
          <div
            class="pinselring"
            style={`left:${zeiger.x}px;top:${zeiger.y}px;width:${groesse * massstab}px;height:${groesse * massstab}px`}
            aria-hidden="true"
          ></div>
        {/if}

        <!-- The two steps ride ON the picture, top centre, half faded:
             stepping back and forth is aimed at what was just painted, so
             the buttons stand where the eye already is — quiet enough not
             to cover it, awake the moment the pointer reaches for them. -->
        <div class="verlauf">
          <button class="schritt" disabled={!kannZurueck} onclick={zurueck}
                  title={t('maske.zurueck')} aria-label={t('maske.zurueck')}>
            <MaskenZeichen name="zurueck" groesse={18} />
          </button>
          <button class="schritt" disabled={!kannVor} onclick={vor}
                  title={t('maske.vor')} aria-label={t('maske.vor')}>
            <MaskenZeichen name="vor" groesse={18} />
          </button>
        </div>

        <!-- Only there when it has something to say: how far in, way back. -->
        {#if zoom > TIEFSTE}
          <button class="ansicht" onclick={ansichtZurueck}
                  title={t('maske.ansicht')} aria-label={t('maske.ansicht')}>
            <MaskenZeichen name="ganzzeigen" groesse={16} />
            <span>{Math.round(zoom * 100)} %</span>
          </button>
        {/if}
      </div>

    <!-- Every tool as a plaque, in one row directly under the picture. The
         word each would have worn stays as its label for the pointer and for
         a reader that cannot see the drawing. -->
    <div class="leiste">
      <button class="plakette" class:an={!radiert && !schiebend}
              onclick={() => { radiert = false; handModus = false }}
              aria-pressed={!radiert && !schiebend} title={t('maske.pinsel')} aria-label={t('maske.pinsel')}>
        <MaskenZeichen name="pinsel" />
      </button>
      <button class="plakette" class:an={radiert && !schiebend}
              onclick={() => { radiert = true; handModus = false }}
              aria-pressed={radiert && !schiebend} title={t('maske.radierer')} aria-label={t('maske.radierer')}>
        <MaskenZeichen name="radierer" />
      </button>
      <button class="plakette" class:an={handModus} onclick={() => (handModus = !handModus)}
              aria-pressed={handModus} title={t('maske.verschieben')} aria-label={t('maske.verschieben')}>
        <MaskenZeichen name={handModus ? 'hand' : 'zeiger'} />
      </button>


      <!-- One button, two faces — the way the hand button changes its sign:
           on an empty mask it offers to fill everything, on a painted one to
           swap painted and free. Both are the same inversion underneath. -->
      <button class="plakette" onclick={allesUmkehren}
              title={t(etwasGemalt ? 'maske.umkehren' : 'maske.fuellen')}
              aria-label={t(etwasGemalt ? 'maske.umkehren' : 'maske.fuellen')}>
        <MaskenZeichen name={etwasGemalt ? 'umkehren' : 'fuellen'} />
      </button>
      <!-- Open eye while the mask is on show, closed while it stepped aside:
           the sign says what the next press will undo, the way the hand
           button does. -->
      <button class="plakette" onclick={() => (maskeSichtbar = !maskeSichtbar)}
              aria-pressed={maskeSichtbar}
              title={t(maskeSichtbar ? 'maske.zeigen' : 'maske.verbergen')}
              aria-label={t(maskeSichtbar ? 'maske.zeigen' : 'maske.verbergen')}>
        <MaskenZeichen name={maskeSichtbar ? 'zeigen' : 'zeigen-zu'} />
      </button>
      <button class="plakette" onclick={allesWeg}
              title={t('maske.leeren')} aria-label={t('maske.leeren')}>
        <MaskenZeichen name="leeren" />
      </button>
      <!-- The two sliders ride IN the row, filling what the tools leave of
           it. No written names: each shows what it does while it is being
           moved — the brush ring changes size, the mask changes tint — and a
           word repeating that would cost the length they need. The name
           lives on as the label a pointer and a screen reader find. -->
      <div class="schieber">
        <input class="regler" type="range" min="4" max="240" step="2" bind:value={groesse}
               title={t('maske.groesse')} aria-label={t('maske.groesse')} />
        <input class="regler" type="range" min="0.15" max="0.9" step="0.05" bind:value={toenung}
               title={t('maske.toenung')} aria-label={t('maske.toenung')} />
      </div>

      <!-- The tick carries the word: taking the mask is the one thing in this
           room that reports a state — done — and green is the colour the
           house keeps for exactly that. The word stays as its label. -->
      <button class="tat" disabled={!etwasGemalt} onclick={uebernehmen}
              title={t('maske.uebernehmen')} aria-label={t('maske.uebernehmen')}>
        <MaskenZeichen name="haken" />
      </button>
    </div>
  </div>
</Fenster>

<style>
  /* The heading keeps no height of its own any more — the plaque hangs off
     the window's rim above it, so a line held open underneath would be dead
     air between the plaque and the picture. What is left is the gap: far
     enough below the plaque's lower half for the picture to breathe. */
  /* Fills the whole window — the box it is measured against is the window
     itself, which is the one positioned ancestor here. Kept at z-index 0 and
     not below: a negative layer would slide behind the window's own ground
     and never be seen. Everything else in the room is lifted one step above
     it. The corner matches the window's. */
  .feldgrund {
    display: none;
    position: absolute;
    inset: 0;
    z-index: 0;
    border-radius: 16px;
    background-size: cover;
    pointer-events: none;
    /* Present, never loud: the field is the room's ground, and what is
       painted on the picture has to stay the brightest thing in here. */
    opacity: 0.4;
  }
  /* The pearl skin gets no field but a ground: its raised surface is so close
     to white that a window of it beside the picture glares. The house's warm
     taupe — the same contrast token the selected tab and the input frame
     wear — settles it without inventing a colour. */
  :global(:root[data-modus='hell']) .feldgrund,
  :global(:root:not([data-modus])) .feldgrund {
    display: block;
    background-image: none;
    background-color: var(--kontrast);
  }
  :global(:root[data-modus='heaven']) .feldgrund {
    display: block;
    background-image: var(--himmelfeld);
    background-color: transparent;
    background-position: 48% 34%;
  }
  :global(:root[data-modus='darkmatter']) .feldgrund {
    display: block;
    background-image: var(--materiefeld);
    background-position: 64% 30%;
  }

  .ueberschrift {
    position: relative;
    z-index: 1;
    /* A real height, never zero: a zero-height line collapses its own
       margins together and the whole line — plaque included — is pushed down
       by the very gap meant to sit below it. This height is what the
       plaque's lower half reaches past the rim; the margin is the air
       between it and the picture. */
    height: 7px;
    margin-bottom: 10px;
    color: var(--text);
  }
  .markenplakette {
    position: absolute;
    left: 50%;
    /* Lifted onto the WINDOW's own top edge — the window's padding is exactly
       how far above this line that edge lies. With the half-height shift its
       middle lands on the rim: half of the plaque outside the window, half
       inside, which is what makes it read as laid on rather than placed in. */
    top: -16px;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 18px;
    border-radius: 9px;
    /* The window's ground carrying the same tint the field lays over it, at
       the same strength — so the plaque reads as a piece of the window in
       every skin instead of a bright label stuck to it. Pearl's raised
       surface is nearly cream and Heaven's nearly white; both need the
       contrast token mixed in, and the other two take it without harm. One
       rule, no per-skin exception. */
    background: color-mix(in srgb, var(--kontrast) 40%, var(--bg-erhoben));
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--fensterring, var(--text)) 70%, transparent);
    white-space: nowrap;
  }
  /* The work area: the picture (with its sliders under it) on the left, the
     tool column on the right. Fills the window body between heading and foot. */
  .arbeit {
    position: relative;
    z-index: 1;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    gap: 14px;
    align-items: flex-start;
  }
  /* Shrink-wraps the picture: only as wide as the picture is shown, never
     wider — that is what keeps the tool column anchored to the picture's
     right edge at every format, instead of drifting to the window's edge. */
  .mitte {
    flex: 0 1 auto;
    min-width: 0;
    min-height: 0;
    align-self: stretch;
    display: flex;
    flex-direction: column;
  }
  /* The tools in one vertical column, at the top-right beside the picture. */
  /* The tools in one row under the picture, never wrapping: a second line of
     tools would move every sign the moment the picture changed shape, and a
     hand that learned where a tool sits would have to learn again. */
  .leiste {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
  }
  /* The sliders take whatever length the tools leave, stacked so both fit
     the row's own height. */
  .schieber {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin: 0 6px;
  }
  /* A timeline, not a bar: a hairline to travel along and the playhead from
     the house catalogue riding above it — the same shape the sibling
     program's timeline wears, so a hand that knows one knows the other.
     Drawn from scratch because the browser's own slider cannot be reshaped;
     the element keeps its behaviour and gives up only its looks. */
  .regler {
    appearance: none;
    -webkit-appearance: none;
    width: 100%;
    height: 12px;
    margin: 0;
    background: none;
    cursor: pointer;
  }
  .regler::-webkit-slider-runnable-track {
    height: 2px;
    border-radius: 2px;
    background: var(--text-leise);
  }
  .regler::-moz-range-track {
    height: 2px;
    border-radius: 2px;
    background: var(--text-leise);
  }
  /* The playhead: filled triangle, point down, sitting ON the line. The
     negative offset is what lifts it above the track instead of centring it
     across — a mark that straddles the line would hide the spot it marks. */
  .regler::-webkit-slider-thumb {
    appearance: none;
    -webkit-appearance: none;
    width: 12px;
    height: 8px;
    margin-top: -7px;
    background: var(--text-leise);
    clip-path: polygon(0 0, 100% 0, 50% 100%);
  }
  .regler::-moz-range-thumb {
    width: 12px;
    height: 8px;
    border: none;
    border-radius: 0;
    background: var(--text-leise);
    clip-path: polygon(0 0, 100% 0, 50% 100%);
  }
  .regler:hover::-webkit-slider-thumb { background: var(--text); }
  .regler:hover::-moz-range-thumb { background: var(--text); }
  /* The picture sets the size, the layer follows it exactly — anything else
     and the strokes land beside what they were aimed at. The stage takes the
     picture's own measure and the WINDOW follows the stage (art="werk"), so
     the frame hugs the picture at every format. */
  .buehne {
    position: relative;
    display: block;
    width: fit-content;
    flex: 0 1 auto;
    line-height: 0;
    border-radius: 12px;
    /* The stage is the window onto the picture: what the zoom pushes past
       its edge is cut off here, which is why the frame never grows. */
    overflow: hidden;
    border: 2px solid var(--linie-stark);
    touch-action: none;
  }
  .buehne.hand { cursor: grab; }
  .buehne.greift { cursor: grabbing; }
  .leinwand {
    position: relative;
    /* From the top left, so the offset means the same thing at every zoom. */
    transform-origin: 0 0;
    will-change: transform;
  }
  .buehne img {
    display: block;
    width: auto;
    height: auto;
    /* The picture's ceilings ARE the window's: the window hugs the stage, so
       the caps that keep the window on the screen have to live here, on the
       thing everything else takes its measure from. The subtracted terms are
       the fixed chrome around the picture — heading, sliders, foot, padding
       sideways the tool column — with a floor so a tiny viewport still
       shows a workable picture. */
    max-height: max(260px, calc(89vh - 270px));
    max-width: calc(92vw - 40px);
    /* Never narrower than the row of tools underneath: a picture the row
       cannot fit under would make that row the widest thing in the window
       and hang it over the picture's edge. */
    min-width: 380px;
  }
  .maske {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    /* The dashed ring IS the cursor — a second marker would only argue
       with it about where the stroke lands. */
    cursor: none;
    touch-action: none;
  }
  .buehne.hand .maske { cursor: inherit; }
  .pinselring {
    position: absolute;
    transform: translate(-50%, -50%);
    border-radius: 50%;
    border: 1.5px dashed rgba(255, 255, 255, 0.95);
    /* A dark ring under the light dashes: one of the two reads on any
       ground — blue mask, white dress, deep shadow. */
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.55), inset 0 0 0 1px rgba(0, 0, 0, 0.55);
    pointer-events: none;
  }
  /* The two steps, floating at the picture's top centre. Half faded as a
     pair: present enough to be found, quiet enough not to sit on what was
     just painted — and fully awake under the pointer. */
  .verlauf {
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 6px;
    opacity: 0.6;
    transition: opacity 0.12s;
  }
  .verlauf:hover { opacity: 1; }
  .schritt {
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: color-mix(in srgb, var(--linie-stark) 92%, transparent);
    color: var(--text);
    cursor: pointer;
  }
  .schritt:not(:disabled):hover { background: var(--linie-stark); }
  .schritt:disabled { opacity: 0.4; cursor: default; }

  .ansicht {
    position: absolute;
    right: 8px;
    bottom: 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font: inherit;
    font-size: 11.5px;
    line-height: 1;
    color: var(--text);
    background: color-mix(in srgb, var(--linie-stark) 92%, transparent);
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 6px 11px;
    cursor: pointer;
  }
  .ansicht:hover { background: var(--linie-stark); }

  /* A tool plaque: a square that carries a drawn sign, in the family the
     model cards wear. Big enough to be hit without aiming, quiet enough not
     to compete with the picture above it. */
  .plakette {
    width: 52px;
    height: 52px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    background: none;
    color: var(--text-leise);
    cursor: pointer;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }
  /* A tool is not a state: the chosen one brightens, it never takes a state
     colour — those are reserved for what a thing IS, not what it does. */
  .plakette.an {
    background: var(--linie-stark);
    color: var(--text);
    border-color: var(--kontrast, var(--linie-stark));
  }
  .plakette:not(:disabled):hover {
    background: var(--linie);
    color: var(--text);
  }
  .plakette:disabled {
    opacity: 0.35;
    cursor: default;
  }

  /* The same plaque the tools wear, so the row of shapes stays one family —
     but green, because this one reports a state and they do not. */
  .tat {
    width: 52px;
    height: 52px;
    display: grid;
    place-items: center;
    padding: 0;
    border: 1px solid color-mix(in srgb, var(--gruen) 55%, transparent);
    border-radius: 9px;
    color: var(--gruen);
    background: color-mix(in srgb, var(--gruen) 12%, transparent);
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
  }
  .tat:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .tat:not(:disabled):hover {
    background: color-mix(in srgb, var(--gruen) 22%, transparent);
    border-color: var(--gruen);
  }
</style>
