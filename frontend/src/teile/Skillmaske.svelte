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

  /* Writing a skill of one's own: a name and the file's text. The template
     is filled in, not empty, so nobody has to guess the shape. `description`
     is what the list shows; `auto` decides whether it may be reached for
     without being named. */
  let schreibt = $state(false)
  let neuName = $state('')
  let neuInhalt = $state('')
  const VORLAGE = `---
description: What this skill does, in one line.
auto: false
---

Write the instruction here. When this skill is chosen, the model follows
what stands below.
`
  function neuAnfangen() {
    neuName = ''
    neuInhalt = VORLAGE
    schreibt = true
  }
  async function neuSpeichern() {
    const name = neuName.trim()
    if (!name || !neuInhalt.trim()) return
    try {
      await api.skillSchreiben(name, neuInhalt)
      schreibt = false
      await laden()
      skillsLaden()
      melde(t('skills.geschrieben', { name }), 'erfolg')
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

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

{#if schreibt}
  <div class="schreibform">
    <input
      class="namensfeld"
      bind:value={neuName}
      placeholder={t('skills.neu_name')}
      spellcheck="false"
      autocapitalize="off"
    />
    <textarea class="inhaltsfeld" bind:value={neuInhalt} spellcheck="false"></textarea>
    <div class="formfuss">
      <button class="textknopf" onclick={() => (schreibt = false)}>{t('app.abbrechen')}</button>
      <button class="knopf wichtig" disabled={!neuName.trim() || !neuInhalt.trim()} onclick={neuSpeichern}>
        {t('app.sichern')}
      </button>
    </div>
  </div>
{:else}
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

<button class="skillneu" onclick={neuAnfangen}>
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2.2" stroke-linecap="round"><path d="M12 5 V19 M5 12 H19" /></svg>
  {t('skills.schreiben')}
</button>
{/if}

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

  /* The way to a skill of one's own: a dashed tile, plus and word, the same
     shape the agents list uses for a new agent. */
  .skillneu {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    border: 1px dashed var(--linie-stark);
    border-radius: 12px;
    background: none;
    color: var(--text-still);
    font: 600 12.5px var(--schrift);
    padding: 0 12px;
    height: 46px;
    margin-top: 12px;
    cursor: pointer;
    transition: color 0.12s, border-color 0.12s;
  }
  .skillneu:hover {
    color: var(--text);
    border-color: var(--text-still);
  }

  .schreibform {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .namensfeld {
    font: 600 13.5px var(--schrift-fest);
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 8px 12px;
  }
  .inhaltsfeld {
    font: 400 12.5px/1.6 var(--schrift-fest);
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    padding: 10px 12px;
    min-height: 220px;
    resize: vertical;
    width: 100%;
  }
  .formfuss {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 7px 15px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .knopf:hover:not(:disabled) {
    background: var(--linie);
  }
  .knopf.wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .knopf:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .textknopf {
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 7px;
  }
  .textknopf:hover {
    background: var(--linie);
    color: var(--text);
  }
</style>
