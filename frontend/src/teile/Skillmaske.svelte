<script>
  /* The skill list in the settings: what exists, and which of them the model
     may reach for by itself.

     One list for both places. Where a skill comes from only matters here,
     where it decides what a change does — a shipped one is copied before it
     is touched, so the next update walks past the copy instead of taking it
     back. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde } from '../lib/zustand.svelte.js'
  import { skillsLaden } from '../lib/skills.svelte.js'
  import Schalter from './Schalter.svelte'
  import Werkzeugzeichen from './Werkzeugzeichen.svelte'

  let zeilen = $state([])
  let selbstWaehlen = $state(true)

  /* Only the automatic ones cost anything, and only they are counted. The
     number is here because the cost is invisible otherwise: it is paid on
     every request, in a place nobody looks. */
  const automatisch = $derived(zeilen.filter((z) => z.auto).length)

  /* Loaded here rather than by whoever shows the mask: the component does
     not exist yet at the moment the section is switched to, so a call from
     outside lands on nothing. */
  $effect(() => {
    laden()
  })

  async function laden() {
    try {
      zeilen = await api.skillsVerwaltung()
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
    try {
      const stand = await api.einstellungAufgeloest('skills_auto')
      if (stand?.wert && typeof stand.wert.an === 'boolean') selbstWaehlen = stand.wert.an
    } catch {
      /* No setting means the default, and the default is on. */
    }
  }

  async function selbstSchalten(an) {
    const vorher = selbstWaehlen
    selbstWaehlen = an
    try {
      await api.einstellungSetzen('global', 'skills_auto', { an })
    } catch (fehler) {
      selbstWaehlen = vorher
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

  async function autoSchalten(zeile, an) {
    const vorher = zeile.auto
    zeile.auto = an
    try {
      const neu = await api.skillAuto(zeile.name, an)
      Object.assign(zeile, neu)
      skillsLaden()
    } catch (fehler) {
      zeile.auto = vorher
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

  async function zuruecksetzen(zeile) {
    try {
      await api.skillZuruecksetzen(zeile.name)
      await laden()
      skillsLaden()
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }
</script>

<div class="kopf">
  <span>{t('skills.wieviele', { anzahl: automatisch })}</span>
</div>

<div class="schalterzeile">
  <div class="beschriftung">
    {t('skills.selbst')}
    <span class="hinweis">{t('skills.selbst_hinweis')}</span>
  </div>
  <Schalter an={selbstWaehlen} beschriftung={t('skills.selbst')} onschalten={selbstSchalten} />
</div>

{#if !zeilen.length}
  <p class="leer">{t('skills.keine')}</p>
{/if}

{#each zeilen as zeile (zeile.name)}
  <div class="zeile">
    <!-- Through the server, exactly as the chat row resolves it: the answer
         has to be the same everywhere it is asked. -->
    <Werkzeugzeichen server="skills" />
    <div class="mitte">
      <div class="name">
        /{zeile.name}
        {#if zeile.mitgeliefert && zeile.eigen}
          <span class="vermerk">{t('skills.geaendert')}</span>
        {/if}
      </div>
      <div class="was">{zeile.beschreibung}</div>
    </div>
    {#if zeile.mitgeliefert && zeile.eigen}
      <button class="zurueck" onclick={() => zuruecksetzen(zeile)}>
        {t('skills.zuruecksetzen')}
      </button>
    {/if}
    <Schalter
      an={zeile.auto}
      beschriftung={t('skills.selbst')}
      onschalten={(an) => autoSchalten(zeile, an)}
    />
  </div>
{/each}

<style>
  .kopf {
    font-size: 12.5px;
    color: var(--text-still);
    padding-bottom: 12px;
  }
  .schalterzeile {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 0;
    border-top: 1px solid var(--linie);
  }
  .beschriftung {
    font-size: 13.5px;
    min-width: 0;
  }
  .hinweis {
    display: block;
    font-size: 12px;
    color: var(--text-still);
    margin-top: 2px;
  }
  .zeile {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 11px 0;
    border-top: 1px solid var(--linie);
  }
  .mitte {
    flex: 1;
    min-width: 0;
  }
  .name {
    font-size: 13.5px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .was {
    font-size: 12px;
    color: var(--text-still);
    margin-top: 1px;
  }
  /* Brightness, not colour: having taken a shipped skill over is a fact
     about it, not a state it is in. */
  .vermerk {
    font-size: 11px;
    color: var(--text-still);
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 0 7px 1px;
  }
  .zurueck {
    border: 1px solid var(--linie-stark);
    background: none;
    border-radius: 99px;
    color: var(--text-leise);
    font: inherit;
    font-size: 12px;
    padding: 3px 11px 4px;
    cursor: pointer;
    flex: none;
  }
  .zurueck:hover {
    color: var(--text);
    border-color: var(--text-still);
  }
  .leer {
    font-size: 13px;
    color: var(--text-still);
    padding: 14px 0 0;
    border-top: 1px solid var(--linie);
    margin: 0;
  }
</style>
