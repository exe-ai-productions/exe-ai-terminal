<script module>
  /* All selection rows know each other: when one opens its menu, the
     others close. Necessary because the opening
     click stops the event — the other rows would never get to see it,
     and two open menus would stand on top of each other. */
  const alleOffenen = new Set()

  function andereSchliessen(ausser) {
    for (const schliesser of [...alleOffenen]) {
      if (schliesser !== ausser) schliesser()
    }
  }
</script>

<script>
  /* A quiet selection row — same construction as the model picker in
     the input bar: no frame, just the name and a
     chevron, and a dropdown with a check before the chosen one.

     Extracted so the job dialog and the input bar don't maintain the
     same behavior twice. Modellwahl.svelte stays independent for now: it
     hangs off `zustand.modellId` and has its own size variant for the
     empty chat.

     The menu deliberately hangs off nothing (`position: fixed`, location
     via script): that way no `overflow: hidden` clips it, and with
     little room it flips downward by itself.

     **What goes in here are the server's answers, raw.** No renaming, no
     intermediate list: `name` is displayed, below it `quelle` if the
     server reports one; `id` serves as the key, otherwise the name. That
     way every user sees what their own setup reports — and there is no
     second place that would have to be maintained. */
  let {
    wert = $bindable(''),
    eintraege = [],
    leerText = '',
    beschriftung = '',
    // Centered in the empty chat: quieter and a bit smaller, so the row
    // falls in line instead of offering itself.
    klein = false,
    /* In the header, the button sits at the right edge — then the menu
       aligns to its right edge instead of the left. */
    rechts = false,
    /* How wide the row may become. In the input bar a third — the name
       should show what function this is, not occupy half the field. In
       the dialog it may take more room. */
    maxBreite = '60%',
    /* Framed instead of bare: in the sidebar foot the
       picker stands next to the collapse toggle, and the two have to look
       like a pair — same height, same line width, same radius. Everywhere
       else the button stays quiet and borderless. */
    /* Whoever wants not just to notice the choice but to record it
       themselves (the input bar remembers it in device storage) gets it
       reported here — instead of mirroring the value back and forth. */
    onwahl = null,
  } = $props()

  let offen = $state(false)
  let knopf = $state(null)
  let menue = $state(null)
  let ort = $state({ oben: 0, links: 0, nachUnten: false })

  /* Models bring an `id` along, agents don't — there the name is the
     key. Both come from the API this way and are not rewritten here. */
  const kennung = (eintrag) => eintrag.id ?? eintrag.name

  const gewaehlt = $derived(eintraege.find((e) => kennung(e) === wert) || null)

  const schliesser = () => (offen = false)

  $effect(() => {
    alleOffenen.add(schliesser)
    return () => alleOffenen.delete(schliesser)
  })

  function schalten(ereignis) {
    ereignis.stopPropagation()
    if (!eintraege.length) return
    if (!offen) andereSchliessen(schliesser)
    offen = !offen
    if (offen) queueMicrotask(ausrichten)
  }

  /* Measure first, then set: the height is only known once the menu
     already hangs in the tree. If it doesn't fit upward, it unfolds
     downward. */
  function ausrichten() {
    if (!knopf || !menue) return
    const r = knopf.getBoundingClientRect()
    const h = menue.offsetHeight
    const nachUnten = r.top - 12 < h
    const links = rechts
      ? Math.max(16, r.right - menue.offsetWidth)
      : Math.max(16, Math.min(r.left, window.innerWidth - menue.offsetWidth - 16))
    ort = { oben: nachUnten ? r.bottom + 8 : r.top - 8 - h, links, nachUnten }
  }

  function waehlen(id) {
    offen = false
    wert = id
    onwahl?.(id)
  }
</script>

<svelte:window
  onclick={() => (offen = false)}
  onresize={() => (offen = false)}
  onkeydown={(e) => { if (e.key === 'Escape' && offen) { e.stopPropagation(); offen = false } }}
/>

<button
  bind:this={knopf}
  class="stillknopf"
  class:klein
  class:offen
  onclick={schalten}
  title={gewaehlt?.name ?? ''}
  style="max-width:{maxBreite}"
  aria-label={beschriftung}
  aria-haspopup="listbox"
  aria-expanded={offen}
