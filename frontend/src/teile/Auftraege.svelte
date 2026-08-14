<script>
  import { rollfade } from '../lib/rollfade.js'
  /* The jobs view (6.5, variant A).

     Its own section next to the chats: the sidebar switches over, the
     list stands here. A waiting job gets the yellow banner at the very
     top — waiting for input has to leap out immediately, and the banner
     alone suffices.

     The report of a finished job unfolds right in the card, no separate
     detail view. The log likewise, in the style of the tool rows from
     3.9: one row per step, expandable.

     The start dialog (AuftragStarten.svelte) hangs here, but its button
     sits in the sidebar — where "Neuer Chat" is for the chats.
     That's why its open state lives in the shared state and
     not locally in one of the two components. */
  import { slide } from 'svelte/transition'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { zustand, auftraegeLaden, melde } from '../lib/zustand.svelte.js'
  import AuftragStarten from './AuftragStarten.svelte'
  import Agentenmarke from './Agentenmarke.svelte'
  import AgentenLademarke from './AgentenLademarke.svelte'
  import Werkzeugzeichen from './Werkzeugzeichen.svelte'
  import Wasserzeichen from './Wasserzeichen.svelte'
  import Standpille from './Standpille.svelte'

  /* Colour means state (house rule): blue runs, yellow waits, green is
     done, red failed. Anything else has no state worth a colour. */
  const ZUSTANDSFARBE = {
    laeuft: 'blau', wartet: 'gelb', fertig: 'gruen', gescheitert: 'rot',
  }

  /* The mark stands **permanently** in the background of this section,
     not just while it is empty. It hangs behind the content and doesn't
     scroll along: a watermark that slides away isn't one.

     Only the sentence below it disappears once the first task is there.

     The size is no longer in pixels but at **75% of the section**:
     large enough to carry, small enough to fit in
     entirely — nothing gets clipped, and a strip stays free at the
     bottom where the sentence sits readable. The number therefore lives
     in the styles, not here; `100%` merely passes the mark through to
     its box. */
  const MARKE = '100%'

  const hatAuftraege = $derived(zustand.auftraege.length > 0)

  // Unfolded cards and their lazily loaded logs.
  let offene = $state({})
  let protokolle = $state({})

  const wartende = $derived(zustand.auftraege.filter((a) => a.state === 'wartet'))
  const laufende = $derived(zustand.auftraege.filter((a) => a.state === 'laeuft'))

  /* Reload on a cadence as long as the section is open. Three seconds
     are deliberately leisurely: this is an overview, not a live stream —
     whoever wants to watch a run will get that later via the event
     stream. */
  $effect(() => {
    // With the beta mask over it, the section is dead — then nothing
    // needs reloading either. That saves more than work: on every
    // restart of the service, every failed query otherwise ran into an
    // error message, and the visitor got a salvo of popups for a section
    // they can't operate anyway.
    if (zustand.features?.beta_lock) return
    const uhr = setInterval(nachladen, 3000)
    nachladen()
    return () => clearInterval(uhr)
  })

  async function nachladen() {
    await auftraegeLaden()
    // Unfolded logs of living jobs grow along.
    for (const auftrag of zustand.auftraege) {
      if (offene[auftrag.id] && (auftrag.state === 'laeuft' || protokolle[auftrag.id] === undefined)) {
        protokollLaden(auftrag.id)
      }
    }
  }

  async function protokollLaden(id) {
    try {
      const detail = await api.auftrag(id)
      protokolle[id] = detail.schritte
    } catch {
      /* It works again on the next tick — no toast for an overview. */
    }
  }

  function klappen(id) {
    offene[id] = !offene[id]
    if (offene[id] && protokolle[id] === undefined) protokollLaden(id)
  }

  /* From the click in the sidebar: unfold the card and scroll to it. */
  $effect(() => {
    const id = zustand.auftragAusgewaehlt
    if (!id) return
    zustand.auftragAusgewaehlt = null
    offene[id] = true
    if (protokolle[id] === undefined) protokollLaden(id)
    requestAnimationFrame(() =>
      document.getElementById(`auftrag-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
    )
  })

  async function abbrechen(auftrag) {
    try {
      await api.auftragAbbrechen(auftrag.id)
      melde(t('jobs.abgebrochen'), 'erfolg')
      await auftraegeLaden()
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

  /* The reason is a stable key ('zeitgrenze', …) — translated via the
     catalog. 'fehler: …' carries the error text itself. */
  function grundText(grund) {
    if (!grund) return ''
    if (grund.startsWith('fehler:')) return grund.slice(7).trim()
    const uebersetzt = t(`jobs.grund.${grund}`)
    return uebersetzt.startsWith('jobs.grund.') ? grund : uebersetzt
  }

  function zustandText(state) {
    const uebersetzt = t(`jobs.zustand.${state}`)
    return uebersetzt.startsWith('jobs.zustand.') ? state : uebersetzt
  }

  function zeit(iso) {
    return iso ? iso.slice(11, 16) : ''
  }

  function schrittInhalt(schritt) {
    if (schritt.typ === 'tool_call' || schritt.typ === 'tool_result') {
      try {
        const daten = JSON.parse(schritt.inhalt)
        if (schritt.typ === 'tool_call')
          return `${daten.name} ${JSON.stringify(daten.argumente)}`
        return `${daten.name} → ${daten.text ?? ''}`
      } catch {
        return schritt.inhalt
      }
    }
    return schritt.inhalt
  }

  /* For the tool icon before a tool_call step: the name sits in the
     log's JSON. The log holds history — the icon therefore always stands
     still; drawing happens only in the chat. */
  function schrittWerkzeug(schritt) {
    if (schritt.typ !== 'tool_call') return null
    try {
      return JSON.parse(schritt.inhalt).name
    } catch {
      return null
    }
  }
</script>

<div class="agentenbereich">
  <!-- Beta layer. Lies OVER the whole section and intercepts every
       click — the section stays visible as a preview but is dead.
       English even in the German interface: it is a
       product statement, not an operating aid. -->
  {#if zustand.features?.beta_lock}
  <div class="beta-schicht" role="note">
    <div class="beta-tafel">
      <div class="beta-kopf">{t('beta.nur_vollversion')}</div>
      <p class="beta-text">{t('beta.nur_vollversion_text')}</p>
    </div>
  </div>
  {/if}
  <!-- The watermark lies next to the scroll area, not inside it: that
       way it stays put while the cards run past it. -->
  <Wasserzeichen blass={hatAuftraege}>
    <Agentenmarke groesse={MARKE} />
  </Wasserzeichen>
  {#if !hatAuftraege}
    <p class="leer">{t('jobs.leer')}</p>
  {/if}

  <div class="auftraege" use:rollfade>
  <div class="spur">
    {#each wartende as auftrag (auftrag.id)}
      <div class="banner" transition:slide={{ duration: 180 }}>
        <span class="uhr">⏳</span>
        <span class="banner-text">{t('jobs.banner', { agent: auftrag.agent })}</span>
        <button class="knopf" onclick={() => klappen(auftrag.id)}>{t('jobs.bericht')}</button>
      </div>
    {/each}


    {#each zustand.auftraege as auftrag (auftrag.id)}
      <div class="karte" id={`auftrag-${auftrag.id}`}>
        <button class="kopf" onclick={() => klappen(auftrag.id)}>
          <!-- The mark before the name, like a sender avatar: it says at
               a glance that a machine worked here. -->
          <Agentenmarke groesse={16} />
          <span class="agent">{auftrag.agent}</span>
          <Standpille farbe={ZUSTANDSFARBE[auftrag.state] ?? 'still'}>{zustandText(auftrag.state)}</Standpille>
          <!-- The chevron shows that the card folds —
               same symbol as on the reasoning block, rotates on
               opening. -->
          <svg class="klappwinkel" class:offen={offene[auftrag.id]}
               width="12" height="12" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <path d="M9 6l6 6-6 6" />
          </svg>
          {#if auftrag.end_reason && auftrag.end_reason !== 'fertig'}
            <span class="grund">{grundText(auftrag.end_reason)}</span>
          {/if}
          <span class="wann">{zeit(auftrag.created_at)}</span>
        </button>
        <p class="aufgabe">{auftrag.task}</p>

        {#if auftrag.state === 'laeuft' || auftrag.state === 'wartet'}
          <div class="laufzeile">
            <!-- Behind the status, the mark that draws itself and the
                 trailing dots — the pulsing dot in
                 front is thereby retired. -->
            {#if auftrag.state === 'laeuft'}<AgentenLademarke />{/if}
            <button class="knopf" onclick={() => abbrechen(auftrag)}>{t('jobs.abbrechen')}</button>
          </div>
        {/if}

        {#if offene[auftrag.id]}
          <div class="innen" transition:slide={{ duration: 180 }}>
            {#if protokolle[auftrag.id]?.length}
              <div class="gruppe">{t('jobs.protokoll', { anzahl: protokolle[auftrag.id].length })}</div>
              {#each protokolle[auftrag.id] as schritt (schritt.nummer)}
                <div class="schritt">
                  <span class="nummer">{schritt.nummer}</span>
                  <span class="typ">{schritt.typ}</span>
                  {#if schrittWerkzeug(schritt)}
                    <!-- Right before the tool name in the content, tucked
                         in close and centered instead of on the baseline —
                         an SVG has none. -->
                    <span class="zeichenhalter"><Werkzeugzeichen name={schrittWerkzeug(schritt)} /></span>
                  {/if}
                  <span class="inhalt">{schrittInhalt(schritt)}</span>
                </div>
              {/each}
            {/if}
            {#if auftrag.result}
              <div class="gruppe">{t('jobs.bericht')}</div>
              <div class="bericht">{auftrag.result}</div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  </div>
  </div>
</div>

<AuftragStarten bind:offen={zustand.auftragStartenOffen} />

<style>
  /* Two layers: the watermark stands still, the content scrolls over it. */
  .agentenbereich {
    flex: 1;
    position: relative;
    display: flex;
    min-height: 0;
  }
  /* ══ Beta layer ══
     `inset: 0` covers the whole section, the high z-index puts it above
     the cards (which sit at z-index 1). It intercepts the clicks
     itself — no `pointer-events: none`, that would be the opposite. */
  .beta-schicht {
    position: absolute;
    inset: 0;
    z-index: 40;
    display: grid;
    place-items: center;
    padding: 24px;
    background: color-mix(in srgb, var(--flaeche) 74%, transparent);
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
  }
  .beta-tafel {
    max-width: 360px;
    text-align: center;
  }
  .beta-kopf {
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text);
  }
  .beta-text {
    margin: 10px 0 0;
    font-size: 13px;
    line-height: 1.55;
    color: var(--text-still);
  }
  .auftraege {
    flex: 1;
    overflow-y: auto;
    /* Above the watermark, otherwise it swallows the cards' clicks. */
    position: relative;
    z-index: 1;
  }
  .spur {
    max-width: 720px;
    margin: 0 auto;
    padding: 26px 28px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  /* The sentence — only as long as no task exists yet. It sits in the
     free strip below the mark (which takes 75% of the height, so a good
     12% remains at the bottom), not on it: that way it is readable
     without a backdrop. */
  .leer {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 18px;
    margin: 0;
    padding: 0 20px;
    pointer-events: none;
    color: var(--text-still);
    text-align: center;
    font-size: 13.5px;
  }


  /* The yellow banner: the one spot that has to leap out at you. */
  .banner {
    display: flex;
    align-items: center;
    gap: 10px;
    border: 1px solid var(--gelb);
    background: color-mix(in srgb, var(--gelb) 12%, var(--bg));
    border-radius: var(--radius);
    padding: 10px 14px;
    font-size: 13.5px;
  }
  .banner-text {
    flex: 1;
    min-width: 0;
  }
  .uhr {
    flex: none;
  }

  .karte {
    background: var(--bg-erhoben);
    border: 1px solid var(--linie);
    border-radius: var(--radius);
    padding: 12px 14px;
  }
  .kopf {
    display: flex;
    align-items: baseline;
    gap: 10px;
    width: 100%;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    padding: 0;
    text-align: left;
    cursor: pointer;
  }
  .agent {
    font-weight: 600;
    font-size: 13.5px;
  }
  /* The fold chevron next to the pill: same construction as on the
     reasoning block, rotates downward on opening. align-self centered,
     because the header row aligns on the baseline. */
  .klappwinkel {
    flex: none;
    align-self: center;
    color: var(--text-still);
    transition: transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .klappwinkel.offen {
    transform: rotate(90deg);
  }
  @media (prefers-reduced-motion: reduce) {
    .klappwinkel { transition: none; }
  }
  .grund {
    color: var(--text-still);
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .wann {
    margin-left: auto;
    flex: none;
    color: var(--text-still);
    font-size: 11.5px;
  }
  .aufgabe {
    color: var(--text-leise);
    font-size: 13px;
    margin: 6px 0 0;
    line-height: 1.5;
  }

  .laufzeile {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
  }
  .innen {
    margin-top: 10px;
    border-top: 1px solid var(--linie);
    padding-top: 6px;
  }
  .gruppe {
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-still);
    padding: 8px 0 5px;
  }
  /* One row per step — same construction as the tool rows (3.9). */
  .schritt {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 5px 4px;
    font-size: 12.5px;
    border-radius: 7px;
  }
  .schritt:hover {
    background: var(--blase);
  }
  .zeichenhalter {
    flex: none;
    display: inline-flex;
    align-self: center;
    /* Tighter than the row gap: the icon belongs to the name behind it. */
    margin: 0 -4px 0 -2px;
  }
  .nummer {
    flex: none;
    min-width: 2ch;
    color: var(--text-still);
    font-family: var(--schrift-fest, monospace);
    font-size: 11px;
  }
  .typ {
    flex: none;
    min-width: 84px;
    text-align: center;
    font-family: var(--schrift-fest, monospace);
    font-size: 10.5px;
    color: var(--text-leise);
    background: var(--blase);
    border-radius: 6px;
    padding: 1px 7px;
  }
  .inhalt {
    color: var(--text-leise);
    white-space: pre-wrap;
    word-break: break-word;
    min-width: 0;
  }
  .bericht {
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    padding: 4px;
  }

  .knopf {
    flex: none;
    border: 1px solid var(--linie-stark);
    background: var(--bg-erhoben);
    color: var(--text);
    font: inherit;
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .knopf:hover {
    background: var(--linie);
  }

  @media (max-width: 720px) {
    .spur {
      padding: 26px 18px;
    }
  }
</style>
