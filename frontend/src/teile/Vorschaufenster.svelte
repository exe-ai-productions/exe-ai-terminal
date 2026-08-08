<script>
  /* The window that shows a file from the chat.

     A file in an answer is text until someone looks at it. This window is
     that look — and it is deliberately ours instead of the system's default
     program: the browser cannot hand a local file to another application,
     and every way around that is a different one on every operating system.
     Showing it ourselves needs none of them.

     Three ways to show, decided by the catalogue in `lib/dateiarten.js`:
     drawn (HTML, SVG), as a table (CSV), or as plain text. Everything can
     be downloaded and put into a working folder, however it is shown. */
  import Fenster from './Fenster.svelte'
  import { api } from '../lib/api.js'
  import { dateiart, dateigroesse, dateizeichen, tabelleLesen } from '../lib/dateiarten.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde } from '../lib/zustand.svelte.js'

  let {
    offen = $bindable(false),
    name = '',
    art = '',
    inhalt = '',
    chatId = null,
    ordner = [],
  } = $props()

  let quelltextZeigen = $state(false)

  const eintrag = $derived(dateiart(art))
  const kannZeichnen = $derived(eintrag?.zeigen === 'gerendert')
  const kannTabelle = $derived(eintrag?.zeigen === 'tabelle')
  const umschaltbar = $derived(kannZeichnen || kannTabelle)
  const zeilen = $derived(
    kannTabelle ? tabelleLesen(inhalt, art === 'tsv' ? '\t' : ',') : [],
  )

  /* A new file starts drawn again — the last file's source view should not
     decide how the next one opens. */
  $effect(() => {
    void name
    quelltextZeigen = false
  })

  let rahmen = $state(null)

  const marke = $derived(dateizeichen(art, 20))
  const fakten = $derived(
    eintrag ? `${eintrag.endung.toUpperCase()} · ${dateigroesse(inhalt)}` : '',
  )

  function herunterladen() {
    const blob = new Blob([inhalt], { type: eintrag?.typ || 'text/plain' })
    const adresse = URL.createObjectURL(blob)
    const verweis = document.createElement('a')
    verweis.href = adresse
    verweis.download = name
    verweis.click()
    URL.revokeObjectURL(adresse)
  }

  async function ablegen() {
    if (!ordner.length) return melde(t('datei.kein_ordner'), 'warnung')
    try {
      const { pfad } = await api.erzeugnisAblegen({ chat_id: chatId, name, inhalt })
      melde(t('datei.gespeichert', { pfad }), 'erfolg')
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  /* Printing goes through the frame, not the page: the page would print the
     chat around it. The browser's print dialog offers "save as PDF" on every
     system — that is where PDF comes from, without a library. */
  function drucken() {
    rahmen?.contentWindow?.focus()
    rahmen?.contentWindow?.print()
  }
</script>

{#snippet zeichen()}
  <!-- Our own constant markup from the catalogue, never anything that came
       out of an answer. -->
  <span class="marke">{@html marke}</span>
{/snippet}

<Fenster bind:offen titel={name} art="vorschau" symbol={zeichen}>
  <div class="leiste">
    {#if umschaltbar}
      <button class="knopf" onclick={() => (quelltextZeigen = !quelltextZeigen)}>
        {quelltextZeigen ? t('datei.gerendert') : t('datei.quelltext')}
      </button>
    {/if}
    <span class="fakten">{fakten}</span>
    <span class="fueller"></span>
    {#if kannZeichnen && !quelltextZeigen}
      <button class="knopf" onclick={drucken}>{t('datei.drucken')}</button>
    {/if}
    <button class="knopf" onclick={herunterladen}>{t('datei.herunterladen')}</button>
    <button class="knopf" onclick={ablegen} disabled={!ordner.length}>
      {t('datei.speichern')}
    </button>
  </div>

  <div class="buehne">
    {#if kannZeichnen && !quelltextZeigen}
      <!-- Sandboxed WITHOUT allow-same-origin, and that pairing is the whole
           point: the document comes from the model, and with a same origin
           its scripts would sit inside our own program and could talk to our
           own API with our own session. Scripts stay allowed — a page that
           cannot run is not a preview of that page — but they run in an
           origin of their own, next to nothing. -->
      <iframe
        bind:this={rahmen}
        title={name}
        srcdoc={inhalt}
        sandbox="allow-scripts"
        referrerpolicy="no-referrer"
      ></iframe>
    {:else if kannTabelle && !quelltextZeigen}
      <div class="tabellenfeld">
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
      <pre class="quelle"><code>{inhalt}</code></pre>
    {/if}
  </div>
</Fenster>

<style>
  .leiste {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 10px;
    flex: none;
  }
  .fueller { flex: 1; }

  /* Kind and weight are facts about the file, so they carry no colour —
     only the quietest brightness the palette has. */
  .fakten {
    font-size: 11.5px;
    color: var(--text-still);
    font-variant-numeric: tabular-nums;
  }
  .marke { display: inline-flex; color: var(--text-still); }

  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 12.5px;
    padding: 5px 11px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .knopf:hover:not(:disabled) { background: var(--linie); }
  .knopf:disabled { color: var(--text-still); cursor: default; }

  /* The same edge as around a picture, and for the same reason: what is
     shown starts at the first pixel inside it. Square corners — a document
     has square corners, and a rounded frame would clip its own content at
     the top left. */
  .buehne {
    flex: 1;
    min-height: 0;
    border: 2px solid var(--linie-stark);
    border-radius: 0;
    overflow: hidden;
    background: var(--bg);
  }

  /* `display: block` is what makes the document start at the first pixel
     inside the frame — as an inline element it would sit on a text baseline
     and leave a gap underneath. */
  iframe {
    width: 100%;
    height: 100%;
    border: none;
    display: block;
    background: #fff;
  }

  /* The one place a bar may appear is inside a document that is wider than
     the window — and even there it stays invisible, house rule. */
  .tabellenfeld,
  .quelle {
    width: 100%;
    height: 100%;
    overflow: auto;
    margin: 0;
  }

  table {
    border-collapse: collapse;
    font-size: 13px;
    width: 100%;
  }
  th, td {
    border-bottom: 1px solid var(--linie);
    padding: 7px 12px;
    text-align: left;
    white-space: nowrap;
  }
  th {
    position: sticky;
    top: 0;
    background: var(--bg);
    font-weight: 600;
  }
  td { font-variant-numeric: tabular-nums; }

  .quelle {
    padding: 14px 16px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12.5px;
    line-height: 1.55;
  }
</style>
