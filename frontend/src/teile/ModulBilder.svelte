<script>
  /* The pictures module: every picture the generator has drawn, as a wall of
     thumbnails, and above them the folder they live in.

     It lives in the work rail beside the note, not in a window: the rail is
     the resizable side surface, so dragging it wider grows the pictures and
     narrower shrinks them — the tiles fill the width the way the document
     dock's do, only a size larger. The catalogue's folder mark opens the
     move-it dialog; the same glyph everywhere for "this is about a folder".

     Read fresh whenever the module is shown, never held between visits — the
     folder on disk is the truth, not a copy kept here. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde } from '../lib/zustand.svelte.js'
  import { bildZeigen } from '../lib/bildschau.svelte.js'
  import Speicherortzeile from './Speicherortzeile.svelte'

  let bilder = $state([])
  let laedt = $state(false)

  async function laden() {
    laedt = true
    try {
      bilder = (await api.bilderListe()).bilder
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    } finally {
      laedt = false
    }
  }

  /* The module is mounted only while shown, so mounting is the moment to
     refresh: a picture drawn since the last look appears without a reload. */
  $effect(() => { laden() })
</script>

<div class="modul">
  <div class="ordnerzeile">
    <Speicherortzeile name="bilder" etikett={t('bilder.bildordner')} onaendern={laden} />
  </div>

  <div class="rollen">
    {#if laedt && bilder.length === 0}
      <p class="leer">{t('bilder.laedt')}</p>
    {:else if bilder.length === 0}
      <p class="leer">{t('bilder.leer')}</p>
    {:else}
      <div class="raster">
        {#each bilder as name (name)}
          <button class="kachel" onclick={() => bildZeigen(api.bildAdresse(name))}>
            <img src={api.bildAdresse(name)} alt="" loading="lazy" />
          </button>
        {/each}
      </div>
    {/if}
  </div>
</div>

<style>
  .modul {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
  }
  /* Just the frame around the shared folder row — the row draws itself. */
  .ordnerzeile {
    flex: none;
    padding: 12px 14px;
    border-bottom: 1px solid var(--linie);
  }
  /* The wall of pictures scrolls; nothing else in the module does. */
  .rollen {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 12px 14px;
  }
  .leer {
    color: var(--text-still);
    font-size: 12.5px;
    text-align: center;
    padding: 26px 0;
  }
  /* Tiles fill the width and grow with the rail — a size larger than the
     document dock's squares, which sit around 52px at the narrowest rail. */
  .raster {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
    gap: 8px;
  }
  .kachel {
    padding: 0;
    border: 1px solid var(--linie);
    border-radius: 9px;
    overflow: hidden;
    background: var(--bg-erhoben);
    cursor: pointer;
    aspect-ratio: 1;
  }
  .kachel img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }
  .kachel:hover { border-color: var(--linie-stark); }
</style>
