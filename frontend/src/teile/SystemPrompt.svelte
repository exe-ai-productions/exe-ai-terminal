<script>
  import { rollfade } from '../lib/rollfade.js'
  import Klappwahl from './Klappwahl.svelte'
  /* The settings window — one window, grouped like a real settings app.

     The left column is no longer a flat list but raised, named boxes:
     General, Assistant behaviour, Prompts & agents, Connections & keys,
     Files. Every entry carries a drawn sign and a subtitle that says its
     current state — "2 connected · 28 tools", "On · stays with local
     models" — so the standing of a thing shows without clicking into it.
     The right column is the open page: appearance tiles, the prompt and
     agent editors, the memory switches, the connections gallery, the file
     editors, and the Hugging Face token.

     It stays ONE window (opened by zustand.promptOffen, routed by
     zustand.promptStart), sized by the shared frame; a page is a value of
     `art` plus a nav entry and a right-side branch.

     A broken file still gets saved — it is the user's file — but the window
     says so at once, in the red line under the field. Secrets never reach
     the interface: the editor shows only ${…} placeholders, a status dot
     says set or missing. */
  import { fade } from 'svelte/transition'
  import Fenster from './Fenster.svelte'
  import WachsendesFeld from './WachsendesFeld.svelte'
  import Agentenmarke from './Agentenmarke.svelte'
  import Schriftzug from './Schriftzug.svelte'
  import Hauszeichen from './Hauszeichen.svelte'
  import Auswahlfeld from './Auswahlfeld.svelte'
  import { eew, schalten as eewSchalten, standLaden as eewStandLaden } from '../lib/eew.svelte.js'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import Kachel from './Kachel.svelte'
  import Skillmaske from './Skillmaske.svelte'
  import Standpille from './Standpille.svelte'
  import Verbindungen from './Verbindungen.svelte'
  import Klangwahl from './Klangwahl.svelte'
  import { klangwahl } from '../lib/klaenge.svelte.js'
  import Schalter from './Schalter.svelte'
  import { api } from '../lib/api.js'
  import { zustand, aktuellerChat, chatAendern, konturSetzen, schriftSetzen, oberflaecheSetzen, codefarbenSetzen, blasenfarbeSetzen, melde, frage, modelleLaden } from '../lib/zustand.svelte.js'

  function blasenStandard() {
    // The picker's "current default" swatch must match what an untouched
    // bubble actually shows — a theme may ship its own default (Dark Matter's
    // lavender), so prefer that over the plain house bubble.
    const stil = getComputedStyle(document.documentElement)
    const wert = (
      stil.getPropertyValue('--blase-eigen-standard').trim() ||
      stil.getPropertyValue('--blase').trim()
    )
    return /^#[0-9a-fA-F]{6}$/.test(wert) ? wert : '#232320'
  }
  import {
    t, texte, gemerkteSprachwahl, spracheWaehlen, spracheZuruecksetzen,
  } from '../lib/texte.svelte.js'
  import { begruessung, anredeSpeichern } from '../lib/begruessung.svelte.js'

  let { offen = $bindable(false), modus = $bindable('auto') } = $props()

  let art = $state('system') // sprache|darstellung|system|memory|skills|agent|tools|tools_datei|huggingface|konfiguration|zugangsdaten
  let agentName = $state('')
  let dateien = $state([]) // [{ name, kaputt }]
  let text = $state('')
  let geladen = $state('')
  let kaputt = $state(null)
  let platzhalter = $state([]) // tools only
  let lese = $state(null) // GET /tools live readout
  let feld = $state(null)
  let laedt = $state(false)

  const chat = $derived(aktuellerChat())
  const ausgesetzt = $derived(Boolean(chat?.prompt_aus))
  const istSprache = $derived(art === 'sprache')
  const istDarstellung = $derived(art === 'darstellung')
  const istSystem = $derived(art === 'system')
  const istGedaechtnis = $derived(art === 'memory')
  const istSkills = $derived(art === 'skills')
  const istGalerie = $derived(art === 'tools')
  const istTools = $derived(art === 'tools_datei')
  const istAgent = $derived(art === 'agent')
  const istHf = $derived(art === 'huggingface')
  const gesperrt = $derived(Boolean(zustand.features?.beta_lock))
  const istDatei = $derived(art === 'konfiguration' || art === 'zugangsdaten')
  /* The agent page has two faces: the list of agents, and the editor for
     one of them. A name means the editor is open. */
  const agentBearbeiten = $derived(istAgent && agentName !== '')
  const bearbeitet = $derived(istSystem || istGedaechtnis || istDatei || istTools || agentBearbeiten)

  const MODI = [
    ['auto', 'einstellungen.auto'],
    ['hell', 'einstellungen.hell'],
    ['dunkel', 'einstellungen.dunkel'],
    ['darkmatter', 'einstellungen.darkmatter'],
    ['heaven', 'einstellungen.heaven'],
  ]

  /* The switches that decide whether the memory travels. */
  let gedaechtnisSchalter = $state({ lokal: true, cloud: false })
  async function gedaechtnisStandLaden() {
    try {
      const stand = await api.einstellungAufgeloest('gedaechtnis')
      if (stand?.wert && typeof stand.wert === 'object') {
        gedaechtnisSchalter = { ...gedaechtnisSchalter, ...stand.wert }
      }
    } catch {
      /* Leaves the default standing — it is the careful one. */
    }
  }
  async function gedaechtnisSchalten(seite, an) {
    const vorher = gedaechtnisSchalter
    gedaechtnisSchalter = { ...vorher, [seite]: an }
    try {
      await api.einstellungSetzen('global', 'gedaechtnis', gedaechtnisSchalter)
    } catch {
      gedaechtnisSchalter = vorher
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  /* The switch that strips a picture of everything but its pixels — uploaded
     and generated alike. Shipped on: a picture leaves no trail unless this is
     turned off on purpose. Stored as a set of one, like the memory switches,
     so "off" is a truthy value the settings route keeps rather than discards. */
  let bildschutzSchalter = $state({ an: true })
  async function bildschutzStandLaden() {
    try {
      const stand = await api.einstellungAufgeloest('bildmetadaten')
      if (stand?.wert && typeof stand.wert === 'object') {
        bildschutzSchalter = { ...bildschutzSchalter, ...stand.wert }
      }
    } catch {
      /* Leaves the default standing — it is the careful one. */
    }
  }
  async function bildschutzSchalten(an) {
    const vorher = bildschutzSchalter
    bildschutzSchalter = { an }
    try {
      await api.einstellungSetzen('global', 'bildmetadaten', bildschutzSchalter)
    } catch {
      bildschutzSchalter = vorher
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  /* The guardian's switch. Shipped on: it only ever offers, so leaving it
     on can cost nothing but a few seconds after a step that already went
     wrong.

     The fact itself lives in `lib/eew.svelte.js`, because the same switch
     also stands in the module's own head — two switches for one fact is
     fine, two copies of the fact are not. */
  const waechterStandLaden = eewStandLaden
  async function waechterSchalten(an) {
    try {
      await eewSchalten(an)
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  /* The switch for cutting long documents into passages. Shipped on: the
     alternative is not "nothing happens" but a context that quietly
     overruns. */
  let einbettungAn = $state(true)
  async function einbettungStandLaden() {
    try {
      const stand = await api.einstellungAufgeloest('einbettung')
      if (stand?.wert && typeof stand.wert.an === 'boolean') einbettungAn = stand.wert.an
    } catch {
      /* Leaves the default standing. */
    }
  }
  async function einbettungSchalten(an) {
    const vorher = einbettungAn
    einbettungAn = an
    try {
      await api.einstellungSetzen('global', 'einbettung', { an })
    } catch {
      einbettungAn = vorher
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  let sprachwahl = $state(gemerkteSprachwahl())
  const sprachauswahl = $derived([
    { wert: 'auto', text: t('einstellungen.sprache_auto') },
    { wert: 'en', text: t('einstellungen.sprache_englisch') },
    { wert: 'de', text: t('einstellungen.sprache_deutsch') },
  ])
  async function spracheStellen(wert) {
    sprachwahl = wert
    try {
      if (wert === 'auto') await spracheZuruecksetzen()
      else await spracheWaehlen(wert)
      await modelleLaden()
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  /* The Hugging Face token: lifts rate limits, opens gated models. Only
     ever set here, never read back — the light is derived from a boolean. */
  let hfGesetzt = $state(false)
  let hfEingabe = $state('')
  async function hfSetzen() {
    try {
      await api.hfTokenSetzen(hfEingabe.trim())
      hfEingabe = ''
      hfGesetzt = true
      stand.hf = true
    } catch (fehler) {
      melde(fehler.message, 'fehler')
    }
  }

  /* The live state behind the subtitles — fetched once when the window
     opens, so a glance at the list shows where everything stands. */
  let stand = $state({ serverAnzahl: 0, werkzeugAnzahl: 0, skills: 0, skillsAuto: true, hf: false })
  async function standLaden() {
    api.werkzeuge().then((wz) => {
      stand.serverAnzahl = wz?.server?.length ?? 0
      stand.werkzeugAnzahl = wz?.werkzeuge?.length ?? 0
    }).catch(() => {})
    api.skillsVerwaltung().then((z) => (stand.skills = z.length)).catch(() => {})
    api.einstellungAufgeloest('skills_auto').then((s) => {
      if (s?.wert && typeof s.wert.an === 'boolean') stand.skillsAuto = s.wert.an
    }).catch(() => {})
    api.hfTokenStand().then((s) => { stand.hf = s.gesetzt; hfGesetzt = s.gesetzt }).catch(() => {})
    gedaechtnisStandLaden()
    bildschutzStandLaden()
    waechterStandLaden()
    einbettungStandLaden()
  }

  const VORLAGE = () =>
    `---
model:
tools:
  - web_search
max_rounds: 30
max_minutes: 20
---

You are a concise researcher. You answer the question with at most one web
search and then deliver a short report right away: one sentence of answer
first, then at most three bullet points with sources. Do not keep searching
once the question is answered.
`
  const STANDARDNAME = 'exe-agent'
  function freierName() {
    const belegt = new Set(dateien.map((d) => d.name))
    if (!belegt.has(STANDARDNAME)) return STANDARDNAME
    let zaehler = 2
    while (belegt.has(`${STANDARDNAME}-${zaehler}`)) zaehler += 1
    return `${STANDARDNAME}-${zaehler}`
  }

  /* The grouped nav: each box a group, each entry a sign, a title and a
     live-state subtitle. `sperrbar` marks entries the beta lock disables. */
  const EINTRAEGE = {
    sprache: { zeichen: 'sprache', titel: 'editor.quelle_sprache' },
    darstellung: { zeichen: 'erscheinung', titel: 'editor.quelle_darstellung' },
    memory: { zeichen: 'wolke', titel: 'gedaechtnis.quelle', sperrbar: true },
    skills: { zeichen: 'buch', titel: 'skills.quelle' },
    system: { zeichen: 'feder', titel: 'agenten.quelle_system', sperrbar: true },
    agent: { zeichen: 'person', titel: 'editor.quelle_agenten', sperrbar: true },
    tools: { zeichen: 'server', titel: 'editor.quelle_tools', sperrbar: true },
    huggingface: { zeichen: 'paket', titel: 'editor.quelle_hf', sperrbar: true },
    zugangsdaten: { zeichen: 'schluessel', titel: 'editor.quelle_zugangsdaten', sperrbar: true },
    konfiguration: { zeichen: 'dokument', titel: 'editor.quelle_konfiguration', sperrbar: true },
    tools_datei: { zeichen: 'dokument_pfeil', titel: 'editor.quelle_tools_datei', sperrbar: true },
  }
  const GRUPPEN = [
    { name: 'general', titel: 'editor.gruppe_general', eintraege: ['sprache', 'darstellung'] },
    { name: 'verhalten', titel: 'editor.gruppe_verhalten', eintraege: ['memory', 'skills'] },
    { name: 'prompts', titel: 'editor.gruppe_prompts', eintraege: ['system', 'agent'] },
    { name: 'verbindungen', titel: 'editor.gruppe_verbindungen', eintraege: ['tools', 'huggingface', 'zugangsdaten'] },
    { name: 'dateien', titel: 'editor.gruppe_dateien', eintraege: ['konfiguration', 'tools_datei'] },
  ]

  const spracheName = $derived(
    texte.sprache === 'de' ? t('einstellungen.sprache_deutsch') : t('einstellungen.sprache_englisch'),
  )

  function unterText(key) {
    switch (key) {
      case 'sprache':
        return `${spracheName} · ${t(klangwahl.aus ? 'einstellungen.toene_aus' : 'einstellungen.toene_an')}`
      case 'darstellung': {
        const schriftKey = 'einstellungen.schrift_' + zustand.schrift
        return `${t('einstellungen.' + modus)} · ${t(schriftKey)}`
      }
      case 'memory':
        return gedaechtnisSchalter.lokal
          ? t(gedaechtnisSchalter.cloud ? 'editor.mem_lokal_cloud' : 'editor.mem_lokal')
          : t('editor.mem_aus')
      case 'skills':
        return t('editor.unter_skills', { n: stand.skills })
      case 'system':
        return t('editor.unter_system')
      case 'agent':
        return t('editor.unter_agenten', { n: dateien.length })
      case 'tools':
        return t('editor.unter_server', { n: stand.serverAnzahl, w: stand.werkzeugAnzahl })
      case 'huggingface':
        return t(hfGesetzt ? 'editor.hf_gesetzt_kurz' : 'editor.hf_fehlt_kurz')
      case 'zugangsdaten':
        return t('editor.unter_zugang')
      case 'konfiguration':
        return t('editor.unter_konfig')
      case 'tools_datei':
        return t('editor.unter_tools_datei')
      default:
        return ''
    }
  }
  /* An entry carries a status lamp only where there is a state worth one. */
  function ampelFarbe(key) {
    switch (key) {
      case 'memory':
        return gedaechtnisSchalter.lokal ? 'gruen' : 'still'
      case 'skills':
        return stand.skillsAuto ? 'gruen' : 'still'
      case 'tools':
        return stand.serverAnzahl > 0 ? 'gruen' : 'still'
      case 'huggingface':
        return hfGesetzt ? 'gruen' : 'still'
      default:
        return null
    }
  }
  function istAktiv(key) {
    return art === key
  }
  function navZiel(key) {
    // The agent entry always opens the list first, never the last file.
    if (key === 'agent') return wechseln('agent', '')
    return wechseln(key)
  }

  $effect(() => {
    if (!offen) return
    dateienLaden()
    standLaden()
    if (gesperrt) laden('darstellung')
    else if (zustand.promptStart === 'darstellung') laden('darstellung')
    else if (zustand.promptStart === 'tools') laden('tools')
    else if (zustand.promptStart?.startsWith?.('agent:')) laden('agent', zustand.promptStart.slice(6))
    else laden('system')
  })

  async function dateienLaden() {
    try {
      dateien = await api.agentDateien()
    } catch {
      dateien = []
    }
  }
  async function leseanzeigeLaden() {
    try {
      lese = await api.werkzeuge()
    } catch {
      lese = null
    }
  }

  function meldeschluessel(fall) {
    if (istSystem) return `systemprompt.${fall}`
    if (istGedaechtnis) return `gedaechtnis.${fall}`
    if (istDatei) return `dateien.${fall}`
    if (istTools) return `werkzeuge.${fall}`
    return `agenten.${fall}`
  }

  /* File-less pages carry no text to fetch or discard. The agent LIST is
     one of them; only an agent with a name loads a file. */
  const OHNE_DATEI = ['sprache', 'darstellung', 'tools', 'skills', 'huggingface']

  async function laden(neueArt, name = '') {
    if (OHNE_DATEI.includes(neueArt) || (neueArt === 'agent' && !name)) {
      art = neueArt
      agentName = name
      text = ''
      geladen = ''
      kaputt = null
      platzhalter = []
      return
    }
    laedt = true
    kaputt = null
    platzhalter = []
    try {
      if (neueArt === 'system') {
        const daten = await api.systemPrompt()
        text = daten.text
      } else if (neueArt === 'memory') {
        const daten = await api.gedaechtnis()
        text = daten.text
        gedaechtnisStandLaden()
      } else if (neueArt === 'tools_datei') {
        const daten = await api.werkzeugKonfiguration()
        text = daten.content
        kaputt = daten.kaputt
        platzhalter = daten.platzhalter
        leseanzeigeLaden()
      } else if (neueArt === 'konfiguration' || neueArt === 'zugangsdaten') {
        const daten = await api.datei(neueArt)
        text = daten.inhalt
        kaputt = daten.kaputt
      } else {
        const daten = await api.agentDatei(name)
        text = daten.content
        kaputt = daten.kaputt
      }
      geladen = text
      art = neueArt
      agentName = name
    } catch {
      melde(t(meldeschluessel('nicht_geladen')), 'fehler')
    } finally {
      laedt = false
      setTimeout(() => feld?.fokus(), 60)
    }
  }

  async function wechseln(neueArt, name = '') {
    if (neueArt === art && name === agentName) return
    if (text !== geladen && !(await frage(t('agenten.verwerfen_frage')))) return
    laden(neueArt, name)
  }

  async function neuerAgent() {
    if (text !== geladen && !(await frage(t('agenten.verwerfen_frage')))) return
    art = 'agent'
    agentName = freierName()
    text = VORLAGE()
    geladen = null
    kaputt = null
    platzhalter = []
    setTimeout(() => feld?.fokus(), 60)
  }

  async function sichern() {
    try {
      if (istSystem) {
        const daten = await api.systemPromptSichern(text)
        geladen = daten.text
        melde(daten.text ? t('systemprompt.gesichert') : t('systemprompt.geleert'), 'erfolg')
        offen = false
      } else if (istGedaechtnis) {
        const daten = await api.gedaechtnisSichern(text)
        geladen = daten.text
        melde(daten.text ? t('gedaechtnis.gesichert') : t('gedaechtnis.geleert'), 'erfolg')
      } else if (istDatei) {
        const daten = await api.dateiSichern(art, text)
        geladen = daten.inhalt
        kaputt = daten.kaputt
        melde(t(kaputt ? 'dateien.gesichert_kaputt' : 'dateien.gesichert'), kaputt ? 'hinweis' : 'erfolg')
      } else if (istTools) {
        const daten = await api.werkzeugKonfigurationSichern(text)
        geladen = daten.content
        kaputt = daten.kaputt
        platzhalter = daten.platzhalter
        melde(kaputt ? t('werkzeuge.gesichert_kaputt') : t('werkzeuge.gesichert'), kaputt ? 'hinweis' : 'erfolg')
        if (!kaputt) {
          setTimeout(leseanzeigeLaden, 1500)
          setTimeout(leseanzeigeLaden, 5000)
        }
      } else {
        if (!/^[A-Za-z0-9_-]{1,100}$/.test(agentName)) {
          melde(t('fehler.agent_name_ungueltig'), 'fehler')
          return
        }
        const daten = await api.agentSichern(agentName, text)
        geladen = daten.content
        kaputt = daten.kaputt
        await dateienLaden()
        melde(t('agenten.gesichert', { name: agentName }), kaputt ? 'hinweis' : 'erfolg')
        if (!kaputt) wechseln('agent', '')
      }
    } catch {
      melde(t(meldeschluessel('nicht_gesichert')), 'fehler')
    }
  }

  async function agentLoeschen() {
    if (!(await frage(t('agenten.loeschen_frage', { name: agentName })))) return
    try {
      if (geladen !== null) await api.agentLoeschen(agentName)
      melde(t('agenten.geloescht', { name: agentName }), 'erfolg')
      await dateienLaden()
      laden('agent', '')
    } catch {
      melde(t('agenten.nicht_gesichert'), 'fehler')
    }
  }

  async function aussetzen(an) {
    if (!chat) {
      melde(t('chat.erst_oeffnen'))
      return
    }
    try {
      await chatAendern(chat.id, { prompt_aus: an })
    } catch {
      melde(t('systemprompt.schalter_fehler'), 'fehler')
    }
  }

  const kopfEintrag = $derived(agentBearbeiten ? EINTRAEGE.agent : EINTRAEGE[art] ?? EINTRAEGE.system)
</script>

<Fenster bind:offen art="liste">
  <div class="ganz">
    <div class="markenkopf" role="heading" aria-level="2" aria-label={t('editor.titel')}>
      <div class="markenzeile">
        <svg viewBox="0 0 100 100" width="38" height="38" fill="none" stroke="currentColor"
             stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="50" cy="50" r="16" />
          <path d="M50 22 V32 M50 68 V78 M22 50 H32 M68 50 H78 M30 30 l7 7 M63 63 l7 7 M70 30 l-7 7 M37 63 l-7 7" />
        </svg>
        <Schriftzug zug="einstellungen" hoehe={18} />
      </div>
      <div class="markensatz">{t('editor.markensatz')}</div>
    </div>

    <div class="set-zwei">
      <nav class="set-links" use:rollfade aria-label={t('editor.titel')}>
        {#each GRUPPEN as g (g.name)}
          <div class="s2-gruppe">{t(g.titel)}</div>
          <div class="s2-box">
            {#each g.eintraege as key (key)}
              <button
                class="s2-eintrag"
                class:gewaehlt={istAktiv(key)}
                class:gesperrt={gesperrt && EINTRAEGE[key].sperrbar}
                disabled={gesperrt && EINTRAEGE[key].sperrbar}
                aria-current={istAktiv(key)}
                onclick={() => navZiel(key)}
              >
                <span class="s2-zeichen"><Hauszeichen zeichen={EINTRAEGE[key].zeichen} groesse="mittel" /></span>
                <div class="s2-mitte">
                  <div class="s2-titel">{t(EINTRAEGE[key].titel)}</div>
                  <div class="s2-satz">{unterText(key)}</div>
                </div>
                {#if gesperrt && EINTRAEGE[key].sperrbar}
                  <span class="beta">{t('beta.marke')}</span>
                {:else if ampelFarbe(key)}
                  <span class="s2-recht"><Leuchtpunkt farbe={ampelFarbe(key)} groesse={7} /></span>
                {/if}
              </button>
            {/each}
          </div>
        {/each}
      </nav>

      <div class="set-rechts" use:rollfade>
        <div class="set-kopf">
          <span class="s2-zeichen gross"><Hauszeichen zeichen={kopfEintrag.zeichen} groesse="gross" /></span>
          <h3>{t(kopfEintrag.titel)}</h3>
        </div>

        {#if istSprache}
          <div class="kachelliste">
            <div class="einstellkachel">
              <div class="zeilentext">
                {t('einstellungen.sprache')}
                <span class="hinweis">{t('einstellungen.sprache_hinweis')}</span>
              </div>
              <div class="auswahl">
                <Auswahlfeld
                  wert={sprachwahl}
                  eintraege={sprachauswahl}
                  beschriftung={t('einstellungen.sprache')}
                  gewaehlt={spracheStellen}
                />
              </div>
            </div>
            <!-- The sounds sit here and not under appearance: how loud the
                 program is is not a question of how it looks, and that panel
                 had grown long enough. -->
            <Klangwahl />
          </div>
        {:else if istDarstellung}
          <div class="kachelliste">
            <div class="einstellkachel">
              <div class="zeilentext">
                {t('einstellungen.erscheinungsbild')}
                <span class="hinweis">{t('einstellungen.auto_hinweis')}</span>
              </div>
              <Klappwahl
                optionen={MODI.map(([wert, schluessel]) => [wert, t(schluessel)])}
                bind:wert={modus}
                beschriftung={t('einstellungen.erscheinungsbild')}
              />
            </div>
            <div class="einstellkachel">
              <div class="zeilentext">
                {t('einstellungen.kontur')}
                <span class="hinweis">{t('einstellungen.kontur_hinweis')}</span>
              </div>
              <Schalter an={zustand.kontur} beschriftung={t('einstellungen.kontur')} onschalten={(an) => konturSetzen(an)} />
            </div>
            <div class="einstellkachel">
              <div class="zeilentext">
                {t('einstellungen.oberflaeche')}
                <span class="hinweis">{t('einstellungen.oberflaeche_hinweis')}</span>
              </div>
              <div class="segment">
                {#each [['standard', 'einstellungen.schrift_standard'], ['gross', 'einstellungen.schrift_gross'], ['groesser', 'einstellungen.schrift_groesser']] as [wert, beschriftung] (wert)}
                  <button aria-pressed={zustand.oberflaeche === wert} onclick={() => oberflaecheSetzen(wert)}>{t(beschriftung)}</button>
                {/each}
              </div>
            </div>
            <div class="einstellkachel">
              <div class="zeilentext">
                {t('einstellungen.schrift')}
                <span class="hinweis">{t('einstellungen.schrift_hinweis')}</span>
              </div>
              <div class="segment">
                {#each [['standard', 'einstellungen.schrift_standard'], ['gross', 'einstellungen.schrift_gross'], ['groesser', 'einstellungen.schrift_groesser']] as [wert, beschriftung] (wert)}
                  <button aria-pressed={zustand.schrift === wert} onclick={() => schriftSetzen(wert)}>{t(beschriftung)}</button>
                {/each}
              </div>
            </div>
            <div class="einstellkachel">
              <div class="zeilentext">
                {t('einstellungen.codefarben')}
                <span class="hinweis">{t('einstellungen.codefarben_hinweis')}</span>
              </div>
              <div class="segment">
                {#each [['exe', 'einstellungen.codefarben_exe'], ['tokyo', 'einstellungen.codefarben_tokyo'], ['onelight', 'einstellungen.codefarben_onelight']] as [wert, beschriftung] (wert)}
                  <button aria-pressed={zustand.codefarben === wert} onclick={() => codefarbenSetzen(wert)}>{t(beschriftung)}</button>
                {/each}
              </div>
            </div>
            <div class="einstellkachel">
              <div class="zeilentext">
                {t('einstellungen.blase')}
                <span class="hinweis">{t('einstellungen.blase_hinweis')}</span>
              </div>
              <div class="farbwahl">
                {#if zustand.blasenfarbe}
                  <button class="ruecksetzer" onclick={() => blasenfarbeSetzen('')}>{t('einstellungen.blase_standard')}</button>
                {/if}
                <input type="color" aria-label={t('einstellungen.blase')}
                       value={zustand.blasenfarbe || blasenStandard()} oninput={(e) => blasenfarbeSetzen(e.currentTarget.value)} />
              </div>
            </div>
          </div>
        {:else if istSkills}
          <Skillmaske />
        {:else if istGalerie}
          <Verbindungen
            zuDatei={() => wechseln('tools_datei')}
            zuZugangsdaten={() => wechseln('zugangsdaten')}
            zuWerkzeugen={() => { offen = false; zustand.werkzeugeOffen = true }}
          />
        {:else if istHf}
          <div class="hf-seite">
            <div class="set-satz">{t('editor.hf_erklaerung')}</div>
            <div class="hf-stand">
              <Leuchtpunkt farbe={hfGesetzt ? 'gruen' : 'still'} groesse={7} />
              {t(hfGesetzt ? 'editor.hf_gesetzt_lang' : 'editor.hf_fehlt_lang')}
            </div>
            {#if !hfGesetzt}
              <div class="feldzeile">
                <input class="feld" type="password" bind:value={hfEingabe} placeholder={t('modell.hf_token')}
                       autocomplete="off" onkeydown={(e) => { if (e.key === 'Enter' && hfEingabe.trim().length >= 8) hfSetzen() }} />
                <button class="knopf" disabled={hfEingabe.trim().length < 8} onclick={hfSetzen}>{t('modell.verbinden')}</button>
              </div>
              <div class="fussnote">{t('editor.hf_fussnote')}</div>
            {/if}
          </div>
        {:else if istAgent && !agentBearbeiten}
          <div class="agentliste">
            {#each dateien as datei (datei.name)}
              <div class="kachelzeile">
                <Kachel titel={datei.name} onclick={() => wechseln('agent', datei.name)} ariaLabel={datei.name}>
                  {#snippet marke()}<Agentenmarke groesse={18} />{/snippet}
                  {#snippet rechts()}
                    {#if datei.kaputt}<span class="warnpunkt" title={datei.kaputt}></span>{:else}<span class="pfeil">→</span>{/if}
                  {/snippet}
                </Kachel>
              </div>
            {/each}
            <button class="agentneu" onclick={neuerAgent}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2.2" stroke-linecap="round"><path d="M12 5 V19 M5 12 H19" /></svg>
              {t('agenten.neu')}
            </button>
          </div>
        {:else}
          <WachsendesFeld
            bind:this={feld}
            bind:wert={text}
            gesperrt={laedt}
            gedimmt={istSystem && ausgesetzt}
            platzhalter={istSystem || agentBearbeiten ? t('systemprompt.platzhalter') : ''}
            beschriftung={t('editor.titel')}
            volleHoehe
          />
        {/if}

        {#if kaputt}
          <div class="warnung" transition:fade={{ duration: 120 }}>
            {t(istTools ? 'werkzeuge.kaputt' : 'agenten.kaputt', { grund: kaputt })}
          </div>
        {/if}

        {#if istTools && platzhalter.length}
          <div class="ampeln">
            {#each platzhalter as eintrag (eintrag.name)}
              <span class="ampelzeile" class:fehlt={!eintrag.gesetzt}>
                <Leuchtpunkt farbe={eintrag.gesetzt ? 'gruen' : 'still'} groesse={7} />
                {eintrag.name} — {t(eintrag.gesetzt ? 'werkzeuge.platzhalter_gesetzt' : 'werkzeuge.platzhalter_fehlt')}
              </span>
            {/each}
          </div>
        {/if}

        {#if istTools}
          <div class="lese">
            <div class="lesetitel">{t('werkzeuge.live')}</div>
            {#if !lese}
              <span class="leseleer">{t('werkzeuge.keine')}</span>
            {:else if !lese.aktiv}
              <span class="leseleer">{t('werkzeuge.abgeschaltet')}</span>
            {:else}
              {#each lese.server as server (server)}
                <span class="server"><Leuchtpunkt farbe="gruen" groesse={7} />{server}</span>
              {/each}
              {#if lese.werkzeuge.length}
                <div class="werkzeugpillen">
                  {#each lese.werkzeuge as werkzeug (werkzeug.name)}
                    <Standpille>{werkzeug.name}</Standpille>
                  {/each}
                </div>
              {:else}
                <span class="leseleer">{t('werkzeuge.keine')}</span>
              {/if}
            {/if}
          </div>
        {/if}

        {#if istGedaechtnis}
          <div class="schalterzeile">
            <div class="beschriftung">
              {t('gedaechtnis.an_lokal')}
              <span class="hinweis">{t('gedaechtnis.an_lokal_hinweis')}</span>
            </div>
            <Schalter an={gedaechtnisSchalter.lokal} beschriftung={t('gedaechtnis.an_lokal')} onschalten={(an) => gedaechtnisSchalten('lokal', an)} />
          </div>
          <div class="schalterzeile">
            <div class="beschriftung">
              {t('gedaechtnis.an_cloud')}
              <span class="hinweis">{t('gedaechtnis.an_cloud_hinweis')}</span>
            </div>
            <Schalter an={gedaechtnisSchalter.cloud} beschriftung={t('gedaechtnis.an_cloud')} onschalten={(an) => gedaechtnisSchalten('cloud', an)} />
          </div>
          <div class="schalterzeile">
            <div class="beschriftung">
              {t('bildschutz.titel')}
              <span class="hinweis">{t('bildschutz.hinweis')}</span>
            </div>
            <Schalter an={bildschutzSchalter.an} beschriftung={t('bildschutz.titel')} onschalten={(an) => bildschutzSchalten(an)} />
          </div>
        {/if}

        {#if istSystem}
          <div class="schalterzeile">
            <div class="beschriftung">{t('waechter.titel')}
              <span class="hinweis">{t('waechter.schalter')}</span>
            </div>
            <Schalter an={eew.an} beschriftung={t('waechter.titel')}
                      onschalten={(an) => waechterSchalten(an)} />
          </div>
          <div class="schalterzeile">
            <div class="beschriftung">{t('einbettung.titel')}
              <span class="hinweis">{t('einbettung.schalter')}</span>
            </div>
            <Schalter an={einbettungAn} beschriftung={t('einbettung.titel')}
                      onschalten={(an) => einbettungSchalten(an)} />
          </div>
          <div class="schalterzeile">
            <div class="beschriftung">{t('editor.anrede_titel')}
              <span class="hinweis">{t('editor.anrede_unter')}</span>
            </div>
            <input class="anredefeld" value={begruessung.name} placeholder={begruessung.vorschlag}
                   aria-label={t('editor.anrede_titel')}
                   onchange={(e) => anredeSpeichern(e.currentTarget.value, begruessung.an)} />
          </div>
          <div class="schalterzeile">
            <div class="beschriftung">{t('editor.anrede_schalter')}
              <span class="hinweis">{t('editor.anrede_schalter_unter')}</span>
            </div>
            <Schalter an={begruessung.an} beschriftung={t('editor.anrede_schalter')}
                      onschalten={(an) => anredeSpeichern(begruessung.name, an)} />
          </div>
          <div class="schalterzeile">
            <div class="beschriftung">{t('systemprompt.aussetzen')}</div>
            <Schalter an={ausgesetzt} art="eingriff" beschriftung={t('systemprompt.aussetzen')} onschalten={(an) => aussetzen(an)} />
          </div>
        {/if}

        <div class="fuss">
          {#if istSystem || istGedaechtnis}
            <button class="textknopf" onclick={() => { text = ''; feld?.fokus() }}>{t('app.leeren')}</button>
          {:else if agentBearbeiten}
            <button class="textknopf gefahr" onclick={agentLoeschen}>{t('agenten.loeschen')}</button>
          {:else}
            <span></span>
          {/if}
          <div class="rechts">
            {#if bearbeitet}
              <button class="knopf" onclick={() => { offen = false }}>{t('app.abbrechen')}</button>
              <button class="knopf wichtig" onclick={sichern}>{t('app.sichern')}</button>
            {:else}
              <button class="knopf" onclick={() => { offen = false }}>{t('app.fertig')}</button>
            {/if}
          </div>
        </div>
      </div>
    </div>
  </div>
</Fenster>

<style>
  .ganz {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    margin: -4px 0 0;
  }
  .markenkopf {
    flex: none;
    margin: 2px 0 12px;
  }
  .markenzeile {
    display: flex;
    align-items: center;
    gap: 13px;
    color: var(--text);
  }
  .markensatz {
    color: var(--text-still);
    font-size: 13px;
    margin-top: 8px;
  }

  .set-zwei {
    display: flex;
    border: 1px solid var(--linie);
    border-radius: 12px;
    overflow: hidden;
    flex: 1;
    min-height: 0;
  }
  .set-links {
    width: 300px;
    flex: none;
    border-right: 1px solid var(--linie);
    background: var(--bg-seite);
    padding: 12px 10px;
    overflow-y: auto;
  }
  .s2-gruppe {
    font-size: 10.5px;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 600;
    margin: 16px 8px 6px;
  }
  .s2-gruppe:first-child {
    margin-top: 2px;
  }
  .s2-box {
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg-erhoben);
    overflow: hidden;
  }
  .s2-eintrag {
    display: flex;
    align-items: center;
    gap: 11px;
    width: 100%;
    text-align: left;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    padding: 10px 12px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .s2-eintrag + .s2-eintrag {
    border-top: 1px solid var(--linie);
  }
  .s2-eintrag:hover {
    background: var(--linie);
  }
  .s2-eintrag.gewaehlt {
    background: var(--linie);
  }
  .s2-zeichen {
    width: 30px;
    height: 30px;
    flex: none;
    border-radius: 9px;
    border: 1px solid var(--linie);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-leise);
  }
  .s2-zeichen.gross {
    width: 36px;
    height: 36px;
  }
  .s2-mitte {
    flex: 1;
    min-width: 0;
  }
  .s2-titel {
    font: 600 13px var(--schrift);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .s2-satz {
    font-size: 11px;
    color: var(--text-still);
    margin-top: 1px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .s2-recht {
    margin-left: auto;
    flex: none;
    display: inline-flex;
    align-items: center;
  }
  .beta {
    margin-left: auto;
    flex: none;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-still);
  }
  .s2-eintrag.gesperrt {
    opacity: 0.5;
    cursor: default;
  }
  .s2-eintrag.gesperrt:hover {
    background: none;
  }

  .set-rechts {
    flex: 1;
    min-width: 0;
    padding: 16px 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  .set-kopf {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
    flex: none;
  }
  .set-kopf h3 {
    font-size: 16px;
    font-weight: 600;
    margin: 0;
  }
  .set-satz {
    color: var(--text-leise);
    font-size: 12.5px;
    line-height: 1.6;
    margin: 0 0 16px;
    max-width: 440px;
  }

  .hf-seite {
    max-width: 440px;
  }
  .hf-stand {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: var(--text-leise);
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 9px 12px;
    max-width: 360px;
    margin-bottom: 14px;
  }
  .feldzeile {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .feld {
    width: 100%;
    max-width: 300px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg);
    color: var(--text);
    font: 13px var(--schrift);
    padding: 8px 12px;
  }
  .fussnote {
    font-size: 11.5px;
    color: var(--text-still);
    margin-top: 10px;
  }

  .agentliste {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .kachelzeile {
    margin: 0;
  }
  .warnpunkt {
    width: 7px;
    height: 7px;
    border-radius: 99px;
    background: var(--rot);
    box-shadow: 0 0 0 1.5px var(--text);
    flex: none;
  }
  .pfeil {
    color: var(--text-still);
    font-size: 12px;
  }
  .agentneu {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: 1px dashed var(--linie-stark);
    border-radius: 12px;
    background: none;
    color: var(--text-still);
    font: 600 12.5px var(--schrift);
    padding: 0 12px;
    height: 58px;
    cursor: pointer;
    transition: color 0.12s, border-color 0.12s;
  }
  .agentneu:hover {
    color: var(--text);
    border-color: var(--text-still);
  }

  .warnung {
    margin-top: 10px;
    border: 1px solid var(--rot);
    border-radius: 12px;
    color: var(--rot);
    font-size: 12.5px;
    line-height: 1.5;
    padding: 8px 12px;
  }

  .ampeln {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 16px;
    margin-top: 10px;
  }
  .ampelzeile {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-leise);
  }
  .ampelzeile.fehlt {
    color: var(--text-still);
  }

  .lese {
    margin-top: 12px;
    border-top: 1px solid var(--linie);
    padding-top: 8px;
  }
  .lesetitel {
    font-size: 10.5px;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-still);
    margin-bottom: 6px;
  }
  .server {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12.5px;
    margin-right: 14px;
  }
  .werkzeugpillen {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 6px;
  }
  .leseleer {
    font-size: 12px;
    color: var(--text-still);
  }

  .schalterzeile {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 13px 2px 3px;
    margin-top: 12px;
    border-top: 1px solid var(--linie);
  }
  .beschriftung {
    flex: 1;
    min-width: 0;
    font-size: 13px;
  }

  .kachelliste {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 2px 2px 0;
  }
  .einstellkachel {
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    padding: 12px 13px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .zeilentext {
    flex: 1;
    min-width: 0;
    font-size: 13px;
  }
  .hinweis {
    display: block;
    font-size: 11.5px;
    color: var(--text-still);
    margin-top: 2px;
  }
  .segment {
    display: flex;
    flex: none;
    background: var(--bg-seite);
    border: 1px solid var(--linie);
    border-radius: 9px;
    padding: 2px;
  }
  .segment button {
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
  .segment button[aria-pressed='true'] {
    background: var(--bg-erhoben);
    color: var(--text);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }
  /* The picker brings its own measure; the row only says how wide it may be
     so the label keeps the rest. */
  .auswahl {
    flex: none;
    width: 190px;
  }
  .farbwahl {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .farbwahl input[type='color'] {
    width: 44px;
    height: 28px;
    padding: 2px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg-seite);
    cursor: pointer;
  }
  .ruecksetzer {
    font: inherit;
    font-size: 12.5px;
    color: var(--text-leise);
    background: none;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 4px 10px;
    cursor: pointer;
  }
  .ruecksetzer:hover {
    color: var(--text);
  }

  .fuss {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: auto;
    padding-top: 14px;
    flex: none;
  }
  .rechts {
    display: flex;
    gap: 8px;
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13px;
    padding: 7px 15px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s, transform 0.08s;
  }
  .knopf:hover:not(:disabled) {
    background: var(--linie);
  }
  .knopf:active:not(:disabled) {
    transform: scale(0.975);
  }
  .knopf:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .wichtig:hover:not(:disabled) {
    background: var(--text);
    opacity: 0.88;
  }
  .textknopf {
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 7px;
  }
  .textknopf:hover {
    background: var(--linie);
    color: var(--text);
  }
  .textknopf.gefahr:hover {
    background: var(--rot);
    color: #fff;
  }

  @media (max-width: 720px) {
    .set-zwei {
      flex-direction: column;
      flex: none;
    }
    .set-links {
      width: 100%;
      border-right: none;
      border-bottom: 1px solid var(--linie);
    }
  }
  .anredefeld {
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg);
    color: var(--text);
    font: 13px var(--schrift);
    padding: 6px 11px;
    width: 150px;
    flex: none;
  }
</style>
