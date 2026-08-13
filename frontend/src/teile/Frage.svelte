<script>
  /* The house's prompt dialog: replaces the bare
     confirm()/prompt() boxes of the browser — those were the last
     foreign body in the interface.

     Two shapes, one component: question only (yes/no) or question with
     an input field (renaming). Answering runs through frageBeantworten —
     that resolves the promise from zustand.frage(). Escape and a click
     on the veil mean no, Enter means yes.

     Lies ABOVE the windows (z-index 80 against their 70): most prompts
     arise in the middle of the settings window. */
  import { fade, scale } from 'svelte/transition'
  import { zustand, frageBeantworten } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  let eingabefeld = $state(null)
  let okKnopf = $state(null)
  let wert = $state('')

  const mitEingabe = $derived(zustand.frage?.eingabe != null)

  $effect(() => {
    if (!zustand.frage) return
    wert = zustand.frage.eingabe ?? ''
    // Focus where the answer comes into being: into the field or onto the yes.
    setTimeout(() => (eingabefeld ?? okKnopf)?.focus(), 40)
  })

  function ja() {
    frageBeantworten(mitEingabe ? wert : true)
  }
  function nein() {
    frageBeantworten(mitEingabe ? null : false)
  }
  function taste(ereignis) {
    if (ereignis.key === 'Enter') {
      ereignis.preventDefault()
      ja()
    }
  }
</script>

{#if zustand.frage}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="schleier" transition:fade={{ duration: 120 }} onclick={nein}>
    <div
      class="popup"
      role="alertdialog"
      aria-modal="true"
      aria-label={zustand.frage.text}
      transition:scale={{ start: 0.96, duration: 140 }}
      onclick={(e) => e.stopPropagation()}
    >
      <div class="frage">{zustand.frage.text}</div>
      {#if mitEingabe}
        <input
          class="feld"
          bind:this={eingabefeld}
          bind:value={wert}
          onkeydown={taste}
          spellcheck="false"
        />
      {/if}
      <div class="knoepfe">
        <button class="knopf" onclick={nein}>{t('app.abbrechen')}</button>
        <button class="knopf wichtig" bind:this={okKnopf} onclick={ja}>
          {t(zustand.frage.okSchluessel)}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .schleier {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 80;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 22vh 16px 0;
  }
  .popup {
    background: var(--bg-erhoben);
    border-radius: 16px;
    padding: 16px 18px 14px;
    width: min(400px, 92vw);
    /* The house's outer window frame — the notifications' vector stroke,
       a 2px ring hung off var(--text). Same frame the main windows wear. */
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--text) 70%, transparent),
      0 18px 48px rgba(0, 0, 0, 0.25);
  }
  .frage {
    font-size: 13.5px;
    line-height: 1.55;
  }
  .feld {
    width: 100%;
    margin-top: 12px;
    font: inherit;
    font-size: 13px;
    color: var(--text);
    background: var(--bg-seite);
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 7px 10px;
  }
  .knoepfe {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 14px;
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 7px 15px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s, transform 0.08s;
  }
  .knopf:hover {
    background: var(--linie);
  }
  .knopf:active {
    transform: scale(0.975);
  }
  .wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .wichtig:hover {
    background: var(--text);
    opacity: 0.88;
  }
</style>
