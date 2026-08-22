<script>
  import { rollfade } from '../lib/rollfade.js'
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
  import { ausFenster } from '../lib/fensterweg.svelte.js'
  import { katalogOeffnen, melde, modelleLaden, zustand } from '../lib/zustand.svelte.js'
  import { speicherSchaetzung } from '../lib/speicherschaetzung.js'
  import { empfehlungFuer } from '../lib/modellempfehlungen.js'
  import { FEINEINSTELLUNGEN } from '../lib/feineinstellungen.js'
  import Auswahlfeld from './Auswahlfeld.svelte'
  import { eew, modellWaehlen as eewModellWaehlen } from '../lib/eew.svelte.js'
  import Schalter from './Schalter.svelte'
  import Schieberegler from './Schieberegler.svelte'
  import EEWzeichen from './EEWzeichen.svelte'
  import Servertafel from './Servertafel.svelte'
  import Zahlenfeld from './Zahlenfeld.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import Hauszeichen from './Hauszeichen.svelte'
  import { setzeStartAktion, loescheStartAktion } from '../lib/startknopf.svelte.js'
  import {
    protokollOffen,
    oeffneProtokoll,
    setzeProtokollZeilen,
  } from '../lib/protokollfenster.svelte.js'

  let auskunft = $state(null)
  let protokoll = $state([])
  let protokollAuf = $state(false)
  let arbeitet = $state(false)
  let protokollKasten = $state(null)

  // Keep the big log window fed while it is open.
  $effect(() => {
    if (protokollOffen()) setzeProtokollZeilen(protokoll)
  })
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

  /* Held back until the remembered numbers are in: without it the watcher
     below would write the defaults over them on the very first pass. */
  let zahlenStehen = $state(false)
  let kontext = $state(32768)
  let schichten = $state(99)
  let port = $state(8080)
  let modell = $state('')
  let drafter = $state('')
  let vision = $state('')

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

  // Publish this panel's start/stop action to the rail's foot button.
  $effect(() => {
    setzeStartAktion({
      text: laeuft ? t('modell.server_anhalten') : t('modell.server_starten'),
      punkt: laeuft ? 'gruen' : 'still',
      gesperrt: arbeitet || (!laeuft && !modell),
      onTat: laeuft ? anhalten : starten,
    })
    return () => loescheStartAktion()
  })

  const hatProgramm = $derived(Boolean(auskunft?.programm))
  const hatModelle = $derived((auskunft?.modelle?.length ?? 0) > 0)
  const maschineGb = $derived(auskunft?.speicher_gb ?? null)
  /* The first-run guidance stands in place of the form until a model lies
     in the folder. */
  const erststart = $derived(!laeuft && !hatModelle)
  const vorschlag = $derived(maschineGb ? empfehlungFuer(maschineGb) : null)

  const kurzK = (n) => (n ? Math.round(n / 1024) + 'k' : '')

  /* The steps a context really comes in. Below 4096 there is no conversation
     worth having, and above that the engine only understands these numbers —
     a field that silently accepts 33000 and then behaves like 32768 teaches
     nobody anything.

     What a given model can actually hold is not asked here, because nothing
     in the program knows it yet: it stands in the model file's own header,
     and reading that is a job of its own. Until then the list is the same
     everywhere, and a model that cannot hold the chosen size says so when it
     starts — which is where it said so before as well. */
  const kontextstufen = [4096, 8192, 16384, 32768, 65536, 131072]
  /* 99 is llama.cpp's own way of saying "all of them", and the right-hand
     stop of the slider says the same thing in words. */
  const MAX_SCHICHTEN = 99
  /* The machine's own core count, read from the server. More threads than
     cores makes a run SLOWER — they fight for the same cores — so the track
     stops where the machine does instead of offering a value that only
     hurts. The fallback is a small, safe number for the moment before the
     first answer arrives. */
  const MAX_FAEDEN = $derived(auskunft?.kerne ?? 8)

  /* The advanced section. Shut on start: somebody who does not know what a
     KV cache is should never have to find out. */
  let erweitertOffen = $state(false)
  /* flash_attention is deliberately NOT in here any more: there is no
     control for it, the engine's "auto" decides — and a stored "off" from
     an older version must not keep riding along with every start. */
  let fein = $state({
    kv_cache: 'f16',
    moe_auf_cpu: false,
    festnageln: false,
  })
  /* Kept as plain numbers here because the number field speaks numbers; 0
     means "let the engine decide" and travels as nothing. */
  let faeden = $state(0)
  let moeSchichten = $state(0)

  const feindaten = $derived({
    ...fein,
    faeden: faeden || null,
    moe_schichten: moeSchichten || null,
  })

  /* The levers used to live only here, in this form. Reloading the window
     put every one of them back to its default while the server kept running
     with what it was given — so the drawer said f16 about a server holding
     q4_0, and the next start went out without the settings that were the
     only reason the model fitted at all.

     Loaded once: the running server first, the stored choice otherwise. */
  let feinGeladen = $state(false)

  function feinUebernehmen(daten) {
    fein = {
      /* The step an older version offered maps to the surviving saving
         step — whoever stored q4_0 was saving memory on purpose. Same rule
         as the backend's KV_ALT. */
      kv_cache: daten.kv_cache === 'q4_0' ? 'q8_0' : (daten.kv_cache ?? fein.kv_cache),
      moe_auf_cpu: Boolean(daten.moe_auf_cpu),
      festnageln: Boolean(daten.festnageln),
    }
    faeden = daten.faeden || 0
    moeSchichten = daten.moe_schichten || 0
    feinGeladen = true
  }

  async function feinLaden() {
    try {
      const antwort = await api.einstellungAufgeloest(FEINEINSTELLUNGEN)
      if (antwort?.wert && typeof antwort.wert === 'object') feinUebernehmen(antwort.wert)
    } catch {
      /* Nothing stored yet is the normal first case, not an error. */
    } finally {
      feinGeladen = true
    }
  }

  /* Written when the levers come to rest, not on every click — and never
     before they were read, or the first poll would store the defaults over
     whatever was there. */
  $effect(() => {
    const _ = JSON.stringify(feindaten)
    if (!feinGeladen) return
    const uhr = setTimeout(() => {
      api.einstellungSetzen('global', FEINEINSTELLUNGEN, feindaten).catch(() => {})
    }, 600)
    return () => clearTimeout(uhr)
  })

  /* What the panel is doing, as the head card's one line: the facts that
     used to be spread over a status card, joined by the same separator the
     rest of the house uses. The speed module is named here too — it is the
     one running fact the form below does not repeat while locked. */
  const laufzeile = $derived.by(() => {
    if (!laeuft) return ''
    const teile = [
      t('modell.laeuft_port', { port: auskunft.port }),
      t('modell.kontext_kurz', { n: kurzK(auskunft.kontext) }),
    ]
    if (auskunft.drafter) teile.push(`${t('modell.mtp_label')}: ${auskunft.drafter}`)
    if (auskunft.belegt_gb) teile.push(t('modell.im_speicher', { gb: auskunft.belegt_gb }))
    return teile.join(' · ')
  })

  /* The same folder the chat model comes from — a small model is a model.
     The list is not narrowed by size: what counts as small enough is a
     judgement the measurements made, not one a filter can make. */
  const eewauswahl = $derived([
    // "Without" first, so Extended Workflow can run with no small model of
    // its own — the same escape the speed module offers a line above.
    { wert: '', text: t('modell.eew_keiner') },
    ...(auskunft?.modelle ?? []).map((m) => ({ wert: m.name, text: `${m.name} · ${m.groesse_gb} GB` })),
  ])

  const drafterauswahl = $derived([
    { wert: '', text: t('modell.drafter_keiner') },
    ...drafterKandidaten.map((m) => ({ wert: m.name, text: `${m.name} · ${m.groesse_gb} GB` })),
  ])

  /* Every projector in the vision folder, "without" first. Not narrowed by
     name: the whole point of this row is the companion the name heuristic
     cannot pair — so the choice is the user's, across the full list. */
  const visionauswahl = $derived([
    { wert: '', text: t('modell.vision_keiner') },
    ...(auskunft?.mmproj ?? []).map((name) => ({ wert: name, text: name })),
  ])

  /* An empty choice at the top, like the three module rows have: a fresh
     install ships with nothing loaded, and a list that cannot be set back to
     nothing would make "no model" a state only the first start ever sees. */
  const modellauswahl = $derived([
    { wert: '', text: t('modell.modell_keiner') },
    ...(auskunft?.modelle ?? []).map((m) => ({ wert: m.name, text: `${m.name} · ${m.groesse_gb} GB` })),
  ])

  async function laden() {
    try {
      auskunft = await api.runnerAuskunft()
      if (!modell) {
        /* The mask remembers the hand: a running server wins, then the model
           last STARTED here (if its file is still in the folder), then the
           first in the list. The drafter follows the remembered per-model
           choice — including a remembered "none" — before the catalogue's
           recorded pairing gets to guess. */
        const gemerkt = localStorage.getItem('runner:modell')
        const gemerktGilt =
          gemerkt !== null && (gemerkt === '' || auskunft.modelle.some((m) => m.name === gemerkt))
        modell = auskunft.modell || (gemerktGilt ? gemerkt : auskunft.modelle[0]?.name || '')
        const drafterGemerkt = localStorage.getItem('runner:drafter:' + modell)
        if (drafterGemerkt !== null) {
          drafter = drafterGemerkt
        } else {
          const z = auskunft.zuordnung?.[modell]
          if (z?.mtp) drafter = z.mtp
        }
        kontext = gemerkteZahl('kontext', kontext)
        schichten = gemerkteZahl('schichten', schichten)
        port = gemerkteZahl('port', port)
        zahlenStehen = true
        const visionGemerkt = localStorage.getItem('runner:vision:' + modell)
        if (visionGemerkt !== null) {
          vision = visionGemerkt
        } else {
          const z = auskunft.zuordnung?.[modell]
          if (z?.mmproj) vision = z.mmproj
        }
      }
      if (auskunft.laeuft) {
        kontext = auskunft.kontext
        schichten = auskunft.schichten
        port = auskunft.port
        drafter = auskunft.drafter || ''
        vision = auskunft.vision || vision
        /* What the running server was actually started with beats what was
           once chosen — and it is taken only once, because this runs every
           two seconds and would otherwise fight the hand in the drawer. */
        if (!feinGeladen && auskunft.fein) feinUebernehmen(auskunft.fein)
      }
      if (!feinGeladen && !auskunft.laeuft) await feinLaden()
      if (protokollAuf || protokollOffen() || auskunft.laeuft) protokoll = await api.runnerProtokoll()
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

  $effect(() => {
    if (!zahlenStehen) return
    merken('kontext', kontext)
    merken('schichten', schichten)
    merken('port', port)
  })

  /* Picking a model pre-picks its speed module: first the choice the hand
     made last time for THIS model (a remembered "none" counts), then the
     association the catalogue wrote when it fetched them. */
  /* What the hand set stays set. Every control in this panel writes its
     choice down the moment it is made, and the panel reads them back when it
     opens — a value that only survives a start would be a value the reload
     two seconds later throws away.

     Written as strings and read back with a guard: an empty string is a
     deliberate "none", which is why a plain falsy test would lose it. */
  function merken(name, wert) {
    localStorage.setItem('runner:' + name, String(wert))
  }
  function gemerkteZahl(name, ersatz) {
    const wert = localStorage.getItem('runner:' + name)
    const zahl = Number(wert)
    return wert !== null && wert !== '' && Number.isFinite(zahl) ? zahl : ersatz
  }

  function drafterGewaehlt() {
    merken('drafter:' + modell, drafter)
  }
  function visionGewaehlt() {
    merken('vision:' + modell, vision)
  }

  function modellGewaehlt() {
    /* Remembered the moment it is picked, not only when a server starts:
       an empty choice never starts anything, and without this the reload a
       second later would find no model and pre-pick one again — the choice
       would not survive its own row. The empty string is a remembered
       "none", exactly as it is for the modules below. */
    localStorage.setItem('runner:modell', modell)
    const gemerkt = localStorage.getItem('runner:drafter:' + modell)
    drafter = gemerkt !== null ? gemerkt : (auskunft?.zuordnung?.[modell]?.mtp ?? '')
    const vGemerkt = localStorage.getItem('runner:vision:' + modell)
    vision = vGemerkt !== null ? vGemerkt : (auskunft?.zuordnung?.[modell]?.mmproj ?? '')
  }

  async function starten() {
    arbeitet = true
    try {
      auskunft = await api.runnerStarten({
        modell, kontext, schichten, port, drafter: drafter || null,
        vision: vision || null, fein: feindaten,
      })
      /* Remember what actually started — the model, and the drafter choice
         for exactly this model (an empty string is a remembered "none"). */
      localStorage.setItem('runner:modell', modell)
      localStorage.setItem('runner:drafter:' + modell, drafter || '')
      localStorage.setItem('runner:vision:' + modell, vision || '')
      protokollAuf = true
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
</script>

{#if erststart}
  <div class="erstetafel">
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
        <button class="knopf wichtig" disabled={!hatProgramm} onclick={() => ausFenster(
          () => { zustand.lokalOffen = false; zustand.katalogOffen = true },
          () => { zustand.katalogOffen = false; zustand.lokalOffen = true },
        )}>
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
  </div>
{:else}
    <!-- The house's server shape, shared with the embedding and picture
         panels: head card, one sentence, the model, then what only this
         server needs, then the foot. What used to stand in a status card of
         its own — the running port, the context, the memory in use — is the
         head card's second line now, and the start button moved down to the
         foot where the other two panels keep theirs. -->
    <Servertafel
      titel={t('modell.server_stand')}
      unter={laufzeile}
      standfarbe={laeuft ? 'gruen' : 'still'}
      standtext={laeuft ? t('status.aktiv') : t('status.inaktiv')}
      modelle={modellauswahl}
      bind:gewaehlt={modell}
      modellBeschriftung={t('modell.feld_modell')}
      modellGesperrt={laeuft}
      modellGeaendert={modellGewaehlt}
      leerText={t('modell.kein_modell_da')}
      katalogTat={() => katalogOeffnen('chat')}
      speicherort="modelle"
    >
      {#snippet mitte()}
        <div class="gruppe">
          <div class="gruppenname">
            <!-- A block that docks into a rail: the three rows below are
                 exactly that — small models that plug into the big one. -->
            <svg class="gruppenzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
                 stroke-linejoin="round" aria-hidden="true">
              <rect x="3.75" y="13.5" width="16.5" height="6.75" rx="1.5" />
              <rect x="8.25" y="3.75" width="7.5" height="5.6" rx="1.1" />
              <path d="M10.1 9.4 V13.5 M13.9 9.4 V13.5" />
            </svg>{t('modell.gruppe_tempo')}</div>
          <!-- The three modules in one frame: they are one choice made three
               times over — which small model helps the big one — and a frame
               says that faster than a heading can. Same box the head card
               wears, so the panel keeps one vocabulary of shapes. -->
          <div class="regler kasten modulkasten">
            <label for="rs-drafter"><svg class="modulzeichen blitzfarbe" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 3 L5 13.5 H10.5 L9.5 21 L17.5 10.5 H12 Z" /></svg>{t('modell.feld_speedmodul')}</label>
            <Auswahlfeld
              id="rs-drafter"
              bind:wert={drafter}
              eintraege={drafterauswahl}
              gesperrt={laeuft}
              beschriftung={t('modell.feld_speedmodul')}
              gewaehlt={drafterGewaehlt}
            />

            <label for="rs-vision"><svg class="modulzeichen augenfarbe" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 12 C6 6.5, 18 6.5, 21.5 12 C18 17.5, 6 17.5, 2.5 12 Z" /><circle cx="12" cy="12" r="3" /></svg>{t('modell.feld_vision')}</label>
            <Auswahlfeld
              id="rs-vision"
              bind:wert={vision}
              eintraege={visionauswahl}
              gesperrt={laeuft}
              beschriftung={t('modell.feld_vision')}
              gewaehlt={visionGewaehlt}
            />

            <!-- The third row, and deliberately no tile of its own: which
                 small model Extended Workflow uses is a model choice like
                 the two above it, and a fourth tile under SET UP would
                 promise a page that has nothing else on it. -->
            <label for="rs-eew"><span class="modulzeichen"><EEWzeichen groesse={16.2} /></span>{t('modell.feld_eew')}</label>
            <Auswahlfeld
              id="rs-eew"
              wert={eew.modell}
              eintraege={eewauswahl}
              beschriftung={t('modell.feld_eew')}
              gewaehlt={eewModellWaehlen}
            />
          </div>
        </div>

        <div class="gruppe">
          <div class="gruppenname">
            <!-- A memory module: the board, its chips, and the contacts it
                 stands on. -->
            <svg class="gruppenzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
                 stroke-linejoin="round" aria-hidden="true">
              <rect x="2.8" y="6.6" width="18.4" height="10.2" rx="1.6" />
              <path d="M8 10 V13.4 M12 10 V13.4 M16 10 V13.4" stroke-width="1.5" />
              <path d="M7.5 16.8 V19.6 M16.5 16.8 V19.6" stroke-width="1.5" />
            </svg>{t('modell.gruppe_speicher')}</div>
          <!-- The three numbers that decide what a run costs, in one frame —
               the same box the modules above wear. -->
          <div class="regler kasten">
            <label for="rs-kontext">{t('modell.feld_kontext')}</label>
            <!-- Dragged for the steps everybody needs, typed for the one
                 case that is not a step at all: a context above 128k, which
                 the slider's fixed marks were never meant to reach. The
                 slider keeps its old shape — same steps, same snap — the
                 field beside it is the only new thing, and it is what a
                 typed number always was: the truth. The slider settles on
                 whichever mark sits nearest once the field goes higher. -->
            <div class="kontextzeile">
              <Schieberegler
                id="rs-kontext"
                bind:wert={kontext}
                stufen={kontextstufen}
                gesperrt={laeuft}
                beschriftung={t('modell.feld_kontext')}
                anzeige={kurzK}
                mit_zahl={false}
              />
              <Zahlenfeld bind:wert={kontext} gesperrt={laeuft} min={512} max={1048576} schritt={1024} />
            </div>

            <label for="rs-schichten">{t('modell.feld_schichten')}</label>
            <div class="kontextzeile">
              <Schieberegler
                id="rs-schichten"
                bind:wert={schichten}
                min={0}
                max={MAX_SCHICHTEN}
                gesperrt={laeuft}
                beschriftung={t('modell.feld_schichten')}
                endtext={t('modell.schichten_alle')}
                mit_zahl={false}
              />
              <Zahlenfeld bind:wert={schichten} gesperrt={laeuft} min={0} max={MAX_SCHICHTEN} />
            </div>

            <label for="rs-faeden">{t('modell.feld_faeden')}</label>
            <!-- Dragged like the two above it: three numbers that decide what
                 a run costs, set the same way, on tracks of one length. -->
            <div class="kontextzeile">
              <Schieberegler
                id="rs-faeden"
                bind:wert={faeden}
                min={0}
                max={MAX_FAEDEN}
                gesperrt={laeuft}
                beschriftung={t('modell.feld_faeden')}
                endtext={t('modell.faeden_auto')}
                mit_zahl={false}
              />
              <Zahlenfeld bind:wert={faeden} gesperrt={laeuft} min={0} max={MAX_FAEDEN} />
            </div>

            {#if schaetzung && maschineGb}
              <span class="schaetz">{t('modell.schaetz_zeile', { plan: schaetzung.gesamt.toFixed(1), gesamt: maschineGb })}</span>
            {/if}
          </div>
        </div>

        <!-- Shut by default, and that is the whole point: somebody who does
             not know what a KV cache is never has to find out. -->
        <div class="gruppe">
          <button class="klappkopf" onclick={() => (erweitertOffen = !erweitertOffen)}
                  aria-expanded={erweitertOffen}>
            <span class="winkel" class:auf={erweitertOffen}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 6l6 6-6 6" />
              </svg>
            </span>
            {t('modell.gruppe_erweitert')}
          </button>
          {#if erweitertOffen}
            <!-- Three switches on one line: each is a single yes or no, and
                 a column of three would leave the width beside them empty
                 for no reason. Measured to fit — the longest of them still
                 has room. -->
            <div class="schalterreihe">
              <!-- Each switch keeps its name beside it, the pairs spread
                   across the full width with a hairline between them: three
                   yes/no settings on one line, first name flush left, last
                   switch flush right. -->
              <span class="paar">
                <!-- What the switch turns the cache INTO. Without it the row
                     asks a yes/no question about a word, and the answer only
                     means something to somebody who already knows the
                     default is 16-bit. -->
                <label>{t('modell.feld_kv')}<i class="labeltrenner" aria-hidden="true"></i><i class="labelwert">{t('modell.feld_kv_wert')}</i></label>
                <Schalter an={fein.kv_cache === 'q8_0'} gesperrt={laeuft}
                          beschriftung={t('modell.feld_kv')}
                          onschalten={() => (fein.kv_cache = fein.kv_cache === 'q8_0' ? 'f16' : 'q8_0')} />
              </span>

              <span class="reihentrenner" aria-hidden="true"></span>

              <span class="paar">
                <label>{t('modell.feld_moe')}</label>
                <Schalter an={fein.moe_auf_cpu} gesperrt={laeuft}
                          beschriftung={t('modell.feld_moe')}
                          onschalten={() => (fein.moe_auf_cpu = !fein.moe_auf_cpu)} />
                {#if fein.moe_auf_cpu}
                  <Zahlenfeld id="rs-moe-n" bind:wert={moeSchichten} gesperrt={laeuft} min={0} max={999} />
                {/if}
              </span>

              <span class="reihentrenner" aria-hidden="true"></span>

              <span class="paar">
                <label>{t('modell.feld_mlock')}</label>
                <Schalter an={fein.festnageln} gesperrt={laeuft}
                          beschriftung={t('modell.feld_mlock')}
                          onschalten={() => (fein.festnageln = !fein.festnageln)} />
              </span>
            </div>
          {/if}
        </div>

        <div class="gruppe">
          <div class="gruppenname">{t('modell.gruppe_netz')}</div>
          <!-- The same frame the two groups above wear. -->
          <div class="regler kasten">
            <label for="rs-port">{t('modell.feld_port')}</label>
            <Zahlenfeld id="rs-port" bind:wert={port} gesperrt={laeuft} min={1024} max={65535} />
          </div>
        </div>
      {/snippet}

      {#snippet unten()}
        <!-- The log is not an action, so it does not sit in the foot row
             with the one that is. -->
        <div class="protokollzeile">
          <button class="klapper" onclick={() => (protokollAuf = !protokollAuf)}>
            {t('modell.protokoll')} {protokollAuf ? '▾' : '▸'}
          </button>
          <!-- Same log, popped out into a window: the collapsed strip is for a
               glance, the window for reading it. -->
          <button class="vergroessern" onclick={() => oeffneProtokoll(t('modell.protokoll_titel'))}
                  title={t('modell.protokoll_vergroessern')}
                  aria-label={t('modell.protokoll_vergroessern')}>
            <Hauszeichen zeichen="auskoppeln" groesse="klein" />
          </button>
        </div>
        {#if protokollAuf}
          <pre class="protokoll" use:rollfade bind:this={protokollKasten}>{protokoll.join('\n') || '—'}</pre>
        {/if}
      {/snippet}
    </Servertafel>
{/if}

<style>
  /* Only the first-run journey still brings its own frame; the panel proper
     stands in the shared one. */
  .erstetafel {
    display: flex;
    flex-direction: column;
  }

  /* Where one stands on the way to a first model. */
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

  /* One heading, worn by every section's head — TEMPO, SPEICHER & KONTEXT,
     ERWEITERT, NETZWERK. They used to be two different definitions (a
     different size, a different colour, ERWEITERT with no font of its own)
     and read as if the page had two hands; now there is exactly one place
     that says what a section head looks like. Both classes take it, so a
     row of divs and a row with a button behind it end up identical. */
  .gruppenzeichen {
    flex: none;
  }
  .gruppenname,
  .klappkopf {
    font: 600 11px var(--schrift);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-leise);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  /* The trailing line used to be gruppenname's alone; ERWEITERT sat there
     unfinished. Both now end the same way. */
  .gruppenname::after,
  .klappkopf::after {
    content: '';
    flex: 1;
    border-top: 1px solid var(--linie);
  }

  /* The section's head is a row you press, not a title with a button in it:
     the whole line is the target, which is what a shut drawer wants. */
  .klappkopf {
    width: 100%;
    border: none;
    background: none;
    padding: 0 0 8px;
    cursor: pointer;
  }
  .klappkopf:hover { color: var(--text); }
  .winkel {
    display: inline-flex;
    transition: transform 0.15s;
  }
  .winkel.auf { transform: rotate(90deg); }
  /* Same size and colour as every field's own explanation below it — see
     `label span`. Only the weight and case reset, because it sits inside an
     uppercase heading rather than under a normal-case field name. */
  .klapphilfe {
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    color: var(--text-still);
    font-size: 11.5px;
  }
  @media (prefers-reduced-motion: reduce) {
    .winkel { transition: none; }
  }

  .gruppe {
    margin-bottom: 16px;
  }
  /* A group of rows read as one thing, framed like the card at the top. */
  .kasten {
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 12px 14px;
  }
  .regler {
    display: grid;
    grid-template-columns: minmax(150px, 190px) 1fr;
    gap: 10px 14px;
    align-items: center;
  }
  label {
    font-size: 13px;
    white-space: nowrap;
  }
  /* Sign and word on one line — only where there are signs. */
  .modulkasten label {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  /* The capability colours the model cards use — bolt blue, eye violet —
     so one capability wears one colour wherever it turns up. */
  .modulzeichen {
    flex: none;
    display: inline-flex;
  }
  /* The header's own hairline, inside a label: it separates the name of a
     setting from the value the switch puts it at. */
  /* Not a span: the helper-line rule sets every span inside a label to
     block, and these two belong ON the line, not under it. */
  .labeltrenner {
    display: inline-block;
    font-style: normal;
    width: 1px;
    height: 9px;
    margin: 0 8px;
    vertical-align: -1px;
    background: var(--linie-stark);
  }
  .labelwert {
    font-style: normal;
    color: var(--text-still);
  }
  /* Name and switch stay a pair; the pairs sit side by side and wrap only
     if a narrow window forces it. */
  .schalterreihe {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .paar {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
  }
  .paar label {
    margin: 0;
  }
  /* The header's hairline again, between the pairs. */
  .reihentrenner {
    flex: none;
    width: 1px;
    height: 9px;
    background: var(--linie-stark);
  }
  .blitzfarbe { color: #5b8dbe; }
  .augenfarbe { color: #8d78bd; }
  label span {
    display: block;
    font-size: 11.5px;
    color: var(--text-still);
  }
  .kontextzeile {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .kontextzeile :global(.regler) {
    flex: 1;
    min-width: 0;
  }
  .kontextzeile :global(.zahl) {
    flex: none;
    width: 108px;
  }
  .schaetz {
    grid-column: 2;
    font-size: 11.5px;
    color: var(--text-leise);
  }

  .protokollzeile {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 2px;
  }
  .klapper {
    border: none;
    background: none;
    color: var(--text-still);
    font: 12px var(--schrift);
    cursor: pointer;
    padding: 6px 4px;
  }
  .vergroessern {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    color: var(--text-still);
    cursor: pointer;
    padding: 6px 4px;
  }
  .vergroessern:hover {
    color: var(--text);
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
