<script>
  import { fly } from 'svelte/transition'
  import { t } from '../lib/texte.svelte.js'
  import {
    zustand, aktuellerChat, chatAendern, chatLoeschen, neuerChat, melde,
    frage, menueFensterOeffnen,
  } from '../lib/zustand.svelte.js'

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

  export function schliessen() {
    offen = null
  }
  export function istOffen() {
    return offen !== null
  }
</script>

<svelte:window onclick={() => (offen = null)} />

<!-- No bar of its own any more: the items sit inline in the ONE header,
     between the wordmark and the status group — the same single band the
     sibling programs wear. The dropdown anchors to this block. -->
<div class="menuepunkte">
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
      menueFensterOeffnen('lokal')
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
      menueFensterOeffnen('cloud')
    }}
  >
    {t('menue.cloud')}
  </button>

  <!-- The catalogue sits between the two that compute and the machinery:
       it is where a local model comes from, one step before the tools. -->
  <button
    class="punkt"
    class:offen={zustand.katalogOffen}
    onclick={(e) => {
      e.stopPropagation()
      offen = null
      menueFensterOeffnen('katalog')
    }}
  >
    {t('menue.katalog')}
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
      menueFensterOeffnen('werkzeuge')
    }}
  >
    {t('menue.werkzeuge')}
  </button>

  <!-- Settings is no longer in here: it wears the gear at the header's
       right edge, where the sibling programs carry it. -->

  {#if offen}
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <div
      class="klapp"
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
</div>

<style>
  /* An inline block, not a bar: background, height and border belong to
     the one header this sits in. The block anchors the dropdown. */
  .menuepunkte {
    display: flex;
    align-items: center;
    gap: 2px;
    flex: none;
    font-size: 13.5px;
    color: var(--text-leise);
    user-select: none;
    position: relative;
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
  .klapp {
    position: absolute;
    top: 36px;
    left: 0;
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
