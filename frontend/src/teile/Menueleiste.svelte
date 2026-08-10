<script>
  import { fly } from 'svelte/transition'
  import { t } from '../lib/texte.svelte.js'
  import { api } from '../lib/api.js'
  import {
    zustand, aktuellerChat, chatAendern, chatLoeschen, neuerChat, melde,
    modellWaehlen, frage,
  } from '../lib/zustand.svelte.js'

  let { einstellungenOeffnen } = $props()

  let offen = $state(null) // 'chat' | 'modell'

  const chat = $derived(aktuellerChat())

  function schalten(name) {
    offen = offen === name ? null : name
  }
  /* Like on macOS: if a menu is open, it switches on hover. */
  function ueberfahren(name) {
    if (offen) offen = name
  }

  function brauchtChat(tat) {
    if (!chat) {
      melde(t('chat.erst_oeffnen'))
      return false
    }
    return true
  }

  async function anheften() {
    offen = null
    if (!brauchtChat()) return
    await chatAendern(chat.id, { pinned: !chat.pinned })
  }
  async function umbenennen() {
    offen = null
    if (!brauchtChat()) return
    const neu = await frage(t('chat.neuer_titel'), {
      eingabe: chat.title, okSchluessel: 'app.sichern',
    })
    if (neu === null) return
    await chatAendern(chat.id, { title: neu })
  }
  async function loeschen() {
    offen = null
    if (!brauchtChat()) return
    if (!(await frage(t('chat.loeschen_frage')))) return
    await chatLoeschen(chat.id)
    melde(t('chat.geloescht'), 'erfolg')
  }
  function letzteKopieren() {
    offen = null
    const letzte = [...zustand.nachrichten].reverse().find((n) => n.role === 'assistant')
    if (!letzte) {
      melde(t('menue.keine_antwort'))
      return
    }
    navigator.clipboard.writeText(letzte.content || '').then(() => melde(t('menue.kopiert'), 'erfolg'))
  }

  /* The server at a glance: is it up, and how much memory it holds right
     now. Polled gently — the bar lives the whole session, and a memory
     readout does not need to race. */
  let serverBlick = $state({ laeuft: false, belegt: null })
  $effect(() => {
    const holen = () =>
      api.runnerAuskunft()
        .then((a) => (serverBlick = { laeuft: Boolean(a.laeuft), belegt: a.belegt_gb }))
        .catch(() => {})
    holen()
    const takt = setInterval(holen, 5000)
    return () => clearInterval(takt)
  })

  export function schliessen() {
    offen = null
  }
  export function istOffen() {
    return offen !== null
  }
</script>

<svelte:window onclick={() => (offen = null)} />

