<script>
  /* One card in the catalogue gallery — a model, not a file.

     Purely a face: the parent (Katalog) knows what is downloaded, what is
     fetching and what the machine holds, and hands this card its state and
     the buttons' actions. The card draws the name, the maker, the one-line
     description, the capability signs, the facts, and — depending on the
     state — a Download button, a progress bar with Cancel, or the
     In-folder mark with a Start button.

     The machine plaque speaks only when something is off: a card that fits
     stays silent, one that does not names the machine it needs. A plaque on
     every card would say nothing. It is deliberately colourless either way:
     a fit is a fact, not a state, so it wears brightness and a border,
     never one of the four state colours. */
  import Hauszeichen from './Hauszeichen.svelte'
  import EEWzeichen from './EEWzeichen.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import { t } from '../lib/texte.svelte.js'
  import { LOGOS } from '../lib/logos.js'
  import { brauchtMaschine, FAEHIGKEIT_FARBE, SORTE_FARBE, SORTE_LABEL as SORTE } from '../lib/modellempfehlungen.js'

  let {
    karte,
    fassung,
    passt = false,
    maschineGb = null,
    status = 'neu', // 'neu' | 'laedt' | 'bereit'
    fortschritt = null, // { anteil: 0..100, text } while laedt
    onOeffnen,
    onDownload,
    onCancel,
    onStart,
  } = $props()

  /* An image card has no context window and no row of builds — it is one
     file of a class. Guarded so the chat facts (context, build count) never
     read NaN on it. */
  const kontextK = $derived(karte.kontext ? Math.round(karte.kontext / 1024) : 0)
  const bauzahl = $derived(karte.fassungen?.length ?? 1)
  const marke = $derived(karte.marke ? LOGOS[karte.marke] : null)
  const KLASSE = { sdxl: 'katalog.klasse_sdxl', sd15: 'katalog.klasse_sd15' }
  /* An accessory shows its kind instead of a class — that is the one thing
     that tells a VAE from a LoRA from a face detector at a glance. Its labels
     come from the shared SORTE_LABEL map (imported as SORTE). */

  /* Full keys in a map, not built inside t(): a composed t('x_'+f) would
     read as a broken key to the interface-text check. */
  const KANN = {
    werkzeug: 'katalog.kann_winkel',
    auge: 'katalog.kann_auge',
    gluehbirne: 'katalog.kann_gluehbirne',
    blitz: 'katalog.kann_blitz',
    eew: 'katalog.kann_eew',
  }

  /* The accessory's tag colour, used for its corner pill and logo. */
  const farbe = $derived(SORTE_FARBE[karte.sorte] ?? 'var(--text-leise)')

  function halt(e, fn) {
    e.stopPropagation()
    fn?.()
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="karte"
  class:zub={karte.zubehoer}
  role="button"
  tabindex="0"
  onclick={onOeffnen}
  onkeydown={(e) => { if (e.key === 'Enter') onOeffnen?.() }}
>
  {#if karte.zubehoer}
    <!-- The compact accessory card: a coloured tag in the corner, the name on
         one line, maker and size on the next, then one full-width button.
         No VRAM plaque (a companion has no memory cost of its own). -->
    <span class="zpille" style={`color:${farbe};border-color:${farbe}55;background:${farbe}18`}>
      {t(SORTE[karte.sorte] ?? 'katalog.sorte_vae')}
    </span>
    <div class="zlogo" style={`border-color:${farbe}66;color:${farbe}`}>{karte.logo}</div>
    <div class="zname">
      {karte.name}
      {#if karte.klasse}
        <!-- Class-bound accessories (LoRA, VAE) name their class in full
             text colour — an SD-1.5 file on an XL model was a real mishap,
             so the answer stands beside the name, not in fine print. -->
        <span class="zklasse">{t(KLASSE[karte.klasse] ?? 'katalog.klasse_sd15')}</span>
      {/if}
    </div>
    <div class="zinfo">
      <span class="zvon">{karte.von}</span>
      <span class="zgb">{t('modell.gb', { zahl: fassung.groesse })}</span>
    </div>
    {#if status === 'laedt'}
      <div class="laufbalken"><span class="balken"><i style="width:{fortschritt?.anteil ?? 0}%"></i></span></div>
      <button class="knopf still voll" onclick={(e) => halt(e, onCancel)}>{t('katalog.abbrechen')}</button>
    {:else if status === 'bereit'}
      <span class="zda"><Leuchtpunkt farbe="still" groesse={7} /> {t('katalog.im_ordner')}</span>
    {:else}
      <button class="knopf wichtig voll" onclick={(e) => halt(e, onDownload)}>{t('katalog.herunterladen')}</button>
    {/if}
  {:else}
  {#if !passt}
    <span class="plakette">{t('katalog.braucht_maschine', { gb: brauchtMaschine(fassung) })}</span>
  {/if}
  {#if karte.marke === 'exe'}
    <span class="empfohlen">{t('katalog.empfohlen')}</span>
  {/if}

  <div class="oben">
    {#if marke}
      <div class="logo echt" class:eigen={karte.marke === 'exe'}>{#if karte.marke === 'exe'}<svg viewBox="3 3 66 66" width="44" height="44" aria-hidden="true">{@html marke.html}</svg>{:else}<svg viewBox={marke.vb} width="26" height="26" aria-hidden="true">{@html marke.html}</svg>{/if}</div>
    {:else}
      <div class="logo">{karte.logo}</div>
    {/if}
    <div class="wer">
      <div class="name">{karte.name}</div>
      <div class="von">{karte.von}</div>
    </div>
  </div>

  <div class="satz">{t(karte.satz)}</div>

  <div class="zeichenreihe">
    {#if karte.zubehoer}
      <!-- An accessory shows its kind: VAE, LoRA, face detector, projector,
           drafter. That, not a class, is what sets it apart. -->
      <span class="klassepille">{t(SORTE[karte.sorte] ?? 'katalog.sorte_vae')}</span>
    {:else if karte.bild}
      <!-- An image model shows the one sign that decides how it draws: its
           class, which sets the resolution it opens at. -->
      <span class="klassepille">{t(KLASSE[karte.klasse] ?? 'katalog.klasse_sd15')}</span>
    {:else}
      {#each karte.faehigkeiten as f (f)}
        <span class="zeichen" title={t(KANN[f])} style={FAEHIGKEIT_FARBE[f] ? `color:${FAEHIGKEIT_FARBE[f]}` : undefined}>{#if f === 'eew'}<EEWzeichen groesse={22} />{:else}<Hauszeichen zeichen={f} groesse="mittel" />{/if}</span>
      {/each}
    {/if}
  </div>

  <div class="fakten">
    <span>{t('modell.gb', { zahl: fassung.groesse })}</span>
    {#if karte.bild}
      <span>·</span>
      <span>{t('katalog.einzeldatei')}</span>
    {:else}
      <span>·</span>
      <span>{t('katalog.n_kontext', { n: kontextK })}</span>
      <span>·</span>
      <span>{bauzahl === 1 ? t('katalog.bau_eins') : t('katalog.bau_mehr', { n: bauzahl })}</span>
    {/if}
  </div>

  {#if status === 'bereit'}
    <div class="fuss">
      <span class="pille"><Leuchtpunkt farbe="still" groesse={7} /> {t('katalog.im_ordner')}</span>
      <button class="knopf wichtig" onclick={(e) => halt(e, onStart)}>{t('katalog.starten')}</button>
    </div>
  {:else if status === 'laedt'}
    <div class="laufbalken">
      <span class="balken"><i style="width:{fortschritt?.anteil ?? 0}%"></i></span>
    </div>
    <div class="fuss">
      <span class="laufzahl">{fortschritt?.text ?? ''}</span>
      <button class="knopf still" onclick={(e) => halt(e, onCancel)}>{t('katalog.abbrechen')}</button>
    </div>
  {:else}
    <div class="fuss">
      <button class="knopf wichtig" onclick={(e) => halt(e, onDownload)}>{t('katalog.herunterladen')}</button>
    </div>
  {/if}
  {/if}
</div>

<style>
  .karte {
    position: relative;
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg-erhoben);
    padding: 16px 16px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    text-align: left;
    cursor: pointer;
    transition: border-color 0.12s;
  }
  .karte:hover {
    border-color: var(--linie-stark);
  }

  /* The compact accessory card: tighter, single line per row, a coloured tag
     in the corner and the size as a bright monospace value. */
  .karte.zub {
    gap: 8px;
    padding: 12px 13px;
  }
  .zpille {
    position: absolute;
    top: 12px;
    right: 12px;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.02em;
    border: 1px solid;
    border-radius: 99px;
    padding: 2px 9px;
  }
  .zlogo {
    width: 30px;
    height: 30px;
    border: 1px dashed;
    border-radius: 8px;
    display: grid;
    place-items: center;
    font-size: 13px;
    font-weight: 600;
  }
  .zname {
    font-size: 12.5px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* The class pill of a class-bound accessory — full text colour, so the
     SD 1.5 / SDXL question is answered before anything is downloaded. */
  .zklasse {
    display: inline-block;
    margin-left: 6px;
    border: 1px solid var(--text-still);
    border-radius: 99px;
    padding: 1px 8px;
    font: 600 10.5px var(--schrift);
    color: var(--text);
    vertical-align: 1px;
  }
  .zinfo {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
  }
  .zvon {
    font-size: 11px;
    color: var(--text-still);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* The size stands out as a technical value: brighter, bolder, monospace. */
  .zgb {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-leise);
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    letter-spacing: -0.01em;
    flex: none;
  }
  .zda {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    color: var(--text-still);
  }
  .knopf.voll {
    width: 100%;
  }
  /* Colourless on purpose: a fit is a fact, so it carries brightness and a
     border, not a state colour. */
  .plakette {
    position: absolute;
    top: -9px;
    right: 12px;
    background: var(--bg);
    border: 1.5px solid var(--linie-stark);
    border-radius: 99px;
    padding: 2px 10px;
    font: 700 10.5px var(--schrift);
    color: var(--text-leise);
  }
  /* The house black-pearl, over tokens so it holds in every skin: a
     near-black fill lifted off the ground, with pearl text — the same
     filled-mark idiom the sibling programs use for their one strong badge. */
  .empfohlen {
    position: absolute;
    bottom: 20px;
    left: 20px;
    background: color-mix(in srgb, var(--text) 86%, var(--bg));
    border: 1px solid transparent;
    border-radius: 99px;
    padding: 2px 9px;
    font: 600 10px var(--schrift);
    color: var(--bg);
    white-space: nowrap;
  }
  .oben {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  /* A dashed letter, never a redrawn maker's logo: an original vector goes
     in lib/logos.js when there is one (the catalogue names it as `marke`);
     until then this honest placeholder. With the real mark the frame turns
     solid — dashed is the placeholder's word for "still missing". */
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
  .logo.echt {
    border: 1px solid var(--linie);
  }
  .logo.eigen {
    border: none;
    padding: 0;
  }
  .wer {
    min-width: 0;
  }
  .name {
    font: 600 15px var(--schrift);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .von {
    font-size: 11.5px;
    color: var(--text-still);
    margin-top: 1px;
  }
  /* Three lines reserved — the longest description in the catalogue. Every
     card holds the same room, so the tiles of one group stay one size. */
  .satz {
    font-size: 12.5px;
    color: var(--text-leise);
    line-height: 1.5;
    min-height: 57px;
  }
  .zeichenreihe {
    display: flex;
    gap: 9px;
    align-items: center;
    color: var(--text-leise);
  }
  .zeichen {
    display: inline-flex;
  }
  /* The image model's class, worn as a quiet pill — a fact about the model,
     so it carries a border, not a state colour. */
  .klassepille {
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 2px 10px;
    font: 600 11px var(--schrift);
    color: var(--text-leise);
  }
  .fakten {
    display: flex;
    align-items: center;
    gap: 10px;
    font: 500 11.5px var(--schrift-fest);
    color: var(--text-still);
  }
  /* The foot sinks to the card's bottom edge: the grid stretches every card
     of a row to one height, and the buttons then stand on one line. While
     loading, the progress bar is what sinks and the foot follows it. */
  .fuss {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: auto;
  }
  .laufbalken {
    display: flex;
    align-items: center;
    margin-top: auto;
  }
  .laufbalken + .fuss {
    margin-top: 2px;
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
  .pille {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 3px 10px;
    font: 600 11px var(--schrift);
    color: var(--text);
    white-space: nowrap;
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: 600 12.5px var(--schrift);
    padding: 6px 13px;
    border-radius: 9px;
    white-space: nowrap;
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
    margin-left: auto;
  }
  .knopf.wichtig:hover {
    background: var(--text);
    opacity: 0.88;
  }
  .knopf.still {
    color: var(--text-still);
    border-color: var(--linie);
    margin-left: auto;
  }
</style>
