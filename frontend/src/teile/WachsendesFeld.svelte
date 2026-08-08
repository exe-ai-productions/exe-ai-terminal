<script>
  /* The windows' text field: grows with the text up to a cap, after
     which the window stays the same size and the text scrolls INSIDE the
     field — no visible scrollbar and no resize handle (without the cap,
     the editor grew out of the picture in all directions).

     Monospace for all content: in the system prompt
     it keeps the text stable, in an agent's front matter the dashes and
     indentation. Extracted from the system-prompt window so the job
     dialog doesn't maintain the same mechanics a second time. */
  let {
    wert = $bindable(''),
    platzhalter = '',
    beschriftung = '',
    gesperrt = false,
    // Grayed out but readable — the system prompt uses this when it is
    // suspended for the current chat.
    gedimmt = false,
    /* Always fill the full available height instead of growing with the
       content. The editor alternates between short
       (system prompt) and long content (MCP configuration) — without
       this, the window jumped to a different size on every switch. The
       job dialog uses the same component and deliberately stays out of
       it: full height for one line of text would just be empty space
       there. */
    volleHoehe = false,
  } = $props()

  let feld = $state(null)

  function hoehe() {
    // In full mode, flexbox determines the size (rest of the 60vh row
    // after the extra blocks below) - setting a height of our own here
    // would work against it.
    if (!feld || volleHoehe) return
    feld.style.height = 'auto'
    feld.style.height = feld.scrollHeight + 'px'
  }

  $effect(() => {
    wert
    hoehe()
  })

  /* For the caller: put the cursor into the field after loading. */
  export function fokus() {
    feld?.focus()
    hoehe()
  }
</script>

<div class="feld" class:gedimmt class:volleHoehe>
  <textarea
    bind:this={feld}
    bind:value={wert}
    rows="1"
    disabled={gesperrt}
    placeholder={platzhalter}
    aria-label={beschriftung}
  ></textarea>
</div>

<style>
  /* Its own box with air all around, not a borderless band. Border,
     rounding and behavior like the input bar at the bottom of the
     window. */
  .feld {
    border: 1px solid var(--linie-stark);
    /* 12 — it is a surface, and the palette gives surfaces 12. */
    border-radius: 12px;
    background: var(--bg);
    padding: 4px;
    transition: border-color 0.15s, opacity 0.18s;
  }
  .feld:focus-within {
    border-color: var(--text-still);
  }
  .feld.gedimmt {
    opacity: 0.35;
  }
  textarea {
    width: 100%;
    border: none;
    background: none;
    color: var(--text);
    font-family: var(--schrift-fest);
    font-size: 12.5px;
    line-height: 1.6;
    padding: 9px 11px;
    resize: none;
    outline: none;
    display: block;
    /* The cap: the field grows up to here, from then on the text scrolls
       inside. No visible scrollbar — scrolling still works (wheel,
       swipe, cursor), and while typing the field follows the cursor by
       itself, because IT is the scroll container, not a frame around
       it. */
    max-height: 60vh;
    overflow-y: auto;
    scrollbar-width: none;
    transition: height 0.16s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  textarea::-webkit-scrollbar {
    display: none;
  }
  textarea::placeholder {
    color: var(--text-still);
  }
  /* Full mode: the field takes up the rest of the fixed height the
     caller sets for its content area. That makes the window exactly the
     same height on every tab, even though some show extra blocks below
     (status lights, read indicator, suspend switch). Its own cap goes
     away — capping is now done by the flex frame. */
  .feld.volleHoehe {
    display: flex;
    flex: 1;
    min-height: 0;
  }
  .feld.volleHoehe textarea {
    flex: 1;
    height: 100%;
    max-height: none;
  }
  @media (prefers-reduced-motion: reduce) {
    textarea { transition: none; }
  }
</style>
