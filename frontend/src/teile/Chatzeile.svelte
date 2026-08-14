<script>
  /* One row of the chat list.

     It used to stand twice in the sidebar, once for the pinned chats and
     once for the rest — two copies that had to be changed in step, and
     every state the row learns would have doubled that work. Here it is
     one thing, and the difference between the two lists is a single flag.

     The row reads from left to right in the order one needs it: what the
     conversation is called, then the pin, then what the conversation is
     doing right now. The status dot sits last on purpose — at the right
     edge it lines up down the whole list, and since the invitation pin
     keeps its box even while invisible, nothing shifts under the hand. */
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import { t } from '../lib/texte.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'
  import { ringFarbe } from '../lib/chatringe.svelte.js'

  /* What each colour is called. On the module and not inside the component:
     a list of thirty chats would otherwise build thirty copies of the same
     four entries. */
  const RINGTEXTE = {
    gelb: 'chat.wartet_auf_dich',
    blau: 'chat.laeuft_gerade',
    rot: 'chat.lauf_gescheitert',
    gruen: 'chat.antwort_fertig',
  }

  let { chat, oeffnen, menue, anheften } = $props()

  const farbe = $derived(ringFarbe(chat.id))
  const punkttext = $derived(RINGTEXTE[farbe] ? t(RINGTEXTE[farbe]) : '')
</script>

<button
  class="chat"
  class:aktiv={chat.id === zustand.aktiverChat}
  onclick={() => oeffnen(chat.id)}
  oncontextmenu={(e) => menue(e, chat)}
>
  <span class="titel">{chat.title}</span>
  <!-- The pin releases on click — no detour through the right-click menu
       when the symbol is standing there anyway. On an unpinned row it is
       an invitation and only shows under the hand; span instead of
       button, because a button inside a button is forbidden. -->
  <span
    class="nadel"
    class:einladung={!chat.pinned}
    role="button"
    tabindex="0"
    title={chat.pinned ? t('chat.loesen') : t('chat.anheften')}
    aria-label={chat.pinned ? t('chat.loesen') : t('chat.anheften')}
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
  <span class="punkt" title={punkttext} aria-label={punkttext}>
    <Leuchtpunkt {farbe} groesse={7} />
  </span>
</button>

<style>
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
  /* The dot sits INSIDE the row, not on its edge: right-aligned against
     the row's own padding, centred on the row's height, the same distance
     from the edge whether the row is hovered or not. It used to hang half
     on the tile's border, which read as a mark stuck to the list rather
     than a state of the row.

     The box is wider than the dot so its glow has somewhere to fall
     without touching the row's edge. */
  .punkt {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 15px;
    height: 15px;
    margin-left: 2px;
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
     every chat row would carry a symbol that indicates nothing. It keeps
     its box while hidden, so the dot behind it does not travel. */
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
</style>
