<script module>
  /* Only one list stands open in the whole program. Shared by every
     instance, so opening one closes whatever was open before it — the job
     the window click would do if the fields did not have to swallow their
     own opening click. */
  let offener = null
</script>

<script>
  /* The house's one selection field.

     It replaces the browser's `<select>` everywhere a form asks a question
     with a fixed set of answers, and it exists for two reasons the native
     control could not give:

     * **One measure.** Three windows styled their own selects and drifted:
       11.5px here, 13.5px there, different padding again. A field is a
       field — the numbers live here once, and every form that uses this
       component is the same height without anybody measuring.
     * **It opens downward.** A native select on this platform drops its
       list OVER the field, so the thing you just clicked disappears under
       its own menu. Reading a list while the question is hidden is the
       wrong way round; here the question stays put and the answers appear
       beneath it.

     `eintraege` is a list of `{ wert, text }`. The caller decides what a
     value is called; this component only draws it. */
  import { rollfade } from '../lib/rollfade.js'

  let {
    wert = $bindable(''),
    eintraege = [],
    gesperrt = false,
    id = undefined,
    beschriftung = '',
    leerText = '',
    gewaehlt: onGewaehlt = null,
  } = $props()

  let offen = $state(false)
  let dran = $state(-1)
  let feld = $state(null)
  let liste = $state(null)

  /* Every field stops the click that opens it, so the window handler that
     closes the others never hears it — two lists could stand open at once,
     both claiming to be the answer to their own question. Rather than let
     the click through (it would close this one again in the same breath),
     the open field says so here and the next one to open closes it. */
  let schliesserAbmelden = null

  const kennung = `auswahl-${Math.random().toString(36).slice(2, 9)}`
  const aktuell = $derived(eintraege.find((e) => e.wert === wert) ?? null)
  const text = $derived(aktuell?.text ?? leerText)

  function oeffnen() {
    offener?.()
    offen = true
    offener = zumachen
    schliesserAbmelden = zumachen
    /* Opening lands on what is chosen, so the arrow keys carry on from
       there instead of from the top of a list somebody already answered. */
    dran = Math.max(0, eintraege.findIndex((e) => e.wert === wert))
  }

  function zumachen() {
    offen = false
    dran = -1
    if (offener === schliesserAbmelden) offener = null
  }

  function schalten(ereignis) {
    ereignis.stopPropagation()
    if (gesperrt || !eintraege.length) return
    if (offen) zumachen()
    else oeffnen()
  }

  function waehlen(neu) {
    zumachen()
    /* Back to the field. A native select never leaves the focus on nothing;
       losing it here would drop the caller out of the form and make the next
       Tab start over from the top of the page. */
    feld?.focus()
    if (neu === wert) return
    wert = neu
    onGewaehlt?.(neu)
  }

  /* The walked-to entry is scrolled into view. Without this the list moves
     the highlight below its own edge from about the eighth entry on, and
     everything after that is chosen blind. */
  $effect(() => {
    if (!offen || dran < 0 || !liste) return
    liste.children[dran]?.scrollIntoView({ block: 'nearest' })
  })

  $effect(() => () => {
    if (offener === schliesserAbmelden) offener = null
  })

  /* Typing a letter jumps to the entry that starts with it, the way the
     native control does. On a list of model files that is the difference
     between finding one and scrolling for it. The buffer resets after a
     pause, so "ge" finds "gemma" and a later "g" starts again. */
  let getippt = ''
  let tippUhr = null

  function tippsuche(zeichen) {
    clearTimeout(tippUhr)
    getippt += zeichen.toLowerCase()
    tippUhr = setTimeout(() => (getippt = ''), 700)
    const ab = offen ? dran : eintraege.findIndex((e) => e.wert === wert)
    const treffer = eintraege.findIndex((e) => (e.text ?? '').toLowerCase().startsWith(getippt))
    if (treffer < 0) return
    if (offen) dran = treffer
    else if (treffer !== ab) waehlen(eintraege[treffer].wert)
  }

  /* The keyboard walks the list without opening it, the same way the native
     control did — losing that would make the field worse than what it
     replaces. */
  function tasten(ereignis) {
    if (gesperrt || !eintraege.length) return
    const { key } = ereignis
    if (key === 'Escape' && offen) {
      ereignis.stopPropagation()
      zumachen()
      return
    }
    if (key === 'ArrowDown' || key === 'ArrowUp') {
      ereignis.preventDefault()
      const richtung = key === 'ArrowDown' ? 1 : -1
      if (!offen) {
        const jetzt = eintraege.findIndex((e) => e.wert === wert)
        const naechster = Math.min(eintraege.length - 1, Math.max(0, jetzt + richtung))
        waehlen(eintraege[naechster].wert)
        return
      }
      dran = Math.min(eintraege.length - 1, Math.max(0, dran + richtung))
      return
    }
    if (key === 'Home' || key === 'End') {
      ereignis.preventDefault()
      const ziel = key === 'Home' ? 0 : eintraege.length - 1
      if (offen) dran = ziel
      else waehlen(eintraege[ziel].wert)
      return
    }
    if ((key === 'Enter' || key === ' ') && offen) {
      ereignis.preventDefault()
      if (dran >= 0) waehlen(eintraege[dran].wert)
      return
    }
    /* Enter or Space on a shut field opens it — the native control does the
       same, and without it the keyboard can only ever step one entry at a
       time without seeing the list. */
    if ((key === 'Enter' || key === ' ') && !offen) {
      ereignis.preventDefault()
      oeffnen()
      return
    }
    if (key.length === 1 && !ereignis.metaKey && !ereignis.ctrlKey && !ereignis.altKey) {
      ereignis.preventDefault()
      tippsuche(key)
    }
  }
