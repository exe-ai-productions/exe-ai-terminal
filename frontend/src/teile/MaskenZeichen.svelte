<script>
  /* The mask editor's drawn signs, in one place.

     Every tool in the editor wears a sign instead of a word: a row of words
     reads as a sentence to be parsed, a row of signs as a set of tools to be
     picked from — and the editor is a place for the hand, not for reading.

     One idiom throughout: no fill, round-capped strokes, `currentColor`, so
     a sign takes the colour of the plaque that carries it and needs no
     variant per skin. Two signs carry a filled area on purpose — "fill" and
     "invert" are ABOUT covered area, and an outline alone would say the
     opposite of what they do.

     Its own module because these signs appear on the plaques and, later,
     anywhere the same action is offered; one drawing, one file. */
  let { name = '', groesse = 30 } = $props()
</script>

<svg
  width={groesse}
  height={groesse}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.7"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === 'pinsel'}
    <!-- The brush from the room's own mark, lifted out as a sign of its own:
         handle, metal band, and a head shaped like a glass drop — full and
         round where it meets the band, drawn to a fine point. The point is
         the one place the round join is dropped; a rounded tip would be a
         blunt brush, and a brush is what it can reach.
         Drawn upright and turned as one piece, so all three stay on the
         same axis. -->
    <g transform="rotate(-135 12 12)">
      <path d="M12 9.77 L12 21.67" stroke-width="1.9" />
      <path d="M10.13 9.42 L13.87 9.42" stroke-width="1.9" />
      <path d="M12 2.15 C13.35 4.21, 14.05 5.67, 14.05 6.96 A2.05 2.05 0 1 1 9.95 6.96 C9.95 5.67, 10.65 4.21, 12 2.15 Z"
            stroke-linejoin="miter" />
    </g>
  {:else if name === 'radierer'}
    <!-- Eraser: a block set on its edge, with the line it rubs along. -->
    <path d="M8.4 19.6 L4.4 15.6 a1.6 1.6 0 0 1 0-2.3 L12.9 4.8 a1.6 1.6 0 0 1 2.3 0 L19.6 9.2 a1.6 1.6 0 0 1 0 2.3 L11.5 19.6 Z" />
    <path d="M8.7 9 L15.4 15.7" />
    <path d="M11.5 19.6 H20.5" />
  {:else if name === 'zeiger'}
    <!-- Pointer: painting is on. -->
    <path d="M5.6 3.4 L18.2 11.6 L12.9 12.8 L15.6 18.4 L13.1 19.6 L10.4 14 L6.4 17.7 Z" />
  {:else if name === 'hand'}
    <!-- Open hand: the picture moves instead of taking paint. -->
    <path d="M9 11.6 V5.7 a1.35 1.35 0 0 1 2.7 0 V10.7" />
    <path d="M11.7 10.7 V4.5 a1.35 1.35 0 0 1 2.7 0 V10.7" />
    <path d="M14.4 11 V6.3 a1.35 1.35 0 0 1 2.7 0 V13.6" />
    <path d="M9 11.6 V9.3 a1.35 1.35 0 0 0-2.7 0 V14.7 c0 3.3 2.4 5.8 5.6 5.8 s5.2-2.1 5.2-5.4" />
  {:else if name === 'zurueck'}
    <!-- One step back: the arc returns to where it came from. -->
    <path d="M4.6 8.6 H13.6 a5.2 5.2 0 0 1 0 10.4 H8.4" />
    <path d="M8.4 4.4 L4.2 8.6 L8.4 12.8" />
  {:else if name === 'vor'}
    <path d="M19.4 8.6 H10.4 a5.2 5.2 0 0 0 0 10.4 H15.6" />
    <path d="M15.6 4.4 L19.8 8.6 L15.6 12.8" />
  {:else if name === 'leeren'}
    <!-- Nothing left: a circle struck through. Deliberately NOT a sibling of
         the frame the other whole-mask signs wear — this is the one tool
         that destroys work, and a sign that looks like its neighbours would
         be pressed by a hand aiming for one of them. -->
    <circle cx="12" cy="12" r="8.4" />
    <!-- The stroke runs onto the ring's own centre line, so its round cap
         overlaps the ring and fills the sharp angle where the two meet
         instead of leaving a notch there. -->
    <path d="M6.06 6.06 L17.94 17.94" />
  {:else if name === 'fuellen'}
    <!-- Everything marked: the whole frame is covered. -->
    <rect x="3.6" y="3.6" width="16.8" height="16.8" rx="4" />
    <rect x="6.6" y="6.6" width="10.8" height="10.8" rx="2" fill="currentColor" stroke="none" />
  {:else if name === 'haken'}
    <!-- The house tick, unchanged from the catalogue: take this mask. -->
    <path d="M4 12.5 L9.5 18 L20 6.5" stroke-width="2.6" />
  {:else if name === 'umkehren'}
    <!-- Swapped: what was marked is released, what was free is marked. The
         fill is exactly half the square — corner to corner across the true
         diagonal — and the frame's own rounding is what trims it, so the
         two halves stay equal instead of one being eyeballed to fit. -->
    <defs>
      <clipPath id="maskenzeichen-halb">
        <rect x="3.6" y="3.6" width="16.8" height="16.8" rx="4" />
      </clipPath>
    </defs>
    <rect x="3.6" y="3.6" width="16.8" height="16.8" rx="4" />
    <path d="M20.4 3.6 L20.4 20.4 L3.6 20.4 Z" fill="currentColor" stroke="none"
          clip-path="url(#maskenzeichen-halb)" />
  {:else if name === 'zeigen'}
    <!-- The house eye, unchanged from the catalogue: there is exactly one,
         and every place that shows an eye shows this one. -->
    <path d="M2.5 12 C6 6.5, 18 6.5, 21.5 12 C18 17.5, 6 17.5, 2.5 12 Z" />
    <circle cx="12" cy="12" r="3" />
  {:else if name === 'zeigen-zu'}
    <!-- The same eye closed: its own lower lid line, three lashes. The pair
         reads as one switch — open means the mask is on show, closed means
         it stepped aside for a look underneath. -->
    <path d="M2.5 12 C6 17.5, 18 17.5, 21.5 12" />
    <path d="M6.45 15.1 L5.46 17.5" />
    <path d="M12 16.15 L12 18.75" />
    <path d="M17.55 15.1 L18.54 17.5" />
  {:else if name === 'ganzzeigen'}
    <!-- Back to the whole picture: corners pulled outward. -->
    <path d="M9.4 3.8 H4.8 a1 1 0 0 0-1 1 V9.4" />
    <path d="M14.6 3.8 H19.2 a1 1 0 0 1 1 1 V9.4" />
    <path d="M20.2 14.6 V19.2 a1 1 0 0 1-1 1 H14.6" />
    <path d="M3.8 14.6 V19.2 a1 1 0 0 0 1 1 H9.4" />
  {/if}
</svg>

<style>
  svg {
    flex: none;
    display: block;
  }
</style>
