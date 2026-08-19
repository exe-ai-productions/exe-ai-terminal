<script>
  /* The Dark-Matter field: a soft flowing violet vector pattern, fixed behind
     the whole app and shown ONLY under the Dark Matter skin. Kept very quiet:
     low opacity plus a radial mask so it concentrates in one area and melts
     into calm black everywhere else — a hint, not a wall-to-wall pattern. It
     sits at z-index -1 (over the body ground, under the app); the solid frame
     and every bubble/card cover it, so it only shows in the empty gaps.
     Static — a vector image, nothing to animate. */
  import feldUrl from '../lib/materiefeld.svg'
</script>

<div class="materiefeld" style:background-image={`url(${feldUrl})`} aria-hidden="true"></div>

<style>
  .materiefeld {
    display: none;
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background-size: cover;
    background-position: 64% 30%;
    opacity: 0.13;
    /* concentrate upper-right, dissolve to calm black at the edges */
    -webkit-mask-image: radial-gradient(78% 70% at 66% 28%, #000 0%, rgba(0, 0, 0, 0.4) 54%, transparent 100%);
    mask-image: radial-gradient(78% 70% at 66% 28%, #000 0%, rgba(0, 0, 0, 0.4) 54%, transparent 100%);
  }
  :global(:root[data-modus='darkmatter']) .materiefeld {
    display: block;
  }
</style>