</script>

<svelte:window onclick={zumachen} onresize={zumachen} />

<div class="feldplatz">
  <button
    bind:this={feld}
    {id}
    type="button"
    class="feld"
    class:offen
    class:gesperrt
    role="combobox"
    aria-haspopup="listbox"
    aria-expanded={offen}
    aria-controls={offen ? `${kennung}-liste` : undefined}
    aria-label={beschriftung || undefined}
    aria-activedescendant={offen && dran >= 0 ? `${kennung}-${dran}` : undefined}
    disabled={gesperrt}
    onclick={schalten}
    onkeydown={tasten}
  >
    <span class="text">{text}</span>
    <svg class="winkel" width="11" height="11" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2.6" stroke-linecap="round"
         stroke-linejoin="round" aria-hidden="true">
      <path d="M6 9l6 6 6-6" />
    </svg>
  </button>

  {#if offen}
    <div
      class="klapp"
      id="{kennung}-liste"
      role="listbox"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <div class="liste" bind:this={liste} use:rollfade>
        <!-- tabindex="-1" is deliberate: the field is the one tab stop and
             the arrow keys walk from there. Tabbable entries let Tab fall
             into the open list, where Escape and the arrows are no longer
             heard and the list stays open with nothing driving it. -->
        {#each eintraege as eintrag, i (eintrag.wert)}
          <button
            type="button"
            role="option"
            id="{kennung}-{i}"
            tabindex="-1"
            class:dran={i === dran}
            aria-selected={eintrag.wert === wert}
            onclick={() => waehlen(eintrag.wert)}
            onmouseenter={() => (dran = i)}
          >
            <span class="haken">
              {#if eintrag.wert === wert}
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 12.5 L9.5 18 L20 6.5" />
                </svg>
              {/if}
            </span>
            <span class="zeile">{eintrag.text}</span>
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  /* The anchor the list hangs under. Relative and nothing else — the field
     keeps its own place in whatever form it stands in. */
  .feldplatz {
    position: relative;
    min-width: 0;
  }

  /* THE measure. Every selection field in the house is this. */
  .feld {
    width: 100%;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 8px;
    font: inherit;
    font-size: 13.5px;
    line-height: 1.3;
    color: var(--text);
    background: var(--bg-leiste);
    border: 1px solid var(--linie);
    border-radius: 9px;
    padding: 8px 10px;
    cursor: pointer;
    text-align: left;
  }
  .feld:hover:not(.gesperrt) {
    border-color: var(--linie-stark);
  }
  .feld.offen {
    border-color: var(--linie-stark);
  }
  .feld.gesperrt {
    opacity: 0.6;
    cursor: default;
  }
  .text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .winkel {
    flex: none;
    color: var(--text-still);
    transition: transform 0.15s;
  }
  .feld.offen .winkel {
    transform: rotate(180deg);
  }

  /* Always beneath the field, never over it. */
  .klapp {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    right: 0;
    z-index: 40;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
    overflow: hidden;
  }
  .liste {
    max-height: 260px;
    overflow-y: auto;
    padding: 4px;
  }
  .liste button {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 7px;
    font: inherit;
    font-size: 13px;
    color: var(--text);
    background: none;
    border: none;
    border-radius: 7px;
    padding: 7px 8px;
    cursor: pointer;
    text-align: left;
  }
  .liste button.dran {
    background: var(--linie);
  }
  .haken {
    flex: none;
    width: 12px;
    display: inline-flex;
    color: var(--text-leise);
  }
  .zeile {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  @media (prefers-reduced-motion: reduce) {
    .winkel { transition: none; }
  }
</style>
