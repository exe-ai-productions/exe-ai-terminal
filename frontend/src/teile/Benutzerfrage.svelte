<script>
  /* The model's question to the user (ask_user).

     It hangs where the tool confirmation hangs — right above the input
     field, exactly as wide. Buttons inside the message were the obvious
     alternative and were dropped: a message scrolls away, and the buttons
     in it stay behind as controls that do nothing.

     Whoever does not want any of the options simply types. The input field
     right below is the fourth answer, always. */
  import { fly } from 'svelte/transition'
  import { backOut, cubicIn } from 'svelte/easing'
  import { t } from '../lib/texte.svelte.js'

  let { frage, antworten } = $props()
</script>

<div
  class="frage"
  role="group"
  aria-label={frage.frage}
  in:fly={{ y: 14, duration: 300, easing: backOut }}
  out:fly={{ y: 8, duration: 160, easing: cubicIn }}
>
  <p class="text">{frage.frage}</p>

  {#if frage.optionen?.length}
    <div class="optionen">
      {#each frage.optionen as option (option.label)}
        <button class="option" onclick={() => antworten(option.label)}>
          <span class="beschriftung">{option.label}</span>
          {#if option.description}
            <span class="satz">{option.description}</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}

  <p class="hinweis">{t('benutzerfrage.frei')}</p>
</div>

<style>
  /* Same frame as the tool confirmation: one shape for everything that
     hangs above the field. */
  .frage {
    width: 100%;
    border: 1px solid var(--text-leise);
    border-radius: 18px;
    background: var(--bg-erhoben);
    padding: 12px 13px 10px;
  }
  .text {
    margin: 0 0 10px;
    font-size: 13.5px;
    color: var(--text);
    line-height: 1.5;
  }
  .optionen {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
  }
  /* One group, one size: every option is the same height, whatever it
     says. The recommended one comes first because the model was told to
     put it there — nothing here re-sorts them. */
  .option {
    flex: 1 1 auto;
    min-width: 140px;
    min-height: 40px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    text-align: left;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg);
    color: var(--text);
    font: inherit;
    padding: 7px 11px;
    cursor: pointer;
    transition: background 0.14s, border-color 0.14s;
  }
  .option:hover {
    background: var(--linie);
    border-color: var(--text-leise);
  }
  .beschriftung {
    font-size: 13px;
  }
  .satz {
    font-size: 11.5px;
    color: var(--text-still);
    line-height: 1.4;
  }
  .hinweis {
    margin: 9px 2px 0;
    font-size: 11.5px;
    color: var(--text-still);
  }
</style>
