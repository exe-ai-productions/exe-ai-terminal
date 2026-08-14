<script>
  /* Painting the part of a picture that should be drawn again.

     The starting picture lies underneath, what gets painted lies over it as
     a translucent house colour. Translucent on purpose: a mask you cannot
     see through is a mask you cannot aim, and aiming is the entire job
     here.

     Three tools and no more — brush, eraser, clear. Everything a person
     needs to mark a region, and nothing that would turn this into a
     drawing program. What leaves here is black and white (lib/maske.js);
     the colour is for the eye only. */
  import Fenster from './Fenster.svelte'
  import { t } from '../lib/texte.svelte.js'
  import { alsDatei, aufFlaeche, bemalt, leeren, malflaeche, strich } from '../lib/maske.js'

  let { offen = $bindable(false), bildUrl = '', fertig } = $props()

  let anzeige = $state(null)
  let flaeche = null
  let stift = $state(null)
  let groesse = $state(48)
  let radiert = $state(false)
  let etwasGemalt = $state(false)
  let letzter = null

  /* The mask is created at the STARTING PICTURE's size, not at the size it
     is shown in. The window scales to fit; the strokes belong to the
     picture's own pixels, so nothing is lost and the export needs no second
     resampling. */
  function bildGeladen(ereignis) {
    const bild = ereignis.currentTarget
    flaeche = malflaeche(bild.naturalWidth, bild.naturalHeight)
    etwasGemalt = false
    zeichnenAufSicht()
  }

  /* What the eye sees: the painted layer, tinted, on top of the picture.

     The tint is painted HERE and not left to a CSS filter: the layer is
     white, and no filter turns white into a chosen colour reliably. The
     mask is drawn first and then filled through itself (`source-in`), which
     colours exactly what was painted and nothing else.

     Redrawn after every stroke — at these sizes that is a copy of a few
     hundred kilobytes and cheaper than keeping two canvases in step. */
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

  function fassen(ereignis) {
    if (!flaeche || ereignis.button !== 0) return
    ereignis.currentTarget.setPointerCapture(ereignis.pointerId)
    letzter = aufFlaeche(ereignis, anzeige, flaeche)
    // A click without a drag should leave a dot, not nothing.
    strich(flaeche, letzter, letzter, groesse, radiert)
    etwasGemalt = bemalt(flaeche)
    zeichnenAufSicht()
  }

  function ziehen(ereignis) {
    if (!letzter || !ereignis.currentTarget.hasPointerCapture?.(ereignis.pointerId)) return
    const jetzt = aufFlaeche(ereignis, anzeige, flaeche)
    strich(flaeche, letzter, jetzt, groesse, radiert)
    letzter = jetzt
    zeichnenAufSicht()
  }

  function loslassen(ereignis) {
    if (ereignis.currentTarget.hasPointerCapture?.(ereignis.pointerId)) {
      ereignis.currentTarget.releasePointerCapture(ereignis.pointerId)
    }
    letzter = null
    etwasGemalt = bemalt(flaeche)
  }

  function allesWeg() {
    if (!flaeche) return
    leeren(flaeche)
    etwasGemalt = false
    zeichnenAufSicht()
  }

  async function uebernehmen() {
    if (!flaeche || !etwasGemalt) return
    fertig(await alsDatei(flaeche))
    offen = false
  }
</script>

<Fenster bind:offen titel={t('maske.titel')} art="vorschau">
  <p class="wofuer">{t('maske.wofuer')}</p>

  <div class="buehne">
    <!-- The picture and the painted layer lie exactly on top of each other;
         the layer takes the strokes, the picture only shows what they are
         aimed at. -->
    <img src={bildUrl} alt={t('bild.startbild')} bind:this={anzeige} onload={bildGeladen} />
    <canvas
      bind:this={stift}
      class="maske"
      onpointerdown={fassen}
      onpointermove={ziehen}
      onpointerup={loslassen}
      onpointercancel={loslassen}
    ></canvas>
  </div>

  <div class="werkzeuge">
    <button class="wahl" class:an={!radiert} onclick={() => (radiert = false)}>
      {t('maske.pinsel')}
    </button>
    <button class="wahl" class:an={radiert} onclick={() => (radiert = true)}>
      {t('maske.radierer')}
    </button>
    <label class="regler">
      <span>{t('maske.groesse')}</span>
      <input type="range" min="4" max="240" step="2" bind:value={groesse}
             aria-label={t('maske.groesse')} />
      <span class="zahl">{groesse}</span>
    </label>
    <button class="wahl" onclick={allesWeg}>{t('maske.leeren')}</button>
  </div>

  <!-- Said in the window, not in a release note: this works with the
       ordinary model and looks it. -->
  <p class="wofuer leise">{t('maske.qualitaet')}</p>

  <div class="fuss">
    <button class="tat" disabled={!etwasGemalt} onclick={uebernehmen}>
      {t('maske.uebernehmen')}
    </button>
  </div>
</Fenster>

<style>
  .wofuer {
    margin: 0 0 10px;
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-still);
  }
  .leise {
    margin: 10px 0 0;
    font-size: 12px;
  }
  /* The picture sets the size, the layer follows it exactly — anything else
     and the strokes land beside what they were aimed at, which is exactly
     what happened: the window's body stretches its children, the stage grew
     wider than the picture, and the painted layer stretched with it while
     the strokes were still being measured against the picture.
     `width: fit-content` plus `align-self` is what keeps the box on the
     picture in both a flex and a block parent. */
  .buehne {
    position: relative;
    display: block;
    width: fit-content;
    align-self: flex-start;
    max-width: 100%;
    line-height: 0;
    border-radius: 12px;
    overflow: hidden;
    border: 2px solid var(--linie-stark);
  }
  .buehne img {
    display: block;
    max-width: 100%;
    max-height: 52vh;
    width: auto;
    height: auto;
  }
  .maske {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    cursor: crosshair;
    touch-action: none;
    /* Translucent, because a mask you cannot see through is a mask you
       cannot aim. Blue is the house colour for "active". */
    opacity: 0.5;
  }
  .werkzeuge {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
    flex-wrap: wrap;
  }
  .regler {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-still);
    margin-left: auto;
  }
  .regler input {
    width: 150px;
    accent-color: var(--text-leise);
  }
  .zahl {
    width: 30px;
    font-variant-numeric: tabular-nums;
  }
  .fuss {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
  }
  .wahl,
  .tat {
    font: inherit;
    font-size: 13px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    border-radius: 9px;
    padding: 6px 13px;
    cursor: pointer;
  }
  .wahl.an {
    background: var(--linie-stark);
  }
  .tat {
    background: var(--linie-stark);
  }
  .tat:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .wahl:hover,
  .tat:not(:disabled):hover {
    background: var(--linie);
  }
</style>