>
  <span class="name">{gewaehlt?.name ?? leerText}</span>
  <svg class="winkel" width="10" height="10" viewBox="0 0 24 24"
       fill="none" stroke="currentColor" stroke-width="2.6"
       stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M6 15l6-6 6 6" />
  </svg>
</button>

{#if offen}
  <div
    bind:this={menue}
    class="klapp"
    class:nachunten={ort.nachUnten}
    class:rechts
    role="listbox"
    tabindex="-1"
    style="top:{ort.oben}px; left:{ort.links}px"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => { if (e.key === 'Escape') offen = false }}
  >
    <div class="liste">
      {#if !eintraege.length}
        <p class="keins">{leerText}</p>
      {/if}
      {#each eintraege as eintrag (kennung(eintrag))}
        <button
          role="option"
          aria-selected={kennung(eintrag) === wert}
          onclick={() => waehlen(kennung(eintrag))}
        >
          <span class="haken">
            {#if kennung(eintrag) === wert}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 12.5 L9.5 18 L20 6.5" />
              </svg>
            {/if}
          </span>
          <span class="zeile">
            <span class="voll">{eintrag.name}</span>
            {#if eintrag.quelle}<span class="quelle">{eintrag.quelle}</span>{/if}
          </span>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .stillknopf {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    padding: 5px 9px;
    border-radius: 999px;
    cursor: default;
    transition: background 0.14s, color 0.14s;
  }
  .stillknopf:hover,
  .stillknopf.offen {
    background: var(--linie);
    color: var(--text);
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .winkel {
    flex: none;
    transition: transform 0.22s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .stillknopf.offen .winkel {
    transform: rotate(180deg);
  }
  /* Centered in the empty chat: color of the context indicator, so it
     falls in line instead of offering itself. */
  .stillknopf.klein {
    color: var(--text-still);
    font-size: 12px;
  }
  .stillknopf.klein:hover,
  .stillknopf.klein.offen {
    color: var(--text-leise);
  }

  .klapp {
    position: fixed;
    z-index: 80;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    /* 12 — it is a surface, and the palette gives surfaces 12. */
    border-radius: 12px;
    padding: 5px;
    width: 320px;
    max-width: calc(100vw - 32px);
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.18);
    animation: aufgehen 0.22s cubic-bezier(0.2, 0.9, 0.3, 1);
    transform-origin: bottom left;
  }
  .klapp.nachunten {
    transform-origin: top left;
    animation-name: aufgehen-unten;
  }
  .klapp.rechts { transform-origin: bottom right; }
  .klapp.nachunten.rechts { transform-origin: top right; }
  @keyframes aufgehen {
    from { opacity: 0; transform: translateY(6px) scale(0.97); }
  }
  @keyframes aufgehen-unten {
    from { opacity: 0; transform: translateY(-6px) scale(0.97); }
  }

  .liste {
    max-height: 300px;
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    scrollbar-color: var(--linie-stark) transparent;
  }
  .liste::-webkit-scrollbar { width: 10px; }
  .liste::-webkit-scrollbar-track { background: transparent; }
  .liste::-webkit-scrollbar-thumb {
    background-color: var(--linie-stark);
    background-clip: padding-box;
    border: 3px solid transparent;
    border-radius: 999px;
  }
  .liste::-webkit-scrollbar-thumb:hover { background-color: var(--text-still); }

  .klapp button {
    display: flex;
    align-items: center;
    gap: 9px;
    width: 100%;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    text-align: left;
    padding: 8px 10px 8px 7px;
    border-radius: 9px;
    cursor: default;
    transition: background 0.12s;
  }
  .klapp button:hover { background: var(--linie); }
  .haken {
    width: 14px;
    flex: none;
    display: grid;
    place-items: center;
    color: var(--text-leise);
  }
  .zeile {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .voll {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .quelle {
    font-size: 11.5px;
    color: var(--text-still);
  }
  .keins {
    margin: 0;
    padding: 8px 10px;
    font-size: 13px;
    color: var(--text-still);
  }

  @media (prefers-reduced-motion: reduce) {
    .klapp { animation: none; }
    .winkel { transition: none; }
  }
</style>
