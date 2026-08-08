<script>
  /* The icon before a tool row.

     Every tool may carry its own hand-drawn icon — built like the marks:
     round stroke caps, no fill, strong enough for 15 pixels. While the
     call is still running, the icon draws itself in a loop (timing and
     breather of the loading marks, 3.4 s — nothing ticks against
     anything); once the result is in, it stands still.

     Which mark belongs to which tool is not decided here but in
     lib/werkzeugkatalog.js — this file only draws. New marks are added
     below and entered in the catalogue; the procedure is in the
     "exe-werkzeug-bauen" skill.

     The three strokes are named z1/z2/z3 so every icon uses the same
     choreography, no matter what it shows. */
  import { zeichenFuer } from '../lib/werkzeugkatalog.js'

  let { name = '', server = '', laeuft = false } = $props()

  /* Minimum drawing time: fast calls (SearXNG in
     under a second) were done before the first stroke stood — the icon
     popped up statically. Now, after appearing, it draws itself all the
     way through at least once (up to the breather at 78% of the cycle)
     and only then stands still. The transition is seamless because the
     icon looks exactly the same in the breather as at a standstill. */
  const MINDEST_MS = 2650
  let mindestAktiv = $state(false)
  let mindestTimer = 0

  $effect(() => {
    if (laeuft) {
      mindestAktiv = true
      clearTimeout(mindestTimer)
      mindestTimer = setTimeout(() => (mindestAktiv = false), MINDEST_MS)
    }
  })
  $effect(() => () => clearTimeout(mindestTimer))

  const animiert = $derived(laeuft || mindestAktiv)

  /* Which mark it is comes from the catalogue, not from here — this file
     draws, the catalogue decides. `server` is the reliable part of that
     answer; see lib/werkzeugkatalog.js. */
  const zeichen = $derived(zeichenFuer(name, server))
</script>

