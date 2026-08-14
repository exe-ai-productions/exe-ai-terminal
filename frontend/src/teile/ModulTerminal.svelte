<script>
  /* The terminal module: everything this chat has had done for it.

     It used to show shell commands and nothing else, which meant a
     conversation spent reading and writing files reported "no command has
     run yet" — empty and wrong. Now every tool call of the chat stands
     here, whatever its source: the five built-in ones, the question tool,
     the memory, and every server in the tool window.

     Two weights, and the difference is deliberate. A run with live output
     is a big entry — there is something to watch. Every other call is one
     quiet line: which tool, what about, and how it ended. Together they
     are the chat's small history.


     Why beside the conversation and not inside it: output scrolls faster
     than anyone reads, and a chat that jumps with it cannot be read at all.
     The folded box in the message stays what it was — the record of what
     came out at the end. This is the run itself while it happens.

     Commands are coloured by the bash grammar, program output by its own
     ANSI codes (lib/ansi.js) — one look for everything that shows code. */
  import Hauszeichen from './Hauszeichen.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import { ansiZuHtml } from '../lib/ansi.js'
  import { hervorheben } from '../lib/einfaerben.js'
  import { rollfade } from '../lib/rollfade.js'
  import { t } from '../lib/texte.svelte.js'
  import { laufampel } from '../lib/laufampel.js'
  import { terminal } from '../lib/terminalfenster.svelte.js'
  import { historie } from '../lib/werkzeughistorie.js'
  import Werkzeugzeichen from './Werkzeugzeichen.svelte'
  import { zustand } from '../lib/zustand.svelte.js'

  /* Calls and runs in one list, in the order they happened. The messages
     carry the order; the runs are threaded in where they were started. */
  const eintraege = $derived(historie(zustand.nachrichten, terminal.laeufe))

  let spur = $state(null)

  /* Sticks to the end while nobody scrolls. The moment somebody scrolls up
     it lets go — reading beats watching — and a small button offers the way
     back down. */
  function gerollt() {
    if (!spur) return
    const unten = spur.scrollHeight - spur.scrollTop - spur.clientHeight
    terminal.klebt = unten < 24
  }

  function ansEnde() {
    terminal.klebt = true
    if (spur) spur.scrollTop = spur.scrollHeight
  }

  /* Runs at every new line, because the text of the last run is what
     changes — the effect reads it, so it re-runs with it. */
  $effect(() => {
    const _ = terminal.laeufe.map((l) => l.ausgabe).join('').length + eintraege.length
    if (terminal.klebt && spur) spur.scrollTop = spur.scrollHeight
  })

  const punktfarbe = (lauf) => laufampel(lauf.zustand)
</script>

