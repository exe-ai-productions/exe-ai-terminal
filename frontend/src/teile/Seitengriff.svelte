<script>
  /* The handle that collapses the sidebar — invisible until it is looked for.

     Its own module because it belongs to neither side: the sidebar does not
     own the border it sits on, and the chat does not own the sidebar. It
     lives on the seam between them.

     There is nothing to see at rest. A control that is only ever used twice
     a session does not deserve permanent space, and every visible version of
     it looked stuck on. The strip is 26 px wide, so the mouse finds it
     without aiming; the handle then grows out of the dividing line.

     Because it is invisible, it needs a key: ⌘B, the shortcut every other
     program uses for exactly this. The strip alone would leave anyone who
     never brushes the seam without a way in. */
  import { zustand, seitenleisteSchalten } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'

</script>

<div class="zone" class:zu={zustand.seitenleisteEingeklappt}>
  <button
    class="griff"
    onclick={seitenleisteSchalten}
    title={zustand.seitenleisteEingeklappt
      ? t('seitenleiste.einblenden')
      : t('seitenleiste.ausblenden')}
    aria-label={zustand.seitenleisteEingeklappt
      ? t('seitenleiste.einblenden')
      : t('seitenleiste.ausblenden')}
    aria-pressed={!zustand.seitenleisteEingeklappt}
  >
    <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="3" stroke-linecap="round" stroke-linejoin="round"
         class:gedreht={zustand.seitenleisteEingeklappt}>
      <path d="M15 6l-6 6 6 6" />
    </svg>
  </button>
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

  .griff {
    position: absolute;
    left: -9px;
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 44px;
    border-radius: 99px;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    color: var(--text-still);
    display: grid;
    place-items: center;
    padding: 0;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.14s, color 0.14s;
  }
  /* Appears for the whole catch area, not only over the 18 px itself —
     otherwise it would flicker away the moment you move towards it. */
  .zone:hover .griff,
  .griff:focus-visible {
    opacity: 1;
  }
  .griff:hover {
    color: var(--text);
  }
  .gedreht {
    transform: rotate(180deg);
  }

  /* Collapsed, the seam IS the left edge of the window. Straddling it would
     put half the handle — and half the catch area — outside the screen:
     measured at −9 px, which leaves 9 px of an 18 px control to hit. So both
     move fully inside and lean against the edge. */
  .zone.zu::before {
    left: 0;
  }
  .zone.zu .griff {
    left: 0;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-left: none;
  }

  /* On a narrow screen the sidebar is a drawer over the chat, opened by the
     icon in the menu bar. A handle on a seam that is not there would point
     at nothing. */
  @media (max-width: 720px) {
    .zone { display: none; }
  }
</style>
