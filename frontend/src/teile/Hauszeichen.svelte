<script>
  /* The house's drawn signs, in one place.

     Every sign the catalog, the local view and the settings reach for —
     the model capabilities (chevron, eye, bulb, bolt), the section marks
     (a grid, server racks, a cloud, a mallet, a pencil, a person, a box,
     a key, a document), and a folder. All one idiom: no fill, round-capped
     strokes, currentColor so the sign takes the colour of whatever wraps
     it (grey as a fact, blue when it stands for a live speed module).

     Its own module because a sign that appears in a card, a tile badge and
     a settings row must be the same drawing in all three — one file to
     draw it, none to keep in step. These are static signposts, not the
     running-tool marks, so no stroke-draw animation and — deliberately —
     not the tool catalogue, whose test forbids a drawn sign that maps to
     no tool.

       werkzeug   calls tools (wrench)  raster     the catalog grid
       auge       sees images           server     a model server (racks)
       gluehbirne thinks first          wolke      memory
       blitz      the speed module      buch       skills
       sprache    language              feder      the standing instructions
       erscheinung appearance           person     an agent
       paket      Hugging Face          schluessel a stored key
       dokument   a config file         dokument_pfeil  a raw list file
       ordner     the model folder      bild       a picture server
       einbettung an embedding server

     The three server kinds used to share the rack sign, which said "a
     server" three times and which of the three never. Now the rack stays
     with the model server alone, the picture server wears the framed
     picture the chat menu already uses for making one, and the embedding
     server gets a sign of its own: three points held together by fine
     lines — a vector space small enough to fit in a tile. */
  /* Three sizes, no loose numbers. Callers name a step instead of passing
     pixels, so the whole house can grow or shrink from this one table —
     the old way spread eleven hand-picked numbers over six files, and the
     same sign ended up in three different sizes depending on where it
     stood. A bare number still works where one truly has to differ. */
  const STUFEN = { klein: 15, mittel: 19, gross: 23 }

  let { zeichen = '', groesse = 'mittel' } = $props()

  const kante = $derived(STUFEN[groesse] ?? groesse)
</script>

<svg
  viewBox="0 0 24 24"
  width={kante}
  height={kante}
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if zeichen === 'werkzeug'}
    <!-- The open-end wrench — it replaced the caret, which said
         "terminal" when it meant "calls tools". -->
    <path d="M7 10h3v-3l-3.5-3.5a6 6 0 0 1 8 8l6 6a2 2 0 0 1-3 3l-6-6a6 6 0 0 1-8-8l3.5 3.5" />
  {:else if zeichen === 'auge'}
    <path d="M2.5 12 C6 6.5, 18 6.5, 21.5 12 C18 17.5, 6 17.5, 2.5 12 Z" />
    <circle cx="12" cy="12" r="3" />
  {:else if zeichen === 'gluehbirne'}
    <path d="M12 3 a6.3 6.3 0 0 1 3.4 11.6 c-.6.4-1 1-1 1.7 v.7 h-4.8 v-.7 c0-.7-.4-1.3-1-1.7 A6.3 6.3 0 0 1 12 3 Z" />
    <path d="M10 20.5 h4" />
  {:else if zeichen === 'blitz'}
    <path d="M13 3 L5 13.5 H10.5 L9.5 21 L17.5 10.5 H12 Z" />
  {:else if zeichen === 'raster'}
    <rect x="3.5" y="3.5" width="7.5" height="7.5" rx="2" />
    <rect x="13" y="3.5" width="7.5" height="7.5" rx="2" />
    <rect x="3.5" y="13" width="7.5" height="7.5" rx="2" />
    <rect x="13" y="13" width="7.5" height="7.5" rx="2" />
  {:else if zeichen === 'server'}
    <rect x="3.5" y="4" width="17" height="7" rx="2.5" />
    <rect x="3.5" y="13" width="17" height="7" rx="2.5" />
    <path d="M7 7.5 h.01 M7 16.5 h.01" />
  {:else if zeichen === 'wolke'}
    <path d="M6.3 17.5 h10.9 a3.3 3.3 0 0 0 .4-6.6 A5 5 0 0 0 7.9 9.6 A3.7 3.7 0 0 0 6.3 17.5 Z" />
  {:else if zeichen === 'buch'}
    <path d="M12 6.6 C9.5 5.1 6 5.1 3.6 5.9 V18.2 C6 17.4 9.5 17.4 12 18.9 C14.5 17.4 18 17.4 20.4 18.2 V5.9 C18 5.1 14.5 5.1 12 6.6 Z" />
    <path d="M12 6.6 V18.9" />
  {:else if zeichen === 'sprache'}
    <path d="M20 5.5 H4 V15.5 H8 V19 L12.5 15.5 H20 Z" />
  {:else if zeichen === 'erscheinung'}
    <circle cx="12" cy="12" r="4.2" />
    <path d="M12 3.5v1.8 M12 18.7v1.8 M3.5 12h1.8 M18.7 12h1.8 M6 6l1.3 1.3 M16.7 16.7 18 18 M18 6l-1.3 1.3 M7.3 16.7 6 18" />
  {:else if zeichen === 'feder'}
    <path d="M4 20 l3.5-1 L19 7.5 a1.75 1.75 0 0 0-2.5-2.5 L5 16.5 Z" />
    <path d="M14 6.5 l3.5 3.5" />
  {:else if zeichen === 'person'}
    <circle cx="12" cy="8" r="3.6" />
    <path d="M5.5 19.5 a6.5 6.5 0 0 1 13 0" />
  {:else if zeichen === 'paket'}
    <path d="M12 3 L20.5 7.5 L12 12 L3.5 7.5 Z" />
    <path d="M3.5 7.5 V16 L12 20.5 L20.5 16 V7.5" />
    <path d="M12 12 V20.5" />
  {:else if zeichen === 'schluessel'}
    <circle cx="8.5" cy="8.5" r="3.8" />
    <path d="M11.5 11.5 19.5 19.5 M16.5 16.5 19 14 M14 14 l2.5-2.5" />
  {:else if zeichen === 'dokument'}
    <path d="M6 3.5 h8 l4 4 V20.5 H6 Z" />
    <path d="M14 3.5 V7.5 h4" />
  {:else if zeichen === 'dokument_pfeil'}
    <path d="M6 3.5 h8 l4 4 V20.5 H6 Z" />
    <path d="M14 3.5 V7.5 h4" />
    <path d="M10 12.5 l2.2 2.2-2.2 2.2" />
  {:else if zeichen === 'ordner'}
    <path d="M3 7 a2 2 0 0 1 2-2 h4 l2 2.5 h8 a2 2 0 0 1 2 2 V17 a2 2 0 0 1-2 2 H5 a2 2 0 0 1-2-2 Z" />
  {:else if zeichen === 'bild'}
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="8.5" cy="9.5" r="1.6" />
    <path d="M4 17l4.5-5 3.5 4 3-2.5L20 17" />
  {:else if zeichen === 'einbettung'}
    <!-- The web first, the points on top of it: the lines carry less weight
         than what they connect, which is what makes it read as three things
         in a relation rather than as a triangle. -->
    <path d="M5.5 17.5 L12 5.5 L18.5 14.5 Z" stroke-width="1.4" />
    <path d="M5.5 17.5 h.01 M12 5.5 h.01 M18.5 14.5 h.01" stroke-width="4.2" />
  {/if}
</svg>

<style>
  svg {
    flex: none;
    display: block;
  }
</style>
