<script>
  import { rollfade } from '../lib/rollfade.js'
  /* The MCP server gallery — a connection is an icon, and what to do with it
     opens on a click.

     A tile is deliberately spare: the maker's logo, the name, and a dotted
     status dot. Everything else — the key, the browser sign-in, the switch,
     the tool count, forgetting or removing — lives in a small options menu
     that opens when the tile is clicked, anchored to it. This keeps the
     gallery calm: a wall of icons you scan, not a wall of controls you read.

     The list is the union of the shipped catalog and everything in
     mcp_servers.json; the file stays the one source of truth, reached
     through the plus tile at the end. Logos are our own embedded original
     vendor vectors (lib/logos.js) — nothing is fetched at runtime. */
  import Bereichszeichen from './Bereichszeichen.svelte'
  import Schriftzug from './Schriftzug.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import { api } from '../lib/api.js'
  import { melde, frage } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import { LOGOS } from '../lib/logos.js'
  import { SERVERKATALOG as KATALOG } from '../lib/serverkatalog.js'

  let { zuDatei, zuZugangsdaten, zuWerkzeugen } = $props()

  let eintraege = $state([]) // GET /tools/servers
  let status = $state({}) // server -> { verbunden, laeuft_ab }
  let kennung = $state('')
  let geheimnis = $state('')
  let beschaeftigt = $state(null) // server currently being worked on
  let abfrage = 0

  /* The open options menu: which tile it belongs to, and where to draw it.
     Anchored to the tile in fixed coordinates so no scroll container clips
     it. */
  let menue = $state(null) // { name, top, left, nachOben } | null

  export async function laden() {
    try {
      const [server, oauth] = await Promise.all([
        api.serverUebersicht(),
        api.oauthStatus(),
      ])
      eintraege = server
      status = Object.fromEntries(oauth.map((s) => [s.server, s]))
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  $effect(() => {
    laden()
    return () => clearInterval(abfrage)
  })

  const alle = $derived.by(() => {
    const nachName = Object.fromEntries(eintraege.map((e) => [e.name, e]))
    const katalogNamen = new Set(KATALOG.map((k) => k.name))
    return [
      ...KATALOG.map((k) => ({ katalog: k, eintrag: nachName[k.name] || null })),
      ...eintraege
        .filter((e) => !katalogNamen.has(e.name))
        .map((e) => ({ katalog: null, eintrag: e })),
    ]
  })
  const verbundene = $derived(
    alle.filter((k) => ['verbunden', 'wartet'].includes(zustand(k))),
  )
  const weitere = $derived(
    alle.filter((k) => !['verbunden', 'wartet'].includes(zustand(k))),
  )

  function zustand(kachel) {
    const { katalog, eintrag } = kachel
    if (!eintrag) return 'frei'
    if (eintrag.api_key_env && eintrag.schluessel_gesetzt === false) return 'schluessel_fehlt'
    if (!eintrag.enabled) return 'aus'
    const oertlich = katalog && katalog.anmeldung === 'keine'
    const oauthKachel =
      katalog && !oertlich && katalog.anmeldung !== 'schluessel' && !eintrag.api_key_env
    if (oauthKachel && !status[eintrag.name]?.verbunden) return 'getrennt'
    if (eintrag.laeuft) return 'verbunden'
    return 'wartet'
  }

  const punktFarbe = (stand) =>
    stand === 'verbunden' || stand === 'wartet' ? 'gruen'
    : stand === 'getrennt' || stand === 'schluessel_fehlt' ? 'rot'
    : 'still'

  const nameVon = (k) => k.katalog?.name || k.eintrag.name
  const titelVon = (k) => k.katalog?.titel || nameVon(k)
  const kachelVon = (name) => alle.find((k) => nameVon(k) === name) || null
  const offeneKachel = $derived(menue ? kachelVon(menue.name) : null)

  /* Open the options menu for a tile, placed just under it — or above when
     the bottom of the window is too close. */
  function oeffnen(k, ereignis) {
    const name = nameVon(k)
    if (menue?.name === name) {
      menue = null
      return
    }
    kennung = ''
    geheimnis = ''
    const r = ereignis.currentTarget.getBoundingClientRect()
    const platzUnten = window.innerHeight - r.bottom
    const nachOben = platzUnten < 240
    menue = {
      name,
      top: nachOben ? r.top - 8 : r.bottom + 8,
      left: Math.min(r.left, window.innerWidth - 244),
      nachOben,
    }
  }
  function schliessen() {
    menue = null
  }

  function nachziehen() {
    setTimeout(laden, 1200)
    setTimeout(laden, 5000)
  }

  async function verbinden(kachel) {
    const k = kachel.katalog
    beschaeftigt = k.name
    try {
      const felder = { type: 'http', url: k.url, enabled: true }
      if (k.api_key_env) felder.api_key_env = k.api_key_env
      if (k.vorauswahl) felder.allowed_tools = k.vorauswahl
      await api.serverSchreiben(k.name, felder)
      if (k.anmeldung === 'schluessel') {
        await laden()
        nachziehen()
        return
      }
      if (k.anmeldung === 'oauth_kennung' && !kennung) {
        // The manual path (Google): the client id is asked for in the menu.
        return
      }
      const daten = { server: k.name }
      if (kennung) {
        daten.client_id = kennung
        if (geheimnis) daten.client_secret = geheimnis
      }
      const { url } = await api.oauthStart(daten)
      window.open(url, '_blank')
      melde(t('verbindungen.browser_hinweis'))
      schliessen()
      clearInterval(abfrage)
      let verbleibend = 45
      abfrage = setInterval(async () => {
        await laden()
        const frisch = eintraege.find((e) => e.name === k.name)
        if (frisch?.laeuft || --verbleibend <= 0) clearInterval(abfrage)
      }, 2000)
    } catch (fehler) {
      melde(fehler.message || t('fehler.allgemein'), 'fehler')
    } finally {
      beschaeftigt = null
    }
  }

  async function kippen(eintrag) {
    try {
      await api.serverSchreiben(eintrag.name, { enabled: !eintrag.enabled })
      await laden()
      nachziehen()
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  async function vergessen(eintrag) {
    if (!(await frage(t('verbindungen.vergessen_frage', { name: eintrag.name })))) return
    try {
      await api.oauthVergessen(eintrag.name)
      schliessen()
      await laden()
      nachziehen()
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  async function entfernen(eintrag) {
    if (!(await frage(t('verbindungen.entfernen_frage', { name: eintrag.name })))) return
    try {
      await api.serverEntfernen(eintrag.name)
      schliessen()
      await laden()
      nachziehen()
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  function angeboten(eintrag, werkzeug) {
    return eintrag.allowed_tools === null || eintrag.allowed_tools.includes(werkzeug)
  }
  const werkzeugzahl = (eintrag) =>
    eintrag?.laeuft && eintrag.alle_werkzeuge?.length
      ? `${eintrag.alle_werkzeuge.filter((w) => angeboten(eintrag, w.name)).length}/${eintrag.alle_werkzeuge.length}`
      : null
</script>

<svelte:window
  onfocus={() => laden()}
  onresize={schliessen}
  onkeydown={(e) => { if (e.key === 'Escape') schliessen() }}
/>

{#snippet kachel(k)}
  {@const name = nameVon(k)}
  {@const stand = zustand(k)}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <button
    class="kachel"
    class:offen={menue?.name === name}
    onclick={(e) => { e.stopPropagation(); oeffnen(k, e) }}
    aria-haspopup="menu"
    aria-expanded={menue?.name === name}
  >
    <span class="punktecke"><Leuchtpunkt farbe={punktFarbe(stand)} groesse={7} /></span>
    <span class="logo" aria-hidden="true">
      {#if LOGOS[name]}
        <svg viewBox={LOGOS[name].vb} width="30" height="30">{@html LOGOS[name].html}</svg>
      {:else}
        <Bereichszeichen zeichen="stecker" groesse={26} />
      {/if}
    </span>
    <span class="titel">{titelVon(k)}</span>
  </button>
{/snippet}

<div class="rollbereich" use:rollfade>
  {#if verbundene.length}
    <div class="bereich" role="heading" aria-level="3" aria-label={t('verbindungen.gruppe_verbunden')}>
      <Schriftzug zug="verbunden" />
    </div>
    <div class="galerie">
      {#each verbundene as k (nameVon(k))}{@render kachel(k)}{/each}
    </div>
  {/if}
  <div class="bereich" role="heading" aria-level="3" aria-label={t('verbindungen.gruppe_mehr')}>
    <Schriftzug zug="mehr" />
  </div>
  <div class="galerie">
    {#each weitere as k (nameVon(k))}{@render kachel(k)}{/each}
    <button class="kachel plus" onclick={zuDatei} aria-label={t('verbindungen.hinzufuegen')}>
      <svg width="18" height="18" viewBox="3.4 3.4 17.2 17.2" fill="none" stroke="currentColor"
           stroke-width="2.2" stroke-linecap="round" aria-hidden="true">
        <path d="M12 4.5v15M4.5 12h15" />
      </svg>
      <Schriftzug zug="hinzufuegen" hoehe={9.5} />
    </button>
  </div>
</div>

{#if menue && offeneKachel}
  {@const k = offeneKachel}
  {@const stand = zustand(k)}
  {@const name = menue.name}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="schirm" onclick={schliessen}></div>
  <div class="menue" class:oben={menue.nachOben}
       style="top:{menue.top}px; left:{menue.left}px; {menue.nachOben ? 'transform:translateY(-100%);' : ''}">
    <div class="mkopf">
      <span class="mlogo" aria-hidden="true">
        {#if LOGOS[name]}
          <svg viewBox={LOGOS[name].vb} width="20" height="20">{@html LOGOS[name].html}</svg>
        {:else}<Bereichszeichen zeichen="stecker" groesse={18} />{/if}
      </span>
      <span class="mtitel">{titelVon(k)}</span>
      <span class="mstand" data-stand={stand}>{t(`verbindungen.stand_${stand}`)}</span>
    </div>

    {#if stand === 'frei' || stand === 'getrennt'}
      {#if k.katalog?.anmeldung === 'oauth_kennung'}
        <!-- The manual path: a self-created client id (Google). -->
        <input class="feld" bind:value={kennung} placeholder={t('verbindungen.kennung')}
               spellcheck="false" autocapitalize="off" />
        <input class="feld" bind:value={geheimnis} placeholder={t('verbindungen.geheimnis')}
               spellcheck="false" autocapitalize="off" />
        <button class="knopf wichtig" disabled={!kennung || beschaeftigt === name} onclick={() => verbinden(k)}>
          {t('verbindungen.verbinden')}
        </button>
      {:else}
        <p class="msatz">{t('verbindungen.menue_verbinden_satz')}</p>
        <button class="knopf wichtig" disabled={beschaeftigt === name} onclick={() => verbinden(k)}>
          {t('verbindungen.verbinden')}
        </button>
      {/if}
    {:else if stand === 'schluessel_fehlt'}
      <p class="msatz">{t('verbindungen.menue_schluessel_satz')} <code>{k.eintrag.api_key_env}</code></p>
      <button class="knopf" onclick={() => { schliessen(); zuZugangsdaten() }}>{t('verbindungen.zugangsdaten')}</button>
      <button class="mleise" onclick={() => kippen(k.eintrag)}>{k.eintrag.enabled ? t('verbindungen.aus_schalten') : t('verbindungen.an_schalten')}</button>
    {:else}
      <!-- Connected or configured: switch, tools, and the way out. -->
      <div class="mzeile">
        <span>{t('verbindungen.aktiv')}</span>
        <button class="schalter" aria-pressed={k.eintrag.enabled}
                aria-label={t('verbindungen.aktiv')} onclick={() => kippen(k.eintrag)}><i></i></button>
      </div>
      {#if werkzeugzahl(k.eintrag)}
        <button class="mzeile alsknopf" onclick={() => { schliessen(); zuWerkzeugen() }}>
          <span>{t('verbindungen.werkzeuge')}</span>
          <span class="mwert">{werkzeugzahl(k.eintrag)} ›</span>
        </button>
      {/if}
      {#if status[name]?.verbunden}
        <button class="mleise" onclick={() => vergessen(k.eintrag)}>{t('verbindungen.vergessen')}</button>
      {/if}
      {#if !k.katalog}
        <button class="mleise gefahr" onclick={() => entfernen(k.eintrag)}>{t('verbindungen.entfernen')}</button>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .rollbereich {
    overflow-y: auto;
    flex: 1;
    min-height: 0;
    padding: 2px;
  }
  .bereich {
    color: var(--text-leise);
    padding: 6px 2px 10px;
  }
  .bereich + .galerie {
    margin-bottom: 14px;
  }
  .galerie {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
    gap: 10px;
    align-content: start;
  }

  /* A tile is an icon, a name and a status dot — nothing to read, only to
     click. */
  .kachel {
    position: relative;
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    background: var(--bg-erhoben);
    color: var(--text);
    padding: 16px 10px 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: border-color 0.12s, background 0.12s;
  }
  .kachel:hover,
  .kachel.offen {
    border-color: var(--text-still);
  }
  .kachel.offen {
    background: var(--linie);
  }
  .punktecke {
    position: absolute;
    top: 9px;
    right: 9px;
    display: inline-flex;
  }
  .logo {
    width: 30px;
    height: 30px;
    flex: none;
    display: grid;
    place-items: center;
    color: var(--text);
  }
  .titel {
    max-width: 100%;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .kachel.plus {
    border-style: dashed;
    color: var(--text-still);
    justify-content: center;
    gap: 10px;
    min-height: 92px;
  }
  .kachel.plus:hover {
    color: var(--text);
  }

  /* The click-away shield sits under the menu and over everything else. */
  .schirm {
    position: fixed;
    inset: 0;
    z-index: 80;
  }
  .menue {
    position: fixed;
    z-index: 81;
    width: 236px;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    box-shadow: 0 14px 40px rgba(0, 0, 0, 0.28);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .mkopf {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--linie);
  }
  .mlogo {
    width: 20px;
    height: 20px;
    flex: none;
    display: grid;
    place-items: center;
    color: var(--text);
  }
  .mtitel {
    font-size: 13px;
    font-weight: 600;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mstand {
    font-size: 11px;
    color: var(--text-still);
    flex: none;
  }
  .mstand[data-stand='verbunden'],
  .mstand[data-stand='wartet'] {
    color: var(--gruen);
  }
  .mstand[data-stand='getrennt'],
  .mstand[data-stand='schluessel_fehlt'] {
    color: var(--rot);
  }
  .msatz {
    font-size: 12px;
    color: var(--text-leise);
    line-height: 1.5;
    margin: 0;
  }
  .msatz code {
    font-size: 11px;
  }
  .feld {
    font: inherit;
    font-size: 12.5px;
    color: var(--text);
    background: var(--bg-seite);
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 7px 10px;
  }
  .mzeile {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font-size: 12.5px;
  }
  .mzeile.alsknopf {
    border: none;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    padding: 2px 0;
    cursor: pointer;
    text-align: left;
    width: 100%;
  }
  .mzeile.alsknopf:hover {
    color: var(--text);
  }
  .mwert {
    color: var(--text-still);
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 12.5px;
    padding: 7px 12px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .knopf:hover:not(:disabled) {
    background: var(--linie);
  }
  .knopf:disabled {
    opacity: 0.5;
    cursor: default;
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
  .mleise {
    border: none;
    background: none;
    color: var(--text-still);
    font: inherit;
    font-size: 12px;
    padding: 4px 2px;
    border-radius: 7px;
    cursor: pointer;
    text-align: left;
  }
  .mleise:hover {
    color: var(--text);
  }
  .mleise.gefahr:hover {
    color: var(--rot);
  }
  .schalter {
    position: relative;
    width: 34px;
    height: 20px;
    flex: none;
    border: none;
    padding: 0;
    border-radius: 10px;
    background: var(--linie-stark);
    cursor: pointer;
    transition: background 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .schalter i {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--bg-erhoben);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transition: transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .schalter[aria-pressed='true'] {
    background: var(--text);
  }
  .schalter[aria-pressed='true'] i {
    transform: translateX(14px);
  }
</style>
