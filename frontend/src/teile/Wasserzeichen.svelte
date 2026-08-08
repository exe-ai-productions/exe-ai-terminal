<script>
  /* The watermark behind a section — one mark, large and quiet.

     Extracted because two sections carry it: the agents (agent mark) and
     the chats (wordmark). One box, one size, one opacity — not the same
     thing maintained twice.

     **Size:** 75% of the section's height, square, never wider than 75%
     of the width. That way the drawing fits entirely into every window
     and a strip stays free at the bottom with room for a sentence.

     **Opacity:** 40% while the section is empty; 2% as soon as content
     sits in front — otherwise you'd read the content through the
     drawing. The 2 was walked to, not guessed: 7 and 4 both still stood
     out too clearly behind the text.

     The empty state at 40% is used **only** by the agent section. The
     chat doesn't know it: there, as long as nothing has been written,
     the wordmark stands above the centered input — a second large symbol
     behind it would be doubled. That's why the chat gets `blass` fixed
     and `sichtbar` only with the first message.

     **`sichtbar`:** in the chat the watermark is gone at first (the
     wordmark still stands above the input field there) and only grows in
     once the first message is sent. It goes from small to full — on the
     same timing and the same curve as the input bar travels down, so
     both are one motion. */
  let { blass = false, sichtbar = true, children } = $props()
</script>

<div class="wasserzeichen">
  <span class="zeichen" class:blass class:weg={!sichtbar} aria-hidden="true">
    {@render children?.()}
  </span>
</div>

<style>
  .wasserzeichen {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    /* Not clickable: it lies over the surface, but nobody should be able
       to hit it. */
    pointer-events: none;
  }
  .zeichen {
    grid-area: 1 / 1;
    height: 75%;
    max-width: 75%;
    aspect-ratio: 1;
    opacity: 0.4;
    transform: scale(1);
    transition:
      opacity var(--anlauf-dauer) ease,
      transform var(--anlauf-dauer) var(--anlauf-schwung);
  }
  .zeichen.blass {
    opacity: 0.02;
  }
  /* The entrance: grown out from the center, not faded in. */
  .zeichen.weg {
    opacity: 0;
    transform: scale(0.28);
  }
  /* The mark fills its box; the drawing keeps its aspect ratio by
     itself. */
  .zeichen :global(.marke),
  .zeichen :global(svg) {
    width: 100%;
    height: 100%;
  }
  @media (prefers-reduced-motion: reduce) {
    .zeichen { transition: none; }
  }
</style>
