<script>
  /* The house's one window frame: veil, box, title —
     nothing else. What goes in the window is brought by the caller.

     Extracted because three windows each maintained the same frame once
     (system prompt, settings, new job) — and more are coming.

     Anchored at the top, not centered: otherwise the window grows apart
     upward AND downward while typing. If it gets taller than the screen,
     the veil scrolls — the window as a whole, never a region inside it.
     That's the scrollbar rule: none where none has to be. */
  import { fade, scale } from 'svelte/transition'
  import { t } from '../lib/texte.svelte.js'
  import { cubicIn } from 'svelte/easing'

  /* `symbol` is an optional icon before the title — the job dialog puts
     the agent mark there. As a snippet and not a fixed component, so the
     frame doesn't have to know what fills it. */
  /* Two kinds of window, and the kind decides the size — not the caller.
     Five widths grew here over time (460, 480, 560, 780, 880), and they only
     stand out when two windows are opened one after the other. A single
     `art` instead of a free width is on purpose: a caller cannot pick 780
     and forget the height that belongs to it, which is exactly how the
     settings window drifted 279 px away from the other three.

       frage  460 wide, height follows the content — one question with one
              answer (choose a folder, start a job). Three rows in a box of
              fixed height would stand mostly empty.

       liste  900 wide and a body of FIXED height — everything with a side
              list (settings, models, tools). They are opened one after the
              other and switched between, so any difference reads as a jump.
              The width grew from 780 when the server form's labels started
              wrapping into three lines; the side lists keep their measure,
              so all the new room goes to the content half.

       vorschau  the widest, and taller — it holds a document that was
              written to be looked at. A page squeezed into a list window
              would be judged by the squeeze and not by the page.

     Every width is a `min(…, 92vw)` and every height a `clamp`, so the
     numbers are ceilings for a large screen and never a floor on a small
     one. That is what makes one set of numbers work from a laptop to a 5K
     display: the window takes the room it is given and stops where reading
     would turn into scanning.

     Equal height used to be called impossible here, and that was wrong: it
     is impossible only while a window grows with its content. With a fixed
     body and scrolling inside — the bars are invisible house-wide — every
     window of one kind is the same, whether three rows stand in it or
     thirty. */
  /* galerie: the model catalogue. Wider than a list window so a three-up
     card grid breathes, and a touch taller — a gallery is looked at, not
     scanned down a side list. Still capped to the app area by the same
     min()/clamp() as the others. */
  // `bild` is wider than a question but keeps a question's content-height (no
  // fixed body, no clipping): the picture window lays its controls in two
  // columns so it is broad and short, not one endlessly long tube.
  const BREITE = { frage: '460px', bild: '860px', liste: '1040px', vorschau: '1200px', galerie: '1040px' }

  /* `schrumpfen` closes the window the way the first-start window does:
     it collapses to a point instead of fading. Reserved for a window whose
     closing IS the start of something — the work then appears where the
     window went, and the eye follows it there. The mechanic is the
     first-start window's; only the numbers live here now, so both breathe
     the same way. */
  /* `zurueck` turns the window into a step: an arrow appears in the top-left
     corner and runs it. Closing still closes everything — the arrow is the
     way back, not a second close button. */
  let {
    offen = $bindable(false), titel = '', art = 'frage', symbol, schrumpfen = false,
    zurueck = null, kopf, children,
  } = $props()
</script>