<div class="spur" bind:this={spur} onscroll={gerollt} use:rollfade>
  {#if !eintraege.length}
    <p class="leer">{t('terminal.leer')}</p>
  {/if}
  {#each eintraege as eintrag, i (eintrag.art === 'lauf' ? `l${eintrag.lauf.lauf}` : `a${i}`)}
    {#if eintrag.art === 'lauf'}
      <div class="lauf">
        <div class="lkopf">
          <Leuchtpunkt farbe={punktfarbe(eintrag.lauf)} groesse={7} />
          {#if eintrag.lauf.art === 'bild'}
            <!-- A drawing job wears the sign the plus menu offers it under, so
                 the eye finds it in the list without reading. Its text is a
                 prompt and not a command, so it is not syntax-coloured. -->
            <span class="bildzeichen"><Hauszeichen zeichen="bild" groesse="klein" /></span>
            <span class="befehl klartext">{eintrag.lauf.befehl}</span>
          {:else}
            <span class="befehl">{@html hervorheben(eintrag.lauf.befehl, 'bash')}</span>
          {/if}
          {#if eintrag.lauf.hintergrund}
            <span class="marke">{t('terminal.hintergrund')}</span>
          {/if}
          <!-- How long it took, once it is over. A picture has no exit code;
               the duration is the one number worth keeping about it. -->
          {#if eintrag.lauf.dauer_sekunden != null}
            <span class="dauer">{t('terminal.dauer', { s: eintrag.lauf.dauer_sekunden })}</span>
          {/if}
        </div>
        {#if eintrag.lauf.ausgabe}
          <pre class="ausgabe">{@html ansiZuHtml(eintrag.lauf.ausgabe)}</pre>
        {/if}
      </div>
    {:else}
      <!-- One quiet line per call: its mark, its name, what it was about,
           and how it ended. The mark comes from the same catalogue the
           chat uses, so a call looks the same in both places. -->
      <div class="aufruf" class:schief={eintrag.fehlgeschlagen}>
        <span class="zeichen"><Werkzeugzeichen name={eintrag.name} server={eintrag.server} /></span>
        <span class="name">{eintrag.name}</span>
        {#if eintrag.kurz}<span class="kurz">{eintrag.kurz}</span>{/if}
        <span class="ausgang">{eintrag.fehlgeschlagen ? '✗' : '✓'}</span>
      </div>
    {/if}
  {/each}
</div>

{#if !terminal.klebt}
  <button class="runter" onclick={ansEnde}>{t('terminal.ans_ende')}</button>
{/if}

<style>
  .spur {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 10px 12px 16px;
  }
  /* A call, in one line. The row is quiet on purpose — thirty of them
     under one another are a history, not thirty announcements. */
  .aufruf {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 2px;
    font-size: 12.5px;
    color: var(--text-leise);
    min-width: 0;
  }
  .aufruf .zeichen {
    flex: none;
    display: inline-flex;
    opacity: 0.8;
    /* Smaller than in the chat: here it identifies a line, there it heads
       a block. */
    --wz-groesse: 15px;
  }
  .aufruf .name {
    font-family: var(--schrift-fest);
    flex: none;
  }
  .aufruf .kurz {
    color: var(--text-still);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .aufruf .ausgang {
    margin-left: auto;
    flex: none;
    color: var(--text-still);
  }
  /* Red only on the outcome mark, not on the whole row: a failed call is
     still a record, and a row shouting in red would make a history of
     ordinary work look like a list of disasters. */
  .aufruf.schief .ausgang {
    color: var(--rot);
  }
  .leer {
    margin: 6px 2px;
    font-size: 13px;
    color: var(--text-still);
  }
  .lauf {
    border-radius: 12px;
    background: var(--bg-erhoben);
    padding: 9px 11px;
    margin-bottom: 8px;
  }
  .lkopf {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .befehl {
    flex: 1;
    min-width: 0;
    font-family: var(--schrift-fest);
    font-size: 12px;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* The sign takes the quiet grey of the line it stands in — it marks the
     kind of run, it does not announce it. */
  .bildzeichen {
    flex: none;
    display: inline-flex;
    color: var(--text-still);
  }
  /* A prompt is prose. Syntax colours on it would claim a structure it
     does not have. */
  .befehl.klartext {
    color: var(--text-leise);
  }
  .dauer {
    flex: none;
    margin-left: auto;
    font-family: var(--schrift-fest);
    font-size: 10.5px;
    color: var(--text-still);
  }
  .marke {
    flex: none;
    font-size: 11px;
    color: var(--text-still);
  }
  .ausgabe {
    margin: 8px 0 0;
    font-family: var(--schrift-fest);
    font-size: 12px;
    line-height: 1.45;
    color: var(--text-leise);
    white-space: pre-wrap;
    word-break: break-word;
  }
  .runter {
    position: absolute;
    left: 50%;
    bottom: 58px;
    transform: translateX(-50%);
    border: 1px solid var(--linie);
    background: var(--bg-erhoben);
    color: var(--text-leise);
    font: inherit;
    font-size: 12px;
    padding: 5px 12px;
    border-radius: 99px;
    cursor: pointer;
  }
  .runter:hover { color: var(--text); }
</style>
