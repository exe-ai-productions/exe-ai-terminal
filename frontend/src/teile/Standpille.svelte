<script>
  /* The small outlined pill that names a state: connected, on, running,
     failed.

     Its own component because the same fourteen lines stood in three files
     word for word, and a fourth had drifted a little already. A shape that
     appears in four places and is corrected in one of them is how a house
     style comes apart.

     `farbe` follows the house rule — colour means state, never decoration:

       gruen  done, ready, connected
       blau   running, active, switched on
       gelb   waiting, and caution
       rot    failed, dangerous
       still  no state worth a colour: off, unreachable, unset

     Nothing here positions the pill. Where it sits belongs to whoever puts
     it somewhere. */
  let { farbe = 'still', children } = $props()
</script>

<span class="pille" data-farbe={farbe}>{@render children?.()}</span>

<style>
  .pille {
    /* inline-flex and line-height 1, so the text is centred against the box
       instead of hanging in an inherited line height. As an inline span with
       1 px of padding it sat visibly too high — that was the whole bug. */
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    line-height: 1;
    font-size: 14px;
    white-space: nowrap;
    border: 1px solid var(--linie-stark);
    /* A control's corner, not a pill's: it reports a state beside a heading,
       and every other bordered thing in these panels wears this radius. */
    border-radius: 9px;
    color: var(--text-still);
    /* One pixel less above than below. Measured, not guessed — and the
       measurement went against the guess: with even padding the ink of these
       words sits about a pixel BELOW the middle of the box, because the
       baseline hangs low in a line box of height 1. So the text moves up.

       It cannot be right for every word at once: a word of pure x-height
       ("an", "on") measures 1.1 px lower than one with ascenders and
       descenders ("connected"), and no single padding centres both. So the
       value sits halfway between them — measured, nothing is off by more
       than half a pixel either way, where favouring the long words left the
       short ones a full pixel low.

       Same lesson as the round letters of the lettering: what is measured
       equal is not yet what looks equal. */
    padding: 3.5px 9px 5.5px;
  }

  .pille[data-farbe='gruen'] {
    color: var(--gruen);
    border-color: color-mix(in srgb, var(--gruen) 45%, transparent);
  }
  .pille[data-farbe='blau'] {
    color: var(--blau);
    border-color: color-mix(in srgb, var(--blau) 45%, transparent);
  }
  .pille[data-farbe='gelb'] {
    color: var(--gelb);
    border-color: color-mix(in srgb, var(--gelb) 45%, transparent);
  }
  .pille[data-farbe='rot'] {
    color: var(--rot);
    border-color: color-mix(in srgb, var(--rot) 45%, transparent);
  }
</style>
