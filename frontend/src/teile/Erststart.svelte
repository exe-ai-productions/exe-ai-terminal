<script>
  /* The first start — the one window that makes the terminal yours.

     It grows straight out of the house mark in the middle of the empty
     chat and shrinks back into it on Done: the program does not open a
     dialog, its own mark comes toward you. Shown once per installation;
     everything it asks lives in the settings afterwards. */
  import { t, texte, spracheWaehlen } from '../lib/texte.svelte.js'
  import Wortmarke from './Wortmarke.svelte'
  import {
    begruessung, anredeSpeichern, erststartNoetig, erststartErledigt,
  } from '../lib/begruessung.svelte.js'

  let { modus = $bindable('auto') } = $props()

  const MODI = [
    ['auto', 'einstellungen.auto'],
    ['hell', 'einstellungen.hell'],
    ['dunkel', 'einstellungen.dunkel'],
  ]

  let phase = $state('aus') // aus | klein | auf | zu
  let name = $state('')
  // The pill mirrors the language that is actually loaded — never a guess:
  // a pill that claims German over an English window would lie.
  let sprachwahl = $state(texte.sprache)

  $effect(() => {
    sprachwahl = texte.sprache
  })

  $effect(() => {
    if (phase === 'aus' && erststartNoetig()) {
      name = begruessung.vorschlag
      phase = 'klein'
      requestAnimationFrame(() => requestAnimationFrame(() => (phase = 'auf')))
    }
  })

  function spracheStellen(wert) {
    sprachwahl = wert
    spracheWaehlen(wert)
  }

  async function fertig() {
    erststartErledigt()
    phase = 'zu'
    await anredeSpeichern(name || begruessung.vorschlag, true)
    setTimeout(() => (phase = 'aus'), 600)
  }
</script>

{#if phase !== 'aus'}
  <div class="schleier" class:da={phase === 'auf'}>
    <div class="fenster" class:klein={phase !== 'auf'}>
      <div class="kopf">
        <Wortmarke hoehe={40} mitText={false} />
        <div class="titel">{t('erststart.titel')}</div>
        <p class="satz">{t('erststart.satz')}</p>
      </div>
      <div class="kachel">
        <span class="strich"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3l4 4L8 20l-5 1 1-5L17 3z" /></svg></span>
        <div class="w"><div class="t">{t('erststart.anrede')}</div><div class="u">{t('erststart.anrede_unter')}</div></div>
        <input class="feld" bind:value={name} placeholder={begruessung.vorschlag} aria-label={t('erststart.anrede')} />
      </div>
      <div class="kachel">
        <span class="strich"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8 8 0 1 1-4-6.9" /><path d="M15 2l6 1-4 4" /></svg></span>
        <div class="w"><div class="t">{t('erststart.sprache')}</div></div>
        <div class="segment">
          <button aria-pressed={sprachwahl === 'de'} onclick={() => spracheStellen('de')}>{t('einstellungen.sprache_deutsch')}</button>
          <button aria-pressed={sprachwahl === 'en'} onclick={() => spracheStellen('en')}>{t('einstellungen.sprache_englisch')}</button>
        </div>
      </div>
      <div class="kachel">
        <span class="strich"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" /></svg></span>
        <div class="w"><div class="t">{t('erststart.erscheinung')}</div></div>
        <div class="segment">
          {#each MODI as [wert, beschriftung] (wert)}
            <button aria-pressed={modus === wert} onclick={() => (modus = wert)}>{t(beschriftung)}</button>
          {/each}
        </div>
      </div>
      <div class="fuss">
        <span class="lokal"><span class="punkt"><i></i><em></em></span> {t('erststart.alle_daten')}</span>
        <button class="knopf" onclick={fertig}>{t('erststart.fertig')}</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .schleier {
    position: fixed;
    inset: 0;
    z-index: 60;
    display: grid;
    place-items: center;
    background: transparent;
    transition: background 0.4s ease;
  }
  .schleier.da {
    background: color-mix(in srgb, var(--bg) 55%, transparent);
  }
  .fenster {
    width: min(440px, calc(100vw - 48px));
    border: 1px solid var(--linie-stark);
    border-radius: 16px;
    background: var(--bg-erhoben);
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.55);
    padding: 22px 22px 18px;
    transition: transform 0.62s cubic-bezier(0.3, 1.18, 0.35, 1), opacity 0.4s ease;
    transform: scale(1);
    transform-origin: center;
  }
  /* Collapsed it sits as a point on the house mark, a hair above centre —
     the window breathes out of the mark and back into it. */
  .fenster.klein {
    transform: translateY(-26px) scale(0.03);
    opacity: 0;
    pointer-events: none;
    transition: transform 0.5s cubic-bezier(0.6, 0, 0.8, 0.4), opacity 0.34s 0.14s ease;
  }
  .kopf { display: flex; flex-direction: column; align-items: center; gap: 7px; margin-bottom: 16px; }
  .titel { font: 700 15px var(--schrift-fest); letter-spacing: 0.22em; }
  .satz { color: var(--text-still); font-size: 12.5px; margin: 0; }
  .kachel {
    display: flex; align-items: center; gap: 12px;
    border: 1px solid var(--linie); border-radius: 12px; background: var(--bg);
    padding: 0 13px; height: 54px; margin-bottom: 8px;
  }
  .strich { flex: none; color: var(--text-still); display: grid; place-items: center; }
  .kachel .w { flex: 1; min-width: 0; }
  .kachel .t { font-weight: 600; font-size: 13px; }
  .kachel .u { font-size: 11px; color: var(--text-still); }
  .feld {
    border: 1px solid var(--linie-stark); border-radius: 9px; background: var(--bg-erhoben);
    color: var(--text); font: 13px var(--schrift); padding: 6px 11px; width: 130px;
  }
  .segment {
    display: flex; border: 1px solid var(--linie); border-radius: 9px;
    background: var(--bg-erhoben); padding: 2px;
  }
  .segment button {
    border: none; background: none; color: var(--text-still);
    font: 600 11.5px var(--schrift); padding: 4px 10px; border-radius: 7px; cursor: pointer;
  }
  .segment button[aria-pressed='true'] { background: var(--bg); color: var(--text); }
  .fuss { display: flex; align-items: center; gap: 10px; margin-top: 14px; }
  .lokal { display: flex; align-items: center; gap: 7px; font-size: 11.5px; color: var(--text-still); flex: 1; }
  .punkt { display: inline-grid; place-items: center; width: 12px; height: 12px; flex: none; }
  .punkt i { grid-area: 1/1; width: 7px; height: 7px; border-radius: 99px; background: var(--gruen); }
  .punkt em { grid-area: 1/1; width: 11px; height: 11px; border-radius: 99px; border: 1.2px solid var(--text); }
  .knopf {
    border: 1px solid var(--text); background: var(--text); color: var(--bg);
    font: 600 13px var(--schrift); border-radius: 9px; padding: 7px 18px; cursor: pointer;
  }
  .knopf:hover { opacity: 0.88; }
</style>
