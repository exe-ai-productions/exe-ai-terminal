<script>
  /* Getting a model — the recommended list and the search next to it.

     The program has always assumed a model server was already running. For
     whoever installs it fresh that assumption is the whole problem: nothing
     happens, and nothing says why. This panel is the answer we can give
     today — which model to take, and the finished command to start it.

     One button per model, and nothing else. A command to copy would have
     been quicker to build and would have missed the whole purpose: whoever
     needs a terminal for this has already been sent somewhere they did not
     want to go. Pick, press, watch the bar, done — the server next door
     starts it. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde } from '../lib/zustand.svelte.js'
  import { EMPFEHLUNGEN } from '../lib/modellempfehlungen.js'

  let suchbegriff = $state('')
  let treffer = $state(null)
  let sucht = $state(false)
  let stand = $state(null)
  let vorhanden = $state([])

  /* The files of the unfolded search hit. Only one hit is open at a time —
     the question is "which file of THIS one", not a spreadsheet of all. */
  let offenesRepo = $state(null)
  let dateien = $state(null)
  let repoAugen = $state(null)
  let dateienLaden = $state(false)

  /* The eyes that follow the model: once the model file has arrived, its
     vision projector is fetched next — same button, nobody has to know
     what an mmproj is. One at a time, like the download itself. */
  let nachzug = null

  const laedt = $derived(Boolean(stand) && !stand.fertig && !stand.fehler)

  /* The speed, measured between two polls and lightly smoothed — the
     difference between "waiting" and "stuck" is a number. */
  let tempo = $state(0)
  let messung = null

  function tempoMessen(neu) {
    const jetzt = Date.now()
    if (neu && messung && messung.datei === neu.datei && jetzt > messung.zeit) {
      const frisch = ((neu.geladen - messung.geladen) / (jetzt - messung.zeit)) * 1000
      tempo = tempo ? tempo * 0.4 + frisch * 0.6 : frisch
    } else {
      tempo = 0
    }
    messung = neu ? { datei: neu.datei, geladen: neu.geladen, zeit: jetzt } : null
  }

  const mbs = $derived(tempo > 50_000 ? (tempo / 1e6).toFixed(1) + ' MB/s' : '')

  /* While something is being fetched the bar has to move, so the state is
     asked for again. The rest of the time this costs one request every two
     seconds and keeps the list of what is already there up to date. */
  $effect(() => {
    const holen = async () => {
      try {
        stand = await api.modellHolenStand()
        tempoMessen(stand && !stand.fertig && !stand.fehler ? stand : null)
        const auskunft = await api.runnerAuskunft()
        vorhanden = [...auskunft.modelle.map((m) => m.name), ...(auskunft.mmproj ?? [])]
        if (stand?.fertig && nachzug && stand.datei === nachzug.datei) {
          const n = nachzug
          nachzug = null
          if (!vorhanden.includes(n.ziel)) {
            stand = await api.modellHolen(n.repo, n.mmproj, n.ziel)
          }
        }
      } catch {
        // A model server that is not answering is not this panel's problem.
      }
    }
    holen()
    const takt = setInterval(holen, 2000)
    return () => clearInterval(takt)
  })

  const istDa = (datei) => vorhanden.includes(datei)
  const wirdGeholt = (datei) => laedt && stand?.datei === datei
  /* A download that died mid-way must say so — the bar disappearing on its
     own looks like a broken program. A cancel is the one exception: whoever
     pressed it knows. */
  const schiefGegangen = (datei) =>
    stand?.fehler && stand.fehler !== 'abgebrochen' && stand.datei === datei

  /* The search runs while typing. Two beats, not one keystroke: the pause is
     what turns letters into a word, and Enter skips it for the impatient. */
  let takt = null
  function tippt() {
    clearTimeout(takt)
    takt = setTimeout(suchen, 400)
  }

  async function suchen() {
    clearTimeout(takt)
    const begriff = suchbegriff.trim()
    if (!begriff) {
      treffer = null
      return
    }
    sucht = true
    try {
      treffer = await api.modellSuche(begriff, 'gguf')
    } catch (fehler) {
      melde(fehler.message, 'fehler')
      treffer = []
    } finally {
      sucht = false
    }
  }

  async function aufklappen(fund) {
    if (offenesRepo === fund.id) {
      offenesRepo = null
      return
    }
    offenesRepo = fund.id
    dateien = null
    repoAugen = null
    dateienLaden = true
    try {
      const antwort = await api.modellDateien(fund.id)
      dateien = antwort.dateien
      repoAugen = antwort.mmproj
    } catch (fehler) {
      melde(fehler.message, 'fehler')
      dateien = []
    } finally {
      dateienLaden = false
    }
  }

  /* Local name for a found repository's projector: the model's own stem
     plus the projector's tail, so the runner can tie the two together and
     two bare `mmproj-BF16.gguf` never collide. */
  const augenZiel = (modellDatei, mmprojDatei) =>
    modellDatei.replace(/\.gguf$/i, '') +
    '-' + mmprojDatei.slice(mmprojDatei.toLowerCase().indexOf('mmproj'))

  async function holen(repo, datei, augen = null, ziel = null) {
    try {
      stand = await api.modellHolen(repo, datei, ziel)
      nachzug = augen ? { repo, datei, ...augen } : null
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  /* The button fetches what is missing — the model, or only its eyes when
     the model already arrived. The follow-up marker lives in page memory,
     so a reload in mid-download would otherwise strand a model without
     its projector, with a button that keeps failing on "already there". */
  function fehlendesHolen(repo, datei, mmproj, mmprojZiel) {
    if (!istDa(datei)) {
      return holen(repo, datei, mmproj ? { mmproj, ziel: mmprojZiel } : null)
    }
    return holen(repo, mmproj, null, mmprojZiel)
  }

  async function abbrechen() {
    await api.modellHolenAbbrechen()
  }

  const gb = (bytes) => (bytes / 1e9).toFixed(1)

  const zahl = (n) => (n >= 1000 ? Math.round(n / 1000) + 'k' : String(n))

  /* The optional Hugging Face token: lifts rate limits, opens gated
     models. Asked once when the panel opens; set like every other key —
     stored on this machine, shown never. */
  let hfGesetzt = $state(false)
  let hfEingabe = $state('')
  $effect(() => {
    api.hfTokenStand().then((s) => (hfGesetzt = s.gesetzt)).catch(() => {})
  })
  async function hfSetzen() {
    try {
      await api.hfTokenSetzen(hfEingabe.trim())
      hfEingabe = ''
      hfGesetzt = true
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }
</script>

<div class="tafel">

  <h4>{t('modell.empfohlen')}</h4>
  {#each EMPFEHLUNGEN as stufe}
    <div class="stufe">
      <div class="stufenkopf">{t('modell.bis_gb', { gb: stufe.bis })}</div>
      {#each stufe.modelle as m}
        {@const dran = wirdGeholt(m.datei) || (m.mmproj_ziel && wirdGeholt(m.mmproj_ziel))}
        <div class="zeile">
          <span class="wer">
            <span class="name">{m.name}</span>
            <span class="unter">{t('modell.' + m.warum)} · {t('modell.gb', { zahl: m.groesse })}</span>
          </span>
          {#if istDa(m.datei) && (!m.mmproj_ziel || istDa(m.mmproj_ziel))}
            <span class="fertig">{t('modell.im_ordner')}</span>
          {:else if dran}
            <button class="knopf still" onclick={abbrechen}>{t('modell.abbrechen')}</button>
          {:else}
            <button
              class="knopf wichtig"
              onclick={() => fehlendesHolen(m.id, m.datei, m.mmproj, m.mmproj_ziel)}
              disabled={laedt}
            >
              {t('modell.herunterladen')}
            </button>
          {/if}
        </div>
        {#if dran}
          <!-- Blue is the house colour for "running", and that is what this
               is: not an error, not a result, something in progress. -->
          <div class="balkenzeile">
            <span class="balken"><i style="width:{Math.round(stand.anteil * 100)}%"></i></span>
            <span class="balkenzahl">
              {m.mmproj_ziel && stand.datei === m.mmproj_ziel ? t('modell.augen') + ' · ' : ''}{gb(stand.geladen)} / {gb(stand.gesamt)} GB · {Math.round(stand.anteil * 100)} %{mbs ? ' · ' + mbs : ''}
            </span>
          </div>
        {:else if schiefGegangen(m.datei) || (m.mmproj_ziel && schiefGegangen(m.mmproj_ziel))}
          <!-- Red is the house colour for "failed" — a fact, said once,
               replaced by the next attempt. -->
          <div class="fehlzeile">{t('fehler.download_fehlgeschlagen')}</div>
        {/if}
      {:else}
        <!-- An empty step says "not chosen yet", which is true. Leaving it
             out would say "there is nothing for your machine". -->
        <div class="offen-noch">{t('modell.kommt_noch')}</div>
      {/each}
    </div>
  {/each}

  <h4>{t('modell.selbst_suchen')}</h4>
  <div class="suchzeile">
    <input
      class="feld"
      bind:value={suchbegriff}
      placeholder={t('modell.suchen_platzhalter')}
      oninput={tippt}
      onkeydown={(e) => { if (e.key === 'Enter') suchen() }}
    />
  </div>

  {#if sucht}
    <p class="leer">{t('modell.suche_laeuft')}</p>
  {:else if treffer?.length}
    {#each treffer as f (f.id)}
      <div
        class="zeile klappbar"
        class:offen={offenesRepo === f.id}
        role="button"
        tabindex="0"
        onclick={() => aufklappen(f)}
        onkeydown={(e) => { if (e.key === 'Enter') aufklappen(f) }}
      >
        <span class="wer">
          <span class="name">{f.name}</span>
          <span class="unter">{f.anbieter}</span>
        </span>
        <span class="fertig">{zahl(f.ladungen)} ↓</span>
        <span class="pfeil" class:auf={offenesRepo === f.id} aria-hidden="true">▸</span>
      </div>
      {#if offenesRepo === f.id}
        {#if dateienLaden}
          <p class="leer eingerueckt">{t('modell.dateien_laden')}</p>
        {:else if dateien?.length}
          {#each dateien as d (d.datei)}
            {@const ziel = repoAugen ? augenZiel(d.datei, repoAugen.datei) : null}
            {@const dran = wirdGeholt(d.datei) || (ziel && wirdGeholt(ziel))}
            <div class="zeile datei">
              <span class="wer">
                <span class="name">{d.datei}</span>
                <span class="unter">{t('modell.gb', { zahl: d.groesse_gb })}</span>
              </span>
              {#if istDa(d.datei) && (!ziel || istDa(ziel))}
                <span class="fertig">{t('modell.im_ordner')}</span>
              {:else if dran}
                <button class="knopf still" onclick={abbrechen}>{t('modell.abbrechen')}</button>
              {:else}
                <button
                  class="knopf wichtig"
                  onclick={() => fehlendesHolen(f.id, d.datei, repoAugen?.datei, ziel)}
                  disabled={laedt}
                >
                  {t('modell.herunterladen')}
                </button>
              {/if}
            </div>
            {#if dran}
              <div class="balkenzeile">
                <span class="balken"><i style="width:{Math.round(stand.anteil * 100)}%"></i></span>
                <span class="balkenzahl">
                  {ziel && stand.datei === ziel ? t('modell.augen') + ' · ' : ''}{gb(stand.geladen)} / {gb(stand.gesamt)} GB · {Math.round(stand.anteil * 100)} %{mbs ? ' · ' + mbs : ''}
                </span>
              </div>
            {:else if schiefGegangen(d.datei) || (ziel && schiefGegangen(ziel))}
              <div class="fehlzeile">{t('fehler.download_fehlgeschlagen')}</div>
            {/if}
          {/each}
        {:else}
          <p class="leer eingerueckt">{t('modell.keine_dateien')}</p>
        {/if}
      {/if}
    {/each}
  {:else if treffer}
    <p class="leer">{t('modell.keine_treffer')}</p>
  {/if}

  {#if hfGesetzt}
    <p class="leer">{t('modell.hf_token_gesetzt')}</p>
  {:else}
    <div class="suchzeile hf">
      <input
        class="feld"
        type="password"
        bind:value={hfEingabe}
        placeholder={t('modell.hf_token')}
        autocomplete="off"
        onkeydown={(e) => { if (e.key === 'Enter' && hfEingabe.trim().length >= 8) hfSetzen() }}
      />
      <button class="knopf" disabled={hfEingabe.trim().length < 8} onclick={hfSetzen}>
        {t('modell.verbinden')}
      </button>
    </div>
    <p class="leer klein">{t('modell.hf_token_hinweis')}</p>
  {/if}

  <!-- The way to what all the buttons above produce: the folder itself. -->
  <button class="knopf ordner" onclick={() => api.modellordnerOeffnen().catch((f) => melde(f.message, 'fehler'))}>
    {t('modell.ordner_oeffnen')}
  </button>

</div>

<style>
  .tafel { display: flex; flex-direction: column; }
  h4 {
    font-size: 10.5px;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 500;
    margin: 4px 0 8px;
  }
  h4 + h4, .stufe + h4 { margin-top: 20px; }

  .stufe { margin-bottom: 10px; }
  .stufenkopf {
    font-size: 11.5px;
    color: var(--text-still);
    padding: 0 2px 4px;
  }
  .offen-noch {
    font-size: 12px;
    color: var(--text-still);
    padding: 6px 12px;
    border: 1px dashed var(--linie);
    border-radius: 10px;
  }

  .zeile {
    display: flex;
    align-items: center;
    gap: 10px;
    border: 1px solid var(--linie);
    border-radius: 10px;
    background: var(--bg-erhoben);
    color: var(--text);
    padding: 9px 10px 9px 12px;
    margin-bottom: 5px;
  }
  .wer { flex: 1; min-width: 0; }
  .name {
    display: block;
    font-size: 13.5px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* Size and downloads are facts about a model, not states it is in — so
     they carry no colour, only the quietest brightness. */
  .unter, .zahl { color: var(--text-still); font-size: 11.5px; }
  .zahl { flex: none; font-variant-numeric: tabular-nums; }

  /* The bar while a model is being fetched. Blue means running — the house
     colour for something in progress, not a result and not a fault. */
  .balkenzeile { display: flex; align-items: center; gap: 10px; margin: -1px 0 9px; padding: 0 2px; }
  .balken { flex: 1; height: 5px; border-radius: 99px; background: var(--linie); overflow: hidden; }
  .balken i { display: block; height: 100%; background: var(--blau); transition: width 0.3s; }
  .balkenzahl {
    font: 400 11.5px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text-still); font-variant-numeric: tabular-nums; white-space: nowrap;
  }
  .fertig { flex: none; font-size: 11.5px; color: var(--text-still); white-space: nowrap; }

  .suchzeile { display: flex; gap: 8px; margin-bottom: 10px; }
  .feld {
    flex: 1;
    min-width: 0;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg);
    color: var(--text);
    font: inherit;
    font-size: 13.5px;
    padding: 8px 12px;
  }
  .feld:focus { outline: 2px solid var(--linie-stark); outline-offset: -2px; }

  /* A hit unfolds into its files; the arrow is the only thing that turns. */
  .zeile.klappbar { cursor: pointer; }
  .pfeil { color: var(--text-still); font-size: 11px; transition: transform 0.15s; }
  .pfeil.auf { transform: rotate(90deg); }
  .zeile.datei { margin-left: 18px; }
  .zeile.datei + .balkenzeile, .zeile.datei + .fehlzeile { margin-left: 18px; }
  .leer.eingerueckt { padding-left: 20px; }

  .knopf {
    flex: none;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 12.5px;
    padding: 5px 12px;
    border-radius: 9px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.12s, opacity 0.12s, transform 0.08s;
  }
  .knopf:hover:not(:disabled) { background: var(--linie); }
  .knopf:active:not(:disabled) { transform: scale(0.975); }
  .knopf.wichtig { background: var(--text); color: var(--bg); border-color: var(--text); }
  .knopf.wichtig:hover:not(:disabled) { background: var(--text); opacity: 0.88; }
  .knopf.still { color: var(--text-still); border-color: var(--linie); }
  .knopf:disabled { opacity: 0.5; cursor: default; }

  .leer { color: var(--text-still); font-size: 13px; padding: 6px 2px; }

  /* Failed is a fact and gets the house colour for it — one line, no box. */
  .fehlzeile { font-size: 11.5px; color: var(--rot); padding: 0 2px 8px; margin-top: -1px; }

  .ordner { align-self: flex-start; margin-top: 14px; }
  .suchzeile.hf { margin-top: 14px; margin-bottom: 4px; }
  .leer.klein { font-size: 11.5px; padding-top: 0; }
</style>
