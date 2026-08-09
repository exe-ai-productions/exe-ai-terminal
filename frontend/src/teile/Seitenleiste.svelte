<script>
  import { slide, fade } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { t } from '../lib/texte.svelte.js'
  import { api } from '../lib/api.js'
  import Modellwahl from './Modellwahl.svelte'
  import {
    zustand, chatsLaden, chatOeffnen, neuerChat, chatAendern, chatLoeschen,
    auftragLoeschen, melde, kontextStand, bereichWechseln,
    frage,
} from '../lib/zustand.svelte.js'

  let suchZeit
  let menue = $state(null) // { chat, x, y }
  let auftragMenue = $state(null) // { auftrag, x, y } — the same menu, for tasks

  const angeheftet = $derived(zustand.chats.filter((c) => c.pinned))
  const uebrige = $derived(zustand.chats.filter((c) => !c.pinned))
  const kontext = $derived(kontextStand())

  /* Jobs: the same bar as for the chats — search field, create button,
     list — a direct copy of the chat overlay.

     Filtering happens here in the window instead of on the server: the
     list is already fully loaded and small anyway, a second path over
     the API would only add delay. The search covers agent name AND job
     text — for a job, the task is the title. */
  const gefiltert = $derived.by(() => {
    const suche = zustand.auftragSuche.trim().toLowerCase()
    if (!suche) return zustand.auftraege
    return zustand.auftraege.filter(
      (a) =>
        a.agent.toLowerCase().includes(suche) || (a.task || '').toLowerCase().includes(suche),
    )
  })

  /* Grouped by state (6.5): waiting first, then running, then everything
     finished — the same order as in the main area. */
  const wartende = $derived(gefiltert.filter((a) => a.state === 'wartet'))
  const laufende = $derived(gefiltert.filter((a) => a.state === 'laeuft'))
  const beendete = $derived(
    gefiltert.filter((a) => a.state !== 'wartet' && a.state !== 'laeuft'),
  )

  /* The yellow dot on the switch must not let the search field impress
     it: it reports that a job is waiting somewhere, not that one matches
     the search term. */
  const wartetIrgendwo = $derived(zustand.auftraege.some((a) => a.state === 'wartet'))

  /* The Scheduled group: agents with a schedule, raw
     from GET /agents — no second list to maintain. Fresh on switching
     into the section; the pause situation only changes with runs
     anyway. */
  let geplante = $state([])
  async function geplanteLaden() {
    try {
      geplante = (await api.agenten()).filter((agent) => agent.schedule)
    } catch {
      /* An overview — no toast, the next switch tries again. */
    }
  }
  $effect(() => {
    if (zustand.bereich === 'auftraege') geplanteLaden()
  })

  function agentOeffnen(name) {
    zustand.promptStart = 'agent:' + name
    zustand.promptOffen = true
  }

  function auftragZeigen(id) {
    zustand.auftragAusgewaehlt = id
    zustand.seitenleisteOffen = false
  }

  function suchen(wert) {
    zustand.suche = wert
    clearTimeout(suchZeit)
    suchZeit = setTimeout(chatsLaden, 220)
  }

  function kurz(zahl) {
    if (!zahl) return '—'
    if (zahl < 1000) return String(zahl)
    const k = zahl / 1000
    return (k >= 100 ? Math.round(k) : Math.round(k * 10) / 10) + 'k'
  }

  function menueOeffnen(ereignis, chat) {
    ereignis.preventDefault()
    menue = { chat, x: Math.min(ereignis.clientX, innerWidth - 200), y: Math.min(ereignis.clientY, innerHeight - 140) }
  }

  /* Right-click on a task: the same menu as for the chats —
     only with what actually exists for a job. */
  function auftragMenueOeffnen(ereignis, auftrag) {
    ereignis.preventDefault()
    auftragMenue = { auftrag, x: Math.min(ereignis.clientX, innerWidth - 200), y: Math.min(ereignis.clientY, innerHeight - 140) }
  }

  async function auftragEntfernen(auftrag) {
    auftragMenue = null
    if (!(await frage(t('jobs.loeschen_frage')))) return
    await auftragLoeschen(auftrag.id)
    melde(t('jobs.geloescht'), 'erfolg')
  }

  async function anheften(chat) {
    menue = null
    await chatAendern(chat.id, { pinned: !chat.pinned })
  }
  async function umbenennen(chat) {
    menue = null
    const neu = await frage(t('chat.neuer_titel'), {
      eingabe: chat.title, okSchluessel: 'app.sichern',
    })
    if (neu === null) return
    await chatAendern(chat.id, { title: neu })
  }
  async function loeschen(chat) {
    menue = null
    if (!(await frage(t('chat.loeschen_frage')))) return
    await chatLoeschen(chat.id)
    melde(t('chat.geloescht'), 'erfolg')
  }
