<script>
  import { untrack } from 'svelte'
  /* The notes module: blocks of notes, and the document dock beneath them.

     Notes stack from the top, all the same width, with a small fixed gap —
     they read as one pad, not as a list of cards. The "new note" tile sits
     at the end and moves down with every note saved, so the place to write
     is always where the eye already is.

     A note is written in the same tile it later becomes: heading on top,
     body below, and it grows with what is typed. The tick saves it; on a
     saved block the tick's place is taken by the bin.

     Formatting comes from the toolbar in the rail's head — see
     Notizwerkzeuge.svelte for why it is not in every block. */
  import { rollfade } from '../lib/rollfade.js'
  import { t } from '../lib/texte.svelte.js'
  import { frage } from '../lib/zustand.svelte.js'
  import {
    dock, dockAblegen, dockDatei, dockEntfernen, loeschen, neueNotiz, notizOeffnen,
    notizen, schliessen, sichern,
  } from '../lib/notizen.svelte.js'

  let leib = $state(null)
  let dateiwahl = $state(null)
  let ueberZiel = $state(false)

  /* The editable body carries HTML, so it is filled when a note opens or
     the draft is swapped — never while typing. Reading the draft's content
     inside this effect would make every keystroke a dependency: the effect
     would rewrite the body, the caret would snap to the front, and the
     text would come out mirrored. The draft object itself is the trigger —
     opening and switching assign a fresh one, typing only mutates it. */
  $effect(() => {
    const offen = notizen.offen
    const entwurf = notizen.entwurf
    if (offen && leib) leib.innerHTML = untrack(() => entwurf.inhalt) || ''
  })

  function leibGeaendert() {
    if (leib) notizen.entwurf.inhalt = leib.innerHTML
  }

  async function blockLoeschen(notiz) {
    const ja = await frage(t('notiz.loeschen_frage'), { okSchluessel: 'notiz.loeschen' })
    if (ja) await loeschen(notiz.id)
  }

  async function platzRaeumen(eintrag) {
    const ja = await frage(t('notiz.dock_weg_frage', { name: eintrag.name }), {
      okSchluessel: 'notiz.dock_weg',
    })
    if (ja) await dockEntfernen(eintrag.id)
  }

  function dateienNehmen(dateien) {
    for (const datei of dateien) dockAblegen(datei)
  }

  function abgelegt(ereignis) {
    ereignis.preventDefault()
    ueberZiel = false
    dateienNehmen(ereignis.dataTransfer?.files ?? [])
  }

  /* Dragging a docked file out: the id travels, and whoever catches it asks
     the dock for the file itself. */
  function ziehenStart(ereignis, eintrag) {
    ereignis.dataTransfer.setData('application/x-exe-dock', eintrag.id)
    ereignis.dataTransfer.effectAllowed = 'copy'
  }

  const freiePlaetze = $derived(Math.max(0, dock.plaetze - dock.liste.length))
</script>

