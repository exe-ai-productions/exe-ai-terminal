<script>
  import { rollfade } from '../lib/rollfade.js'
  /* The preview module: what the model built, shown beside the chat.

     A small browser, not a window: tabs on top, an address line, and the
     same sandboxed frame the preview window uses — HTML and SVG drawn, CSV
     as a table, everything else as text.

     The frame is sandboxed WITHOUT allow-same-origin, and that pairing is
     the point: the document comes from the model, and with our origin its
     scripts would sit inside our own program and could talk to our own API
     with our own session. Scripts stay allowed — a page that cannot run is
     not a preview of that page — but they run next to nothing. */
  import { api } from '../lib/api.js'
  import { ordnerListe } from '../lib/arbeitsordner.svelte.js'
  import { dateiart, dateigroesse, tabelleLesen } from '../lib/dateiarten.js'
  import { t } from '../lib/texte.svelte.js'
  import {
    aktiverTab, tabSchliessen, tabWaehlen, tabsVon,
  } from '../lib/vorschautabs.svelte.js'
  import { melde, zustand } from '../lib/zustand.svelte.js'

  const chatId = $derived(zustand.aktiverChat)
  const liste = $derived(tabsVon(chatId))
  const offen = $derived(aktiverTab(chatId))

  const eintrag = $derived(offen ? dateiart(offen.art) : null)
  const kannZeichnen = $derived(eintrag?.zeigen === 'gerendert')
  const kannTabelle = $derived(eintrag?.zeigen === 'tabelle')
  const zeilen = $derived(
    kannTabelle ? tabelleLesen(offen.inhalt, offen.art === 'tsv' ? '\t' : ',') : [],
  )

  /* Reloading means handing the frame its content again — the same trick a
     browser's reload button plays, and enough for a document that lives in
     memory. */
  let stand = $state(0)
  /* Drawn or as source. A new tab starts drawn again: the last file's view
     should not decide how the next one opens. */
  let quelltextZeigen = $state(false)
  $effect(() => {
    void offen?.id
    quelltextZeigen = false
  })

  let rahmen = $state(null)

  const fakten = $derived(
    eintrag && offen ? `${eintrag.endung.toUpperCase()} · ${dateigroesse(offen.inhalt)}` : '',
  )

  /* A file in the panel is still a file: it can leave as a download, land in
     a shared folder, or go through the print dialog — which is where a PDF
     comes from on every system, without a library. */
  function herunterladen() {
    if (!offen) return
    const blob = new Blob([offen.inhalt], { type: eintrag?.typ || 'text/plain' })
    const adresse = URL.createObjectURL(blob)
    const verweis = document.createElement('a')
    verweis.href = adresse
    verweis.download = offen.name
    verweis.click()
    URL.revokeObjectURL(adresse)
  }

  async function ablegen() {
    if (!offen) return
    if (!ordnerListe().length) return melde(t('datei.kein_ordner'), 'warnung')
    try {
      const { pfad } = await api.erzeugnisAblegen({
        chat_id: chatId,
        name: offen.name,
        inhalt: offen.inhalt,
      })
      melde(t('datei.gespeichert', { pfad }), 'erfolg')
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  /* Printing goes through the frame, not the page: the page would print the
     chat around it. */
  function drucken() {
    rahmen?.contentWindow?.focus()
    rahmen?.contentWindow?.print()
  }
</script>

{#if !liste.length}
  <p class="leer">{t('vorschau.leer')}</p>
{:else}
  <div class="reiter">
    {#each liste as tab (tab.id)}
      <div class="reiter-eintrag" class:aktiv={tab.id === offen?.id}>
        <button class="reiter-name" onclick={() => tabWaehlen(chatId, tab.id)}>{tab.name}</button>
        <button
          class="reiter-zu"
          onclick={() => tabSchliessen(chatId, tab.id)}
          aria-label={t('vorschau.schliessen')}
          title={t('vorschau.schliessen')}
        >✕</button>
      </div>
    {/each}
  </div>

  <div class="adresszeile">
    <span class="adresse">{offen?.name}</span>
    <span class="fakten">{fakten}</span>
    {#if kannZeichnen || kannTabelle}
      <button class="knopf" onclick={() => (quelltextZeigen = !quelltextZeigen)}>
        {quelltextZeigen ? t('datei.gerendert') : t('datei.quelltext')}
      </button>
    {/if}
    <button class="knopf" onclick={() => (stand += 1)}>{t('vorschau.neu_laden')}</button>
  </div>

  <div class="buehne">
    {#key `${offen?.id}-${stand}`}
      {#if kannZeichnen && !quelltextZeigen}
        <iframe
          bind:this={rahmen}
          class="rahmen"
          title={offen.name}
          srcdoc={offen.inhalt}
          sandbox="allow-scripts"
          referrerpolicy="no-referrer"
        ></iframe>
      {:else if kannTabelle && !quelltextZeigen}
        <div class="tabellenfeld" use:rollfade>
          <table>
            <thead>
              <tr>{#each zeilen[0] || [] as zelle}<th>{zelle}</th>{/each}</tr>
            </thead>
            <tbody>
              {#each zeilen.slice(1) as reihe}
                <tr>{#each reihe as zelle}<td>{zelle}</td>{/each}</tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <pre class="quelle" use:rollfade><code>{offen?.inhalt}</code></pre>
      {/if}
    {/key}
  </div>

  <div class="fuss">
    {#if kannZeichnen && !quelltextZeigen}
      <button class="knopf" onclick={drucken}>{t('datei.drucken')}</button>
    {/if}
    <button class="knopf" onclick={herunterladen}>{t('datei.herunterladen')}</button>
    <button class="knopf" onclick={ablegen} disabled={!ordnerListe().length}>
      {t('datei.speichern')}
    </button>
  </div>
{/if}

<style>
  .fuss {
    flex: none;
    display: flex;
    justify-content: flex-end;
    gap: 6px;
    padding: 0 12px 12px;
  }
  .fakten {
    flex: none;
    font-size: 11px;
    color: var(--text-still);
  }
  .knopf:disabled {
    color: var(--text-still);
    cursor: default;
  }
  .knopf:disabled:hover { background: none; color: var(--text-still); }
  .leer {
    margin: 14px;
    font-size: 13px;
    color: var(--text-still);
  }
  .reiter {
    flex: none;
    display: flex;
    gap: 4px;
    padding: 8px 10px 0;
    overflow-x: auto;
  }
  /* One row, one size: every tab is the same height whatever it is
     called. */
  .reiter-eintrag {
    display: inline-flex;
    align-items: center;
    height: 26px;
    max-width: 180px;
    border: 1px solid var(--linie);
    border-radius: 9px;
    background: var(--bg);
    padding: 0 2px 0 4px;
  }
  .reiter-eintrag.aktiv {
    background: var(--bg-erhoben);
    border-color: var(--linie-stark);
  }
  /* The highlight sits on the whole tab, so the close sign lights up with
     the name instead of staying dark beside it — same rule as the folder
     chips and the tool rows. */
  .reiter-eintrag:hover {
    background: var(--linie);
    border-color: var(--linie-stark);
  }
  .reiter-eintrag:hover .reiter-name,
  .reiter-eintrag:hover .reiter-zu { color: var(--text); }
  .reiter-name {
    min-width: 0;
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 11.5px;
    padding: 0 5px;
    cursor: pointer;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .reiter-eintrag.aktiv .reiter-name { color: var(--text); }
  .reiter-zu {
    flex: none;
    border: none;
    background: none;
    color: var(--text-still);
    font-size: 11px;
    padding: 2px 4px;
    border-radius: 6px;
    cursor: pointer;
  }
  .reiter-zu:hover { background: var(--linie-stark); color: var(--text); }

  .adresszeile {
    flex: none;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
  }
  .adresse {
    flex: 1;
    min-width: 0;
    font-family: var(--schrift-fest);
    font-size: 11px;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie);
    border-radius: 9px;
    padding: 5px 10px;
    color: var(--text-leise);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .knopf {
    flex: none;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 11.5px;
    padding: 5px 10px;
    border-radius: 9px;
    cursor: pointer;
  }
  .knopf:hover { background: var(--linie); color: var(--text); }

  .buehne {
    flex: 1;
    min-height: 0;
    display: flex;
    padding: 0 12px 12px;
  }
  /* The two-pixel frame of the house: a document from the model is shown,
     never blended into the program around it. */
  .rahmen {
    flex: 1;
    min-height: 0;
    border: 2px solid var(--linie-stark);
    border-radius: 9px;
    background: #fff;
  }
  .tabellenfeld,
  .quelle {
    flex: 1;
    min-height: 0;
    overflow: auto;
    border: 2px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg-erhoben);
    margin: 0;
    padding: 10px 12px;
  }
  .quelle {
    font-family: var(--schrift-fest);
    font-size: 12px;
    line-height: 1.55;
    color: var(--text-leise);
    white-space: pre-wrap;
  }
  table { border-collapse: collapse; font-size: 12px; }
  th, td {
    border: 1px solid var(--linie);
    padding: 4px 8px;
    text-align: left;
    color: var(--text-leise);
  }
  th { color: var(--text); }
</style>
