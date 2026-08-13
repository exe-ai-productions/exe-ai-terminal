<script>
  /* The model server — switched from here instead of from a terminal.

     One truth on top: a status card that says whether the server runs,
     which model, which speed module by name, and how much memory it holds.
     Below it the form, in named groups instead of a bare field list, and
     locked while the server runs — a running server is not edited, it is
     stopped first. On a fresh machine none of that shows yet; instead the
     three steps to a first model stand here.

     The speed module is not guessed. When the catalogue fetched the model
     it wrote which module belongs to it; the runner reads that and this
     form pre-picks it. The name heuristic is only a fallback for
     hand-placed files, and a tightened one: an mtp module must match the
     model's family AND its parameter count, so a 12B module never drafts a
     31B model. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde, modelleLaden, zustand } from '../lib/zustand.svelte.js'
  import { speicherSchaetzung } from '../lib/speicherschaetzung.js'
  import { empfehlungFuer } from '../lib/modellempfehlungen.js'
  import Zahlenfeld from './Zahlenfeld.svelte'
  import Hauszeichen from './Hauszeichen.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'

  let auskunft = $state(null)
  let protokoll = $state([])
  let protokollOffen = $state(false)
  let arbeitet = $state(false)
  let protokollKasten = $state(null)
  let programmStand = $state(null)
  const programmLaedt = $derived(
    Boolean(programmStand) && !programmStand.fertig && !programmStand.fehler,
  )

  let tempo = $state(0)
  let messung = null
  function tempoMessen(neu) {
    const jetzt = Date.now()
    if (neu && messung && jetzt > messung.zeit) {
      const frisch = ((neu.geladen - messung.geladen) / (jetzt - messung.zeit)) * 1000
      tempo = tempo ? tempo * 0.4 + frisch * 0.6 : frisch
    } else {
      tempo = 0
    }
    messung = neu ? { geladen: neu.geladen, zeit: jetzt } : null
  }
  const mbs = $derived(tempo > 50_000 ? (tempo / 1e6).toFixed(1) + ' MB/s' : '')

  $effect(() => {
    void protokoll
    if (protokollKasten) protokollKasten.scrollTop = protokollKasten.scrollHeight
  })

  let kontext = $state(32768)
  let schichten = $state(99)
  let port = $state(8080)
  let modell = $state('')
  let drafter = $state('')

  /* The parameter count in a model name — "12B", "31b", "1.7B". Two models
     of one family but different sizes must not draft one another with an
     mtp module, which is trained for one exact model. */
  function parameterzahl(name) {
    const treffer = name.toLowerCase().match(/(\d+(?:\.\d+)?)\s*b\b/)
    return treffer ? treffer[1] : null
  }
  function gemeinsam(a, b) {
    const x = a.toLowerCase()
    const y = b.toLowerCase()
    let i = 0
    while (i < x.length && i < y.length && x[i] === y[i]) i++
    return i
  }

  /* Draft candidates: same family, clearly smaller. A prediction module
     (mtp) comes first — trained alongside its model, a few hundred
     megabytes, the best draft there is — and it must match the parameter
     count exactly. A tiny sibling model is the fallback, capped at sixty
     percent of the size. Most models rightly end up with none. */
  const drafterKandidaten = $derived.by(() => {
    const haupt = (auskunft?.modelle ?? []).find((m) => m.name === modell)
    if (!haupt) return []
    const hp = parameterzahl(haupt.name)
    const module = (auskunft?.mtp ?? []).filter((m) => {
      const basis = m.name.replace(/^mtp[-._]/i, '')
      if (gemeinsam(basis, haupt.name) < 5) return false
      const mp = parameterzahl(basis)
      // Both sized and different means a wrong pairing; only equal (or an
      // unlabelled one) may draft.
      return hp && mp ? mp === hp : true
    })
    const geschwister = (auskunft?.modelle ?? []).filter(
      (m) =>
        m.name !== modell &&
        gemeinsam(m.name, haupt.name) >= 5 &&
        m.groesse_gb <= haupt.groesse_gb * 0.6,
    )
    return [...module, ...geschwister]
  })
  $effect(() => {
    if (drafter && !drafterKandidaten.some((m) => m.name === drafter)) drafter = ''
  })

  const schaetzung = $derived.by(() => {
    const haupt = (auskunft?.modelle ?? []).find((m) => m.name === modell)
    if (!haupt || !kontext) return null
    const beifahrer =
      (auskunft?.modelle ?? []).find((m) => m.name === drafter) ??
      (auskunft?.mtp ?? []).find((m) => m.name === drafter)
    return speicherSchaetzung(haupt.groesse_gb, kontext, beifahrer?.groesse_gb ?? 0)
  })
  $effect(() => {
    zustand.serverPlan = laeuft ? null : schaetzung
    return () => (zustand.serverPlan = null)
  })

  const laeuft = $derived(Boolean(auskunft?.laeuft))
  const hatProgramm = $derived(Boolean(auskunft?.programm))
  const hatModelle = $derived((auskunft?.modelle?.length ?? 0) > 0)
  const maschineGb = $derived(auskunft?.speicher_gb ?? null)
  /* The first-run guidance stands in place of the form until a model lies
     in the folder. */
  const erststart = $derived(!laeuft && !hatModelle)
  const vorschlag = $derived(maschineGb ? empfehlungFuer(maschineGb) : null)

  const kurzK = (n) => (n ? Math.round(n / 1024) + 'k' : '')

  async function laden() {
    try {
      auskunft = await api.runnerAuskunft()
      if (!modell) {
        modell = auskunft.modell || auskunft.modelle[0]?.name || ''
        const z = auskunft.zuordnung?.[modell]
        if (z?.mtp) drafter = z.mtp
      }
      if (auskunft.laeuft) {
        kontext = auskunft.kontext
        schichten = auskunft.schichten
        port = auskunft.port
        drafter = auskunft.drafter || ''
      }
      if (protokollOffen || auskunft.laeuft) protokoll = await api.runnerProtokoll()
      if (!auskunft.programm) {
        programmStand = await api.serverProgrammStand()
        tempoMessen(
          programmStand && !programmStand.fertig && !programmStand.fehler ? programmStand : null,
        )
      }
      if (auskunft.laeuft && !zustand.modelle.some((m) => m.anbieter === 'runner' && m.erreichbar)) {
        await modelleLaden(true)
      }
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  $effect(() => {
    laden()
    const takt = setInterval(laden, 2000)
    return () => clearInterval(takt)
  })

  /* Picking a model pre-picks its recorded speed module — the association
     the catalogue wrote when it fetched them, so nothing is guessed. */
  function modellGewaehlt() {
    drafter = auskunft?.zuordnung?.[modell]?.mtp ?? ''
  }

  async function starten() {
    arbeitet = true
    try {
      auskunft = await api.runnerStarten({ modell, kontext, schichten, port, drafter: drafter || null })
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
      await modelleLaden()
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    } finally {
      arbeitet = false
    }
  }

  function programmHolen() {
    api.serverProgrammHolen().then((s) => (programmStand = s)).catch((f) => melde(f.message, 'fehler'))
  }
  function ordnerOeffnen() {
    api.modellordnerOeffnen().catch((f) => melde(f.message, 'fehler'))
  }
</script>

<div class="tafel">
  {#if erststart}
    <!-- The three steps to a first model: fetch the engine, pick a model,
         start it. The status card above says honestly where one stands. -->
    <div class="statuskarte">
      <Leuchtpunkt farbe="still" groesse={9} />
      <div class="skmitte">
        <div class="sktitel">{t('modell.reise_titel')}</div>
        <div class="skdetails">
          <span>{t(hatProgramm ? 'modell.reise_stand_programm_da' : 'modell.reise_stand_programm_fehlt')}</span>
        </div>
      </div>
    </div>

    <div class="reisekarten">
      <div class="reisekarte" class:fertig={hatProgramm} class:dran={!hatProgramm}>
        <div class="nr">{#if hatProgramm}✓{:else}1{/if}</div>
        <h3>{t('modell.server_holen')}</h3>
        <div class="rsatz">{t('modell.reise_server_satz')}</div>
        {#if hatProgramm}
          <span class="pille gruen">{t('modell.reise_da')}</span>
        {:else if programmLaedt}
          <div class="balkenzeile">
            <span class="balken"><i style="width:{Math.round(programmStand.anteil * 100)}%"></i></span>
            <span class="balkenzahl">{Math.round(programmStand.anteil * 100)} %{mbs ? ' · ' + mbs : ''}</span>
          </div>
        {:else}
          <button class="knopf wichtig" onclick={programmHolen}>{t('modell.server_holen')}</button>
        {/if}
      </div>

      <div class="reisekarte" class:dran={hatProgramm}>
        <div class="nr">2</div>
        <h3>{t('modell.reise_modell_titel')}</h3>
        <div class="rsatz">
          {vorschlag
            ? t('modell.reise_modell_satz').replace('{gb}', maschineGb)
            : t('modell.reise_modell_satz_neutral')}
        </div>
        <button class="knopf wichtig" disabled={!hatProgramm} onclick={() => (zustand.katalogOffen = true)}>
          {t('modell.katalog_oeffnen')}
        </button>
      </div>

      <div class="reisekarte">
        <div class="nr">3</div>
        <h3>{t('modell.reise_start')}</h3>
        <div class="rsatz">{t('modell.reise_start_satz')}</div>
        <span class="knopf still gesperrt">{t('modell.server_starten_kurz')}</span>
      </div>
    </div>
  {:else}
    <!-- The one truth: is it up, which model, which speed module, how much
         memory. Colour here means state — green runs, grey is off. -->
    <div class="statuskarte">
      <Leuchtpunkt farbe={laeuft ? 'gruen' : 'still'} an={laeuft} groesse={9} />
      <div class="skmitte">
        <div class="sktitel">{laeuft ? auskunft.modell : modell || t('modell.server_aus')}</div>
        <div class="skdetails">
          {#if laeuft}
            <span>{t('modell.laeuft_port', { port: auskunft.port })}</span>
            <span>{t('modell.kontext_kurz', { n: kurzK(auskunft.kontext) })}</span>
            {#if auskunft.drafter}
              <span class="mtpzeile">
                <span class="blitz"><Hauszeichen zeichen="blitz" groesse={13} /></span>
                {t('modell.mtp_label')}: {auskunft.drafter}
              </span>
            {/if}
            {#if auskunft.belegt_gb}
              <span>{t('modell.im_speicher', { gb: auskunft.belegt_gb })}</span>
            {/if}
          {:else}
            <span>{t('modell.server_aus')}</span>
          {/if}
        </div>
      </div>
      <div class="skrechts">
        {#if laeuft}
          <button class="knopf" onclick={anhalten} disabled={arbeitet}>{t('modell.server_anhalten_kurz')}</button>
        {:else}
          <button class="knopf wichtig" onclick={starten} disabled={arbeitet || !modell}>{t('modell.server_starten_kurz')}</button>
        {/if}
      </div>
    </div>

    <div class="gruppe">
      <div class="gruppenname">{t('modell.gruppe_modell_tempo')}</div>
      <div class="regler">
        <label for="rs-modell">{t('modell.feld_modell')}<span>{t('modell.feld_modell_hilfe')}</span></label>
        <select id="rs-modell" class="wert" bind:value={modell} onchange={modellGewaehlt} disabled={laeuft}>
          {#each auskunft?.modelle ?? [] as m}
            <option value={m.name}>{m.name} · {m.groesse_gb} GB</option>
          {/each}
        </select>

        <label for="rs-drafter">{t('modell.feld_speedmodul')}<span>{t('modell.feld_speedmodul_hilfe')}</span></label>
        <select id="rs-drafter" class="wert" bind:value={drafter} disabled={laeuft}>
          <option value="">{t('modell.drafter_keiner')}</option>
          {#each drafterKandidaten as m}
            <option value={m.name}>{m.name} · {m.groesse_gb} GB</option>
          {/each}
        </select>
      </div>
    </div>

    <div class="gruppe">
      <div class="gruppenname">{t('modell.gruppe_speicher')}</div>
      <div class="regler">
        <label for="rs-kontext">{t('modell.feld_kontext')}<span>{t('modell.feld_kontext_hilfe')}</span></label>
        <Zahlenfeld id="rs-kontext" bind:wert={kontext} gesperrt={laeuft} min={512} max={1048576} schritt={1024} />

        <label for="rs-schichten">{t('modell.feld_schichten')}<span>{t('modell.feld_schichten_hilfe')}</span></label>
        <Zahlenfeld id="rs-schichten" bind:wert={schichten} gesperrt={laeuft} min={0} max={999} />

        {#if schaetzung && maschineGb}
          <span class="schaetz">{t('modell.schaetz_zeile', { plan: schaetzung.gesamt.toFixed(1), gesamt: maschineGb })}</span>
        {/if}
      </div>
    </div>

    <div class="gruppe">
      <div class="gruppenname">{t('modell.gruppe_netz')}</div>
      <div class="regler">
        <label for="rs-port">{t('modell.feld_port')}<span>{t('modell.feld_port_hilfe')}</span></label>
        <Zahlenfeld id="rs-port" bind:wert={port} gesperrt={laeuft} min={1024} max={65535} />
      </div>
    </div>

    <div class="serverfuss">
      <button class="ordnerknopf" onclick={ordnerOeffnen}>
        <Hauszeichen zeichen="ordner" groesse={15} />
        {t('modell.ordner_oeffnen')}
      </button>
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
  .tafel {
    display: flex;
    flex-direction: column;
  }

  /* The one truth on top. */
  .statuskarte {
    display: flex;
    align-items: center;
    gap: 14px;
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg-erhoben);
    padding: 14px 16px;
    margin-bottom: 16px;
  }
  .skmitte {
    min-width: 0;
    flex: 1;
  }
  .sktitel {
    font: 600 14px var(--schrift-fest);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .skdetails {
    font-size: 12px;
    color: var(--text-leise);
    margin-top: 3px;
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    align-items: center;
  }
  .mtpzeile {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  /* Blue is the house colour for a running speed module. */
  .blitz {
    display: inline-flex;
    color: var(--blau);
  }
  .skrechts {
    margin-left: auto;
    flex: none;
  }

  .gruppe {
    margin-bottom: 16px;
  }
  .gruppenname {
    font-size: 10.5px;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 600;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .gruppenname::after {
    content: '';
    flex: 1;
    border-top: 1px solid var(--linie);
  }
  .regler {
    display: grid;
    grid-template-columns: minmax(150px, 190px) 1fr;
    gap: 10px 14px;
    align-items: center;
  }
  label {
    font-size: 13px;
  }
  label span {
    display: block;
    font-size: 11.5px;
    color: var(--text-still);
  }
  .wert {
    width: 100%;
    height: 32px;
    border: 1px solid var(--linie-stark);
    border-radius: 8px;
    background: var(--bg);
    color: var(--text);
    font: 400 12.5px/1.2 var(--schrift-fest);
    padding: 6px 10px;
  }
  .wert:disabled {
    color: var(--text-still);
  }
  select.wert {
    text-align: left;
  }
  .schaetz {
    grid-column: 2;
    font-size: 11.5px;
    color: var(--text-leise);
  }

  .serverfuss {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
  }
  .ordnerknopf {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: none;
    background: none;
    color: var(--text-still);
    font: 12px var(--schrift);
    padding: 6px 2px;
    cursor: pointer;
  }
  .ordnerknopf:hover {
    color: var(--text);
  }
  .klapper {
    margin-left: auto;
    border: none;
    background: none;
    color: var(--text-still);
    font: 12px var(--schrift);
    cursor: pointer;
    padding: 6px 4px;
  }

  .protokoll {
    margin: 9px 0 0;
    padding: 10px 12px;
    background: var(--code-bg);
    border: 1px solid var(--linie);
    border-radius: 8px;
    font: 400 11px/1.55 var(--schrift-fest);
    color: var(--text-leise);
    max-height: 150px;
    overflow: auto;
    white-space: pre-wrap;
  }

  /* The first-run journey: three cards side by side. */
  .reisekarten {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-top: 2px;
  }
  @media (max-width: 720px) {
    .reisekarten {
      grid-template-columns: 1fr;
    }
  }
  .reisekarte {
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 14px;
    background: var(--bg-erhoben);
    display: flex;
    flex-direction: column;
    align-items: flex-start;
  }
  .reisekarte .nr {
    width: 26px;
    height: 26px;
    border-radius: 99px;
    border: 1.5px solid var(--linie-stark);
    display: flex;
    align-items: center;
    justify-content: center;
    font: 600 12px var(--schrift-fest);
    color: var(--text-still);
    margin-bottom: 10px;
  }
  .reisekarte.fertig .nr {
    border-color: var(--gruen);
    color: var(--gruen);
  }
  .reisekarte.dran .nr {
    border-color: var(--blau);
    color: var(--blau);
  }
  .reisekarte h3 {
    font-size: 13.5px;
    font-weight: 600;
    margin: 0 0 4px;
  }
  .rsatz {
    font-size: 12px;
    color: var(--text-leise);
    line-height: 1.5;
    min-height: 54px;
    margin-bottom: 10px;
  }
  .balkenzeile {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
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
  .balkenzahl {
    font: 400 11px var(--schrift-fest);
    color: var(--text-still);
    white-space: nowrap;
  }

  .pille {
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 3px 10px;
    font: 600 11px var(--schrift);
    color: var(--text-still);
  }
  .pille.gruen {
    color: var(--gruen);
    border-color: color-mix(in srgb, var(--gruen) 45%, transparent);
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: 600 12.5px var(--schrift);
    padding: 6px 13px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s, opacity 0.12s, transform 0.08s;
  }
  .knopf:hover:not(:disabled) {
    background: var(--linie);
  }
  .knopf:active:not(:disabled) {
    transform: scale(0.975);
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
  .knopf.gesperrt {
    opacity: 0.5;
    cursor: default;
  }
</style>
