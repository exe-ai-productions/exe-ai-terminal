<script>
  /* The strip of module signs at the right edge — always there.

     It replaces the footer the rail carried at first, and the seam that used
     to open it. Both were hover-only: you had to hit a hairline and catch a
     button that appeared once you were on it, which on two screens meant the
     pointer kept sliding onto the neighbouring monitor. Nobody found the CLI
     that way, and nothing told a first-time user the rail existed.

     Signs standing at the edge do that job on their own. The terminal
     sign carries a status dot, so a command running behind a shut panel is
     visible without opening anything. */
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import EEWzeichen from './EEWzeichen.svelte'
  import Modulzeichen from './Modulzeichen.svelte'
  import { leiste, modulWaehlen } from '../lib/arbeitsleiste.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import { laufampel } from '../lib/laufampel.js'
  import { terminal } from '../lib/terminalfenster.svelte.js'
  import { punktfarbe as eewPunktfarbe } from '../lib/eew.svelte.js'
  import { offeneAnzahl } from '../lib/waechter.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'

  /* One size for every stroke sign on this strip, and one larger one for the
     gold mark. Numbers rather than feel: the strip reads as a row only while
     the signs are the same, and the one that differs has to differ on
     purpose. */
  const ZEICHEN_GROESSE = 23
  const EEW_GROESSE = 28

  const MODULE = [
    ['terminal', 'terminal.titel'],
    ['cli', 'cli.titel'],
    ['vorschau', 'vorschau.titel'],
    ['notiz', 'notiz.titel'],
    ['waechter', 'waechter.titel'],
  ]

  /* A finding nobody has dealt with. Yellow, because it is waiting for a
     decision — and it does not breathe: the guardian is not working, it is
     standing there with something to say. */
  const befunde = $derived(offeneAnzahl(zustand.aktiverChat))

  /* The state of the last run, as a colour — read from the same place the
     panel reads it, so the strip and the entry one click away can never
     disagree about the same run. */
  const laufzustand = $derived.by(() => {
    const letzte = terminal.laeufe[terminal.laeufe.length - 1]
    return letzte ? laufampel(letzte.zustand) : null
  })
</script>

<div class="rand">
  {#each MODULE as [name, beschriftung] (name)}
    <button
      class="zeichen"
      class:aktiv={leiste.offen && leiste.modul === name}
      onclick={() => modulWaehlen(name)}
      title={t(beschriftung)}
      aria-label={t(beschriftung)}
      aria-pressed={leiste.offen && leiste.modul === name}
    >
      {#if name === 'waechter'}
        <EEWzeichen groesse={EEW_GROESSE} />
      {:else}
        <Modulzeichen modul={name} groesse={ZEICHEN_GROESSE} />
      {/if}
      {#if name === 'terminal' && laufzustand}
        <span class="punkt"><Leuchtpunkt farbe={laufzustand} groesse={6} /></span>
      {:else if name === 'waechter'}
        <!-- The dot says whether the thing is switched on and answering, and
             a standing finding wins over that: something waiting for you is
             the more urgent of the two facts. -->
        <span class="punkt">
          <Leuchtpunkt farbe={befunde ? 'gelb' : eewPunktfarbe()} groesse={6} />
        </span>
      {/if}
    </button>
  {/each}
  <!-- Room below for whatever docks here next. -->
  <span class="frei"></span>
</div>

<style>
  .rand {
    flex: none;
    width: 52px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 8px 0;
    border-left: 1px solid var(--linie);
    background: var(--bg-leiste);
  }
  /* One group, one size — every sign is the same square, whatever it
     shows. The square grew with the strip: the gold mark is 28 across, and a
     30px box left it nothing to breathe in. */
  .zeichen {
    position: relative;
    width: 38px;
    height: 38px;
    flex: none;
    display: grid;
    place-items: center;
    border: none;
    border-radius: 9px;
    background: none;
    color: var(--text-still);
    padding: 0;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .zeichen:hover { background: var(--bg-erhoben); color: var(--text-leise); }
  .zeichen.aktiv { background: var(--bg-erhoben); color: var(--text); }
  /* The dot sits on the sign's corner, outside the glyph — a run reports
     itself without redrawing the mark. */
  .punkt {
    position: absolute;
    top: 1px;
    right: 1px;
    display: grid;
    place-items: center;
  }
  .frei { flex: 1; }

  /* On a narrow screen the chat needs its whole width. */
  @media (max-width: 720px) {
    .rand { display: none; }
  }
</style>
