<script>
  import { rollfade } from '../lib/rollfade.js'
  /* The catalogue — a gallery of curated models, and the whole of Hugging
     Face one search away.

     Its own window because getting a model is its own act, apart from
     running one: the curated cards answer "which of these is for my
     machine", the search answers "I already know what I want". The card is
     a model; clicking it opens the build chooser. A finished download turns
     the card's button into Start, which brings the server up with sensible
     defaults and hands over to the local view.

     One download runs at a time. Companions (vision, speed module) follow
     the model on the same button, and each carries which model it belongs
     to and its role, so the service records the association and the runner
     attaches it later without guessing. */
  import Fenster from './Fenster.svelte'
  import Schriftzug from './Schriftzug.svelte'
  import Modellkarte from './Modellkarte.svelte'
  import Modelldetail from './Modelldetail.svelte'
  import { api } from '../lib/api.js'
  import { weg, zurueckgehen } from '../lib/fensterweg.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde, modelleLaden, zustand } from '../lib/zustand.svelte.js'
  import {
    ARTEN, ZUBEHOER_ZIEL, SPALTEN_ZUBEHOER, ZUBEHOER_ORDNER, SUCHBARE_ARTEN,
    kartePasst, katalogFuer, passendeFassung,
  } from '../lib/modellempfehlungen.js'
  import { modellMarke } from '../lib/anbieterzeichen.js'

  let { offen = $bindable(false) } = $props()

  /* Which of the three tabs is open — Chat, Einbettung, Bild. Always one of
     them, always switchable back to Chat: the search below is scoped to
     this, and so is the curated gallery. */
  let art = $state('chat')
  /* Whether this tab searches at all, and whether it is the accessory tab
     (five columns instead of the plain grid). */
  const suchbar = $derived(SUCHBARE_ARTEN.includes(art))
  const istZubehoer = $derived(art === 'zubehoer')
  function artWaehlen(neu) {
    if (neu === art) return
    art = neu
    detail = null
    // Leaving for a tab without a search: clear the field and its results,
    // or a stale term would keep the gallery dimmed on a tab that cannot search.
    if (!SUCHBARE_ARTEN.includes(neu)) {
      suchbegriff = ''
      treffer = null
      offenesRepo = null
    } else if (suchAktiv) {
      suchen()
    }
  }

  /* Open the file manager at one accessory folder — the picture side and the
     chat side each have their own whitelisted route. */
  function ordnerOeffnen(sorte) {
    const ziel = ZUBEHOER_ORDNER[sorte]
    if (!ziel) return
    const ruf = ziel.seite === 'chat'
      ? api.chatBegleiterOrdner(ziel.unter)
      : api.bildBegleiterOrdner(ziel.unter)
    ruf.catch(() => {})
  }

  /* A server panel can send the user here with its own tab already open —
     the wish is read once and cleared, so the next plain open starts on
     Chat as always. */
  $effect(() => {
    if (offen && zustand.katalogArtWunsch) {
      artWaehlen(zustand.katalogArtWunsch)
      zustand.katalogArtWunsch = null
    }
  })

  /* What the machine holds and what already lies in the folder — the two
     facts every card reads. Polled gently while the window is open, so a
     finished download lights up the right card without a reopen. */
  let maschineGb = $state(null)
  let vorhanden = $state([])
  let stand = $state(null)
  let nachzuege = []

  /* Which model the detail shows, or null for the gallery. */
  let detail = $state(null)

  const laedt = $derived(Boolean(stand) && !stand.fertig && !stand.fehler)

  /* Download speed, measured between two polls and lightly smoothed — the
     difference between "waiting" and "stuck" is this number. */
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

  const gb = (bytes) => (bytes / 1e9).toFixed(1)
  const istDa = (datei) => Boolean(datei) && vorhanden.includes(datei)
  const wirdGeholt = (datei) => laedt && stand?.datei === datei

  function dran(f) {
    // An accessory keeps its local name in `ziel` (the remote file is named
    // the same across repositories); the progress and the presence check must
    // follow that name, not the remote one, or a renamed card never registers.
    return wirdGeholt(f.ziel ?? f.datei) || (f.mmproj_ziel && wirdGeholt(f.mmproj_ziel)) || (f.drafter_ziel && wirdGeholt(f.drafter_ziel))
  }
  function status(f) {
    if (dran(f)) return 'laedt'
    if (istDa(f.ziel ?? f.datei)) return 'bereit'
    return 'neu'
  }
  function fortschritt(f) {
    if (!dran(f) || !stand) return null
    const teil =
      stand.datei === f.mmproj_ziel ? t('modell.augen') + ' · '
      : stand.datei === f.drafter_ziel ? t('modell.feld_drafter') + ' · '
      : ''
    const anteil = Math.round((stand.anteil ?? 0) * 100)
    const text = `${teil}${gb(stand.geladen)} / ${gb(stand.gesamt)} GB · ${anteil} %${mbs ? ' · ' + mbs : ''}`
    return { anteil, text }
  }

  /* Fitting cards to the front — a fit is a fact worth surfacing. Ties keep
     the curated order. */
  const karten = $derived(
    [...katalogFuer(art)].sort((a, b) => Number(kartePasst(b, maschineGb)) - Number(kartePasst(a, maschineGb))),
  )

  $effect(() => {
    if (!offen) return
    const holen = async () => {
      try {
        stand = await api.modellHolenStand()
        tempoMessen(stand && !stand.fertig && !stand.fehler ? stand : null)
        const auskunft = await api.runnerAuskunft()
        maschineGb = auskunft.speicher_gb ?? null
        // Collected fully, assigned ONCE at the end: an intermediate
        // assignment made every card flip to "download" for a blink on
        // each 2-second poll while the picture list was still in flight.
        const liste = [
          ...auskunft.modelle.map((m) => m.name),
          ...(auskunft.mmproj ?? []),
          ...(auskunft.mtp ?? []).map((m) => m.name),
        ]
        // Picture checkpoints and accessories land in the picture side's own
        // folders, which the runner's list does not see. On those two tabs,
        // add what the picture side already has, or a downloaded model keeps
        // offering itself and a second click only earns a "already there"
        // error (found live with CyberRealistic XL on the picture tab).
        if (art === 'zubehoer' || art === 'bild') {
          try {
            const bild = await api.bildmodelle()
            liste.push(
              ...(bild.modelle ?? []),
              ...(bild.vaes ?? []), ...(bild.loras ?? []), ...(bild.yolos ?? []),
            )
          } catch {
            // No picture server yet — cards just show as not installed.
          }
        }
        // Embedding models land in the embedding server's own folder, which
        // the runner's list does not see either — same story as the picture
        // side, same fix, or a finished download keeps offering itself.
        if (art === 'einbettung') {
          try {
            const einbettung = await api.einbettungAuskunft()
            liste.push(...(einbettung.modelle ?? []))
          } catch {
            // No embedding server yet — cards just show as not installed.
          }
        }
        vorhanden = liste
        if (stand?.fertig && !stand.fehler && nachzuege.length) {
          while (nachzuege.length && vorhanden.includes(nachzuege[0].ziel)) nachzuege.shift()
          const n = nachzuege.shift()
          if (n) {
            try {
              stand = await api.modellHolen(n.repo, n.datei, n.ziel ?? null, n.gehoert_zu ?? null, n.rolle ?? null, n.art ?? 'chat', n.unterordner ?? null)
            } catch {
              // A broken link ends the chain; the button offers the rest.
              nachzuege = []
            }
          }
        }
      } catch {
        // A service that is not answering is not this window's problem yet.
      }
    }
    holen()
    const takt = setInterval(holen, 2000)
    return () => clearInterval(takt)
  })

  /* The companions a build fetches after the model: its vision, then its
     speed module, each named locally so two bare files never collide and
     each tagged with the model it belongs to. */
  function begleiterJobs(f) {
    const jobs = []
    if (f.mmproj) jobs.push({ repo: f.id, datei: f.mmproj, ziel: f.mmproj_ziel, gehoert_zu: f.datei, rolle: 'mmproj' })
    if (f.drafter) jobs.push({ repo: f.drafter_repo ?? f.id, datei: f.drafter, ziel: f.drafter_ziel, gehoert_zu: f.datei, rolle: 'mtp' })
    return jobs
  }
  /* Where a card downloads to. An accessory card carries its own destination
     by its sorte (folder art + sub-folder, or a companion role in the model
     folder); everything else lands in the open tab's art. */
  function routing(karte) {
    if (karte?.zubehoer) return ZUBEHOER_ZIEL[karte.sorte] ?? { art }
    return { art }
  }
  async function starteJob(job, rest, ziel) {
    try {
      stand = await api.modellHolen(
        job.repo, job.datei, job.ziel ?? null,
        job.gehoert_zu ?? null, job.rolle ?? ziel.rolle ?? null,
        ziel.art, ziel.unterordner ?? null,
      )
      nachzuege = rest.map((j) => ({ ...j, art: ziel.art, unterordner: ziel.unterordner ?? null }))
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }
  /* Fetch what is missing — the model, or only the companions that never
     arrived. The follow-up list lives in memory, so a reopen mid-download
     never strands a model without its projector or its draft. An accessory
     names its local file with `ziel` (two LoRA repositories share a file
     name), so the presence check follows that name, not the remote one. */
  async function fassungHolen(f, karte) {
    const ziel = routing(karte)
    const fehlend = begleiterJobs(f).filter((j) => !istDa(j.ziel))
    const lokal = f.ziel ?? f.datei
    if (!istDa(lokal)) {
      await starteJob({ repo: f.id, datei: f.datei, ziel: f.ziel ?? null }, fehlend, ziel)
      return
    }
    const [erst, ...rest] = fehlend
    if (erst) await starteJob(erst, rest, ziel)
  }

  async function abbrechen() {
    try {
      await api.modellHolenAbbrechen()
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  /* A finished model starts here and hands over to the local view: the
     server comes up with the chosen build, its speed module when one lies
     ready, and everyday defaults for context and port. */
  async function starten(f) {
    try {
      if (art === 'einbettung') {
        // An embedding model belongs to the embedding server, not the chat
        // runner — the chat runner would refuse it as outside its folder.
        await api.einbettungStarten(f.datei)
      } else {
        await api.runnerStarten({
          modell: f.datei,
          kontext: 32768,
          schichten: 99,
          port: 8080,
          drafter: f.drafter_ziel && istDa(f.drafter_ziel) ? f.drafter_ziel : null,
        })
      }
      await modelleLaden(true)
      offen = false
      zustand.lokalOffen = true
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  // ---- Free search across Hugging Face ------------------------------------
  let suchbegriff = $state('')
  let treffer = $state(null)
  let sucht = $state(false)
  let offenesRepo = $state(null)
  let dateien = $state(null)
  let repoAugen = $state(null)
  let dateienLaden = $state(false)
  let taktSuche = null

  const suchAktiv = $derived(suchbegriff.trim().length > 0)

  function tippt() {
    clearTimeout(taktSuche)
    taktSuche = setTimeout(suchen, 400)
  }
  /* Only the newest request may write the results: a slow answer for the
     PREVIOUS tab or term would otherwise land last and show its models
     under the wrong tab. */
  let suchlauf = 0
  async function suchen() {
    clearTimeout(taktSuche)
    const begriff = suchbegriff.trim()
    if (!begriff) {
      treffer = null
      return
    }
    const lauf = ++suchlauf
    sucht = true
    try {
      const antwort = await api.modellSuche(begriff, art)
      if (lauf !== suchlauf) return
      treffer = antwort
    } catch (fehler) {
      if (lauf !== suchlauf) return
      melde(fehler.message, 'fehler')
      treffer = []
    } finally {
      if (lauf === suchlauf) sucht = false
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
  /* Local name for a found projector: the model's own stem plus the
     projector's tail, so the runner can tie the two together. */
  const augenZiel = (modellDatei, mmprojDatei) =>
    modellDatei.replace(/\.gguf$/i, '') + '-' + mmprojDatei.slice(mmprojDatei.toLowerCase().indexOf('mmproj'))

  async function suchDateiHolen(repo, d) {
    if (istDa(d.datei)) return
    const jobs = []
    if (repoAugen) {
      const ziel = augenZiel(d.datei, repoAugen.datei)
      if (!istDa(ziel)) jobs.push({ repo, datei: repoAugen.datei, ziel, gehoert_zu: d.datei, rolle: 'mmproj' })
    }
    // A search hit downloads into the open tab's art (search runs only on the
    // searchable tabs); the routing argument is what starteJob now requires.
    await starteJob({ repo, datei: d.datei, ziel: null }, jobs, { art })
  }
  function suchDran(d) {
    const ziel = repoAugen ? augenZiel(d.datei, repoAugen.datei) : null
    return wirdGeholt(d.datei) || (ziel && wirdGeholt(ziel))
  }
  const zahlKurz = (n) => (n >= 1000 ? Math.round(n / 1000) + 'k' : String(n))
</script>

<Fenster bind:offen art="galerie" zurueck={weg.zurueck ? zurueckgehen : null}>
  <div class="kat-kopf">
    <div class="marke">
      <div class="markenzeile">
        <svg viewBox="0 0 100 100" width="40" height="40" fill="none" stroke="currentColor"
             stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="20" y="24" width="60" height="52" rx="11" />
          <path d="M35 40 h30 M35 50 h30 M35 60 h18" />
        </svg>
        <Schriftzug zug="katalog" hoehe={19} />
      </div>
      <div class="markensatz">{t('katalog.markensatz')}</div>
    </div>
    <div class="reiterleiste" role="tablist">
      {#each ARTEN as eintrag (eintrag)}
        <button
          role="tab"
          aria-selected={art === eintrag}
          class:aktiv={art === eintrag}
          onclick={() => artWaehlen(eintrag)}
        >
          {t(`katalog.art_${eintrag}`)}
        </button>
      {/each}
    </div>
    {#if maschineGb}
      <div class="maschine">
        <span class="wort">{t('katalog.maschine')}:</span>
        <span class="wert">{maschineGb} GB</span>
      </div>
    {/if}
  </div>

  {#if detail}
    <div class="rollbereich" use:rollfade>
      <Modelldetail
        karte={detail}
        {maschineGb}
        statusFuer={status}
        fortschrittFuer={fortschritt}
        onClose={() => (detail = null)}
        onDownload={(f) => fassungHolen(f, detail)}
        onCancel={abbrechen}
        onStart={(f) => starten(f)}
      />
    </div>
  {:else}
    {#if suchbar}
      <input
        class="suchfeld"
        bind:value={suchbegriff}
        placeholder={t('katalog.suchen')}
        oninput={tippt}
        onkeydown={(e) => { if (e.key === 'Enter') suchen() }}
      />
    {/if}

    {#snippet karteBlock(karte)}
      {@const f = passendeFassung(karte, maschineGb)}
      <Modellkarte
        {karte}
        fassung={f}
        passt={kartePasst(karte, maschineGb)}
        {maschineGb}
        status={status(f)}
        fortschritt={fortschritt(f)}
        onOeffnen={() => (detail = karte)}
        onDownload={() => fassungHolen(f, karte)}
        onCancel={abbrechen}
        onStart={() => starten(f)}
      />
    {/snippet}

    <div class="rollbereich">
      {#if istZubehoer}
        <!-- One column per accessory kind, each with its own "open folder"
             button; no search box on this tab. -->
        <div class="spaltenraster">
          {#each SPALTEN_ZUBEHOER as sorte (sorte)}
            <div class="zspalte">
              <div class="zkopf">
                <span class="ztitel">{t(`katalog.sorte_${sorte}`)}</span>
                <button class="ordnerknopf" onclick={() => ordnerOeffnen(sorte)}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                  </svg>
                  {t('katalog.ordner_zeigen')}
                </button>
              </div>
              {#each karten.filter((k) => k.sorte === sorte) as karte (karte.id)}
                {@render karteBlock(karte)}
              {/each}
            </div>
          {/each}
        </div>
      {:else}
        <div class="raster" class:gedimmt={suchAktiv}>
          {#each karten as karte (karte.id)}
            {@render karteBlock(karte)}
          {/each}
        </div>
        {#if !karten.length && !suchAktiv}
          <p class="leer">{t('katalog.keine_kuratierten')}</p>
        {/if}
      {/if}

      {#if suchbar && suchAktiv}
        <div class="suchteil">
          <h4 class="abschnitt">{t('katalog.von_hf')}</h4>
          {#if sucht}
            <p class="leer">{t('modell.suche_laeuft')}</p>
          {:else if treffer?.length}
            {#each treffer as f (f.id)}
              {@const marke = modellMarke(f.name, f.anbieter)}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div class="treffer" role="button" tabindex="0"
                   onclick={() => aufklappen(f)}
                   onkeydown={(e) => { if (e.key === 'Enter') aufklappen(f) }}>
                <div class="tmarke" class:echt={marke}>
                  {#if marke}
                    <svg viewBox={marke.vb} width="19" height="19" aria-hidden="true">{@html marke.html}</svg>
                  {:else}
                    {String(f.anbieter || '?').slice(0, 1).toUpperCase()}
                  {/if}
                </div>
                <div class="twer">
                  <div class="tname">{f.name}</div>
                  <div class="tunter">{f.anbieter}</div>
                </div>
                <span class="tzieh">{zahlKurz(f.ladungen)} ↓</span>
                <span class="tpfeil" class:auf={offenesRepo === f.id} aria-hidden="true">▸</span>
              </div>
              {#if offenesRepo === f.id}
                {#if dateienLaden}
                  <p class="leer eingerueckt">{t('modell.dateien_laden')}</p>
                {:else if dateien?.length}
                  {#each dateien as d (d.datei)}
                    {@const ziel = repoAugen ? augenZiel(d.datei, repoAugen.datei) : null}
                    <div class="treffer datei">
                      <div class="twer">
                        <div class="tname mono">{d.datei}</div>
                        <div class="tunter">{t('modell.gb', { zahl: d.groesse_gb })}</div>
                      </div>
                      {#if istDa(d.datei) && (!ziel || istDa(ziel))}
                        <span class="tzieh">{t('katalog.im_ordner')}</span>
                      {:else if suchDran(d)}
                        <button class="knopf still" onclick={abbrechen}>{t('katalog.abbrechen')}</button>
                      {:else}
                        <button class="knopf wichtig" onclick={() => suchDateiHolen(f.id, d)} disabled={laedt}>
                          {t('katalog.herunterladen')}
                        </button>
                      {/if}
                    </div>
                    {#if suchDran(d)}
                      <div class="laufbalken eingerueckt">
                        <span class="balken"><i style="width:{Math.round((stand?.anteil ?? 0) * 100)}%"></i></span>
                        <span class="laufzahl">{gb(stand.geladen)} / {gb(stand.gesamt)} GB · {Math.round((stand?.anteil ?? 0) * 100)} %{mbs ? ' · ' + mbs : ''}</span>
                      </div>
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
        </div>
      {/if}
    </div>
  {/if}
</Fenster>

<style>
  .kat-kopf {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin: 4px 0 14px;
    flex: none;
    flex-wrap: wrap;
  }
  /* The three catalogue tabs — Chat always reachable from the other two,
     the other two always reachable from Chat. The same segmented switch
     the settings and the sidebar wear (see SystemPrompt's .segment): the
     shape lives in one visual dialect, not a fifth hand-copy of it. */
  .reiterleiste {
    display: inline-flex;
    flex: none;
    background: var(--bg-seite);
    border: 1px solid var(--linie);
    border-radius: 9px;
    padding: 2px;
  }
  .reiterleiste button {
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12px;
    padding: 4px 11px;
    border-radius: 7px;
    cursor: pointer;
    transition: background 0.16s, color 0.16s;
  }
  .reiterleiste button:hover { color: var(--text); }
  .reiterleiste button.aktiv {
    background: var(--bg-erhoben);
    color: var(--text);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }
  .marke {
    min-width: 0;
  }
  .markenzeile {
    display: flex;
    align-items: center;
    gap: 14px;
    color: var(--text);
  }
  .markensatz {
    color: var(--text-still);
    font-size: 13.5px;
    margin-top: 8px;
  }
  .maschine {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: none;
  }
  .maschine .wort {
    font-weight: 600;
    font-size: 13px;
  }
  .maschine .wert {
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 4px 10px;
    font: 500 12.5px var(--schrift-fest);
    white-space: nowrap;
  }
  .suchfeld {
    flex: none;
    width: 100%;
    border: 1px solid var(--linie-stark);
    border-radius: 18px;
    background: var(--bg);
    color: var(--text);
    font: 14px var(--schrift);
    padding: 11px 16px;
    margin-bottom: 16px;
  }
  .suchfeld::placeholder {
    color: var(--text-still);
  }
  .suchfeld:focus {
    outline: 2px solid var(--linie-stark);
    outline-offset: -2px;
  }

  /* The scrolling half of the fixed-height gallery body: the head and the
     search field stay put, the cards scroll under them, the bar invisible. */
  .rollbereich {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 8px 2px 2px;
  }
  .raster {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    align-content: start;
    transition: opacity 0.16s;
  }
  @media (max-width: 900px) {
    .raster { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 620px) {
    .raster { grid-template-columns: 1fr; }
  }
  /* Typing pulls the eye to the results — the curated gallery steps back. */
  .raster.gedimmt {
    opacity: 0.32;
    pointer-events: none;
  }

  /* The accessory tab: one column per kind, each a vertical stack. Below the
     wide breakpoints the columns wrap into fewer, then one. */
  .spaltenraster {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    align-items: start;
  }
  @media (max-width: 1000px) {
    .spaltenraster { grid-template-columns: repeat(3, 1fr); }
  }
  @media (max-width: 700px) {
    .spaltenraster { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 480px) {
    .spaltenraster { grid-template-columns: 1fr; }
  }
  .zspalte {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
  }
  .zkopf {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    padding: 0 2px 2px;
  }
  .ztitel {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--text-leise);
  }
  .ordnerknopf {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border: 1px solid var(--linie-stark);
    background: var(--bg-leiste);
    color: var(--text-leise);
    font: inherit;
    font-size: 11px;
    padding: 4px 8px;
    border-radius: 8px;
    cursor: pointer;
    white-space: nowrap;
  }
  .ordnerknopf:hover {
    color: var(--text);
    border-color: var(--text-still);
  }

  .suchteil {
    margin-top: 18px;
  }
  .abschnitt {
    font-size: 10.5px;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 600;
    margin: 0 0 10px;
  }
  .treffer {
    display: flex;
    align-items: center;
    gap: 10px;
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg-erhoben);
    padding: 9px 12px;
    margin-bottom: 5px;
    cursor: pointer;
  }
  .treffer.datei {
    margin-left: 18px;
    cursor: default;
  }
  /* The maker's mark in front of a hit — the same language as the cards:
     a real vector in a solid frame, a dashed letter until one exists. */
  .tmarke {
    width: 30px;
    height: 30px;
    flex: none;
    border-radius: 9px;
    border: 1.5px dashed var(--linie-stark);
    color: var(--text-still);
    display: flex;
    align-items: center;
    justify-content: center;
    font: 700 11px var(--schrift);
  }
  .tmarke.echt {
    border: 1px solid var(--linie);
  }
  .twer {
    flex: 1;
    min-width: 0;
  }
  .tname {
    font-size: 13.5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tname.mono {
    font-family: var(--schrift-fest);
    font-size: 13px;
  }
  .tunter {
    font-size: 11.5px;
    color: var(--text-still);
  }
  .tzieh {
    flex: none;
    font-size: 11.5px;
    color: var(--text-still);
    white-space: nowrap;
  }
  .tpfeil {
    color: var(--text-still);
    font-size: 11px;
    transition: transform 0.15s;
  }
  .tpfeil.auf {
    transform: rotate(90deg);
  }
  .laufbalken {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: -1px 0 8px;
    padding: 0 2px;
  }
  .laufbalken.eingerueckt {
    margin-left: 18px;
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
  .leer {
    color: var(--text-still);
    font-size: 13px;
    padding: 6px 2px;
  }
  .leer.eingerueckt {
    padding-left: 20px;
  }
  .knopf {
    flex: none;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: 600 12.5px var(--schrift);
    padding: 5px 12px;
    border-radius: 9px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.12s, opacity 0.12s;
  }
  .knopf:hover:not(:disabled) {
    background: var(--linie);
  }
  .knopf.wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .knopf.wichtig:hover:not(:disabled) {
    background: var(--text);
    opacity: 0.88;
  }
  .knopf.still {
    color: var(--text-still);
    border-color: var(--linie);
  }
  .knopf:disabled {
    opacity: 0.5;
    cursor: default;
  }

  @media (max-width: 720px) {
    .rollbereich {
      overflow: visible;
    }
  }
</style>