<div class="leiste">
  <button
    class="seitenleiste-knopf"
    onclick={(e) => {
      e.stopPropagation()
      zustand.seitenleisteOffen = !zustand.seitenleisteOffen
    }}
    aria-label={t('chat.alle')}
  >
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  </button>

  <!-- No File menu anymore: its four entries were
       all chat things and now live there. It returns as soon as there
       are real file things (importing image/document, phase 4). -->
  {#each [['chat', 'menue.chat']] as [name, schluessel]}
    <button
      class="punkt"
      class:offen={offen === name}
      onclick={(e) => {
        e.stopPropagation()
        schalten(name)
      }}
      onmouseenter={() => ueberfahren(name)}
    >
      {t(schluessel)}
    </button>
  {/each}

  <!-- Two entries instead of one: local and cloud have nothing in common
       except the parameter panel. One window that loads AND ticks AND
       manages keys has three jobs; two windows with one each are two
       modules that need to know nothing about one another.

       Local comes first because local is the normal case. -->
  <button
    class="punkt"
    class:offen={zustand.lokalOffen}
    onclick={(e) => {
      e.stopPropagation()
      offen = null
      zustand.lokalOffen = true
    }}
  >
    {t('menue.lokal')}
  </button>

  <button
    class="punkt"
    class:offen={zustand.cloudOffen}
    onclick={(e) => {
      e.stopPropagation()
      offen = null
      zustand.cloudOffen = true
    }}
  >
    {t('menue.cloud')}
  </button>

  <!-- Tools, after the two that compute and before the program itself:
       first what thinks, then what it may reach for, then the machinery.
       It is its own entry and not a corner of the settings because it is
       the thing you change while working, not while setting up. -->
  <button
    class="punkt"
    class:offen={zustand.werkzeugeOffen}
    onclick={(e) => {
      e.stopPropagation()
      offen = null
      zustand.werkzeugeOffen = true
    }}
  >
    {t('menue.werkzeuge')}
  </button>

  <!-- Settings is NOT a menu but a direct
       button: the old dropdown was just a router to one and the same
       window — three choices to get into the same menu
       made no sense. -->
  <button
    class="punkt"
    onclick={(e) => {
      e.stopPropagation()
      offen = null
      einstellungenOeffnen()
    }}
    onmouseenter={() => (offen = null)}
  >
    {t('menue.settings')}
  </button>

  <!-- The manual: its own page, deliberately outside
       the app — it should be able to stay open next to the app. As an
       icon at the right edge so it no longer occupies menu space. -->
  <span class="serverblick">
    {#if serverBlick.laeuft && serverBlick.belegt}
      <span class="blickwort">{t('modell.vram_belegt')}:</span>
      <span class="blickwert">{serverBlick.belegt} GB</span>
    {/if}
    <span class="blickwort">{t('modell.server_status_label')}:</span>
    <span class="blickpunkt" class:an={serverBlick.laeuft} role="img"
          aria-label={serverBlick.laeuft ? t('status.erreichbar') : t('modell.server_aus')}></span>
  </span>

  <button
    class="hilfe"
    aria-label={t('menue.hilfe')}
    title={t('menue.hilfe')}
    onclick={(e) => {
      e.stopPropagation()
      offen = null
      window.open('https://exe-hq.net/docs/', '_blank')
    }}
  >
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9.2 9a2.8 2.8 0 1 1 4 2.55c-.9.42-1.2 1.05-1.2 2.05v.4" />
      <path d="M12 17.6 V17.7" />
    </svg>
  </button>
</div>

{#if offen}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div
    class="klapp"
    style="left:{offen === 'chat' ? 40 : 88}px"
    transition:fly={{ y: -6, duration: 150 }}
    onclick={(e) => e.stopPropagation()}
  >
    {#if offen === 'chat'}
      <button onclick={() => { offen = null; neuerChat() }}>{t('chat.neu')}<span class="kuerzel">⌘N</span></button>
      <button onclick={umbenennen}>{t('chat.umbenennen_lang')}</button>
      <button onclick={anheften}>{chat?.pinned ? t('chat.loesen') : t('chat.anheften_lang')}</button>
      <button onclick={letzteKopieren}>{t('menue.letzte_kopieren')}</button>
      <button onclick={() => { offen = null; document.getElementById('suchfeld')?.focus() }}>
        {t('app.suchen')}<span class="kuerzel">⌘K</span>
      </button>
      <hr />
      <button onclick={loeschen}>{t('chat.loeschen_lang')}</button>
    {/if}
  </div>
{/if}

<style>
  .leiste {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 0 10px;
    height: 33px;
    flex: none;
    background: var(--bg-leiste);
    border-bottom: 1px solid var(--linie);
    font-size: 13.5px;
    color: var(--text-leise);
    user-select: none;
    position: relative;
    z-index: 30;
  }
  .punkt {
    padding: 4px 9px;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    border-radius: 6px;
    cursor: default;
    transition: background 0.12s, color 0.12s;
  }
  .punkt:hover,
  .punkt.offen {
    background: var(--linie-stark);
    color: var(--text);
  }
  .seitenleiste-knopf {
    display: none;
    border: none;
    background: none;
    color: var(--text-leise);
    cursor: pointer;
    padding: 4px;
    margin-right: 6px;
  }
  /* The help icon: right-aligned, same restraint as the menu items. */
  .serverblick {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .blickwort {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-still);
  }
  .blickwert {
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 1.5px 8px;
    font: 500 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text);
    white-space: nowrap;
  }
  .blickwort + .blickwort {
    margin-left: 6px;
  }
  /* The dot wears the finished-chat ring and breathes only while the
     server actually runs. Green and red are exactly the two states the
     colour rules reserve them for. */
  .blickpunkt {
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 99px;
    background: var(--rot);
    box-shadow: 0 0 0 1.5px var(--text);
    margin: 0 4px 0 1px;
  }
  .blickpunkt.an {
    background: var(--gruen);
    animation: blickpuls 1.6s ease-in-out infinite;
  }
  @keyframes blickpuls {
    50% { opacity: 0.5; transform: scale(0.85); }
  }
  @media (prefers-reduced-motion: reduce) {
    .blickpunkt.an { animation: none; }
  }
  .hilfe {
    margin-left: 10px;
    display: inline-flex;
    align-items: center;
    border: none;
    background: none;
    color: var(--text-leise);
    padding: 4px 6px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .hilfe:hover {
    background: var(--linie-stark);
    color: var(--text);
  }

  .klapp {
    position: absolute;
    top: 30px;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    padding: 6px;
    min-width: 240px;
    z-index: 29;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
  }
  .klapp > button {
    display: flex;
    width: 100%;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 7px 10px;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
  }
  .klapp > button:hover {
    background: var(--linie);
  }
  .kuerzel {
    color: var(--text-still);
    font-size: 12px;
  }
  hr {
    border: none;
    border-top: 1px solid var(--linie);
    margin: 5px 8px;
  }

  @media (max-width: 720px) {
    .seitenleiste-knopf {
      display: inline-flex;
    }
  }
</style>
