<script>
  /* The section icons of the settings side list.

     Same language as the tool icons and the marks: round stroke caps, no
     fill, strong enough for 14 pixels — but deliberately WITHOUT the
     stroke-draw animation. These icons are signposts, not activity
     indicators; what isn't working doesn't fidget.

     The selection: a drop instead of a painter's palette and a control
     knob instead of a gear — deliberately unlike the stock icons every
     other program reaches for — a plug for the MCP servers
     (connecting, not managing), a key for the credentials. The page with
     the dog-ear is the same drawing as in the tool icon — one icon, one
     meaning: a document. */
  let { zeichen = '', groesse = 14 } = $props()
</script>

<svg
  viewBox="0 0 64 64"
  width={groesse}
  height={groesse}
  fill="none"
  stroke="currentColor"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if zeichen === 'tropfen'}
    <path d="M32 9 C32 9 13 30 13 41.5 A19 19 0 0 0 51 41.5 C51 30 32 9 32 9 Z" stroke-width="5" />
    <path d="M23.5 42 A9 9 0 0 0 30 50.5" stroke-width="4.5" />
  {:else if zeichen === 'seite'}
    <path d="M16 8 H38 L48 18 V56 H16 Z" stroke-width="5" />
    <path d="M38 8 V18 H48" stroke-width="4.5" />
    <path d="M25 34 H39 M25 44 H39" stroke-width="4.5" />
  {:else if zeichen === 'stecker'}
    <path d="M23 26 H41 V36 C41 42.5 37 46.5 32 46.5 C27 46.5 23 42.5 23 36 Z" stroke-width="5" />
    <path d="M27.5 26 V13 M36.5 26 V13" stroke-width="5" />
    <path d="M32 46.5 V56" stroke-width="4.5" />
  {:else if zeichen === 'drehknopf'}
    <circle cx="32" cy="36" r="17" stroke-width="5" />
    <path d="M34.5 33.5 L44 24" stroke-width="5" />
    <path d="M13 15 L16.5 18.5 M32 8 V13 M51 15 L47.5 18.5" stroke-width="4.5" />
  {:else if zeichen === 'schluessel'}
    <circle cx="21" cy="43" r="9.5" stroke-width="5" />
    <path d="M28 36 L50 14" stroke-width="5" />
    <path d="M40 24 L44.5 28.5 M46 18 L50.5 22.5" stroke-width="5" />
  {/if}
</svg>

<style>
  svg {
    flex: none;
    display: block;
  }
</style>
