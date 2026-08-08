<script>
  /* The settings window — appearance, system prompt (3.10), agents
     (6.6) and tools (A6).

     It remains ONE window, but since A6 a vertical, grouped list on the
     left chooses the source (a list instead of
     pills): Prompts → the global system prompt, Agents → the agent
     files, Connections → the mcp_servers.json. On the right the same
     monospace editor for all three — one truth, no extra fields.

     "Connections" was called "MCP servers" until the tools got their own
     menu entry. The acronym said nothing to anyone reading it, and the
     section stopped being about tools the moment picking and switching
     moved out: what is left here is setting a server up and signing in.

     Appearance lives here too — three choices to get into the same menu
     made no sense. The former small
     appearance window is dissolved; the Settings menu in the bar is now
     a direct button onto this window. Every section carries its own
     section icon in the house style.

     A broken file still gets saved — it is the user's file — but the
     window says so immediately, in the red line under the field. For the
     tools, valid saving means applying at the same time: the servers
     restart in the background, the live readout under the field fetches
     the result live from GET /tools.

     Secrets: the editor shows only ${…} placeholders, the status light
     next to it says set/missing. Values never reach the interface — it
     has no login (A6 decision, rationale in the blueprint). */
  import { fade } from 'svelte/transition'
  import Fenster from './Fenster.svelte'
  import WachsendesFeld from './WachsendesFeld.svelte'
  import Agentenmarke from './Agentenmarke.svelte'
  import Bereichszeichen from './Bereichszeichen.svelte'
  import Skillmaske from './Skillmaske.svelte'
  import Standpille from './Standpille.svelte'
  import Verbindungen from './Verbindungen.svelte'
  import Schalter from './Schalter.svelte'
  import { api } from '../lib/api.js'
  import { zustand, aktuellerChat, chatAendern, konturSetzen, melde, frage, modelleLaden } from '../lib/zustand.svelte.js'
  import {
    t, gemerkteSprachwahl, spracheWaehlen, spracheZuruecksetzen,
  } from '../lib/texte.svelte.js'

  let { offen = $bindable(false), modus = $bindable('auto') } = $props()

  /* 'tools' has been the tile gallery since the gallery rebuild;
     the raw text field of mcp_servers.json is now called
     'tools_datei' and is reachable via the gallery's footer — the path
     for advanced users. */
  let art = $state('system') // 'darstellung' | 'system' | 'memory' | 'agent' | 'tools' | 'tools_datei' | 'konfiguration' | 'zugangsdaten'
  let agentName = $state('')
  let dateien = $state([]) // [{ name, kaputt }] — the broken ones too
  let text = $state('')
  let geladen = $state('')
  let kaputt = $state(null)
  let platzhalter = $state([]) // [{ name, gesetzt }] — tools only
  let lese = $state(null) // GET /tools — the tools' live readout
  let feld = $state(null)
  let laedt = $state(false)

  const chat = $derived(aktuellerChat())
  const ausgesetzt = $derived(Boolean(chat?.prompt_aus))
  const istDarstellung = $derived(art === 'darstellung')
  const istSystem = $derived(art === 'system')
  const istGedaechtnis = $derived(art === 'memory')
  const istSkills = $derived(art === 'skills')
  const istGalerie = $derived(art === 'tools')
  const istTools = $derived(art === 'tools_datei')
  const istAgent = $derived(art === 'agent')
  /* The beta lock used to sit on the window itself — since appearance
     lives here, the window always has to open. Only the entries that
     touch files are still locked; the effective half remains
     app/beta.py. */
  const gesperrt = $derived(Boolean(zustand.features?.beta_lock))

  /* The appearance rows (previously a small window of their own,
     now dissolved): three entrances to one destination were
     one too many. */
  const MODI = [
    ['auto', 'einstellungen.auto'],
    ['hell', 'einstellungen.hell'],
    ['dunkel', 'einstellungen.dunkel'],
  ]

  /* The two switches that decide whether the memory travels: on this
     machine, and off it. Read when the section opens, written straight
     through — the cascade is the same one the parameters use. */
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

  let sprachwahl = $state(gemerkteSprachwahl())

  async function spracheStellen(wert) {
    sprachwahl = wert
    try {
      if (wert === 'auto') await spracheZuruecksetzen()
      else await spracheWaehlen(wert)
      // The model list carries translated parameter labels — after a
      // language switch it has to be fetched again, not just re-rendered.
      await modelleLaden()
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }
  // config.yaml and .env. Editing keys in the window is deliberate:
  // the program runs locally, there is no login to
  // protect and no network exposure. Whoever sees the screen sits in
  // front of it.
  const istDatei = $derived(art === 'konfiguration' || art === 'zugangsdaten')

  /* The template for a new agent: filled in instead
     of empty, so nobody has to guess what belongs in the front matter.
     `model` deliberately stays empty — which model computes is chosen
     when starting the job, not when creating the agent.

     **The prompt is English and does not go through the catalog**:
     a prompt is content, not interface. It must not
     flip just because someone changes the display language — otherwise
     an agent's behavior would hang on the language switch. English,
     because that is the primary language and models hit tool calls more
     reliably in it. */
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

  /* Find a free name: exe-agent, then exe-agent-2, exe-agent-3 … That
     way a name dispute never arises, and the name stays editable as long
     as the file hasn't been saved yet. */
  function freierName() {
    const belegt = new Set(dateien.map((d) => d.name))
    if (!belegt.has(STANDARDNAME)) return STANDARDNAME
    let zaehler = 2
    while (belegt.has(`${STANDARDNAME}-${zaehler}`)) zaehler += 1
    return `${STANDARDNAME}-${zaehler}`
  }

  $effect(() => {
    if (!offen) return
    dateienLaden()
    /* Where the window opens: the Settings button and ⌘, start at
       appearance, "agent:<name>" jumps to exactly that agent — that's
       how the sidebar's Scheduled group gets here.
       Under the beta lock, only appearance remains. */
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

  async function laden(neueArt, name = '') {
    /* Appearance and gallery have no file behind them — nothing to
       fetch, nothing to discard. text and geladen stay the same so the
       discard dialog stays silent when switching away. */
    if (neueArt === 'darstellung' || neueArt === 'tools' || neueArt === 'skills') {
      art = neueArt
      agentName = ''
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

  /* No browser prompt for the name: the new agent
     gets a name and the finished template right away, both editable
     directly here in the window. Only "Sichern" creates the file. */
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
        // Empty is a legitimate result here and deserves its own word:
        // it means the program has forgotten everything about you.
        melde(daten.text ? t('gedaechtnis.gesichert') : t('gedaechtnis.geleert'), 'erfolg')
      } else if (istDatei) {
        const daten = await api.dateiSichern(art, text)
        geladen = daten.inhalt
        kaputt = daten.kaputt
        // Neither file takes effect while running - config.yaml is read at
        // startup, .env when the tool servers start. Saying so beats a
        // cheerful "saved" that hides it.
        melde(t(kaputt ? 'dateien.gesichert_kaputt' : 'dateien.gesichert'),
              kaputt ? 'hinweis' : 'erfolg')
      } else if (istTools) {
        const daten = await api.werkzeugKonfigurationSichern(text)
        geladen = daten.content
        kaputt = daten.kaputt
        platzhalter = daten.platzhalter
        melde(
          kaputt ? t('werkzeuge.gesichert_kaputt') : t('werkzeuge.gesichert'),
          kaputt ? 'hinweis' : 'erfolg',
        )
        /* The window stays open (A6 decision 6): below the field it
           should become visible whether the change took hold. The
           servers restart in the background — check once early, once
           after the cold start. */
        if (!kaputt) {
          setTimeout(leseanzeigeLaden, 1500)
          setTimeout(leseanzeigeLaden, 5000)
        }
      } else {
        // The name comes from a free-form field — check before writing,
        // otherwise the server is the first to reject it.
        if (!/^[A-Za-z0-9_-]{1,100}$/.test(agentName)) {
          melde(t('fehler.agent_name_ungueltig'), 'fehler')
          return
        }
        const daten = await api.agentSichern(agentName, text)
        geladen = daten.content
        kaputt = daten.kaputt
        await dateienLaden()
        melde(t('agenten.gesichert', { name: agentName }), kaputt ? 'hinweis' : 'erfolg')
        // With a broken front matter the window stays open — the red
        // line under the field says what needs fixing.
        if (!kaputt) offen = false
      }
    } catch {
      melde(t(meldeschluessel('nicht_gesichert')), 'fehler')
    }
  }

  async function agentLoeschen() {
    if (!(await frage(t('agenten.loeschen_frage', { name: agentName })))) return
    try {
      // A file that was never saved exists only in the window.
      if (geladen !== null) await api.agentLoeschen(agentName)
      melde(t('agenten.geloescht', { name: agentName }), 'erfolg')
      await dateienLaden()
      laden('system')
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
</script>

<Fenster bind:offen titel={t('editor.titel')} art="liste">
  <div class="rumpf">
    <!-- The sources: vertical and grouped (A6). Broken files carry their
         warning dot, the way to a new agent stands in its group. -->
    <nav class="spalte" aria-label={t('editor.titel')}>
      <div class="gruppe">{t('editor.gruppe_app')}</div>
      <button
        class="eintrag"
        aria-current={istDarstellung}
        onclick={() => wechseln('darstellung')}
      >
        <Bereichszeichen zeichen="tropfen" />
        {t('editor.quelle_darstellung')}
      </button>

      <div class="gruppe">{t('editor.gruppe_prompts')}</div>
      <button
        class="eintrag"
        class:gesperrt
        disabled={gesperrt}
        aria-current={istSystem}
        onclick={() => wechseln('system')}
      >
        <Bereichszeichen zeichen="seite" />
        {t('agenten.quelle_system')}
        {#if gesperrt}<span class="beta">{t('beta.marke')}</span>{/if}
      </button>

      <!-- The memory sits beside the prompt because that is what it is:
           prompt material, read fresh on every request and folded into the
           same system message. Only this one is written by the machine. -->
      <button
        class="eintrag"
        class:gesperrt
        disabled={gesperrt}
        aria-current={istGedaechtnis}
        onclick={() => wechseln('memory')}
      >
        <Bereichszeichen zeichen="seite" />
        {t('gedaechtnis.quelle')}
        {#if gesperrt}<span class="beta">{t('beta.marke')}</span>{/if}
      </button>

      <!-- Skills belong here for the same reason: they shape behaviour. Not
           locked in beta — nothing here edits a file, it only switches which
           of the instructions may be reached for without being named. -->
      <button class="eintrag" aria-current={istSkills} onclick={() => wechseln('skills')}>
        <Bereichszeichen zeichen="seite" />
        {t('skills.quelle')}
      </button>

      <div class="gruppe">{t('editor.gruppe_agents')}</div>
      {#each dateien as datei (datei.name)}
        <button
          class="eintrag"
          class:gesperrt
          disabled={gesperrt}
          aria-current={istAgent && agentName === datei.name}
          onclick={() => wechseln('agent', datei.name)}
        >
          <!-- The mark before every agent: the system prompt has none,
               which separates the kinds at a glance. -->
          <Agentenmarke groesse={14} />
          <span class="eintragname">{datei.name}</span>
          {#if datei.kaputt}<span class="warnpunkt" title={datei.kaputt}></span>{/if}
        </button>
      {/each}
      {#if istAgent && geladen === null}
        <!-- Not yet saved: the name stands as a field in the list and can
             be overwritten before the file comes into being. -->
        <input
          class="eintrag namensfeld"
          bind:value={agentName}
          aria-label={t('agenten.neu_name')}
          spellcheck="false"
          autocapitalize="off"
        />
      {/if}
      <button class="eintrag neu" class:gesperrt disabled={gesperrt} onclick={neuerAgent}>{t('agenten.neu')}</button>

      <div class="gruppe">{t('editor.gruppe_tools')}</div>
      <button
        class="eintrag"
        class:gesperrt
        disabled={gesperrt}
        aria-current={istGalerie || istTools}
        onclick={() => wechseln('tools')}
      >
        <Bereichszeichen zeichen="stecker" />
        {t('editor.quelle_tools')}
        {#if gesperrt}<span class="beta">{t('beta.marke')}</span>{/if}
      </button>

      <!-- Settings that would otherwise mean opening a file in a folder. -->
      <div class="gruppe">{t('editor.gruppe_dateien')}</div>
      <button
        class="eintrag"
        class:gesperrt
        disabled={gesperrt}
        aria-current={art === 'konfiguration'}
        onclick={() => wechseln('konfiguration')}
      >
        <Bereichszeichen zeichen="drehknopf" />
        {t('editor.quelle_konfiguration')}
      </button>
      <button
        class="eintrag"
        class:gesperrt
        disabled={gesperrt}
        aria-current={art === 'zugangsdaten'}
        onclick={() => wechseln('zugangsdaten')}
      >
        <Bereichszeichen zeichen="schluessel" />
        {t('editor.quelle_zugangsdaten')}
      </button>
    </nav>

    <div class="inhalt">
      {#if istDarstellung}
        <!-- The same formal language as the gallery:
             every setting is a tile, no list rule anymore. -->
        <div class="kachelliste">
          <div class="einstellkachel">
            <div class="zeilentext">
              {t('einstellungen.erscheinungsbild')}
              <span class="hinweis">{t('einstellungen.auto_hinweis')}</span>
            </div>
            <div class="segment">
              {#each MODI as [wert, beschriftung] (wert)}
                <button aria-pressed={modus === wert} onclick={() => (modus = wert)}>
                  {t(beschriftung)}
                </button>
              {/each}
            </div>
          </div>

          <div class="einstellkachel">
            <div class="zeilentext">
              {t('einstellungen.sprache')}
              <span class="hinweis">{t('einstellungen.sprache_hinweis')}</span>
            </div>
            <select
              class="auswahl"
              aria-label={t('einstellungen.sprache')}
              value={sprachwahl}
              onchange={(e) => spracheStellen(e.currentTarget.value)}
            >
              <option value="auto">{t('einstellungen.sprache_auto')}</option>
              <option value="en">{t('einstellungen.sprache_englisch')}</option>
              <option value="de">{t('einstellungen.sprache_deutsch')}</option>
            </select>
          </div>

          <div class="einstellkachel">
            <div class="zeilentext">
              {t('einstellungen.kontur')}
              <span class="hinweis">{t('einstellungen.kontur_hinweis')}</span>
            </div>
            <!-- Black, not red: this is a preference, not an
                 intervention. Red stays reserved for suspending the
                 system prompt. -->
            <Schalter
              an={zustand.kontur}
              beschriftung={t('einstellungen.kontur')}
              onschalten={(an) => konturSetzen(an)}
            />
          </div>
        </div>
      {:else if istSkills}
        <Skillmaske />
      {:else if istGalerie}
        <Verbindungen
          zuDatei={() => wechseln('tools_datei')}
          zuZugangsdaten={() => wechseln('zugangsdaten')}
          zuWerkzeugen={() => {
            offen = false
            zustand.werkzeugeOffen = true
          }}
        />
      {:else}
      <WachsendesFeld
        bind:this={feld}
        bind:wert={text}
        gesperrt={laedt}
        gedimmt={istSystem && ausgesetzt}
        platzhalter={istSystem || istAgent ? t('systemprompt.platzhalter') : ''}
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
        <!-- The status lights (A6): per ${…} placeholder, set or missing.
             It never shows values — the .env remains a file on the
             server. -->
        <div class="ampeln">
          {#each platzhalter as eintrag (eintrag.name)}
            <span class="ampel" class:fehlt={!eintrag.gesetzt}>
              <span class="lampe"></span>
              {eintrag.name} — {t(eintrag.gesetzt ? 'werkzeuge.platzhalter_gesetzt' : 'werkzeuge.platzhalter_fehlt')}
            </span>
          {/each}
        </div>
      {/if}

      {#if istTools}
        <!-- The live readout (A6): what the running service actually
             offers. After saving it refreshes itself — the proof that the
             change took hold stands right under the editor. -->
        <div class="lese">
          <div class="lesetitel">{t('werkzeuge.live')}</div>
          {#if !lese}
            <span class="leseleer">{t('werkzeuge.keine')}</span>
          {:else if !lese.aktiv}
            <span class="leseleer">{t('werkzeuge.abgeschaltet')}</span>
          {:else}
            {#each lese.server as server (server)}
              <span class="server"><span class="lampe an"></span>{server}</span>
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
        <!-- Two switches and nothing finer. A memory in a system prompt is
             sent with EVERY request: on this machine that costs nothing, to
             a provider it means a personal profile living on a foreign
             server permanently. Hence off out there by default. -->
        <div class="schalterzeile">
          <div class="beschriftung">
            {t('gedaechtnis.an_lokal')}
            <span class="hinweis">{t('gedaechtnis.an_lokal_hinweis')}</span>
          </div>
          <Schalter
            an={gedaechtnisSchalter.lokal}
            beschriftung={t('gedaechtnis.an_lokal')}
            onschalten={(an) => gedaechtnisSchalten('lokal', an)}
          />
        </div>
        <div class="schalterzeile">
          <div class="beschriftung">
            {t('gedaechtnis.an_cloud')}
            <span class="hinweis">{t('gedaechtnis.an_cloud_hinweis')}</span>
          </div>
          <Schalter
            an={gedaechtnisSchalter.cloud}
            beschriftung={t('gedaechtnis.an_cloud')}
            onschalten={(an) => gedaechtnisSchalten('cloud', an)}
          />
        </div>
      {/if}

      {#if istSystem}
        <div class="schalterzeile">
          <div class="beschriftung">{t('systemprompt.aussetzen')}</div>
          <Schalter
            an={ausgesetzt}
            art="eingriff"
            beschriftung={t('systemprompt.aussetzen')}
            onschalten={(an) => aussetzen(an)}
          />
        </div>
      {/if}

      <div class="fuss">
        {#if istSystem || istGedaechtnis}
          <button class="textknopf" onclick={() => { text = ''; feld?.fokus() }}>{t('app.leeren')}</button>
        {:else if istAgent}
          <button class="textknopf gefahr" onclick={agentLoeschen}>{t('agenten.loeschen')}</button>
        {:else}
          <span></span>
        {/if}
        <div class="rechts">
          {#if istDarstellung || istGalerie || istSkills}
            <!-- Appearance and gallery take effect immediately — nothing to save. -->
            <button class="knopf" onclick={() => { offen = false }}>{t('app.fertig')}</button>
          {:else}
            <button class="knopf" onclick={() => { offen = false }}>{t('app.abbrechen')}</button>
            <button class="knopf wichtig" onclick={sichern}>{t('app.sichern')}</button>
          {/if}
        </div>
      </div>
    </div>
  </div>
</Fenster>

<style>
  /* Fills the window body instead of standing in it: this window was the
     one that grew with its content, 279 px taller than the three next to
     it. The body's height now comes from the window kind (Fenster.svelte),
     and both columns scroll inside it. */
  .rumpf {
    display: flex;
    gap: 0;
    margin: -4px 0 0;
    align-items: flex-start;
    flex: 1;
    min-height: 0;
  }
  .spalte {
    width: 180px;
    flex: none;
    /* The divider runs through: the list stretches
       to the full body height. The rule itself is a pseudo-element with
       the SAME inset top and bottom — flush with the edge it
       previously overshot. */
    align-self: stretch;
    position: relative;
    padding: 2px 10px 2px 0;
    margin-right: 14px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .spalte::after {
    content: '';
    position: absolute;
    right: 0;
    /* Calibrated to exactly 23 px distance from BOTH window edges.
       Measured
       in the running window: above the list lie 43 px (window padding +
       title), below it 15 px window padding — hence negative at the
       top. Whoever tweaks the window padding or title has to re-measure
       here. */
    top: -20px;
    bottom: 8px;
    width: 1px;
    background: var(--linie);
  }
  .gruppe {
    font-size: 10.5px;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-still);
    padding: 10px 10px 4px;
  }
  .eintrag {
    display: flex;
    align-items: center;
    gap: 7px;
    width: 100%;
    text-align: left;
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 13px;
    padding: 6px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .eintrag:hover {
    background: var(--linie);
  }
  .eintrag[aria-current='true'] {
    background: var(--linie-stark);
    color: var(--text);
    font-weight: 600;
  }
  .eintragname {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }
  .eintrag.neu {
    color: var(--text-still);
  }
  /* The name of a not-yet-saved agent: looks like a list entry but is a
     field. */
  .namensfeld {
    background: var(--blase);
    color: var(--text);
    font-weight: 600;
    outline: none;
    border: 1px dashed var(--linie-stark);
  }
  .namensfeld:focus {
    border-color: var(--text-still);
    border-style: solid;
  }
  .warnpunkt {
    width: 7px;
    height: 7px;
    border-radius: 99px;
    background: var(--rot);
    flex: none;
  }
  .inhalt {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    /* Same as the list beside it: the row is anchored at the top, so a
       child has to say for itself that it wants the full height. Without
       this, `flex: 1` only widens it — the main axis here is horizontal. */
    align-self: stretch;
    /* Fixed height instead of content-driven:
       otherwise every tab with different extra blocks (status lights,
       live readout, suspend switch) makes the window a different
       height. The text field below (volleHoehe) fills what's left.

       The number itself no longer stands here. It belongs to the kind of
       window, not to this one file — that is how this window ended up
       being the only one of the four with its own measurement. */
    flex: 1;
    min-height: 0;
  }

  .warnung {
    margin-top: 10px;
    border: 1px solid var(--rot);
    border-radius: 10px;
    color: var(--rot);
    font-size: 12.5px;
    line-height: 1.5;
    padding: 8px 12px;
  }

  /* The status lights: small and terse — green set, red missing. */
  .ampeln {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 16px;
    margin-top: 10px;
  }
  .ampel {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-leise);
  }
  .lampe {
    width: 7px;
    height: 7px;
    border-radius: 99px;
    background: var(--gruen);
    flex: none;
  }
  .ampel.fehlt .lampe {
    background: var(--rot);
  }
  .ampel.fehlt {
    color: var(--rot);
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
  .lampe.an {
    background: var(--gruen);
  }
  /* A row of names, not of states — the pill carries no colour here. The
     gap belongs to the row; where a pill sits is never the pill's business. */
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

  /* Above the line the global, below it what's only for this chat. */
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
  /* The switch itself lives in teile/Schalter.svelte — one build for the
     whole house, so the next one is not drawn again with other numbers. */

  /* The appearance settings speak the same formal language as the
     gallery: one tile per setting — same frame,
     same radius, same inner measure. */
  .kachelliste {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 2px;
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
  .auswahl {
    flex: none;
    font: inherit;
    font-size: 12.5px;
    color: var(--text);
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 5px 8px;
    cursor: pointer;
  }

  /* Locked entries under the beta lock: visible, but not in charge. */
  .eintrag.gesperrt {
    opacity: 0.42;
    cursor: default;
  }
  .beta {
    margin-left: auto;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-still);
  }

  .fuss {
    display: flex;
    align-items: center;
    justify-content: space-between;
    /* auto instead of a fixed distance: in the appearance section there
       is no growing field pushing the row down. */
    margin-top: auto;
    padding-top: 14px;
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
  .knopf:hover {
    background: var(--linie);
  }
  .knopf:active {
    transform: scale(0.975);
  }
  .wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .wichtig:hover {
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

  /* On the phone, the list sits above the editor, horizontally
     scrollable — the narrow column would only be in the way at 375
     pixels. */
  @media (max-width: 720px) {
    .rumpf {
      flex-direction: column;
    }
    .spalte {
      width: 100%;
      flex-direction: row;
      align-items: center;
      overflow-x: auto;
      border-right: none;
      border-bottom: 1px solid var(--linie);
      padding: 0 0 8px;
      margin: 0 0 10px;
      /* The system scrollbar painted a white bar across the dark
         window. The list stays swipeable — the bar is display only, and
         that contributes nothing here. */
      scrollbar-width: none;
    }
    .spalte::-webkit-scrollbar {
      display: none;
    }
    /* In the narrow layout, the bottom edge separates, not the rule on
       the right. */
    .spalte::after {
      display: none;
    }
    .gruppe {
      padding: 0 6px;
      flex: none;
    }
    .eintrag {
      width: auto;
      flex: none;
    }
  }
</style>
