<script>
  /* The window for choosing a working folder.

     Only the mask lives here — the pills are their own view (Ordnerpillen),
     because they appear in two spots, and the logic sits in
     lib/arbeitsordner.svelte.js, because both spots need it. This component
     is mounted exactly once, no matter where the pills currently are.

     Two ways in, because a browser never hands out a real path: the system
     dialog (Finder / Explorer, opened by the service) and the path field.
     The dialog is the comfortable way and brings "New Folder" along; the
     field is the one that works everywhere — in a container, over the
     network, on a machine without a dialog tool. */
  import Fenster from './Fenster.svelte'
  import { t } from '../lib/texte.svelte.js'
  import {
    ordnerZustand, dialogPruefen, ordnerHinzufuegen, systemdialog,
  } from '../lib/arbeitsordner.svelte.js'

  let pfadfeld = $state('')
  let feld = $state(null)

  // Ask once whether this machine has a folder dialog at all. A button that
  // clicks into nothing is worse than no button.
  $effect(() => {
    dialogPruefen()
  })

  // Empty the field each time the window opens, and put the cursor in it.
  $effect(() => {
    if (ordnerZustand.maskeOffen) {
      pfadfeld = ''
      setTimeout(() => feld?.focus(), 80)
    }
  })

  function feldTaste(ereignis) {
    if (ereignis.key === 'Enter') {
      ereignis.preventDefault()
      ordnerHinzufuegen(pfadfeld.trim())
    }
  }
</script>

<Fenster bind:offen={ordnerZustand.maskeOffen} titel={t('arbeitsordner.waehlen')} art="frage">
  <p class="unter">{t('arbeitsordner.erklaerung')}</p>

  {#if ordnerZustand.dialogDa}
    <button class="durchsuchen" onclick={systemdialog} disabled={ordnerZustand.laeuft}>
      <svg width="17" height="17" viewBox="0 0 64 64" fill="none" stroke="currentColor"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M11 50 V14 H27 L32 21 H53 V50 Z" stroke-width="5" />
        <path d="M11 26 H53" stroke-width="4.5" />
      </svg>
      <span>
        {ordnerZustand.laeuft
          ? t('arbeitsordner.dialog_laeuft')
          : t('arbeitsordner.durchsuchen')}
      </span>
    </button>
    <div class="oder"><span>{t('arbeitsordner.oder')}</span></div>
  {/if}

  <input
    class="pfadfeld"
    bind:this={feld}
    bind:value={pfadfeld}
    onkeydown={feldTaste}
    placeholder={t('arbeitsordner.pfad_platzhalter')}
    aria-label={t('arbeitsordner.pfad_platzhalter')}
    spellcheck="false"
  />
  <p class="hilfe">{t('arbeitsordner.pfad_hilfe')}</p>

  <div class="knopfreihe">
    <button class="knopf" onclick={() => (ordnerZustand.maskeOffen = false)}>
      {t('app.abbrechen')}
    </button>
    <button class="knopf stark" disabled={!pfadfeld.trim()}
            onclick={() => ordnerHinzufuegen(pfadfeld.trim())}>
      {t('arbeitsordner.setzen')}
    </button>
  </div>
</Fenster>

<style>
  .unter {
    font-size: 12.5px;
    color: var(--text-still);
    margin: 0 0 14px;
    line-height: 1.5;
  }
  .durchsuchen {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 9px;
    width: 100%;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13.5px;
    padding: 10px 14px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }
  .durchsuchen:hover {
    background: var(--linie);
    border-color: var(--text-still);
  }
  .durchsuchen:disabled {
    opacity: 0.55;
    cursor: default;
  }
  .durchsuchen svg {
    color: var(--text-leise);
    flex: none;
  }
  /* A hairline with the word in the middle — the two ways are equal, one is
     just more comfortable. */
  .oder {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 14px 0;
    color: var(--text-still);
    font-size: 11.5px;
  }
  .oder::before,
  .oder::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--linie);
  }
  .pfadfeld {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg-seite, var(--bg));
    color: var(--text);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
    padding: 9px 11px;
    outline: none;
  }
  .pfadfeld:focus {
    border-color: var(--text-still);
  }
  .hilfe {
    font-size: 11.5px;
    color: var(--text-still);
    margin: 7px 2px 0;
  }
  .knopfreihe {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 18px;
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 7px 14px;
    border-radius: 9px;
    cursor: pointer;
  }
  .knopf:hover {
    background: var(--linie);
  }
  .knopf.stark {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .knopf.stark:hover {
    opacity: 0.88;
  }
  .knopf.stark:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
