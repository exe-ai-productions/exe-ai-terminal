<script>
  /* A picture at full size. Click anywhere or press Escape to close.

     Plain HTML and CSS — it behaves the same on every system, and there is
     nothing here that a viewer would have to install.

     It hangs at the top of the program, never inside the message that owns
     the picture: an overlay has to cover everything, and inside the message
     list it ended up under the sidebar. */
  import { bildschau } from '../lib/bildschau.svelte.js'
</script>

{#if bildschau.offen}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
  <div
    class="schau"
    role="dialog"
    tabindex="-1"
    onclick={() => (bildschau.offen = false)}
    onkeydown={(e) => { if (e.key === 'Escape') bildschau.offen = false }}
  >
    <img src={bildschau.adresse} alt="" />
  </div>
{/if}

<style>
  .schau {
    position: fixed;
    inset: 0;
    z-index: 90;
    background: rgba(0, 0, 0, 0.72);
    display: grid;
    place-items: center;
    cursor: zoom-out;
  }

  /* The same edge as everywhere else, and `block` so the picture starts at
     the first pixel inside it instead of sitting on a text baseline. */
  .schau img {
    display: block;
    max-width: 92vw;
    max-height: 92vh;
    border: 2px solid var(--linie-stark);
    border-radius: 0;
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
  }
</style>
