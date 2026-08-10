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
  const BREITE = { frage: '460px', liste: '900px', vorschau: '1200px' }

  let {
    offen = $bindable(false), titel = '', art = 'frage', symbol, children,
  } = $props()
</script>

{#if offen}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="schleier" class:weit={art === 'vorschau'} transition:fade={{ duration: 150 }}
       onclick={(e) => { if (e.target === e.currentTarget) offen = false }}>
    <div class="popup" class:liste={art === 'liste'} class:vorschau={art === 'vorschau'}
         style="width:min({BREITE[art] ?? BREITE.frage}, 92vw)"
         transition:scale={{ duration: 190, start: 0.97 }}>
      <h3>{@render symbol?.()}{titel}</h3>
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
  .popup {
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 16px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.3);
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

  /* The body. For a question it follows the content; for a list window it is
     the one number that makes them all the same height.

     clamp and not a bare `min(62vh, …)`: in embedded views the browser
     sometimes reports no window height at all, `vh` resolves to 0, and the
     window collapses to a line. The lower bound in pixels keeps it standing
     there too. */
  .popup.liste .leib {
    height: clamp(440px, 66vh, 640px);
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

  /* On a narrow screen the fixed body would push everything into a
     letterbox — there the window may grow and the page scrolls. */
  @media (max-width: 720px) {
    .popup.liste .leib { height: auto; }
    .popup.vorschau .leib { height: clamp(320px, 70vh, 560px); }
  }
</style>