{#if offen}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="schleier" class:weit={art === 'vorschau'} transition:fade={{ duration: 150 }}
       onclick={(e) => { if (e.target === e.currentTarget) offen = false }}>
    <div class="popup" class:liste={art === 'liste'} class:vorschau={art === 'vorschau'}
         class:galerie={art === 'galerie'} class:mitweg={Boolean(zurueck)}
         style="width:min({BREITE[art] ?? BREITE.frage}, 92vw)"
         transition:scale={schrumpfen
           ? { duration: 420, start: 0.03, opacity: 0, easing: cubicIn }
           : { duration: 190, start: 0.97 }}>
      <!-- A window whose body carries its own drawn heading passes an
           empty title; a second plain-text title above it would say the
           same thing twice. -->
      {#if zurueck}
        <!-- Sits above the body and outside the title, because a window whose
             body carries its own drawn heading passes no title at all — and
             the way back has to be there either way. -->
        <button class="zurueck" onclick={zurueck} aria-label={t('app.zurueck')} title={t('app.zurueck')}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 5 8 12l7 7" />
          </svg>
        </button>
      {/if}
      {#if kopf}
        <!-- A caller-drawn control that rides in the header's top-right corner
             (the picture window hangs its Image-Turbo there). Absolutely
             placed so it never disturbs the title or the back-arrow. -->
        <div class="fensterkopf">{@render kopf()}</div>
      {/if}
      {#if titel || symbol}
        <h3>{@render symbol?.()}{titel}</h3>
      {/if}
      <div class="leib">{@render children?.()}</div>
    </div>
  </div>
{/if}

<style>
  .schleier {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 70;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 13vh 16px 6vh;
    overflow-y: auto;
  }
  /* The arrow rides in the top-left corner, and the window makes room for
     it rather than laying it over whatever is there: the catalogue draws its
     own mark exactly in that spot, and an arrow on top of a mark is two
     things fighting for one corner. The room appears only where an arrow
     does, so every window without one looks exactly as it always did. */
  .popup {
    position: relative;
  }
  .popup.mitweg > h3,
  .popup.mitweg > .leib {
    padding-left: 34px;
  }
  .zurueck {
    position: absolute;
    top: 12px;
    left: 12px;
    z-index: 1;
    width: 28px;
    height: 28px;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    background: none;
    color: var(--text-leise);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .zurueck:hover {
    background: var(--linie);
    color: var(--text);
  }
  .popup {
    background: var(--bg-erhoben);
    border-radius: 16px;
    /* The window's outer frame is the house's vector stroke — the same
       2px ring the notifications wear, hung off var(--text) so it is light
       in the dark and black in the light. A ring ON the edge (box-shadow),
       not a border, so the window keeps its exact size. */
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--fensterring, var(--text)) 70%, transparent),
      0 24px 60px rgba(0, 0, 0, 0.3);
    padding: 16px 18px 14px;
  }
  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 12px;
    font-size: 16px;
    font-weight: 600;
  }
  /* Snug under the top frame: a wide pill reads its top gap along its whole
     width, so the gap above must be clearly smaller than the gap beside it
     for the pill to sit IN the corner instead of floating below it. */
  .fensterkopf {
    position: absolute;
    top: 8px;
    right: 15px;
    z-index: 2;
    display: flex;
    align-items: center;
  }

  /* The body. For a question it follows the content; for a list window it is
     the one number that makes them all the same height.

     clamp and not a bare `min(62vh, …)`: in embedded views the browser
     sometimes reports no window height at all, `vh` resolves to 0, and the
     window collapses to a line. The lower bound in pixels keeps it standing
     there too. */
  .popup.liste .leib {
    height: clamp(440px, 74vh, 720px);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  /* A preview window stands higher up and starts lower down than the
     others: a document wants the height, and the drop from the top edge
     that suits a question would take it away on a laptop screen. */
  .schleier.weit { padding: 6vh 16px 5vh; }

  /* Taller than a list window, for the same reason it is wider. */
  .popup.vorschau .leib {
    height: clamp(380px, 68vh, 900px);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  /* The gallery body: one fixed height so the catalogue keeps its measure
     whether four cards stand in it or twelve. The ceiling of 720 matches
     the kind's intended size; the grid scrolls inside, bars invisible. */
  .popup.galerie .leib {
    height: clamp(480px, 74vh, 720px);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  /* On a narrow screen the fixed body would push everything into a
     letterbox — there the window may grow and the page scrolls. */
  @media (max-width: 720px) {
    .popup.liste .leib { height: auto; }
    .popup.vorschau .leib { height: clamp(320px, 70vh, 560px); }
    .popup.galerie .leib { height: auto; }
  }
</style>
