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
  import { zustand, menueFensterOeffnen } from '../lib/zustand.svelte.js'

  /* One size for every stroke sign on this strip, and one larger one for the
     gold mark. Numbers rather than feel: the strip reads as a row only while
     the signs are the same, and the one that differs has to differ on
     purpose. */
  const ZEICHEN_GROESSE = 23
  const EEW_GROESSE = 28
  /* The manual and the settings: their drawings sit well inside their boxes,
     so they take a larger number to read the same size as the module signs. */
  const NEBEN_GROESSE = 31

  const MODULE = [
    ['terminal', 'terminal.titel'],
    ['cli', 'cli.titel'],
    ['vorschau', 'vorschau.titel'],
    ['notiz', 'notiz.titel'],
    ['bilder', 'bilder.titel'],
    ['waechter', 'waechter.titel'],
  ]

  /* A finding nobody has dealt with. Yellow, because it is waiting for a
     decision — and it does not breathe: the guardian is not working, it is
     standing there with something to say. */
  const befunde = $derived(offeneAnzahl(zustand.aktiverChat))

  /* The state of the last run, as a colour — read from the same place the
     panel reads it, so the strip and the entry one click away can never
     disagree about the same run. */
  function einstellungenOeffnen() {
    zustand.promptStart = 'darstellung'
    menueFensterOeffnen('prompt')
  }

  const laufzustand = $derived.by(() => {
    const letzte = terminal.laeufe[terminal.laeufe.length - 1]
    return letzte ? laufampel(letzte.zustand) : null
  })
</script>

{#snippet modulKnopf(name, beschriftung)}
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
{/snippet}

<div class="rand">
  <!-- Everything but Extended Workflow reads from the top down. -->
  {#each MODULE as [name, beschriftung] (name)}
    {#if name !== 'waechter'}
      {@render modulKnopf(name, beschriftung)}
    {/if}
  {/each}
  <!-- Extended Workflow sits at the very bottom of the rail — the thing the
       program is built around gets the anchoring foot, not a slot in the row.
       The spacer pushes it down and leaves room for whatever docks between. -->
  <span class="frei"></span>
  {@render modulKnopf('waechter', 'waechter.titel')}
  <!-- The manual and the settings close the rail. They are not modules and
       open no panel beside it — but they are the two other places a hand
       goes from anywhere in the program, and a header that carried them had
       them sitting among readings that only report. Same size as the signs
       above them, so the column reads as one. -->
  <button
    class="zeichen"
    onclick={() => window.open('https://exe-hq.net/docs/', '_blank')}
    title={t('menue.hilfe')}
    aria-label={t('menue.hilfe')}
  >
    <!-- Drawn larger than the module signs beside it: both of these fill
         far less of their box than a module sign does, so equal numbers made
         them look the smaller of the two. Measured by eye against the row,
         not by the value. -->
    <svg width={NEBEN_GROESSE} height={NEBEN_GROESSE} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" stroke-width="2" stroke-linecap="round"
         stroke-linejoin="round" aria-hidden="true">
      <path d="M9.2 9a2.8 2.8 0 1 1 4 2.55c-.9.42-1.2 1.05-1.2 2.05v.4" />
      <path d="M12 17.6 V17.7" />
    </svg>
  </button>
  <button
    class="zeichen"
    onclick={einstellungenOeffnen}
    title={t('menue.settings')}
    aria-label={t('menue.settings')}
  >
    <!-- The sun-wheel — the house Settings mark the sibling programs wear. -->
    <svg viewBox="0 0 100 100" width={NEBEN_GROESSE} height={NEBEN_GROESSE} fill="none"
         stroke="currentColor" stroke-width="6.5" stroke-linecap="round"
         stroke-linejoin="round" aria-hidden="true">
      <circle cx="50" cy="50" r="16" />
      <path d="M50 22 V32 M50 68 V78 M22 50 H32 M68 50 H78 M30 30 l7 7 M63 63 l7 7 M70 30 l-7 7 M37 63 l-7 7" />
    </svg>
  </button>
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
    /* Shares the sidebar's tone, not the header bar's — the two side rails
       read as one pair, a step lighter than the header. */
    background: var(--bg-seite);
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
