<script>
  /* The CLI module: history above, one input line pinned at the bottom.

     That input line is the whole reason this exists as a panel and not as a
     separate program: framed, always in the same place, with a block cursor
     that says where typing lands. The terminal-in-a-terminal version had it
     floating, and nobody could tell whether it was listening. */
  import { ansiZuHtml } from '../lib/ansi.js'
  import { cli, ausfuehren, zeilenVon } from '../lib/cli.svelte.js'
  import { hervorheben } from '../lib/einfaerben.js'
  import { rollfade } from '../lib/rollfade.js'
  import { t } from '../lib/texte.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'

  const chatId = $derived(zustand.aktiverChat)
  const zeilen = $derived(zeilenVon(chatId))

  let eingabe = $state('')
  let feld = $state(null)
  let spur = $state(null)
  /* Where the arrow keys currently stand in the history. -1 means: at the
     line being typed, not in the past. */
  let stelle = $state(-1)

  $effect(() => {
    const _ = zeilen.length
    if (spur) spur.scrollTop = spur.scrollHeight
  })

  async function abschicken() {
    const text = eingabe
    eingabe = ''
    stelle = -1
    await ausfuehren(chatId, text)
  }

  function taste(ereignis) {
    if (ereignis.key === 'Enter') {
      ereignis.preventDefault()
      abschicken()
      return
    }
    if (ereignis.key === 'ArrowUp') {
      if (!cli.verlauf.length) return
      ereignis.preventDefault()
      stelle = stelle < 0 ? cli.verlauf.length - 1 : Math.max(0, stelle - 1)
      eingabe = cli.verlauf[stelle]
      return
    }
    if (ereignis.key === 'ArrowDown') {
      if (stelle < 0) return
      ereignis.preventDefault()
      stelle += 1
      if (stelle >= cli.verlauf.length) {
        stelle = -1
        eingabe = ''
      } else {
        eingabe = cli.verlauf[stelle]
      }
    }
  }
</script>

<div class="cli">
  <div class="verlauf" bind:this={spur} use:rollfade>
    {#if !zeilen.length}
      <p class="leer">{t('cli.leer')}</p>
    {/if}
    {#each zeilen as zeile, i (i)}
      {#if zeile.art === 'eingabe'}
        <div class="zeile ich">&gt; {@html hervorheben(zeile.text, 'bash')}</div>
      {:else if zeile.art === 'fehler'}
        <div class="zeile fehler">{zeile.text}</div>
      {:else}
        <div class="zeile">{@html ansiZuHtml(zeile.text)}</div>
      {/if}
    {/each}
  </div>

  <!-- svelte-ignore a11y_autofocus -->
  <div class="eingabe" onclick={() => feld?.focus()} role="presentation">
    <span class="prompt">&gt;</span>
    <input
      bind:this={feld}
      bind:value={eingabe}
      onkeydown={taste}
      placeholder={t('cli.platzhalter')}
      aria-label={t('cli.titel')}
      spellcheck="false"
      autocomplete="off"
    />
    {#if cli.laeuft}<span class="cursor"></span>{/if}
  </div>
</div>

<style>
  .cli {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    font-family: var(--schrift-fest);
    font-size: 11.5px;
  }
  .verlauf {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 12px 14px;
    line-height: 1.7;
    color: var(--text-leise);
  }
  .leer { margin: 0; color: var(--text-still); }
  .zeile {
    white-space: pre-wrap;
    word-break: break-word;
  }
  .zeile.ich { color: var(--text); }
  .zeile.fehler { color: var(--rot); }

  /* Framed and pinned: the one control in this panel, always in the same
     place. */
  .eingabe {
    flex: none;
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 10px 12px 12px;
    padding: 8px 11px;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    color: var(--text);
    cursor: text;
  }
  .prompt { color: var(--text-still); }
  input {
    flex: 1;
    min-width: 0;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    outline: none;
  }
  input::placeholder { color: var(--text-still); }
  .cursor {
    display: inline-block;
    width: 7px;
    height: 13px;
    background: var(--text);
    animation: blinken 1.1s steps(1) infinite;
  }
  @keyframes blinken { 50% { opacity: 0; } }
</style>
