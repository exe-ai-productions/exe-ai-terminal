<script>
  /* Adding a cloud provider — the way out of a window that had none.

     It fits inside the right half of the list window and does not make it
     any bigger: the window sizes are settled, and one that grows for one
     purpose is the beginning of four different windows.

     Three kinds, and the third carries the other two: for anything
     OpenAI-compatible only the address differs, so somebody's own server in
     their own network costs no extra mask. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde, modelleLaden } from '../lib/zustand.svelte.js'

  let { fertig } = $props()

  const ARTEN = [
    { id: 'anthropic', name: 'Anthropic', unter: 'Claude' },
    { id: 'openai', name: 'OpenAI', unter: 'GPT' },
    { id: 'eigen', name: null, unter: null },
  ]

  let art = $state('anthropic')
  let schluessel = $state('')
  let kennung = $state('')
  let url = $state('')
  let arbeitet = $state(false)

  const eigen = $derived(art === 'eigen')
  const bereit = $derived(
    schluessel.trim().length >= 8 && (!eigen || (kennung.trim() && url.trim())),
  )

  async function verbinden() {
    arbeitet = true
    try {
      await api.anbieterHinzufuegen({
        art,
        schluessel: schluessel.trim(),
        kennung: eigen ? kennung.trim() : null,
        url: eigen ? url.trim() : null,
      })
      // The key is gone from here the moment it is saved: it lives in one
      // file on this machine and nowhere else, least of all in a browser.
      schluessel = ''
      // "The models appear by themselves" is this line — a fresh check,
      // because the regular one comes only every half minute.
      await modelleLaden(true)
      melde(t('modell.anbieter_da'), 'erfolg')
      fertig?.()
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    } finally {
      arbeitet = false
    }
  }
</script>

<div class="maske">
  <h4>{t('modell.anbieter_waehlen')}</h4>
  <div class="wahl">
    {#each ARTEN as a}
      <button class="art" class:an={art === a.id} onclick={() => (art = a.id)}>
        <b>{a.name ?? t('modell.eigener')}</b>
        <span>{a.unter ?? t('modell.eigener_unter')}</span>
      </button>
    {/each}
  </div>

  {#if eigen}
    <div class="paar">
      <label class="feld">
        {t('modell.eigener_name')}
        <input class="eingabe" bind:value={kennung} placeholder={t('modell.eigener_name_beispiel')} />
      </label>
      <label class="feld">
        {t('modell.eigener_adresse')}
        <input class="eingabe" bind:value={url} placeholder={t('modell.eigener_adresse_beispiel')} />
      </label>
    </div>
  {/if}

  <label class="feld">
    {t('modell.schluessel')}
    <input class="eingabe" type="password" bind:value={schluessel} autocomplete="off" />
  </label>
  <p class="hinweis">{t('modell.schluessel_hinweis')}</p>

  <div class="knopfzeile">
    <button class="knopf wichtig" onclick={verbinden} disabled={!bereit || arbeitet}>
      {t('modell.verbinden')}
    </button>
    <button class="knopf" onclick={() => fertig?.()}>{t('modell.abbrechen')}</button>
  </div>
</div>

<style>
  .maske { display: flex; flex-direction: column; min-height: 0; }
  h4 {
    font-size: 10.5px; letter-spacing: 0.09em; text-transform: uppercase;
    color: var(--text-still); font-weight: 500; margin: 2px 0 9px;
  }

  .wahl { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; }
  .art {
    border: 1px solid var(--linie); border-radius: 12px; background: var(--bg-seite);
    color: var(--text); font: inherit; text-align: left; padding: 11px 12px; cursor: pointer;
    transition: border-color 0.12s, background 0.12s;
  }
  .art:hover { border-color: var(--linie-stark); }
  /* Chosen is a fact about the form, not a state of the program — so it is
     marked by brightness and an edge, never by colour. */
  .art.an { border-color: var(--text); background: var(--blase); }
  .art b { display: block; font-size: 13.5px; font-weight: 600; }
  .art span { display: block; font-size: 11px; color: var(--text-still); margin-top: 2px; }

  .paar { display: grid; grid-template-columns: 1fr 1.4fr; gap: 10px; }
  .feld { display: block; font-size: 12.5px; color: var(--text-leise); margin-bottom: 10px; }
  .eingabe {
    display: block; width: 100%; margin-top: 5px;
    border: 1px solid var(--linie-stark); border-radius: 9px;
    background: var(--bg); color: var(--text);
    font: 400 12.5px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
    padding: 8px 11px;
  }
  .eingabe:focus { outline: 2px solid var(--linie-stark); outline-offset: -2px; }

  .hinweis { font-size: 11.5px; color: var(--text-still); margin: -2px 0 0; line-height: 1.5; }
  .knopfzeile { display: flex; gap: 8px; margin-top: 16px; }
  .knopf {
    border: 1px solid var(--linie-stark); background: none; color: var(--text);
    font: inherit; font-size: 12.5px; padding: 7px 14px; border-radius: 9px; cursor: pointer;
    transition: background 0.12s, opacity 0.12s, transform 0.08s;
  }
  .knopf:hover:not(:disabled) { background: var(--linie); }
  .knopf:active:not(:disabled) { transform: scale(0.975); }
  .knopf.wichtig { background: var(--text); color: var(--bg-erhoben); border-color: var(--text); }
  .knopf.wichtig:hover:not(:disabled) { background: var(--text); opacity: 0.88; }
  .knopf:disabled { opacity: 0.5; cursor: default; }
</style>
