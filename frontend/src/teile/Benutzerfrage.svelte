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

  /* The own answer, written right here. The main input field below still
     counts as an answer too — this field only makes the offer visible:
     an affordance one can type into beats a sentence saying one could. */
  let eigene = $state('')

  function eigeneSenden() {
    const wert = eigene.trim()
    if (!wert) return
    eigene = ''
    antworten(wert)
  }
</script>

<div
  class="frage"
  role="group"
  aria-label={frage.frage}
  in:fly={{ y: 14, duration: 300, easing: backOut }}
  out:fly={{ y: 8, duration: 160, easing: cubicIn }}
>
  <div class="kopfzeile">
    <p class="text">{frage.frage}</p>
    {#if frage.nummer}
      <!-- Which question of this run this is. No "of N" — the model does
           not know its total in advance, and a guessed total would lie. -->
      <span class="zaehler">{t('benutzerfrage.nummer', { zahl: frage.nummer })}</span>
    {/if}
  </div>

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

  <div class="eigene">
    <input
      class="eigenesfeld"
      bind:value={eigene}
      placeholder={t('benutzerfrage.eigene_platzhalter')}
      aria-label={t('benutzerfrage.frei')}
      onkeydown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          eigeneSenden()
        }
      }}
    />
    <button
      class="eigenesenden"
      disabled={!eigene.trim()}
      onclick={eigeneSenden}
      aria-label={t('benutzerfrage.eigene_senden')}
      title={t('benutzerfrage.eigene_senden')}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    </button>
  </div>
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
  .kopfzeile {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }
  .text {
    margin: 0 0 10px;
    font-size: 13.5px;
    color: var(--text);
    line-height: 1.5;
    min-width: 0;
    flex: 1;
  }
  /* The question count, top right — a quiet fact, so brightness only. */
  .zaehler {
    flex: none;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 1.5px 9px;
    font-size: 11px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text-still);
    white-space: nowrap;
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
  /* The own answer as a real field, not a sentence about one. */
  .eigene {
    display: flex;
    align-items: center;
    gap: 7px;
    margin-top: 9px;
  }
  .eigenesfeld {
    flex: 1;
    min-width: 0;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg);
    color: var(--text);
    font: inherit;
    font-size: 12.5px;
    padding: 6px 11px;
    outline: none;
    transition: border-color 0.14s;
  }
  .eigenesfeld:focus {
    border-color: var(--text-leise);
  }
  .eigenesfeld::placeholder {
    color: var(--text-still);
  }
  .eigenesenden {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    background: var(--bg);
    color: var(--text);
    cursor: pointer;
    transition: background 0.14s, border-color 0.14s, opacity 0.14s;
  }
  .eigenesenden:hover:not(:disabled) {
    background: var(--linie);
    border-color: var(--text-leise);
  }
  .eigenesenden:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
