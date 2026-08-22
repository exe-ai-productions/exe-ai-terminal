<script>
  /* The mask editor's own mark: the house agent, painting.

     It is the agent mark with two deliberate changes. The eyes, a pair of
     chevrons that face each other everywhere else, are turned upward into
     circumflexes — the agent is looking at the work in front of it rather
     than back at the reader. And a brush is set in its hand, which is the
     one thing this room is for.

     Same idiom as the other house marks: no fill, round-capped strokes,
     `currentColor`, drawn on the 64 grid the marks share. */
  let { groesse = 28 } = $props()
</script>

<svg
  width={groesse}
  height={groesse}
  viewBox="0 0 64 64"
  fill="none"
  stroke="currentColor"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  <!-- The agent, drawn a shade smaller and set to one side. Its own shapes
       are untouched; only the room they stand in changed, so the brush gets
       clear space instead of crossing the shoulder it is held beside. -->
  <g transform="translate(-4 3) scale(0.86)">
    <!-- The hat: brim and crown. -->
    <path d="M6 24 Q32 30 58 24" stroke-width="4.2" />
    <path d="M18 24 V15 Q18 8 32 8 Q46 8 46 15 V24" stroke-width="4.2" />
    <!-- The eyes, turned up: a pair of circumflexes instead of a facing pair
         — the agent looks at the work in front of it, not back at the reader. -->
    <path d="M21.5 35.8 L25 30.6 L28.5 35.8" stroke-width="3.7" />
    <path d="M35.5 35.8 L39 30.6 L42.5 35.8" stroke-width="3.7" />
    <!-- Shoulders and collar. -->
    <path d="M8 60 V51 Q8 42 19 39.5 L32 47 L45 39.5 Q56 42 56 51 V60" stroke-width="4.2" />
  </g>
  <!-- The brush: handle, metal band and a head shaped like a glass drop —
       full and round where it meets the band, drawn to a fine point. The
       point is the one place the round join is dropped: a rounded tip would
       be a blunt brush, and a brush is what it can reach.

       Drawn upright and then turned as one piece, so handle, band and head
       stay on the same axis whatever the angle. The handle ends flush
       against the shoulder — touching, never laid across it: a stroke over
       the figure would read as a scribble and both drawings would lose. -->
  <g transform="translate(-4.2 -1.6) rotate(10 52 36)">
    <path d="M52 56.5 L52 36.2" stroke-width="3.2" />
    <path d="M48.8 35.6 L55.2 35.6" stroke-width="3.2" />
    <path d="M52 23.2 C54.3 26.7 55.5 29.2 55.5 31.4 A3.5 3.5 0 1 1 48.5 31.4 C48.5 29.2 49.7 26.7 52 23.2 Z"
          stroke-width="2.8" stroke-linejoin="miter" />
  </g>
</svg>

<style>
  svg {
    flex: none;
    display: block;
  }
</style>
