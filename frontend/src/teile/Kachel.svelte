<script>
  /* One tile, one fixed height — the house's shape of a row.

     Its own component because "tiles of one group are exactly the same
     height" is a house rule, and the only way to guarantee it across
     files is to draw the tile in one place. Every tile is 58px tall; the
     text adapts (one line, ellipsis), the shape never. A get-a-model
     entry, a running-model row, a server entry: all the same box, only
     their contents differ.

     What fills the tile is brought by the caller as snippets:
       zeichen  a sign, drawn inside the bordered 32px badge on the left
       marke    an alternative left mark (a status dot) shown bare
       unter    the subtitle line under the title
       rechts   what sits at the right edge (an arrow, a switch)

     `titel` is the one always-present line. Passing `onclick` turns the
     tile into a button (keyboard-reachable); leaving it off keeps it a
     plain statement, which is what a row carrying its own switch wants —
     a tile must not be a button that swallows the switch inside it. */
  let {
    titel = '',
    gewaehlt = false,
    onclick = null,
    ariaLabel = '',
    zeichen,
    /* A state lamp in front of the name. Sign, lamp, name — the sign says
       WHAT this is, the lamp says how it stands, and the name says which
       one; a lamp under the name, on a line of its own, made the tile twice
       as tall to carry one dot. */
    lampe,
    marke,
    unter,
    rechts,
  } = $props()

  const klickbar = $derived(typeof onclick === 'function')
</script>

<!-- svelte-ignore a11y_no_static_element_interactions, a11y_no_noninteractive_tabindex -->
<div
  class="kachel"
  class:gewaehlt
  class:klickbar
  role={klickbar ? 'button' : undefined}
  tabindex={klickbar ? 0 : undefined}
  aria-label={ariaLabel || undefined}
  {onclick}
  onkeydown={klickbar ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onclick(e) } } : undefined}
>
  {#if zeichen}
    <span class="zbox">{@render zeichen()}</span>
  {:else if marke}
    <span class="marke">{@render marke()}</span>
  {/if}

  <div class="mitte">
    <div class="titel">{#if lampe}<span class="lampe">{@render lampe()}</span>{/if}{titel}</div>
    {#if unter}<div class="unter">{@render unter()}</div>{/if}
  </div>

  {#if rechts}<div class="rechts">{@render rechts()}</div>{/if}
</div>

<style>
  .kachel {
    display: flex;
    align-items: center;
    gap: 11px;
    height: 58px;
    padding: 0 12px;
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg-erhoben);
    color: var(--text);
    text-align: left;
    width: 100%;
    transition: background 0.12s, border-color 0.12s;
  }
  .kachel.klickbar {
    cursor: pointer;
  }
  .kachel.klickbar:hover {
    border-color: var(--linie-stark);
    background: var(--linie);
  }
  /* The chosen tile: a firmer edge and a filled ground, no colour — being
     selected is not a state the palette speaks for. */
  .kachel.gewaehlt {
    border-color: var(--linie-stark);
    background: var(--linie);
  }

  /* The sign badge on the left — a bordered square that holds a drawn
     sign, radius 9 like every control. */
  /* No frame around the sign any more: a sign large enough to be read needs
     no box to be found, and a box around every row drew four rectangles that
     said nothing the sign did not already say. The width stays, so the names
     beside them still start on one line. */
  .zbox {
    width: 32px;
    height: 32px;
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-leise);
  }
  .marke {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .mitte {
    flex: 1;
    min-width: 0;
  }
  .titel {
    display: flex;
    align-items: center;
    gap: 7px;
    font: 600 12.5px var(--schrift);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .lampe {
    flex: none;
    display: inline-flex;
  }
  .unter {
    font-size: 11px;
    color: var(--text-still);
    margin-top: 1px;
    display: flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .rechts {
    margin-left: auto;
    flex: none;
    display: inline-flex;
    align-items: center;
    color: var(--text-still);
    font-size: 12px;
  }
</style>
