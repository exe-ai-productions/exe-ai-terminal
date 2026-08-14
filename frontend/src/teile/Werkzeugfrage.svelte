<script>
  import { rollfade } from '../lib/rollfade.js'
  /* The confirmation before a tool touches anything (1.6).

     It hangs right above the input field and is exactly as wide — the
     width comes from the zone in the input bar, no second number lives
     here. The height follows the content: with one argument the box is
     two lines tall, with ten it grows along and only starts scrolling at
     30 percent of the window height. Same rule as for the input field
     next to it.

     Deliberately no popup with a veil: while writing, the gaze is at the
     bottom, and a window above everything would cover the history you
     need right now for judging. */
  import { fly, slide } from 'svelte/transition'
  import { backOut, cubicIn } from 'svelte/easing'
  import { hervorheben, maskieren } from '../lib/einfaerben.js'
  import { t } from '../lib/texte.svelte.js'

  let { frage, antworten } = $props()

  let kasten = $state(null)

  /* Folded by default. A `cat > game.js << EOF` with two
     hundred lines of code filled the whole window and pushed the two buttons
     out of reach — you cannot judge what you cannot see the end of. Folded,
     the box states what is about to happen in one line; whoever wants the
     detail unfolds it with the same chevron the reasoning and the tool rows
     use. */
  let offen = $state(false)

  /* Arguments as a list of pairs. Strings stand raw, everything else as
     JSON — otherwise you'd read "[object Object]" for a number. */
  const zeilen = $derived(
    Object.entries(frage.argumente ?? {}).map(([schluessel, wert]) => [
      schluessel,
      typeof wert === 'string' ? wert : JSON.stringify(wert),
    ]),
  )

  /* The thing the decision rests on gets a surface of its own, always
     visible: the command, whole, in monospace, coloured by the same bash
     scheme the chat uses. The grey ellipsis line in the head could be read
     but not judged — a command cut off at 68 characters hides exactly the
     part worth refusing.

     For run_command that is the command; for any other tool the first
     argument, which is the one that says what it will touch. */
  const befehl = $derived(String(frage.argumente?.command ?? zeilen[0]?.[1] ?? ''))
  const befehlFarbig = $derived(befehl ? hervorheben(befehl, 'bash') : '')

  /* The reason names a path, and a path is read letter by letter — so it
     stands in monospace inside the sentence. The value travels alongside
     the sentence, so nothing has to be guessed out of it. */
  const grundText = $derived.by(() => {
    const satz = maskieren(frage.grund || '')
    const wert = frage.grundWert || ''
    if (!wert) return satz
    return satz.replace(maskieren(wert), `<span class="pfad">${maskieren(wert)}</span>`)
  })

  /* The box takes the keyboard to itself while it is open: Escape
     declines. Deliberately, the finger rests on neither of the two
     buttons — an accidental Enter must not execute anything. */
  $effect(() => {
    kasten?.focus()
  })

  function taste(ereignis) {
    if (ereignis.key === 'Escape') {
      ereignis.stopPropagation()
      antworten(false)
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_to_interactive_role -->
<div
  class="frage"
  bind:this={kasten}
  tabindex="-1"
  role="alertdialog"
  aria-label={t('werkzeug.bestaetigen')}
  onkeydown={taste}
  in:fly={{ y: 14, duration: 300, easing: backOut }}
  out:fly={{ y: 8, duration: 160, easing: cubicIn }}
>
  <!-- The whole head is the fold toggle: chevron, name, and while folded the
       one line that says what is about to run. -->
  <button
    class="kopf"
    class:offen
    type="button"
    onclick={() => (offen = !offen)}
    aria-expanded={offen}
    disabled={!zeilen.length}
  >
    <span class="winkel">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 6l6 6-6 6" />
      </svg>
    </span>
    <!-- Two parts instead of one sentence: the name stays bold, and in
         English the verb goes before it ("Run websuche?") instead of
         after. -->
    <span class="titel">{t('werkzeug.frage_vor')}<b>{frage.name}</b>{t('werkzeug.frage_nach')}</span>
  </button>

  <!-- The command itself, never folded away. -->
  {#if befehl}
    <div class="befehl" use:rollfade><span class="stumm">$</span> {@html befehlFarbig}</div>
  {/if}

  <!-- The reason, when there is one. It carries the waiting colour of the
       house — the only colour in this box, and only when something really
       reaches beyond what was shared. A tool that is simply configured to
       always ask has no reason to give and shows none. -->
  {#if frage.grund}
    <p class="grund">
      <svg width="13" height="13" viewBox="0 0 64 64" fill="none" stroke="currentColor"
           stroke-width="5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M32 11 L56 52 H8 Z" />
        <path d="M32 28 V38" stroke-width="4.5" />
        <path d="M32 44.5 V45" />
      </svg>
      <span>{@html grundText}</span>
    </p>
  {/if}

  {#if offen}
    {#if zeilen.length}
      <dl class="argumente" use:rollfade transition:slide={{ duration: 200 }}>
        {#each zeilen as [schluessel, wert] (schluessel)}
          <dt>{schluessel}</dt>
          <dd>{wert}</dd>
        {/each}
      </dl>
    {:else}
      <p class="ohne">{t('werkzeug.ohne_angaben')}</p>
    {/if}
  {/if}

  <div class="fuss">
    <!-- The standing yes sits apart on the left: it decides more than this
         one call, so it must not sit where the routine click lands. -->
    <button class="knopf immer" onclick={() => antworten(true, true)}>{t('werkzeug.immer_erlauben')}</button>
    <button class="knopf" onclick={() => antworten(false)}>{t('werkzeug.ablehnen')}</button>
    <button class="knopf wichtig" onclick={() => antworten(true)}>{t('werkzeug.ausfuehren')}</button>
  </div>
</div>

<style>
  /* The brightest line in the house, same as the folder pills — one frame
     for everything that hangs above the field. The
     blue left bar is gone: it read as an alert, and asking a question is not
     alarming. Radius 18 stays, that is the window radius of the input field
     it sits on. */
  .frage {
    width: 100%;
    border: 1px solid var(--text-leise);
    border-radius: 18px;
    background: var(--bg-erhoben);
    padding: 11px 13px 9px;
    outline: none;
  }
  /* The whole head folds. It is a button but must not look like one — no
     frame, no background, only the pointer says it can be clicked. */
  .kopf {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    border: none;
    background: none;
    padding: 0;
    font: inherit;
    font-size: 13.5px;
    color: var(--text);
    text-align: left;
    cursor: pointer;
  }
  .kopf:disabled {
    cursor: default;
  }
  .winkel {
    flex: none;
    display: inline-flex;
    color: var(--text-leise);
  }
  .winkel svg {
    transition: transform 0.18s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .kopf.offen .winkel svg {
    transform: rotate(90deg);
  }
  .kopf:disabled .winkel {
    opacity: 0.35;
  }
  .titel {
    flex: none;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .titel b {
    font-weight: 600;
  }
  /* The command, on a surface of its own. It is what the decision rests
     on, so it is never folded away and never cut off: it wraps, grows with
     the content, and only starts scrolling at a third of the window — the
     same rule the input field beside it follows. */
  .befehl {
    margin: 9px 0 0;
    padding: 7px 10px;
    background: var(--bg);
    border: 1px solid var(--linie);
    border-radius: 9px;
    font-family: var(--schrift-fest);
    font-size: 12px;
    line-height: 1.55;
    color: var(--text);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    max-height: 30vh;
    overflow-y: auto;
  }
  .befehl .stumm {
    color: var(--text-still);
  }
  /* The reason. Yellow is the house's waiting-and-caution colour (the job
     tiles and the context meter use it for the same thing), and reaching
     outside the shared folders is exactly that. Only the form changed: a
     quiet surface instead of a line of full yellow text, the way the house
     rule wants colour on a surface and never behind running text. */
  .grund {
    display: flex;
    align-items: center;
    gap: 7px;
    margin: 9px 0 0;
    padding: 7px 10px;
    border-radius: 9px;
    background: color-mix(in srgb, var(--gelb) 12%, var(--bg-erhoben));
    font-size: 12px;
    line-height: 1.45;
    color: var(--text);
  }
  .grund svg {
    flex: none;
    color: var(--gelb);
  }
  .grund :global(.pfad) {
    font-family: var(--schrift-fest);
    font-size: 11.5px;
  }
  .grund span {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  /* Two columns: the name stays narrow, the value gets the rest and may
     wrap. Only with lots of content does a bar appear — before that the
     box simply grows along. */
  .argumente {
    margin: 8px 0 0;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 2px 10px;
    font-size: 12.5px;
    line-height: 1.5;
    max-height: 30vh;
    overflow-y: auto;
    overflow-x: hidden;
  }
  dt {
    color: var(--text-still);
    font-family: var(--schrift-fest);
    font-size: 11.5px;
    padding-top: 1px;
    white-space: nowrap;
  }
  /* Unfolded, the full value carries the same weight as the folded preview —
     it is the same thing, only longer. */
  dd {
    margin: 0;
    min-width: 0;
    color: var(--text);
    font-family: var(--schrift-fest);
    font-size: 12px;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
  }
  .ohne {
    margin: 6px 0 0;
    font-size: 12.5px;
    color: var(--text-still);
  }

  .fuss {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 10px;
  }
  /* The same buttons as in the system-prompt window — no second pattern. */
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 6px 14px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s, transform 0.08s, opacity 0.12s;
  }
  .knopf:hover {
    background: var(--linie);
  }
  .knopf:active {
    transform: scale(0.975);
  }
  /* Quieter than the pair on the right, and pushed to the far edge — a
     bigger decision deserves a deliberate reach, not a routine click. */
  .immer {
    margin-right: auto;
    border-color: var(--linie);
    color: var(--text-still);
  }
  .immer:hover {
    color: var(--text);
  }
  .wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .wichtig:hover {
    background: var(--text);
    opacity: 0.88;
  }
</style>
