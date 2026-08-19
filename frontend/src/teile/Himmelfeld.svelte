<script>
  /* The Heaven field: a soft pastel sky of overlapping bubbles — blue,
     periwinkle, lavender — fixed behind the whole app and shown ONLY under
     the Heaven skin. Same build as the Dark-Matter field, mirrored into the
     light: low opacity plus a radial mask so it gathers in one area and
     dissolves into the calm ground everywhere else. It sits at z-index -1;
     the solid frame and every bubble/card cover it, so it only shows in the
     empty gaps. Static — a vector image, nothing to animate. */
  import feldUrl from '../lib/himmelfeld.svg'
</script>

<div class="himmelfeld" style:background-image={`url(${feldUrl})`} aria-hidden="true"></div>

<style>
  .himmelfeld {
    display: none;
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background-size: cover;
    background-position: 48% 34%;
    /* Present in the middle, like the dark field: the sky has to be SEEN
       behind the chat, not guessed at. */
    opacity: 0.4;
    /* gather over the chat's middle, dissolve into the light ground at the
       edges */
    -webkit-mask-image: radial-gradient(84% 76% at 50% 40%, #000 0%, rgba(0, 0, 0, 0.5) 58%, transparent 100%);
    mask-image: radial-gradient(84% 76% at 50% 40%, #000 0%, rgba(0, 0, 0, 0.5) 58%, transparent 100%);
  }
  :global(:root[data-modus='heaven']) .himmelfeld {
    display: block;
  }
</style>
