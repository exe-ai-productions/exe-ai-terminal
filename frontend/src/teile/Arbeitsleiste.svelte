<script>
  /* The work rail: five modules, one visible at a time.

     Head says which module and one detail about it — the file name, how
     many runs, whether the CLI is working. The signs sit on the strip
     beside it (Modulrand.svelte), which stays visible whether this panel is
     open or shut.

     The rail is one component and the modules are files beside it; adding
     one is a line on the strip and a file of its own, not a rebuild. */
  import ModulCli from './ModulCli.svelte'
  import EEWzeichen from './EEWzeichen.svelte'
  import Modulzeichen from './Modulzeichen.svelte'
  import Notizwerkzeuge from './Notizwerkzeuge.svelte'
  import ModulNotiz from './ModulNotiz.svelte'
  import ModulTerminal from './ModulTerminal.svelte'
  import ModulVorschau from './ModulVorschau.svelte'
  import ModulWaechter from './ModulWaechter.svelte'
  import { breiteSetzen, leiste, schliessen } from '../lib/arbeitsleiste.svelte.js'
  import { cli, zeilenVon } from '../lib/cli.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import { notizen } from '../lib/notizen.svelte.js'
  import Schalter from './Schalter.svelte'
  import { eew, schalten as eewSchaltenRoh } from '../lib/eew.svelte.js'
  import { befundVerwerfen, befundeVon } from '../lib/waechter.svelte.js'
  import { terminal } from '../lib/terminalfenster.svelte.js'
  import { aktiverTab, tabsVon } from '../lib/vorschautabs.svelte.js'
  import { melde, zustand } from '../lib/zustand.svelte.js'
  import { einreihen } from '../lib/warteschlange.svelte.js'

  /* The one thing this rail cannot do for itself: send a message. The
     guardian's suggestion is a message like any other, so the chat hands
     its own send down here rather than the panel building a second path
     into the model. */
  let { senden } = $props()

  /* The seam sets the width and nothing else — opening and closing belongs
     to the signs on the strip, which are visible without aiming. Dragged
     this far past the minimum the hand still clearly wants it gone. */
  const ZUKLAPP_BREITE = 200
  const KLICK_TOLERANZ = 4

  let startX = 0
  let startBreite = 0
  let bewegt = false

  function fassen(e) {
    if (e.button !== 0) return
    e.preventDefault()
    startX = e.clientX
    startBreite = leiste.breite
    bewegt = false
    e.currentTarget.setPointerCapture(e.pointerId)
  }

  function ziehen(e) {
    if (!e.currentTarget.hasPointerCapture?.(e.pointerId)) return
    const dx = startX - e.clientX
    if (!bewegt && Math.abs(dx) <= KLICK_TOLERANZ) return
    bewegt = true
    leiste.zieht = true
    if (startBreite + dx < ZUKLAPP_BREITE) {
      leiste.zieht = false
      e.currentTarget.releasePointerCapture(e.pointerId)
      schliessen()
      return
    }
    breiteSetzen(startBreite + dx)
  }

  function loslassen(e) {
    leiste.zieht = false
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
    bewegt = false
  }

  const chatId = $derived(zustand.aktiverChat)

  /* The one line of detail in the head. Each module answers for itself what
     is worth knowing about it from outside. */
  const detail = $derived.by(() => {
    if (leiste.modul === 'terminal') {
      const anzahl = terminal.laeufe.length
      return anzahl ? t('terminal.laeufe', { n: anzahl }) : ''
    }
    if (leiste.modul === 'vorschau') return aktiverTab(chatId)?.name ?? ''
    if (leiste.modul === 'cli') {
      return cli.laeuft ? t('cli.laeuft') : t('cli.zeilen', { n: zeilenVon(chatId).length })
    }
    if (leiste.modul === 'notiz') {
      return notizen.liste.length ? t('notiz.anzahl', { n: notizen.liste.length }) : ''
    }
    if (leiste.modul === 'waechter') {
      const n = befundeVon(chatId).length
      return n ? t('waechter.anzahl', { n }) : ''
    }
    return ''
  })

  const MODULE = [
    ['terminal', 'terminal.titel'],
    ['cli', 'cli.titel'],
    ['vorschau', 'vorschau.titel'],
    ['notiz', 'notiz.titel'],
    ['waechter', 'waechter.titel'],
  ]

  /* A failing switch must say so; everything else about it lives in its own
     module. */
  async function eewSchalten(an) {
    try {
      await eewSchaltenRoh(an)
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  /* A suggestion, sent. It travels the same path a typed message travels —
     the panel only writes the sentence, the chat does the rest — and the
     finding goes once it is on its way: it has been dealt with. */
  function befundSenden(befund) {
    if (!befund?.vorschlag) return
    const ziel = chatId
    befundVerwerfen(ziel, befund.id)
    /* The same branch a typed message takes. A finding usually appears WHILE
       something is still running — that is when a tool call fails — so this
       button is pressed against a live run more often than not. Sending
       straight through would start a second run over the first; the queue is
       what the input bar uses for exactly this, and the panel has no reason
       to know better.

       Unless the model is the one waiting: a standing question holds the run
       open, and the suggestion IS the answer to it. */
    if (zustand.laeuft && !zustand.benutzerfrage) {
      einreihen(ziel, {
        inhalt: befund.vorschlag,
        bild: null,
        dokument: null,
        denken: null,
        skill: null,
      })
      return
    }
    senden(befund.vorschlag)
  }

  /* The commands the toolbar fires. `execCommand` is deprecated and still
     the only thing every engine agrees on for a contenteditable; what comes
     out is rebuilt against a whitelist on the way to disk, so nothing here
     decides what a note may contain. */
  function auszeichnen(was, wert) {
    if (was === 'mark') {
      document.execCommand('insertHTML', false, markieren(wert))
      return
    }
    document.execCommand(was, false, null)
  }

  function markieren(farbe) {
    const auswahl = document.getSelection()
    const text = String(auswahl ?? '')
    if (!text) return ''
    const sicher = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return `<mark data-farbe="${farbe}">${sicher}</mark>`
  }

  const titel = $derived(
    t(MODULE.find(([name]) => name === leiste.modul)?.[1] ?? 'terminal.titel'),
  )
</script>

{#if leiste.offen}
  <aside class="leiste" style="width: {leiste.breite}px">
    <!-- Sits on the seam and belongs to neither side, like the one on the
         left. It only sets the width: opening and closing is on the strip
         of signs, where nobody has to aim for a hairline. -->
    <div class="zone">
      <button
        class="griff"
        class:packt={leiste.zieht}
        onpointerdown={fassen}
        onpointermove={ziehen}
        onpointerup={loslassen}
        title={t('leiste.breite')}
        aria-label={t('leiste.breite')}
      ></button>
    </div>

    <div class="kopf">
      <span class="kopfzeichen">
        {#if leiste.modul === 'waechter'}
          <EEWzeichen groesse={22} />
        {:else}
          <Modulzeichen modul={leiste.modul} groesse={15} />
        {/if}
      </span>
      <span class="modulname">{titel}</span>
      <span class="detail">{detail}</span>
      <!-- The formatting row belongs to the note being written, and it sits
           here rather than in every block: four buttons per note would be a
           wall of controls for something used rarely. -->
      {#if leiste.modul === 'notiz'}
        <Notizwerkzeuge aktiv={Boolean(notizen.offen)} ausfuehren={auszeichnen} />
      {/if}
      <!-- The switch sits where the hand already is when it wants the thing.
           On means both halves at once: the triggers go live and the small
           model loads. The settings carry the same switch and the same
           fact. -->
      {#if leiste.modul === 'waechter'}
        <span class="kopfschalter" title={eew.an ? t('waechter.an') : t('waechter.aus')}>
          {#if eew.laedt}<span class="laedt">{t('waechter.laedt')}</span>{/if}
          <Schalter
            an={eew.an}
            beschriftung={t('waechter.titel')}
            onschalten={() => eewSchalten(!eew.an)}
          />
        </span>
      {/if}
    </div>

    <div class="inhalt">
      {#if leiste.modul === 'terminal'}
        <ModulTerminal />
      {:else if leiste.modul === 'cli'}
        <ModulCli />
      {:else if leiste.modul === 'vorschau'}
        <ModulVorschau />
      {:else if leiste.modul === 'waechter'}
        <ModulWaechter senden={befundSenden} />
      {:else}
        <ModulNotiz />
      {/if}
    </div>
  </aside>
{/if}

<style>
  .leiste {
    flex: none;
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 0;
    border-left: 1px solid var(--linie);
    background: var(--bg);
  }
  /* Zero width in the layout: the strip must not push the chat aside for a
     control that is not there most of the time. */
  .zone {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 0;
    z-index: 5;
  }
  .zone::before {
    content: '';
    position: absolute;
    left: -13px;
    top: 0;
    bottom: 0;
    width: 26px;
  }
  .griff {
    position: absolute;
    left: -3px;
    top: 50%;
    transform: translateY(-50%);
    width: 6px;
    height: 96px;
    border-radius: 99px;
    background: var(--linie-stark);
    border: none;
    padding: 0;
    cursor: col-resize;
    touch-action: none;
    opacity: 0;
    transition: opacity 0.14s, background 0.14s;
  }
  .zone:hover .griff,
  .griff:focus-visible,
  .griff.packt { opacity: 1; }
  .griff:hover,
  .griff.packt { background: var(--text-still); }

  .kopf {
    flex: none;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 14px;
    border-bottom: 1px solid var(--linie);
    font-size: 12px;
    color: var(--text-leise);
  }
  .kopfschalter {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .laedt {
    font-size: 11px;
    color: var(--text-still);
  }
  .kopfzeichen {
    flex: none;
    display: grid;
    place-items: center;
    color: var(--text-leise);
  }
  .modulname {
    font-weight: 600;
    color: var(--text);
  }
  .detail {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-still);
  }

  .inhalt {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* On a narrow screen the chat needs its whole width; the rail would leave
     a column nobody can read. */
  @media (max-width: 720px) {
    .leiste, .zone { display: none; }
  }
</style>
