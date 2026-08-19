<script>
  /* One choice out of many, in the space of a single control.

     A row of buttons shows every option at once, which is the right shape
     for two or three of them. Beyond that the row grows past the tile it
     sits in and pushes itself over the label next to it — and the list of
     skins is meant to grow. This keeps the width of one button no matter
     how long the list gets.

     Not a native <select>: its list is drawn by the operating system and
     carries none of the house tokens, so the window would show a grey
     system menu in the middle of a themed dialog. */

  let {
    optionen = [],           // [[wert, beschriftung], …] — beschriftung already translated
    wert = $bindable(null),
    beschriftung = '',       // what the control is called, for screen readers
  } = $props()

  let offen = $state(false)
  let knopf = $state(null)
  let liste = $state(null)

  const jetzige = $derived(optionen.find(([w]) => w === wert))
  const jetzigerText = $derived(jetzige ? jetzige[1] : '')

  function waehlen(neu) {
    wert = neu
    offen = false
    knopf?.focus()
  }

  function umschalten() {
    offen = !offen
  }

  /* The keys people expect from a menu: arrows walk it, Enter and Space take
     what is under the cursor, Escape leaves without changing anything. */
  function taste(ereignis) {
    if (ereignis.key === 'Escape') {
      offen = false
      knopf?.focus()
      return
    }
    if (!offen && (ereignis.key === 'ArrowDown' || ereignis.key === 'ArrowUp')) {
      offen = true
      ereignis.preventDefault()
      return
    }
    if (!offen) return

    const stelle = optionen.findIndex(([w]) => w === wert)
    if (ereignis.key === 'ArrowDown') {
      ereignis.preventDefault()
      waehlenOhneSchliessen(stelle + 1)
    } else if (ereignis.key === 'ArrowUp') {
      ereignis.preventDefault()
      waehlenOhneSchliessen(stelle - 1)
    } else if (ereignis.key === 'Enter' || ereignis.key === ' ') {
      ereignis.preventDefault()
      offen = false
      knopf?.focus()
    }
  }

  function waehlenOhneSchliessen(stelle) {
    if (stelle < 0 || stelle >= optionen.length) return
    wert = optionen[stelle][0]
  }

  /* A click anywhere else closes the list — the same thing every menu does,
     and without it the list would stay open behind the next window. */
  function daneben(ereignis) {
    if (!offen) return
    if (knopf?.contains(ereignis.target) || liste?.contains(ereignis.target)) return
    offen = false
  }
</script>

<svelte:window onclick={daneben} />

<div class="klappwahl">
  <button
    bind:this={knopf}
    class="knopf"
    class:offen
    aria-haspopup="listbox"
    aria-expanded={offen}
    aria-label={beschriftung}
    onclick={umschalten}
    onkeydown={taste}
  >
    <span class="text">{jetzigerText}</span>
    <svg class="pfeil" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M6 9l6 6 6-6" />
    </svg>
  </button>

  {#if offen}
    <div bind:this={liste} class="liste" role="listbox" tabindex="-1" aria-label={beschriftung} onkeydown={taste}>
      {#each optionen as [w, text] (w)}
        <button
          class="eintrag"
          role="option"
          aria-selected={w === wert}
          onclick={() => waehlen(w)}
        >
          <span class="haken" aria-hidden="true">
            {#if w === wert}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5" /></svg>
            {/if}
          </span>
          {text}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .klappwahl { position: relative; flex: none; }

  .knopf {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 116px;
    border: 1px solid var(--linie);
    border-radius: 9px;
    background: var(--bg-erhoben);
    color: var(--text);
    font: 600 11.5px var(--schrift);
    padding: 6px 10px;
    cursor: pointer;
    text-align: left;
  }
  .knopf:hover { border-color: var(--linie-stark); }
  .knopf.offen { border-color: var(--kontrast, var(--linie-stark)); }
  .text { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pfeil { flex: none; color: var(--text-still); transition: transform 0.16s ease; }
  .knopf.offen .pfeil { transform: rotate(180deg); }

  /* Opens upward as well as downward would need measuring; the tiles this
     sits in are near the top of their window, so downward is enough and
     keeps the control honest about where its list appears. */
  .liste {
    position: absolute;
    top: calc(100% + 5px);
    right: 0;
    z-index: 10;
    min-width: 100%;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg-erhoben);
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.4);
    padding: 4px;
    max-height: 232px;
    overflow-y: auto;
    scrollbar-width: none;
  }
  .liste::-webkit-scrollbar { display: none; }

  .eintrag {
    display: flex;
    align-items: center;
    gap: 7px;
    width: 100%;
    border: none;
    border-radius: 7px;
    background: none;
    color: var(--text-still);
    font: 600 11.5px var(--schrift);
    padding: 6px 9px;
    cursor: pointer;
    text-align: left;
    white-space: nowrap;
  }
  .eintrag:hover { background: var(--bg); color: var(--text); }
  .eintrag[aria-selected='true'] { background: var(--bg); color: var(--text); }
  .haken { flex: none; width: 12px; display: grid; place-items: center; color: var(--text); }

  @media (prefers-reduced-motion: reduce) {
    .pfeil { transition: none; }
  }
</style>
