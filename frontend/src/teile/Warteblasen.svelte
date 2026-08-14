<script>
  /* The queued messages, shown where they will land: at the end of the
     history, below the running answer.

     They wear the user's bubble, but quietly — dimmed and outlined
     instead of filled. That difference is the whole message of the thing:
     what stands here has been typed but not yet said, and it must not be
     mistaken for something already in the conversation.

     A held queue says so at every bubble it holds, not only at the first —
     whoever scrolls in from below should not have to look for the reason. */
  import { t } from '../lib/texte.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'
  import { entfernen, fuerChat } from '../lib/warteschlange.svelte.js'

  let { losschicken } = $props()

  const wartende = $derived(fuerChat(zustand.aktiverChat))
</script>

{#each wartende as eintrag (eintrag.id)}
  <div class="wartet" class:haelt={eintrag.haelt}>
    <div class="zeile">
      <svg class="sanduhr" width="13" height="13" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
           aria-hidden="true">
        <path d="M6 3h12M6 21h12M8 3v4l4 5 4-5V3M8 21v-4l4-5 4 5v4" />
      </svg>
      <span class="marke">{eintrag.haelt ? t('warteschlange.haelt') : t('warteschlange.wartet')}</span>
      {#if eintrag.haelt}
        <button class="weiter" onclick={() => losschicken(eintrag)}>
          {t('warteschlange.jetzt_senden')}
        </button>
      {/if}
      <button
        class="weg"
        title={t('warteschlange.entfernen')}
        aria-label={t('warteschlange.entfernen')}
        onclick={() => entfernen(eintrag.id)}
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </div>
    {#if eintrag.inhalt}
      <div class="text">{eintrag.inhalt}</div>
    {/if}
    {#if eintrag.bild || eintrag.dokument}
      <div class="anhang">{eintrag.bild?.name || eintrag.dokument?.name}</div>
    {/if}
  </div>
{/each}

<style>
  .wartet {
    align-self: flex-end;
    max-width: 76%;
    min-width: 0;
    border-radius: 16px;
    padding: 8px 15px 10px;
    /* Outline instead of a filled ground: a bubble that is not yet part of
       the conversation should not look like one that is. */
    box-shadow: inset 0 0 0 1px var(--linie-stark);
    color: var(--text-still);
    line-height: 1.55;
  }
  .zeile {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 2px;
  }
  .sanduhr {
    flex: none;
    opacity: 0.8;
  }
  .marke {
    font-size: 0.78rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* The hold is a state, so it carries the state colour — a queue that
     stopped is waiting for a decision, which is what yellow says here. */
  .wartet.haelt {
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--gelb) 55%, var(--linie-stark));
  }
  .wartet.haelt .marke {
    color: var(--gelb);
  }
  .text {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .anhang {
    font-size: 0.82rem;
    opacity: 0.75;
    overflow-wrap: anywhere;
  }
  .weiter,
  .weg {
    margin-left: auto;
    background: none;
    border: none;
    padding: 2px 6px;
    border-radius: 9px;
    color: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
  }
  .weiter {
    font-size: 0.78rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  /* Only one of the two may claim the free space, or the ✕ would be
     pushed off the edge whenever the hold notice stands. */
  .weiter + .weg {
    margin-left: 0;
  }
  .weiter:hover,
  .weg:hover {
    background: color-mix(in srgb, var(--text) 10%, transparent);
    color: var(--text);
  }
</style>
