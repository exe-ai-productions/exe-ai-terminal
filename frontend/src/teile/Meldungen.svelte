<script>
  import { fly } from 'svelte/transition'
  import { backOut, cubicIn } from 'svelte/easing'
  import Werkzeugzeichen from './Werkzeugzeichen.svelte'
  import { meldungen, schliesseMeldung } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  /* The notification slides out from under the header and lands with an
     overshoot — backOut goes briefly past the target and springs back.
     On disappearing, upward without springing, otherwise it looks silly.

     It lies between the header and the chat: visible above the history,
     but the bar's menus stay above it. */
  const REIN = { y: -70, duration: 460, easing: backOut }
  const RAUS = { y: -40, duration: 220, easing: cubicIn }

  /* Tool notifications no longer carry an icon of their own: there
     stands the tool icon of the call (globe & co.), drawing itself in a
     loop as long as it runs — same language as the line in the chat. */
  const ZEICHEN = {
    hinweis: 'M12 21a9 9 0 100-18 9 9 0 000 18M12 11v5M12 8h.01',
    erfolg: 'M20 6L9 17l-5-5',
    fehler: 'M12 21a9 9 0 100-18 9 9 0 000 18M12 7v6M12 16h.01',
  }
</script>

<div class="stapel" role="status" aria-live="polite">
  {#each meldungen.liste as meldung (meldung.id)}
    <div class="meldung {meldung.art}" in:fly={REIN} out:fly={RAUS}>
      <span class="zeichen">
        {#if meldung.art === 'werkzeug'}
          <Werkzeugzeichen name={meldung.werkzeug} laeuft={true} />
        {:else}
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d={ZEICHEN[meldung.art] ?? ZEICHEN.hinweis} />
          </svg>
        {/if}
      </span>
      <span class="text">{meldung.text}</span>
      <button class="zu" onclick={() => schliesseMeldung(meldung.id)} aria-label={t('app.schliessen')}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
      </button>
    </div>
  {/each}
</div>

<style>
  .stapel {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 25;
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: center;
    padding-top: 12px;
    pointer-events: none;
  }
  /* Borderless and
     raised, outside the stroke of the chat mark — as a ring ON the edge,
     so the card stays exactly the same size. It hangs off var(--text)
     and is thus light in dark mode and black in light mode, like the
     mark. The kind's color lives solely in the icon, no colored edge
     anymore. */
  .meldung {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    max-width: min(460px, calc(100vw - 32px));
    background: var(--bg-erhoben);
    border: none;
    border-radius: 12px;
    padding: 11px 15px 11px 13px;
    font-size: 13px;
    line-height: 1.45;
    /* 70% opacity: fully opaque, the ring cut too
       harshly out of the surface. */
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--text) 70%, transparent),
      0 12px 32px rgba(0, 0, 0, 0.22);
    pointer-events: auto;
  }
  .zeichen {
    flex: none;
    margin-top: 1px;
    display: inline-flex;
  }
  .hinweis .zeichen {
    color: var(--text-leise);
  }
  .erfolg .zeichen {
    color: var(--gruen);
  }
  .fehler .zeichen {
    color: var(--rot);
  }
  /* Tools are neither errors nor successes — they are happening right
     now. Their icon (globe & co.) draws itself as long as they run. */
  .werkzeug .zeichen {
    color: var(--blau);
  }
  .text {
    flex: 1;
    min-width: 0;
    overflow-wrap: anywhere;
    /* Errors may carry the painter's raw log below the sentence — the
       line breaks of that log are meaning, so they stay. */
    white-space: pre-line;
  }
  .zu {
    flex: none;
    border: none;
    background: none;
    color: var(--text-still);
    cursor: pointer;
    padding: 1px 3px;
    border-radius: 5px;
    margin: -1px -4px 0 2px;
  }
  .zu:hover {
    background: var(--linie);
    color: var(--text);
  }
</style>
