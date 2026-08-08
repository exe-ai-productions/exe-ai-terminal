<script>
  /* A catalogue to tick off: search field, one line per entry, a cross.

     Its own component because it is not the cloud window's business how a
     long list becomes usable. Nothing is filtered or sorted by name — a
     provider does not say which of its models are good for talking, and what
     we cannot judge we do not sort out. The search field is enough: typing
     `gpt` turns 124 lines into thirty. */
  import { t } from '../lib/texte.svelte.js'

  /* `istFest` marks entries that cannot be unticked — the configuration named
     them, and a cross that springs back would be a control that lies. */
  let { eintraege = [], istAn, istFest = () => false, onschalten, onalle } = $props()

  let suche = $state('')

  const gefiltert = $derived(
    suche.trim()
      ? eintraege.filter((e) => e.name.toLowerCase().includes(suche.trim().toLowerCase()))
      : eintraege,
  )
  const anzahlAn = $derived(eintraege.filter(istAn).length)
  const alleAn = $derived(eintraege.length > 0 && anzahlAn === eintraege.length)
</script>

<div class="suche">
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="2.2" stroke-linecap="round">
    <circle cx="10.5" cy="10.5" r="7" /><path d="M16 16 L21 21" />
  </svg>
  <input bind:value={suche} placeholder={t('app.suchen')} aria-label={t('app.suchen')} />
</div>

<div class="liste">
  {#each gefiltert as eintrag (eintrag.id)}
    <button
      class="zeile"
      class:fest={istFest(eintrag)}
      disabled={istFest(eintrag)}
      onclick={() => onschalten(eintrag, !istAn(eintrag))}
    >
      <span class="kreuz" class:an={istAn(eintrag)}>
        {#if istAn(eintrag)}
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 12.5 L9.5 18 L20 6" />
          </svg>
        {/if}
      </span>
      <span class="name">{eintrag.name}</span>
      {#if istFest(eintrag)}<span class="woher">{t('liste.aus_konfiguration')}</span>{/if}
    </button>
  {:else}
    <p class="leer">{t('liste.nichts_gefunden')}</p>
  {/each}
</div>

<div class="fuss">
  <span>{t('liste.gewaehlt_zahl').replace('{zahl}', anzahlAn)}</span>
  <button class="textknopf" onclick={() => onalle(!alleAn)}>
    {alleAn ? t('liste.alle_abwaehlen') : t('liste.alle_waehlen')}
  </button>
</div>

<style>
  .suche {
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid var(--linie-stark);
    /* 9 px — small control, see the radius palette. */
    border-radius: 9px;
    padding: 5px 11px;
    color: var(--text-still);
    margin-bottom: 8px;
  }
  .suche input {
    flex: 1;
    min-width: 0;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 12.5px;
    outline: none;
  }

  /* No visible scrollbars anywhere; the list runs out softly at the bottom so
     a half-cut row does not read as a bug. */
  .liste {
    max-height: 252px;
    overflow-y: auto;
    scrollbar-width: none;
    mask-image: linear-gradient(to bottom, #000 88%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, #000 88%, transparent 100%);
  }
  .liste::-webkit-scrollbar { display: none; }

  .zeile {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    text-align: left;
    border: none;
    border-bottom: 1px solid var(--linie);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 7px 4px;
    cursor: pointer;
  }
  .zeile:last-child { border-bottom: 0; }
  .zeile:hover:not(.fest) { background: var(--linie); }
  .zeile.fest { cursor: default; }
  .woher { margin-left: auto; font-size: 10.5px; color: var(--text-still); }
  .name {
    font-family: var(--schrift-fest);
    font-size: 12.5px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kreuz {
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1px solid var(--linie-stark);
    flex: none;
    display: grid;
    place-items: center;
    color: var(--bg-erhoben);
  }
  .kreuz.an { background: var(--text); border-color: var(--text); }

  .leer { color: var(--text-still); font-size: 12.5px; padding: 10px 4px; }

  .fuss {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 10px;
    font-size: 12px;
    color: var(--text-still);
  }
  .textknopf {
    background: none;
    border: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12px;
    cursor: pointer;
    padding: 0;
  }
  .textknopf:hover { color: var(--text); }
</style>
