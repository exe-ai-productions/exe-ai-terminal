<script>
  /* The handle on the seam — invisible until it is looked for.

     Its own module because it belongs to neither side: the sidebar does not
     own the border it sits on, and the chat does not own the sidebar. It
     lives on the seam between them.

     There is nothing to see at rest. Brushing the seam shows a plain bar,
     and the bar answers both hands: a click folds the sidebar away or back,
     a drag sets its width — and dragging far past the minimum folds it too,
     the way a hand expects. The width survives restarts; the seam never
     shows a permanent control.

     Because it is invisible, it needs a key: ⌘B, the shortcut every other
     program uses for exactly this. The strip alone would leave anyone who
     never brushes the seam without a way in. */
  import {
    zustand, seitenleisteSchalten, seitenBreiteSetzen,
  } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  // Dragged this far below the minimum, the hand clearly wants it gone.
  const ZUKLAPP_BREITE = 150
  // Under this movement a press still counts as a click, not a drag.
  const KLICK_TOLERANZ = 4

  let startX = 0
  let startBreite = 0
  let bewegt = false

  function fassen(e) {
    if (e.button !== 0) return
    e.preventDefault()
    if (zustand.seitenleisteEingeklappt) return
    startX = e.clientX
    startBreite = zustand.seitenBreite
    bewegt = false
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  function ziehen(e) {
    if (!e.currentTarget.hasPointerCapture?.(e.pointerId)) return
    const dx = e.clientX - startX
    if (!bewegt && Math.abs(dx) <= KLICK_TOLERANZ) return
    bewegt = true
    zustand.seitenZieht = true
    if (startBreite + dx < ZUKLAPP_BREITE) {
      zustand.seitenZieht = false
      e.currentTarget.releasePointerCapture(e.pointerId)
      seitenleisteSchalten()
      return
    }
    seitenBreiteSetzen(startBreite + dx)
  }

  function loslassen(e) {
    zustand.seitenZieht = false
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
    if (!bewegt) seitenleisteSchalten()
    bewegt = false
  }
</script>

<div class="zone" class:zu={zustand.seitenleisteEingeklappt}>
  <button
    class="griff"
    class:packt={zustand.seitenZieht}
    onpointerdown={fassen}
    onpointermove={ziehen}
    onpointerup={loslassen}
    title={zustand.seitenleisteEingeklappt
      ? t('seitenleiste.einblenden')
      : t('seitenleiste.ausblenden')}
    aria-label={zustand.seitenleisteEingeklappt
      ? t('seitenleiste.einblenden')
      : t('seitenleiste.ausblenden')}
    aria-pressed={!zustand.seitenleisteEingeklappt}
  ></button>
</div>

<style>
  /* Zero width in the layout: the strip must not push the chat aside for a
     control that is not there most of the time. */
  .zone {
    position: relative;
    width: 0;
    flex: none;
    z-index: 5;
  }
  /* Gone while a window is open. It lies BEHIND the veil already, but the
     veil only half covers what is under it — and a bright vertical bar
     showing through beside a dialog reads as a scrollbar, not as the handle
     of a sidebar nobody can reach right now. */
  :global(body:has(.schleier)) .zone {
    display: none;
  }
  /* The catch area, wider than what it shows — 26 px is what a mouse finds
     without being aimed. */
  .zone::before {
    content: '';
    position: absolute;
    left: -13px;
    top: 0;
    bottom: 0;
    width: 26px;
  }

  /* A plain bar, nothing else: no arrow, no plate. What it does, the hand
     finds out by using it. */
  .griff {
    position: absolute;
    left: -3px;
    top: 50%;
    transform: translateY(-50%);
    width: 6px;
    height: 96px;
    border-radius: 99px;
    background: var(--linie-stark);
    border: none;
    padding: 0;
    cursor: col-resize;
    touch-action: none;
    opacity: 0;
    transition: opacity 0.14s, background 0.14s;
  }
  /* Appears for the whole catch area, not only over the 6 px itself —
     otherwise it would flicker away the moment you move towards it. */
  .zone:hover .griff,
  .griff:focus-visible,
  .griff.packt {
    opacity: 1;
  }
  .griff:hover,
  .griff.packt {
    background: var(--text-still);
  }

  /* Collapsed, the seam IS the left edge of the window. Straddling it would
     put half the bar — and half the catch area — outside the screen, so
     both move fully inside and lean against the edge. */
  .zone.zu::before {
    left: 0;
  }
  .zone.zu .griff {
    left: 0;
    border-radius: 0 99px 99px 0;
    cursor: pointer;
  }

  /* On a narrow screen the sidebar is a drawer over the chat, opened by the
     icon in the menu bar. A handle on a seam that is not there would point
     at nothing. */
  @media (max-width: 720px) {
    .zone { display: none; }
  }
</style>
