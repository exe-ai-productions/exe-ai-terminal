<script>
  /* One storage location as a row: where it is, a button to open it, and the
     catalogue's folder mark to move it. The same control wherever a folder
     can be seen and changed — the pictures module and each of the three
     server panels — so "this is about a folder" reads the same everywhere,
     and there is one place to change how it works.

     It owns only this one location, addressed by name ('bilder',
     'bildmodelle', 'modelle', 'einbettung'). After a move it reloads itself
     and tells the parent, so a picture wall or a model list built on the old
     folder can refresh. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde, frage } from '../lib/zustand.svelte.js'

  let { name, etikett = '', onaendern = null } = $props()

  let pfad = $state('')
  let neustartNoetig = $state(false)

  async function laden() {
    try {
      const orte = await api.speicherorteLesen()
      const o = orte.find((x) => x.name === name)
      pfad = o ? o.pfad : ''
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

  $effect(() => { if (name) laden() })

  async function oeffnen() {
    try {
      await api.speicherortOeffnen(name)
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

  async function aendern() {
    const neu = await frage(t('speicherorte.frage'), { eingabe: pfad })
    if (!neu || neu === pfad) return
    try {
      const antwort = await api.speicherortSetzen(name, neu)
      neustartNoetig = !antwort.ist_standard && antwort.neustart_noetig
      pfad = antwort.pfad
      melde(t('speicherorte.geaendert'), 'hinweis')
      onaendern?.()
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }
</script>

<div class="zeile">
  {#if etikett}<span class="etikett">{etikett}</span>{/if}
  <span class="pfad" title={pfad}>{pfad}</span>
  <!-- Open and change as a tight pair of square icon buttons, held closer to
       each other than to the path, so the two read as one cluster of tools. -->
  <div class="knopfpaar">
    <button class="ordnerknopf" onclick={oeffnen} title={t('speicherorte.oeffnen')}
            aria-label={t('speicherorte.oeffnen')}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3.75 18 V6 H9.75 L11.63 8.25 H18 V11.25" />
        <path d="M3.75 18 H16.5 L20.25 11.25 H7.5 Z" />
      </svg>
    </button>
    <button class="ordnerknopf" onclick={aendern} title={t('speicherorte.aendern')}
            aria-label={t('speicherorte.aendern')}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <!-- The house pencil, not a folder: this button does not open the
             folder — the one beside it does — it CHANGES which folder is
             meant. Two buttons wearing one sign taught two different lessons
             in two different windows. -->
        <path d="M17 3l4 4L8 20l-5 1 1-5L17 3z" />
      </svg>
    </button>
  </div>
</div>
{#if neustartNoetig}
  <p class="hinweis">{t('speicherorte.neustart')}</p>
{/if}

<style>
  .zeile {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .etikett {
    font-size: 12px;
    font-weight: 600;
    color: var(--text);
    flex: none;
  }
  .pfad {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    /* Keep the folder name in view under the ellipsis, not the drive root.
       plaintext keeps the path itself reading left-to-right, so the digits
       and punctuation in a path like /Volumes/4TB SSD/… are not reordered by
       the rtl box — only the truncation side moves to the front. */
    direction: rtl;
    unicode-bidi: plaintext;
    text-align: left;
    font: 400 11px var(--schrift-fest, ui-monospace, monospace);
    color: var(--text-still);
  }
  .knopfpaar {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }
  .ordnerknopf {
    flex: none;
    font: inherit;
    font-size: 12px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    border-radius: 8px;
    cursor: pointer;
  }
  /* Square, and the size of the catalogue button it stands under: two
     buttons in one column that end on different edges read as an accident,
     not as an arrangement. */
  .ordnerknopf {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    box-sizing: border-box;
    padding: 0;
    border-radius: 9px;
    color: var(--text-leise);
  }
  .ordnerknopf:hover { background: var(--linie); }
  .hinweis {
    margin: 6px 0 0;
    font-size: 11.5px;
    color: var(--gelb);
  }
</style>