{#if zeichen === 'globus'}
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <circle class="strich z1" cx="32" cy="32" r="24" stroke-width="5" style="--laenge:152" />
    <ellipse class="strich z2" cx="32" cy="32" rx="10.5" ry="24" stroke-width="4.5" style="--laenge:118" />
    <path class="strich z3" d="M9.5 32 H54.5" stroke-width="4.5" style="--laenge:46" />
  </svg>
{:else if zeichen === 'brief'}
  <!-- Gmail: an envelope. Not the brand's own mark — house rule says never
       redraw a maker's logo; this says what the tool does, not who makes it. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M9 16 H55 V48 H9 Z" stroke-width="5" style="--laenge:156" />
    <path class="strich z2" d="M9 19 L32 35 L55 19" stroke-width="4.5" style="--laenge:56" />
  </svg>
{:else if zeichen === 'verzweigung'}
  <!-- GitHub: a branch. The trunk, the branch coming off it, and the node it
       runs into — what version control looks like, in three strokes. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M20 15 V49" stroke-width="5" style="--laenge:34" />
    <path class="strich z2" d="M20 32 H33 C39 32 44 27 44 21" stroke-width="4.5" style="--laenge:32" />
    <circle class="strich z3" cx="44" cy="16" r="4.5" stroke-width="4.5" style="--laenge:29" />
  </svg>
{:else if zeichen === 'flaechen'}
  <!-- Figma: two overlapping shapes — a rectangle and a circle, which is what
       laying out a design comes down to. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M11 11 H36 V36 H11 Z" stroke-width="5" style="--laenge:100" />
    <circle class="strich z2" cx="40" cy="40" r="13" stroke-width="5" style="--laenge:82" />
  </svg>
{:else if zeichen === 'paket'}
  <!-- Hugging Face: a model is a package you fetch and put down. The box says
       that; the face of the brand is the brand's, not ours to draw. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M32 9 L54 21 L32 33 L10 21 Z" stroke-width="5" style="--laenge:100" />
    <path class="strich z2" d="M10 21 V43 L32 55 L54 43 V21" stroke-width="4.5" style="--laenge:94" />
    <path class="strich z3" d="M32 33 V55" stroke-width="4.5" style="--laenge:22" />
  </svg>
{:else if zeichen === 'bild'}
  <!-- generate_image, image_to_image, inpaint_image: frame, horizon, sun —
       the universal picture. Which of the three ran is in the row's text; the
       mark says what kind of work it was. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M10 14 H54 V50 H10 Z" stroke-width="5" style="--laenge:160" />
    <path class="strich z2" d="M10 42 L24 29 L34 38 L43 31 L54 40" stroke-width="4.5" style="--laenge:62" />
    <circle class="strich z3" cx="21" cy="24" r="4.5" stroke-width="4.5" style="--laenge:29" />
  </svg>
{:else if zeichen === 'freistellen'}
  <!-- remove_background: the subject stays, the surroundings fall away. Four
       corner brackets instead of a frame — what is left is the cut-out. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M14 26 V14 H26 M38 14 H50 V26" stroke-width="4.5" style="--laenge:48" />
    <path class="strich z2" d="M50 38 V50 H38 M26 50 H14 V38" stroke-width="4.5" style="--laenge:48" />
    <circle class="strich z3" cx="32" cy="32" r="8.5" stroke-width="5" style="--laenge:54" />
  </svg>
{:else if zeichen === 'eingabe'}
  <!-- run_command: the prompt itself — chevron and cursor bar. Deliberately
       WITHOUT the surrounding frame, because that frame is the wordmark of
       the program: the tool must not look like the terminal it runs in. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M14 17 L31 32 L14 47" stroke-width="5" style="--laenge:46" />
    <path class="strich z2" d="M37 47 H49" stroke-width="4.5" style="--laenge:12" />
  </svg>
{:else if zeichen === 'seite'}
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path class="strich z1" d="M16 8 H38 L48 18 V56 H16 Z" stroke-width="5" style="--laenge:164" />
    <path class="strich z2" d="M38 8 V18 H48" stroke-width="4.5" style="--laenge:22" />
    <path class="strich z3" d="M25 34 H39 M25 44 H39" stroke-width="4.5" style="--laenge:30" />
  </svg>
{:else if zeichen === 'wolke'}
  <!-- One stroke, and that is the whole point: everything a memory sign could
       add inside — a downward arrow, a line, a dot — closes up at 15 px. The
       outline alone survives, and it is the part that carries the meaning. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path
      class="strich z1"
      d="M18 46 A13 13 0 0 1 19 21 A16 16 0 0 1 47 24 A12 12 0 0 1 46 46 Z"
      stroke-width="5"
      style="--laenge:130"
    />
  </svg>
{:else if zeichen === 'hammer'}
  <!-- Upright, with the left underside curving inward so the front corner
       stands out as a claw. A plain rectangle on a shaft reads as a T or a
       signpost; that one concave edge is what makes it a hammer. Two
       strokes, head first, then the shaft — the order the eye takes it in. -->
  <svg
    class="zeichen"
    class:laeuft={animiert}
    viewBox="0 0 64 64"
    fill="none"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path
      class="strich z1"
      d="M16 13 H48 V27 H27 C25 22 21 17 16 13 Z"
      stroke-width="5"
      style="--laenge:90"
    />
    <path
      class="strich z2"
      d="M32 27 V56"
      stroke-width="5"
      style="--laenge:30"
    />
  </svg>
{:else}
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
    <path d="M9 6l6 6-6 6" />
  </svg>
{/if}

<style>
  /* One number for all three places the mark appears — the chat row, the
     notification, the job log. 15 px came from the days when the only mark
     was a globe and it was decoration; the marks carry meaning now and were
     hard to make out. */
  .zeichen {
    width: 26px;
    height: 26px;
    flex: none;
  }
  .strich {
    stroke-dasharray: var(--laenge);
    stroke-dashoffset: 0;
  }
  .laeuft {
    animation: atemzug 3.4s linear infinite;
  }
  .laeuft .z1 { animation: ziehen1 3.4s cubic-bezier(0.45, 0, 0.25, 1) infinite; }
  .laeuft .z2 { animation: ziehen2 3.4s cubic-bezier(0.45, 0, 0.25, 1) infinite; }
  .laeuft .z3 { animation: ziehen3 3.4s cubic-bezier(0.45, 0, 0.25, 1) infinite; }
  @keyframes atemzug { 0%, 78% { opacity: 1; } 96%, 100% { opacity: 0; } }
  @keyframes ziehen1 { 0% { stroke-dashoffset: var(--laenge); } 30%, 100% { stroke-dashoffset: 0; } }
  @keyframes ziehen2 { 0%, 22% { stroke-dashoffset: var(--laenge); } 44%, 100% { stroke-dashoffset: 0; } }
  @keyframes ziehen3 { 0%, 38% { stroke-dashoffset: var(--laenge); } 52%, 100% { stroke-dashoffset: 0; } }

  /* Whoever can't tolerate motion gets the finished icon at a standstill. */
  @media (prefers-reduced-motion: reduce) {
    .laeuft, .laeuft * { animation: none !important; }
  }
</style>