<div class="notizen" use:rollfade>
  {#each notizen.liste as notiz (notiz.id)}
    {#if notizen.offen === notiz.id}
      <div class="kachel eingabe">
        <input
          class="titel"
          bind:value={notizen.entwurf.ueberschrift}
          placeholder={t('notiz.ueberschrift')}
        />
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="leib"
          bind:this={leib}
          contenteditable="true"
          data-platzhalter={t('notiz.platzhalter')}
          oninput={leibGeaendert}
        ></div>
        <div class="fuss">
          <button class="knopf" onclick={schliessen}>{t('app.abbrechen')}</button>
          <button class="haken" onclick={sichern} title={t('notiz.sichern')} aria-label={t('notiz.sichern')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 13 4 4L19 7" /></svg>
          </button>
        </div>
      </div>
    {:else}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="kachel block" onclick={() => notizOeffnen(notiz)} role="button" tabindex="0"
           onkeydown={(e) => e.key === 'Enter' && notizOeffnen(notiz)}>
        {#if notiz.ueberschrift}<h3>{notiz.ueberschrift}</h3>{/if}
        <div class="leib gelesen">{@html notiz.inhalt}</div>
        <button
          class="muell"
          onclick={(e) => { e.stopPropagation(); blockLoeschen(notiz) }}
          title={t('notiz.loeschen')}
          aria-label={t('notiz.loeschen')}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M6 6l1 14h10l1-14" /></svg>
        </button>
      </div>
    {/if}
  {/each}

  {#if notizen.offen === 'neu'}
    <div class="kachel eingabe">
      <input
        class="titel"
        bind:value={notizen.entwurf.ueberschrift}
        placeholder={t('notiz.ueberschrift')}
      />
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="leib"
        bind:this={leib}
        contenteditable="true"
        data-platzhalter={t('notiz.platzhalter')}
        oninput={leibGeaendert}
      ></div>
      <div class="fuss">
        <button class="knopf" onclick={schliessen}>{t('app.abbrechen')}</button>
        <button class="haken" onclick={sichern} title={t('notiz.sichern')} aria-label={t('notiz.sichern')}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m5 13 4 4L19 7" /></svg>
        </button>
      </div>
    </div>
  {:else}
    <!-- The way to write, always at the end of the pad. -->
    <button class="kachel neu" onclick={neueNotiz}>
      <!-- The same plus the chat's input bar wears: a drawn stroke pair in a
           round frame, not a typed character. A glyph carries its font's own
           side bearings and sits on a baseline, so it can never be centred in
           a circle by hand — the two strokes always can. -->
      <span class="plus">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      </span>
      {t('notiz.neu')}
    </button>
  {/if}
</div>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="dock"
  class:ueberZiel
  ondragover={(e) => { e.preventDefault(); ueberZiel = true }}
  ondragleave={() => (ueberZiel = false)}
  ondrop={abgelegt}
>
  <div class="ueber">{t('notiz.dock')}</div>
  <div class="plaetze">
    {#each dock.liste as eintrag (eintrag.id)}
      <div class="platz" draggable="true" ondragstart={(e) => ziehenStart(e, eintrag)}>
        <div class="flaeche">
          {#if (eintrag.typ || '').startsWith('image/')}
            <img src={`/api/v1/notizen/dock/${eintrag.id}`} alt={eintrag.name} />
          {:else}
            <svg width="20" height="20" viewBox="0 0 64 64" fill="none" stroke="currentColor"
                 stroke-width="5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M16 8 H38 L48 18 V56 H16 Z" />
              <path d="M38 8 V18 H48" stroke-width="4.5" />
            </svg>
          {/if}
          <button
            class="weg"
            onclick={() => platzRaeumen(eintrag)}
            title={t('notiz.dock_weg')}
            aria-label={t('notiz.dock_weg')}
          >✕</button>
        </div>
        <span class="name">{eintrag.name}</span>
      </div>
    {/each}
    {#each Array(freiePlaetze) as _, i (i)}
      <div class="platz leer">
        <!-- Drawn, not typed — the same reason the tile's plus is drawn. -->
        <button class="flaeche" onclick={() => dateiwahl?.click()} title={t('notiz.dock_hinzu')} aria-label={t('notiz.dock_hinzu')}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        </button>
        <span class="name"></span>
      </div>
    {/each}
  </div>
  <input
    type="file"
    bind:this={dateiwahl}
    hidden
    onchange={(e) => { dateienNehmen(e.currentTarget.files ?? []); e.currentTarget.value = '' }}
  />
</div>

<style>
  .notizen {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    /* The one number that makes a pad out of a list. */
    gap: 3px;
  }
  /* One shape for every note, written or saved: same width, same radius,
     grows with its content. */
  .kachel {
    width: 100%;
    box-sizing: border-box;
    border-radius: 12px;
    padding: 12px 14px;
    text-align: left;
  }
  .block {
    position: relative;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie);
    cursor: pointer;
  }
  .block h3 {
    margin: 0 0 5px;
    font-size: 13.5px;
    font-weight: 650;
  }
  .leib {
    font-size: 12px;
    line-height: 1.55;
    color: var(--text);
    outline: none;
    word-break: break-word;
  }
  .leib.gelesen { color: var(--text-leise); }
  .leib :global(b), .leib :global(strong) { color: var(--text); }
  .leib :global(mark) {
    background: color-mix(in srgb, var(--gelb) 28%, transparent);
    color: var(--text);
    border-radius: 3px;
    padding: 0 2px;
  }
  .leib :global(mark[data-farbe='blau']) { background: color-mix(in srgb, var(--blau) 28%, transparent); }
  .leib :global(mark[data-farbe='gruen']) { background: color-mix(in srgb, var(--gruen) 28%, transparent); }
  .leib:empty::before {
    content: attr(data-platzhalter);
    color: var(--text-still);
  }
  /* The bin appears on the block it belongs to, and wears the colour of
     deleting only when the pointer is on it. */
  .muell {
    position: absolute;
    top: 9px;
    right: 9px;
    border: none;
    background: none;
    color: var(--text-still);
    cursor: pointer;
    padding: 4px;
    border-radius: 7px;
    opacity: 0;
    transition: opacity 0.12s, color 0.12s, background 0.12s;
  }
  .block:hover .muell { opacity: 1; }
  .muell:hover {
    color: var(--rot);
    background: color-mix(in srgb, var(--rot) 12%, var(--bg-erhoben));
  }

  .eingabe {
    background: var(--bg-erhoben);
    border: 1px solid var(--text-leise);
  }
  .titel {
    width: 100%;
    border: none;
    background: none;
    color: var(--text);
    font: 650 13.5px var(--schrift);
    outline: none;
    padding: 0 0 6px;
  }
  .titel::placeholder { color: var(--text-still); font-weight: 500; }
  .eingabe .leib { min-height: 44px; }
  .fuss {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
    padding-top: 9px;
    border-top: 1px solid var(--linie);
  }
  .knopf {
    border: none;
    background: none;
    color: var(--text-still);
    font: inherit;
    font-size: 12px;
    padding: 3px 6px;
    border-radius: 7px;
    cursor: pointer;
  }
  .knopf:hover { color: var(--text); background: var(--linie); }
  .haken {
    margin-left: auto;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    width: 30px;
    height: 26px;
    border-radius: 9px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .haken:hover { background: var(--text); color: var(--bg); border-color: var(--text); }

  .neu {
    display: flex;
    align-items: center;
    gap: 9px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text-still);
    font: 12.5px var(--schrift);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .neu:hover { background: var(--bg-erhoben); color: var(--text); }
  /* Built like the input bar's plus, number for number: the border counted
     into the box, the pill radius, the stroke centred by the flex box rather
     than by a font metric. */
  .plus {
    width: 28px;
    height: 28px;
    box-sizing: border-box;
    flex: none;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  /* The dock sits at the foot of the panel: four places, always visible, so
     it is clear there are four and not "as many as fit". */
  .dock {
    flex: none;
    border-top: 1px solid var(--linie);
    padding: 11px 14px 13px;
    transition: background 0.12s;
  }
  .dock.ueberZiel { background: var(--bg-erhoben); }
  .ueber {
    font-size: 10.5px;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    color: var(--text-still);
    margin-bottom: 9px;
  }
  .plaetze {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }
  /* Four squares of exactly one size — an occupied place must not be a
     different shape from an empty one. */
  .platz {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-width: 0;
    cursor: grab;
  }
  .platz .flaeche {
    aspect-ratio: 1;
    width: 100%;
    border-radius: 9px;
    border: 1px solid var(--linie);
    background: var(--bg-erhoben);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-leise);
    overflow: hidden;
    position: relative;
    padding: 0;
    font: inherit;
  }
  .platz.leer .flaeche {
    background: none;
    border-style: dashed;
    color: var(--text-still);
    cursor: pointer;
  }
  .platz.leer .flaeche:hover { color: var(--text-leise); border-color: var(--linie-stark); }
  .platz img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .name {
    font-size: 10px;
    color: var(--text-still);
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-height: 12px;
  }
  .weg {
    position: absolute;
    top: 3px;
    right: 3px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: none;
    background: color-mix(in srgb, var(--bg) 72%, transparent);
    color: var(--text-leise);
    font-size: 10px;
    line-height: 1;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.12s;
  }
  .platz:hover .weg { opacity: 1; }
  .weg:hover { color: var(--rot); }
</style>