</script>

<svelte:window onclick={() => { menue = null; auftragMenue = null }} />

<aside
  class="seitenleiste"
  class:offen={zustand.seitenleisteOffen}
  class:eingeklappt={zustand.seitenleisteEingeklappt}
>
  <!-- The section switch (6.5, variant A): same construction as the segment
       in the settings. The yellow dot shows waiting jobs even when you are
       currently in the chats.

       The plus belongs at the START of the list: it is the list's main
       action, and at the end it read as one more thing that was left over.
       No visible word — the sign is unambiguous, and ⌘N stays. -->
  <div class="kopfzeile">
    <div class="bereiche">
      <button
        aria-pressed={zustand.bereich === 'chats'}
        onclick={() => bereichWechseln('chats')}
      >{t('jobs.bereich_chats')}</button>
      <button
        aria-pressed={zustand.bereich === 'auftraege'}
        onclick={() => bereichWechseln('auftraege')}
      >
        {t('jobs.bereich_jobs')}
        {#if wartetIrgendwo}<span class="warte-punkt"></span>{/if}
      </button>
    </div>

    {#if zustand.bereich === 'chats'}
      <button class="plus" onclick={neuerChat} title={t('chat.neu')} aria-label={t('chat.neu')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    {:else}
      <!-- Beta: the section is visible as a preview but dead. Without this
           guard the click would run into a bare 403 from the lock
           (app/beta.py) — a dead end instead of a statement. -->
      <button
        class="plus"
        class:gesperrt={zustand.features?.beta_lock}
        disabled={zustand.features?.beta_lock}
        onclick={() => (zustand.auftragStartenOffen = true)}
        title={t('jobs.starten')}
        aria-label={t('jobs.starten')}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    {/if}
  </div>

  {#if zustand.bereich === 'chats'}
  <div class="suchfeld">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
    </svg>
    <input
      id="suchfeld"
      placeholder={t('chat.suchen')}
      aria-label={t('chat.suchen')}
      value={zustand.suche}
      oninput={(e) => suchen(e.currentTarget.value)}
    />
  </div>

  <div class="liste">
    {#if angeheftet.length}
      <div class="gruppe" transition:slide={{ duration: 160 }}>{t('chat.angeheftet')}</div>
      {#each angeheftet as chat (chat.id)}
        <div animate:flip={{ duration: 220 }} transition:slide={{ duration: 180 }}>
          <button
            class="chat"
            class:aktiv={chat.id === zustand.aktiverChat}
            onclick={() => chatOeffnen(chat.id)}
            oncontextmenu={(e) => menueOeffnen(e, chat)}
          >
            {#if zustand.fertigeChats.includes(chat.id)}
              <span class="fertigpunkt" title={t('chat.antwort_fertig')} aria-label={t('chat.antwort_fertig')}></span>
            {/if}
            <span class="titel">{chat.title}</span>
            <!-- The pin releases on click — no detour
                 through the right-click menu when the symbol is standing
                 there anyway. span instead of button: a button inside a
                 button is forbidden. -->
            <span
              class="nadel"
              role="button"
              tabindex="0"
              title={t('chat.loesen')}
              aria-label={t('chat.loesen')}
              onclick={(e) => { e.stopPropagation(); anheften(chat) }}
              onkeydown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  e.stopPropagation()
                  anheften(chat)
                }
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2">
                <path d="M12 17v5M9 3h6l-1 7 3 3H7l3-3z" />
              </svg>
            </span>
          </button>
        </div>
      {/each}
    {/if}

    {#if uebrige.length}
      <div class="gruppe">{angeheftet.length ? t('chat.zuletzt') : t('chat.alle')}</div>
      {#each uebrige as chat (chat.id)}
        <div animate:flip={{ duration: 220 }} transition:slide={{ duration: 180 }}>
          <button
            class="chat"
            class:aktiv={chat.id === zustand.aktiverChat}
            onclick={() => chatOeffnen(chat.id)}
            oncontextmenu={(e) => menueOeffnen(e, chat)}
          >
            {#if zustand.fertigeChats.includes(chat.id)}
              <span class="fertigpunkt" title={t('chat.antwort_fertig')} aria-label={t('chat.antwort_fertig')}></span>
            {/if}
            <span class="titel">{chat.title}</span>
            <!-- Quick pinning: the pin only appears on
                 hover — the same pin as above, just as an invitation
                 instead of a state. Right-click remains alongside. -->
            <span
              class="nadel einladung"
              role="button"
              tabindex="0"
              title={t('chat.anheften')}
              aria-label={t('chat.anheften')}
              onclick={(e) => { e.stopPropagation(); anheften(chat) }}
              onkeydown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  e.stopPropagation()
                  anheften(chat)
                }
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2">
                <path d="M12 17v5M9 3h6l-1 7 3 3H7l3-3z" />
              </svg>
            </span>
          </button>
        </div>
      {/each}
    {/if}

    {#if !zustand.chats.length}
      <div class="gruppe">{zustand.suche ? t('chat.keine_treffer') : t('chat.leer')}</div>
    {/if}
  </div>
  {:else}
  <!-- Jobs: the same arrangement as for the chats — search field, then
       the create button, then the list. -->
  <div class="suchfeld">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
    </svg>
    <input
      id="auftrag-suchfeld"
      placeholder={t('jobs.suchen')}
      aria-label={t('jobs.suchen')}
      value={zustand.auftragSuche}
      oninput={(e) => (zustand.auftragSuche = e.currentTarget.value)}
    />
  </div>

  <div class="liste">
    <!-- Scheduled first: whatever runs automatically
         stands visibly on top — yellow dot in the list's dot language,
         dashed when the alarm clock is paused. Click opens the agent. -->
    {#if geplante.length}
      <div class="gruppe">{t('jobs.gruppe_geplant')}</div>
      {#each geplante as agent (agent.name)}
        <button
          class="chat"
          onclick={() => agentOeffnen(agent.name)}
          title={agent.schedule_paused
            ? t('jobs.wecker_pausiert')
            : t('jobs.wecker_zeile', { zeit: agent.schedule })}
        >
          <span class="punkt {agent.schedule_paused ? 'p-pause' : 'p-wartet'}"></span>
          <span class="titel">{agent.name}</span>
          <span class="planzeit">{agent.schedule}</span>
        </button>
      {/each}
    {/if}

    <!-- The row title is the task, not the agent name: multiple runs of
         the same agent would otherwise all look alike, and the search
         goes for the task text anyway. Which agent it was is in the card
         in the main area. -->
    {#if wartende.length}
      <div class="gruppe">{t('jobs.gruppe_wartet')}</div>
      {#each wartende as auftrag (auftrag.id)}
        <button class="chat" onclick={() => auftragZeigen(auftrag.id)}
                oncontextmenu={(e) => { if (!zustand.features?.beta_lock) auftragMenueOeffnen(e, auftrag) }}>
          <span class="punkt p-wartet"></span>
          <span class="titel">{auftrag.task}</span>
        </button>
      {/each}
    {/if}
    {#if laufende.length}
      <div class="gruppe">{t('jobs.gruppe_laeuft')}</div>
      {#each laufende as auftrag (auftrag.id)}
        <button class="chat" onclick={() => auftragZeigen(auftrag.id)}
                oncontextmenu={(e) => { if (!zustand.features?.beta_lock) auftragMenueOeffnen(e, auftrag) }}>
          <span class="punkt p-laeuft"></span>
          <span class="titel">{auftrag.task}</span>
        </button>
      {/each}
    {/if}
    {#if beendete.length}
      <div class="gruppe">{t('jobs.gruppe_fertig')}</div>
      {#each beendete as auftrag (auftrag.id)}
        <button class="chat" onclick={() => auftragZeigen(auftrag.id)}
                oncontextmenu={(e) => { if (!zustand.features?.beta_lock) auftragMenueOeffnen(e, auftrag) }}>
          <span class="punkt p-{auftrag.state}"></span>
          <span class="titel">{auftrag.task}</span>
        </button>
      {/each}
    {/if}
    {#if !gefiltert.length}
      <div class="gruppe">
        {zustand.auftragSuche.trim() ? t('jobs.keine_treffer') : t('jobs.leer')}
      </div>
    {/if}
  </div>
  {/if}

  <!-- Its own row above the separator: the line sets off the context
       display, not the toggle. That belongs to the bar, not to the
       display. -->
  <!-- "New" is its own bar across the full width. It
       used to share a row with the collapse toggle; that row now belongs to
       the model picker, which moved down from the header so the header
       could be cleared for the working folders. -->
  <!-- One statement instead of four leftovers: who is answering, and how
       full they are. The foot used to hold an action, a setting, a display
       and a layout control side by side — four kinds in one box, which is
       why it read as glued together. The action moved to the head of the
       list, the layout control onto the seam (Seitengriff.svelte), and what
       remains belongs together: the bar sits directly under the name and is
       read as THAT model's fill.

       The number needs no word. "Tokens" names the unit, not the thing —
       what fills up is the context, and standing under the model name the
       bar says so by itself. The full sentence is in the title, from the
       catalogue, for anyone who cannot see the bar. -->
  {#if zustand.bereich === 'chats'}
    <div
      class="statusfuss"
      title={kontext.gesamt
        ? t('kontext.auslastung', { genutzt: kurz(kontext.genutzt), gesamt: kurz(kontext.gesamt) })
        : t('modell.titel')}
    >
      <div class="statuskopf">
        <Modellwahl leiste />
        <span class="statuszahl">
          {#if kontext.gesamt}{kurz(kontext.genutzt)} / {kurz(kontext.gesamt)}{:else}—{/if}
        </span>
      </div>
      <div class="balken">
        <div
          style="width:{kontext.anteil}%; background:{kontext.anteil > 90
            ? 'var(--rot)'
            : kontext.anteil > 70
              ? 'var(--gelb)'
              : 'var(--text-leise)'}"
        ></div>
      </div>
    </div>
  {/if}
</aside>

{#if menue}
  <div
    class="kontextmenue"
    role="menu"
    tabindex="-1"
    style="left:{menue.x}px; top:{menue.y}px"
    transition:fade={{ duration: 100 }}
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => { if (e.key === 'Escape') menue = null }}
  >
    <button role="menuitem" onclick={() => anheften(menue.chat)}>
      {menue.chat.pinned ? t('chat.loesen') : t('chat.anheften')}
    </button>
    <button role="menuitem" onclick={() => umbenennen(menue.chat)}>{t('chat.umbenennen')}</button>
    <button role="menuitem" class="gefahr" onclick={() => loeschen(menue.chat)}>{t('chat.loeschen')}</button>
  </div>
{/if}

{#if auftragMenue}
  <div
    class="kontextmenue"
    role="menu"
    tabindex="-1"
    style="left:{auftragMenue.x}px; top:{auftragMenue.y}px"
    transition:fade={{ duration: 100 }}
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => { if (e.key === 'Escape') auftragMenue = null }}
  >
    <button role="menuitem" class="gefahr" onclick={() => auftragEntfernen(auftragMenue.auftrag)}>{t('jobs.loeschen')}</button>
  </div>
{/if}

<style>
  /* Locked button: visible, but visibly not in charge. */
  .gesperrt {
    opacity: 0.38;
    cursor: default;
  }

  .seitenleiste {
    /* 15 percent wider than the 248 it started with — titles were
       truncating earlier than the free space around them justified. */
    width: 285px;
    flex: none;
    display: flex;
    flex-direction: column;
    background: var(--bg-seite);
    border-right: 1px solid var(--linie);
    transition: width 0.22s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  /* Collapsed it goes away completely. It used to leave a 50 px rail behind
     because the toggle lived inside it and the way back would otherwise have
     been gone — the handle sits on the seam now (Seitengriff.svelte), so the
     rail has nothing left to carry. An empty strip is not a compromise, it
     is a strip of nothing. */
  .seitenleiste.eingeklappt {
    width: 0;
    border-right: none;
    overflow: hidden;
  }
  @media (prefers-reduced-motion: reduce) {
    .seitenleiste { transition: none; }
  }
  /* The head of the list: what it shows, and the one action that adds to
     it. The plus stands at the START — at the end it read as one more
     leftover, which is what the whole foot suffered from. */
  .kopfzeile {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 12px 12px 10px;
    flex: none;
  }
  .plus {
    width: 30px;
    height: 30px;
    flex: none;
    border: 1px solid var(--linie);
    border-radius: 9px;
    background: var(--bg-seite);
    color: var(--text-leise);
    display: grid;
    place-items: center;
    padding: 0;
    cursor: pointer;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }
  .plus:hover:not(.gesperrt) {
    background: var(--linie);
    color: var(--text);
    border-color: var(--linie-stark);
  }

  /* The switch: same construction as the segment in the settings. */
  .bereiche {
    display: flex;
    flex: 1;
    min-width: 0;
    margin: 0;
    background: var(--bg-seite);
    border: 1px solid var(--linie);
    border-radius: 9px;
    padding: 2px;
  }
  .bereiche button {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    padding: 5px 0;
    border-radius: 7px;
    cursor: pointer;
    transition: background 0.16s, color 0.16s;
  }
  .bereiche button[aria-pressed='true'] {
    background: var(--bg-erhoben);
    color: var(--text);
    font-weight: 600;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }
  .warte-punkt {
    width: 7px;
    height: 7px;
    border-radius: 99px;
    background: var(--gelb);
  }
  .punkt {
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 99px;
    background: var(--text-still);
  }
  .p-wartet { background: var(--gelb); }
  /* Alarm clock paused (after three failures): the dashed yellow ring. */
  .p-pause {
    background: none;
    border: 1.5px dashed var(--gelb);
    width: 6px;
    height: 6px;
  }
  .planzeit {
    margin-left: auto;
    flex: none;
    font-size: 11.5px;
    color: var(--text-still);
    font-variant-numeric: tabular-nums;
  }
  .p-laeuft { background: var(--blau); }
  .p-fertig { background: var(--gruen); }
  .p-gescheitert { background: var(--rot); }

  .suchfeld {
    margin: 0 12px 12px;
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 7px 10px;
    border: 1px solid var(--linie);
    /* 9 like every other small control. --radius is the house's old default
       of 10 and predates the radius palette. */
    border-radius: 9px;
    background: var(--bg-erhoben);
    color: var(--text-still);
  }
  .suchfeld input {
    border: none;
    background: none;
    outline: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    width: 100%;
    min-width: 0;
  }
  .gruppe {
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-still);
    padding: 10px 18px 5px;
  }
  .liste {
    overflow-y: auto;
    flex: 1;
    padding: 0 8px;
  }
  .chat {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 10px;
    border: none;
    border-radius: var(--radius);
    margin-bottom: 1px;
    font: inherit;
    font-size: 13.5px;
    text-align: left;
    background: none;
    color: var(--text-leise);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  /* The finished answer waiting to be seen: blue is the house colour for
     "running, active" and this is its afterglow — ringed in text colour so
     it reads on the active row too, pulsing so the eye finds it. */
  .fertigpunkt {
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 99px;
    background: var(--blau);
    box-shadow: 0 0 0 1.5px var(--text);
    animation: fertigpuls 1.6s ease-in-out infinite;
  }
  @keyframes fertigpuls {
    50% { opacity: 0.45; transform: scale(0.82); }
  }
  @media (prefers-reduced-motion: reduce) {
    .fertigpunkt { animation: none; }
  }
  .chat:hover {
    background: var(--linie);
    color: var(--text);
  }
  .chat.aktiv {
    background: var(--linie-stark);
    color: var(--text);
  }
  .titel {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }
  .nadel {
    opacity: 0.5;
    flex: none;
    display: inline-flex;
    padding: 3px;
    margin: -3px;
    border-radius: 6px;
    cursor: pointer;
    transition: opacity 0.12s, background 0.12s;
  }
  .nadel:hover,
  .nadel:focus-visible {
    opacity: 1;
    background: var(--linie);
  }
  /* The invitation pin is invisible until you are on the row — otherwise
     every chat row would carry a symbol that indicates nothing. */
  .nadel.einladung {
    opacity: 0;
  }
  .chat:hover .nadel.einladung,
  .chat:focus-within .nadel.einladung {
    opacity: 0.5;
  }
  .chat .nadel.einladung:hover,
  .chat .nadel.einladung:focus-visible {
    opacity: 1;
    background: var(--linie-stark);
  }
  /* Keeps toggle and footer at the bottom. Don't let the list do this
     work: collapsed it is hidden, and both slid upward. */
  /* The foot is ONE statement now: who answers, and how full they are.
     Before, four kinds stood here side by side — an action, a setting, a
     display and a layout control — which is exactly why it read as glued
     together. The bar sits directly under the name and is therefore read as
     THAT model's fill, not as a second thing. */
  .statusfuss {
    flex: none;
    margin-top: auto;
    padding: 9px 12px 11px;
    border-top: 1px solid var(--linie);
  }
  .statuskopf {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  /* Quiet and right-aligned: the number is the detail, the name is the
     subject. Tabular figures so the block does not twitch while the count
     runs up. */
  .statuszahl {
    margin-left: auto;
    flex: none;
    font-size: 11px;
    color: var(--text-still);
    font-variant-numeric: tabular-nums;
  }
  .balken {
    height: 3px;
    border-radius: 99px;
    background: var(--linie);
    overflow: hidden;
    margin-top: 7px;
  }
  .balken > div {
    height: 100%;
    border-radius: 99px;
    transition: width 0.35s ease, background 0.35s ease;
  }

  .kontextmenue {
    position: fixed;
    z-index: 50;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 10px;
    padding: 5px;
    min-width: 180px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
  }
  .kontextmenue button {
    display: block;
    width: 100%;
    text-align: left;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 7px 11px;
    border-radius: 7px;
    cursor: pointer;
  }
  .kontextmenue button:hover {
    background: var(--linie);
  }
  .kontextmenue .gefahr:hover {
    background: var(--rot);
    color: #fff;
  }

  @media (max-width: 720px) {
    .seitenleiste {
      position: absolute;
      z-index: 40;
      height: 100%;
      box-shadow: 0 0 40px rgba(0, 0, 0, 0.3);
      transform: translateX(-100%);
      transition: transform 0.22s cubic-bezier(0.2, 0.9, 0.3, 1);
    }
    .seitenleiste.offen {
      transform: none;
    }
    /* On the phone the collapsed state means nothing: the bar lies over the
       chat as a drawer and is closed until opened. So it keeps its full
       width and its full contents here — `offen` decides, not
       `eingeklappt`. */
    .seitenleiste.eingeklappt {
      width: 248px;
      border-right: 1px solid var(--linie);
      overflow: visible;
    }
  }
</style>
