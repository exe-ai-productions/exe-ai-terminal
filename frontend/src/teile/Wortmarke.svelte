<script>
  /* Mark and lettering as one unit.

     Deliberately **no** single SVG anymore: its viewBox was 300 units
     wide, but the drawing ended at 186. The empty remainder on the right
     belonged to the box and pulled the mark to the left when centering —
     invisible in the header, clearly visible in the empty chat. Putting
     logo and text side by side makes the box as wide as the drawing, on
     every device, no matter how wide the font renders there.

     The measurements come from the old SVG: box 40 units tall, type 20,
     mark 35x28, gap 16. Relative to the font size that is 1.75em wide,
     1.4em tall, 0.8em gap.

     The color is inherited, so it flips along by itself on mode change. */
  /* `mitText = false` shows only the drawing. The watermark behind the
     chat needs that: there the symbol grows to window size, and a
     lettering next to it would be meters tall. As a switch here and not
     as a second drawing elsewhere — there is exactly one wordmark. */
  let { hoehe = 26, zentriert = false, mitText = true } = $props()
</script>

<div class="marke" class:zentriert class:nurzeichen={!mitText} role="img"
     aria-label="Exe AI Terminal" style="font-size:{hoehe / 2}px">
  <svg viewBox="0 0 35 28" fill="none" stroke="currentColor"
       stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <rect x="1.35" y="1.35" width="32.3" height="25.3" rx="7.5" stroke-width="2.7" />
    <path d="M9.5 10 L15.5 14.5 L9.5 19" stroke-width="2.5" />
    <path d="M20 19 H 27" stroke-width="2.5" />
  </svg>
  {#if mitText}<span>Exe AI Terminal</span>{/if}
</div>

<style>
  .marke {
    display: flex;
    align-items: center;
    gap: 0.8em;
    color: var(--text);
    font-family: var(--schrift);
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1;
    white-space: nowrap;
    user-select: none;
  }
  svg {
    width: 1.75em;
    height: 1.4em;
    flex: none;
    display: block;
  }
  /* Where the mark sits centered, the optical center counts, not the
     box's: the type juts out past its layout box on the right. Measured
     at 37.3 px type, the drawing sat 4.42 px too far right — hence
     0.118em. Relative, so it holds at every size.
     Left-aligned this doesn't apply: there the ink should start at the
     edge, and it does so without compensation. */
  .zentriert {
    transform: translateX(-0.118em);
  }
  /* Without the lettering there is nothing to compensate and nothing to
     flow around: the drawing fills the box the watermark gives it. The
     viewBox's aspect ratio is preserved in the process. */
  .nurzeichen {
    gap: 0;
    transform: none;
  }
  .nurzeichen svg {
    width: 100%;
    height: 100%;
  }
</style>
