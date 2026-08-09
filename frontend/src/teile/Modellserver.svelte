<script>
  /* The model server, switched from here instead of from a terminal.

     Everything a start script hides in comments stands here as a field with
     a sentence beside it: how much context, how much of it on the graphics
     card, which port. Whoever changes one can see what it means without
     having read anything first.

     The log is folded away. A window that always shows it bursts its height,
     and this one may not be taller than the other option windows. A log is
     interesting exactly when something goes wrong — then it unfolds. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde, modelleLaden, zustand } from '../lib/zustand.svelte.js'

  let auskunft = $state(null)
  let protokoll = $state([])
  let protokollOffen = $state(false)
  let arbeitet = $state(false)
  let protokollKasten = $state(null)
  /* Fetching the server program itself — the way out of "not installed". */
  let programmStand = $state(null)
  const programmLaedt = $derived(
    Boolean(programmStand) && !programmStand.fertig && !programmStand.fehler,
  )

  /* The end of a log is where the news is — a fresh line pulls the view
     down, the way a terminal would. */
  $effect(() => {
    void protokoll
    if (protokollKasten) protokollKasten.scrollTop = protokollKasten.scrollHeight
  })

  let kontext = $state(8192)
  let schichten = $state(99)
  let port = $state(8080)
  let modell = $state('')

  const laeuft = $derived(Boolean(auskunft?.laeuft))
  const hatProgramm = $derived(Boolean(auskunft?.programm))
  const hatModelle = $derived((auskunft?.modelle?.length ?? 0) > 0)

  async function laden() {
    try {
      auskunft = await api.runnerAuskunft()
      if (!modell) modell = auskunft.modell || auskunft.modelle[0]?.name || ''
      if (auskunft.laeuft) {
        kontext = auskunft.kontext
        schichten = auskunft.schichten
        port = auskunft.port
      }
      if (protokollOffen || auskunft.laeuft) protokoll = await api.runnerProtokoll()
      /* While the server program is missing or arriving, watch the fetch —
         the moment it lands, the form above replaces this whole section. */
      if (!auskunft.programm) programmStand = await api.serverProgrammStand()
      /* A server that runs but is missing from the model list is still
         loading its model. Ask with a fresh check until it appears — the
         regular pass comes only every half minute, and whoever pressed
         "start" is watching right now. */
      if (auskunft.laeuft && !zustand.modelle.some((m) => m.anbieter === 'runner' && m.erreichbar)) {
        await modelleLaden(true)
      }
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  /* While a server runs, its output keeps coming. Polling and not a stream:
     a log line is not worth a second connection that has to be held open. */
  $effect(() => {
    laden()
    const takt = setInterval(laden, 2000)
    return () => clearInterval(takt)
  })

  async function starten() {
    arbeitet = true
    try {
      auskunft = await api.runnerStarten({ modell, kontext, schichten, port })
      protokollOffen = true
      await modelleLaden(true)
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    } finally {
      arbeitet = false
    }
  }

  async function anhalten() {
    arbeitet = true
    try {
      auskunft = await api.runnerStoppen()
      /* The entry leaves the picker with the server — no fresh check
         needed, the service already said goodbye to it. */
      await modelleLaden()
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    } finally {
      arbeitet = false
    }
  }
</script>

<div class="tafel">
  <h4>{t('modell.server')}</h4>

  {#if !hatProgramm}
    <p class="hinweis">{t('modell.kein_programm')}</p>
    <p class="hinweis leiser">{t('modell.server_holen_erklaerung')}</p>
    {#if programmLaedt}
      <div class="balkenzeile">
        <span class="balken"><i style="width:{Math.round(programmStand.anteil * 100)}%"></i></span>
        <span class="balkenzahl">{Math.round(programmStand.anteil * 100)} %</span>
      </div>
    {:else}
      {#if programmStand?.fehler}
        <p class="fehlzeile">{t('fehler.serverdownload_fehlgeschlagen')}</p>
      {/if}
      <div class="knopfzeile">
        <button
          class="knopf wichtig"
          onclick={() => api.serverProgrammHolen().then((s) => (programmStand = s)).catch((f) => melde(f.message, 'fehler'))}
        >
          {t('modell.server_holen')}
        </button>
      </div>
    {/if}
  {:else if !hatModelle && !laeuft}
    <p class="hinweis">{t('modell.kein_modell_da')}</p>
  {:else}
    <div class="regler">
      <label for="rs-modell">{t('modell.feld_modell')}<span>{t('modell.feld_modell_hilfe')}</span></label>
      <select id="rs-modell" class="wert" bind:value={modell} disabled={laeuft}>
        {#each auskunft?.modelle ?? [] as m}
          <option value={m.name}>{m.name} · {m.groesse_gb} GB</option>
        {/each}
      </select>

      <label for="rs-kontext">{t('modell.feld_kontext')}<span>{t('modell.feld_kontext_hilfe')}</span></label>
      <input id="rs-kontext" class="wert" type="number" bind:value={kontext} disabled={laeuft}
             min="512" max="1048576" step="1024" />

      <label for="rs-schichten">{t('modell.feld_schichten')}<span>{t('modell.feld_schichten_hilfe')}</span></label>
      <input id="rs-schichten" class="wert" type="number" bind:value={schichten} disabled={laeuft}
             min="0" max="999" />

      <label for="rs-port">{t('modell.feld_port')}<span>{t('modell.feld_port_hilfe')}</span></label>
      <input id="rs-port" class="wert" type="number" bind:value={port} disabled={laeuft}
             min="1024" max="65535" />
    </div>

    <!-- Colour means state here, and only here: green is ready, grey is off. -->
    <div class="stand">
      <span class="punkt" class:an={laeuft}></span>
      {laeuft
        ? t('modell.server_bereit', { kontext: auskunft.kontext, port: auskunft.port })
        : t('modell.server_aus')}
    </div>

    <div class="knopfzeile">
      {#if laeuft}
        <button class="knopf" onclick={anhalten} disabled={arbeitet}>
          {t('modell.server_anhalten')}
        </button>
      {:else}
        <button class="knopf wichtig" onclick={starten} disabled={arbeitet || !modell}>
          {t('modell.server_starten')}
        </button>
      {/if}
      <button class="klapper" onclick={() => (protokollOffen = !protokollOffen)}>
        {t('modell.protokoll')} {protokollOffen ? '▾' : '▸'}
      </button>
    </div>

    {#if protokollOffen}
      <pre class="protokoll" bind:this={protokollKasten}>{protokoll.join('\n') || '—'}</pre>
    {/if}
  {/if}
</div>

<style>
  .tafel { display: flex; flex-direction: column; }
  h4 {
    font-size: 10.5px; letter-spacing: 0.09em; text-transform: uppercase;
    color: var(--text-still); font-weight: 500; margin: 4px 0 10px;
  }
  .hinweis { color: var(--text-still); font-size: 13px; margin: 4px 0; }
  .hinweis.leiser { font-size: 12px; margin-bottom: 10px; }
  .fehlzeile { font-size: 11.5px; color: var(--rot); margin: 0 0 8px; }
  .balkenzeile { display: flex; align-items: center; gap: 10px; margin: 6px 0 2px; }
  .balken { flex: 1; height: 5px; border-radius: 99px; background: var(--linie); overflow: hidden; }
  .balken i { display: block; height: 100%; background: var(--blau); transition: width 0.3s; }
  .balkenzahl {
    font: 400 11.5px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text-still); font-variant-numeric: tabular-nums;
  }

  .regler {
    display: grid; grid-template-columns: 1fr auto; gap: 9px 12px;
    align-items: center; margin-bottom: 12px;
  }
  label { font-size: 13px; }
  label span { display: block; font-size: 11.5px; color: var(--text-still); }
  .wert {
    border: 1px solid var(--linie-stark); border-radius: 8px; background: var(--bg);
    color: var(--text); font: 400 12.5px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    padding: 6px 10px; min-width: 130px; text-align: right;
  }
  .wert:disabled { color: var(--text-still); }
  select.wert { text-align: left; }

  .stand {
    display: flex; align-items: center; gap: 8px; font-size: 12.5px;
    color: var(--text-leise); padding: 9px 12px;
    border: 1px solid var(--linie); border-radius: 10px; margin-bottom: 9px;
  }
  .punkt { width: 7px; height: 7px; border-radius: 99px; background: var(--text-still); flex: none; }
  .punkt.an { background: var(--gruen); }

  .knopfzeile { display: flex; align-items: center; gap: 8px; }
  .knopf {
    border: 1px solid var(--linie-stark); background: none; color: var(--text);
    font: inherit; font-size: 12.5px; padding: 6px 13px; border-radius: 9px; cursor: pointer;
    transition: background 0.12s, opacity 0.12s, transform 0.08s;
  }
  .knopf:hover:not(:disabled) { background: var(--linie); }
  .knopf:active:not(:disabled) { transform: scale(0.975); }
  .knopf.wichtig { background: var(--text); color: var(--bg); border-color: var(--text); }
  .knopf.wichtig:hover:not(:disabled) { background: var(--text); opacity: 0.88; }
  .knopf:disabled { opacity: 0.5; cursor: default; }
  .klapper {
    margin-left: auto; border: none; background: none; color: var(--text-still);
    font: inherit; font-size: 12px; cursor: pointer; padding: 6px 4px;
  }

  .protokoll {
    margin: 9px 0 0; padding: 10px 12px; background: var(--code-bg);
    border: 1px solid var(--linie); border-radius: 8px;
    font: 400 11px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text-leise); max-height: 150px; overflow: auto; white-space: pre-wrap;
  }
</style>
