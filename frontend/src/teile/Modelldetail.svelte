<script>
  /* One model up close — opens when a catalogue card is clicked.

     Here the builds (`fassungen`) are laid out: the one that suits the
     machine is pre-picked, the one too large says honestly what it would
     need. The companion line is the promise the download keeps — vision
     and the speed module ride along automatically and are matched to this
     exact build, because the service writes the assignment when it fetches
     them.

     The download, cancel and start actions belong to the parent (Katalog),
     which owns the one download at a time; this view only chooses a build
     and asks. */
  import Hauszeichen from './Hauszeichen.svelte'
  import { t } from '../lib/texte.svelte.js'
  import { passt, brauchtMaschine, passendeFassung } from '../lib/modellempfehlungen.js'

  let {
    karte,
    maschineGb = null,
    statusFuer,
    fortschrittFuer,
    onClose,
    onDownload,
    onCancel,
    onStart,
  } = $props()

  const KANN = {
    winkel: 'katalog.kann_winkel',
    auge: 'katalog.kann_auge',
    gluehbirne: 'katalog.kann_gluehbirne',
    blitz: 'katalog.kann_blitz',
  }

  const empfohlen = $derived(passendeFassung(karte, maschineGb))
  let gewaehlt = $state(null)
  const aktuelle = $derived(gewaehlt ?? empfohlen)

  const status = $derived(statusFuer?.(aktuelle) ?? 'neu')
  const fortschritt = $derived(fortschrittFuer?.(aktuelle) ?? null)

  function passtSatz(fassung) {
    if (passt(fassung, maschineGb)) {
      return fassung === empfohlen
        ? t('katalog.empfohlen_fuer', { gb: maschineGb })
        : t('katalog.passt_fuer', { gb: maschineGb })
    }
    return t('katalog.braucht_maschine', { gb: brauchtMaschine(fassung) })
  }
</script>

<div class="detail">
  <div class="oben">
    <div class="logo">{karte.logo}</div>
    <div class="wer">
      <div class="name">{karte.name}</div>
      <div class="unter">{karte.von} · {aktuelle.datei.replace(/\.gguf$/i, '')}</div>
    </div>
    <div class="zeichenreihe">
      {#each karte.faehigkeiten as f (f)}
        <span class="zeichen" title={t(KANN[f])}><Hauszeichen zeichen={f} groesse="mittel" /></span>
      {/each}
    </div>
  </div>

  <div class="satzlang">{t(karte.langsatz)}</div>

  {#each karte.fassungen as f (f.id + f.datei)}
    <button class="fassung" class:gewaehlt={f === aktuelle} onclick={() => (gewaehlt = f)}>
      <span class="fpunkt" class:an={f === aktuelle}></span>
      <div class="fwer">
        <div class="fname">{f.name}</div>
        <div class="fpasst">{passtSatz(f)}</div>
      </div>
      <span class="fgb">{t('modell.gb', { zahl: f.groesse })}</span>
    </button>
  {/each}

  {#if aktuelle.mmproj || aktuelle.drafter}
    <div class="begleiter">
      {#if aktuelle.mmproj}<span class="zeichen"><Hauszeichen zeichen="auge" groesse="mittel" /></span>{/if}
      {#if aktuelle.drafter}<span class="zeichen"><Hauszeichen zeichen="blitz" groesse="mittel" /></span>{/if}
      {t('katalog.begleiter')}
    </div>
  {/if}

  {#if status === 'laedt'}
    <div class="laufbalken">
      <span class="balken"><i style="width:{fortschritt?.anteil ?? 0}%"></i></span>
      <span class="laufzahl">{fortschritt?.text ?? ''}</span>
    </div>
  {/if}

  <div class="dfuss">
    <button class="knopf" onclick={onClose}>{t('katalog.schliessen')}</button>
    {#if status === 'bereit'}
      <button class="knopf wichtig" onclick={() => onStart?.(aktuelle)}>{t('katalog.starten')}</button>
    {:else if status === 'laedt'}
      <button class="knopf" onclick={onCancel}>{t('katalog.abbrechen')}</button>
    {:else}
      <button class="knopf wichtig" onclick={() => onDownload?.(aktuelle)}>
        {t('katalog.herunterladen_gb', { gb: aktuelle.groesse })}
      </button>
    {/if}
  </div>
</div>

<style>
  .detail {
    max-width: 640px;
    margin: 0 auto;
    padding: 4px 2px;
  }
  .oben {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 12px;
  }
  .logo {
    width: 44px;
    height: 44px;
    flex: none;
    border-radius: 12px;
    border: 1.5px dashed var(--linie-stark);
    color: var(--text-still);
    display: flex;
    align-items: center;
    justify-content: center;
    font: 700 13px var(--schrift);
  }
  .wer {
    min-width: 0;
  }
  .name {
    font: 600 17px var(--schrift);
  }
  .unter {
    font-size: 11.5px;
    color: var(--text-still);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .zeichenreihe {
    margin-left: auto;
    display: flex;
    gap: 9px;
    align-items: center;
    color: var(--text-leise);
  }
  .zeichen {
    display: inline-flex;
  }
  .satzlang {
    font-size: 13px;
    color: var(--text-leise);
    line-height: 1.6;
    margin-bottom: 14px;
  }
  .fassung {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    text-align: left;
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 11px 14px;
    margin-bottom: 7px;
    background: none;
    color: var(--text);
    cursor: pointer;
    font: inherit;
    transition: border-color 0.12s;
  }
  .fassung:hover {
    border-color: var(--linie-stark);
  }
  .fassung.gewaehlt {
    border-color: var(--text);
  }
  /* A chosen build wears the firm dot, the others an outline — a fact of
     which is picked, so no state colour. */
  .fpunkt {
    width: 8px;
    height: 8px;
    border-radius: 99px;
    flex: none;
    border: 1.5px solid var(--linie-stark);
  }
  .fpunkt.an {
    background: var(--text);
    border-color: var(--text);
  }
  .fwer {
    flex: 1;
    min-width: 0;
  }
  .fname {
    font: 600 13px var(--schrift-fest);
  }
  .fpasst {
    font-size: 11px;
    color: var(--text-leise);
    margin-top: 1px;
  }
  .fgb {
    margin-left: auto;
    font: 500 12px var(--schrift-fest);
    color: var(--text-still);
  }
  .begleiter {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-leise);
    padding: 10px 2px 14px;
  }
  .laufbalken {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 2px 0 12px;
  }
  .balken {
    flex: 1;
    height: 5px;
    border-radius: 99px;
    background: var(--linie);
    overflow: hidden;
  }
  .balken i {
    display: block;
    height: 100%;
    background: var(--blau);
    transition: width 0.3s;
  }
  .laufzahl {
    font: 400 11px var(--schrift-fest);
    color: var(--text-still);
    white-space: nowrap;
  }
  .dfuss {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 4px;
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: 600 12.5px var(--schrift);
    padding: 7px 14px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s, opacity 0.12s, transform 0.08s;
  }
  .knopf:hover {
    background: var(--linie);
  }
  .knopf:active {
    transform: scale(0.975);
  }
  .knopf.wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .knopf.wichtig:hover {
    background: var(--text);
    opacity: 0.88;
  }
</style>
