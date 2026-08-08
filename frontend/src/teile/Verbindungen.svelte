<script>
  /* The tile gallery: the "MCP servers" section shows
     quick connections instead of raw JSON.

     The list is the UNION of the shipped, curated
     catalog (below) and everything in mcp_servers.json — a local stdio server
     thus appears by itself without being in the catalog. The file
     remains the one source of truth; the raw text field behind it is
     reached via the plus tile at the end of "Mehr Server".

     The logos: real trademarks as embedded original vendor
     markups (lib/logos.js) — nothing is
     fetched at runtime. They mark the connection to the respective
     service; the tool row in the chat still shows the house's stroke
     icon. */
  import Bereichszeichen from './Bereichszeichen.svelte'
  import Schriftzug from './Schriftzug.svelte'
  import { api } from '../lib/api.js'
  import { melde, frage } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import { LOGOS } from '../lib/logos.js'
  import { SERVERKATALOG as KATALOG } from '../lib/serverkatalog.js'

  let { zuDatei, zuZugangsdaten, zuWerkzeugen } = $props()

  let eintraege = $state([]) // GET /tools/servers
  let status = $state({}) // server -> { verbunden, laeuft_ab }
  let kennungFuer = $state(null) // tile currently asking for the manual client id
  let kennung = $state('')
  let geheimnis = $state('')
  /* The tile deliberately stays spare in the default
     view: logo, name, switch, status. Everything else —
     disconnect, remove, the tool list — lives behind the chevron on the
     status row. Only "Verbinden" stays outside: the core action of an
     unconnected tile doesn't belong behind an arrow. */
  let offeneDetails = $state({}) // server -> bool (detail section open)
  let beschaeftigt = $state(null) // server currently being worked on
  let abfrage = 0

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

  /* Two groups instead of one wall: "Verbunden" on
     top — ONLY what really runs or is just starting (a switched-off
     SearXNG is not connected, period) — below it "Weitere Server" with
     everything else: catalog offers as well as configured but silent
     entries. Whoever connects moves up automatically. A deliberate side
     effect: each row holds only tiles of the same kind, the sizes stay
     calm. */
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
    // A server that runs here has nothing to sign in to: no address, no key,
    // no session that could be missing. Asking it whether it is "connected"
    // would leave it grey forever.
    const oertlich = katalog && katalog.anmeldung === 'keine'
    const oauthKachel =
      katalog && !oertlich && katalog.anmeldung !== 'schluessel' && !eintrag.api_key_env
    if (oauthKachel && !status[eintrag.name]?.verbunden) return 'getrennt'
    if (eintrag.laeuft) return 'verbunden'
    // Access is there, but the server is not (yet) in the registry: the
    // restart is in progress. That is "Starting …", NOT "Not connected" —
    // exactly this gap wrongly showed red after signing in.
    return 'wartet'
  }

  /* After a change, the registry restart takes a moment — check twice,
     once early, once after the cold start (like the read indicator). */
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
      if (k.anmeldung === 'oauth_kennung' && kennungFuer !== k.name) {
        // The manual path (Google): ask for the client id first, then sign in.
        kennungFuer = k.name
        kennung = ''
        geheimnis = ''
        return
      }
      const daten = { server: k.name }
      if (kennungFuer === k.name && kennung) {
        daten.client_id = kennung
        if (geheimnis) daten.client_secret = geheimnis
      }
      kennungFuer = null
      const { url } = await api.oauthStart(daten)
      window.open(url, '_blank')
      melde(t('verbindungen.browser_hinweis'))
      /* Until the browser comes back: listen until the server REALLY
         lives in the registry — not just until access is there. In
         between lies the registry restart, and stopping earlier exactly
         there meant: the tile stayed on red. */
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
      await laden()
      nachziehen()
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  /* Only for the count on the row that leads to the tools window — picking
     itself happens there (lib/werkzeuge.svelte.js). */
  function angeboten(eintrag, werkzeug) {
    return eintrag.allowed_tools === null || eintrag.allowed_tools.includes(werkzeug)
  }
</script>

<!-- You return from the browser sign-in via a tab or window switch:
     reload once on focus, then the tile is correct without reloading the
     page — even if the sign-in happened in an entirely different
     browser. -->
<svelte:window onfocus={() => laden()} />

{#snippet karte(kachel)}
    {@const name = kachel.katalog?.name || kachel.eintrag.name}
    {@const stand = zustand(kachel)}
    {@const hatDetails = Boolean(kachel.eintrag) && Boolean(
      status[name]?.verbunden
        || !kachel.katalog
        || (kachel.eintrag.laeuft && kachel.eintrag.alle_werkzeuge?.length)
    )}
    <div class="kachel">
      <div class="kopf">
        <span class="logo" aria-hidden="true">
          <!-- The logo also applies for entries without a catalog tile if
               one exists (SearXNG) — otherwise the house's plug. -->
          {#if LOGOS[name]}
            <!-- {@html} over OUR OWN shipped constants from lib/logos.js
                 — no foreign content at runtime. -->
            <svg viewBox={LOGOS[name].vb} width="26" height="26">
              {@html LOGOS[name].html}
            </svg>
          {:else}
            <Bereichszeichen zeichen="stecker" groesse={22} />
          {/if}
        </span>
        <span class="titel">{kachel.katalog?.titel || name}</span>
        {#if kachel.eintrag}
          <button
            class="schalter"
            aria-pressed={kachel.eintrag.enabled}
            aria-label={t('verbindungen.aktiv')}
            onclick={() => kippen(kachel.eintrag)}
          ><i></i></button>
        {/if}
      </div>

      {#if hatDetails}
        <button
          class="stand standknopf"
          data-stand={stand}
          aria-expanded={Boolean(offeneDetails[name])}
          onclick={() => (offeneDetails[name] = !offeneDetails[name])}
        >
          <span class="punkt"></span>
          {t(`verbindungen.stand_${stand}`)}
          {#if stand === 'schluessel_fehlt'}
            <code>{kachel.eintrag.api_key_env}</code>
          {/if}
          <svg class="winkel" class:auf={offeneDetails[name]} width="11" height="11"
               viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
      {:else}
        <!-- No arrow without something behind it: since the tool picking
             moved to its own window, a disconnected catalogue server has no
             details to unfold — an arrow that opens nothing teaches people
             to stop pressing arrows. -->
        <div class="stand" data-stand={stand}>
          <span class="punkt"></span>
          {t(`verbindungen.stand_${stand}`)}
          {#if stand === 'schluessel_fehlt' && kachel.eintrag}
            <code>{kachel.eintrag.api_key_env}</code>
          {/if}
        </div>
      {/if}

      {#if kennungFuer === name}
        <!-- The manual path: Google requires a self-created client id. -->
        <div class="kennungform">
          <input
            bind:value={kennung}
            placeholder={t('verbindungen.kennung')}
            spellcheck="false"
            autocapitalize="off"
          />
          <input
            bind:value={geheimnis}
            placeholder={t('verbindungen.geheimnis')}
            spellcheck="false"
            autocapitalize="off"
          />
          <button class="knopf" disabled={!kennung} onclick={() => verbinden(kachel)}>
            {t('verbindungen.weiter')}
          </button>
        </div>
      {/if}

      {#if (kachel.katalog && (stand === 'frei' || stand === 'getrennt')) || stand === 'schluessel_fehlt'}
        <div class="taten">
          {#if kachel.katalog && (stand === 'frei' || stand === 'getrennt')}
            <!-- One word for one action. "Reconnect" implied a live thing to
                 pick back up; what actually happens is the same sign-in as
                 the first time. -->
            <button
              class="knopf wichtig"
              disabled={beschaeftigt === name}
              onclick={() => verbinden(kachel)}
            >
              {t('verbindungen.verbinden')}
            </button>
          {/if}
          {#if stand === 'schluessel_fehlt'}
            <button class="knopf" onclick={zuZugangsdaten}>
              {t('verbindungen.zugangsdaten')}
            </button>
          {/if}
        </div>
      {/if}

      {#if kachel.eintrag && offeneDetails[name]}
        {#if status[name]?.verbunden || !kachel.katalog}
          <div class="taten">
            {#if status[name]?.verbunden}
              <button class="leise" onclick={() => vergessen(kachel.eintrag)}>
                {t('verbindungen.vergessen')}
              </button>
            {/if}
            {#if !kachel.katalog}
              <button class="leise" onclick={() => entfernen(kachel.eintrag)}>
                {t('verbindungen.entfernen')}
              </button>
            {/if}
          </div>
        {/if}
        <!-- The tool list used to hang here, behind this chevron, and was the
             third job of a window that already had two. It lives in its own
             menu entry now: this gallery connects servers, the tools window
             picks and switches what they deliver. -->
        {#if kachel.eintrag.laeuft && kachel.eintrag.alle_werkzeuge.length}
          {@const frei = kachel.eintrag.alle_werkzeuge.filter((w) => angeboten(kachel.eintrag, w.name)).length}
          <button class="werkzeuglabel" onclick={zuWerkzeugen}>
            {t('verbindungen.werkzeuge')} ({frei}/{kachel.eintrag.alle_werkzeuge.length})
          </button>
        {/if}
      {/if}
    </div>
{/snippet}

<div class="rollbereich">
  {#if verbundene.length}
    <!-- The headings are drawn letterings (house style); the box carries
         the actual word for screen readers. -->
    <div class="bereich" role="heading" aria-level="3"
         aria-label={t('verbindungen.gruppe_verbunden')}>
      <Schriftzug zug="verbunden" />
    </div>
    <div class="galerie">
      {#each verbundene as kachel (kachel.katalog?.name || kachel.eintrag.name)}
        {@render karte(kachel)}
      {/each}
    </div>
  {/if}
  <div class="bereich" role="heading" aria-level="3"
       aria-label={t('verbindungen.gruppe_mehr')}>
    <Schriftzug zug="mehr" />
  </div>
  <div class="galerie">
    {#each weitere as kachel (kachel.katalog?.name || kachel.eintrag.name)}
      {@render karte(kachel)}
    {/each}
    <!-- The plus tile: plus on the left, lettering
         on the right — the ONLY way into the MCP editor since the footer
         is gone. The aria-label carries the word for screen readers. -->
    <button class="kachel plus" onclick={zuDatei}
            aria-label={t('verbindungen.hinzufuegen')}>
      <!-- Tight viewBox (stroke including caps, no dead air): only then
           does flex-center put the VISIBLE middle of the group on the
           tile center — measured 1.75 px of skew with the old 24 box. -->
      <svg width="18" height="18" viewBox="3.4 3.4 17.2 17.2" fill="none"
           stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
           aria-hidden="true">
        <path d="M12 4.5v15M4.5 12h15" />
      </svg>
      <Schriftzug zug="hinzufuegen" hoehe={9.5} />
    </button>
  </div>
</div>

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
  .kachel.plus {
    border-style: dashed;
    border-color: var(--linie-stark);
    background: none;
    color: var(--text-still);
    /* Plus on the left, lettering on the right. */
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: 10px;
    cursor: pointer;
    min-height: 74px;
    transition: color 0.12s, border-color 0.12s;
  }
  .kachel.plus:hover {
    color: var(--text);
    border-color: var(--text-still);
  }
  .bereich + .galerie {
    margin-bottom: 14px;
  }
  .galerie {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
    gap: 10px;
    align-content: start;
  }
  /* No more align-self: start — in the row the tiles stretch to equal
     height; calm in the grid was the explicit wish. */
  .kachel {
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    padding: 12px 13px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .kopf {
    display: flex;
    align-items: center;
    gap: 9px;
  }
  .logo {
    width: 26px;
    height: 26px;
    flex: none;
    display: grid;
    place-items: center;
    color: var(--text);
  }
  .titel {
    flex: 1;
    min-width: 0;
    font-size: 13.5px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .stand {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11.5px;
    color: var(--text-leise);
  }
  .stand code {
    font-size: 10.5px;
  }
  .punkt {
    width: 7px;
    height: 7px;
    border-radius: 99px;
    flex: none;
    background: var(--text-still);
  }
  .stand[data-stand='verbunden'] .punkt { background: var(--gruen); }
  .stand[data-stand='getrennt'] .punkt,
  .stand[data-stand='schluessel_fehlt'] .punkt { background: var(--rot); }
  .stand[data-stand='getrennt'],
  .stand[data-stand='schluessel_fehlt'] { color: var(--rot); }

  .taten {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }
  .knopf {
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 12px;
    padding: 4px 11px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.12s, transform 0.08s;
  }
  .knopf:hover { background: var(--linie); }
  .knopf:active { transform: scale(0.975); }
  .knopf:disabled { opacity: 0.5; cursor: default; }
  .knopf.wichtig {
    background: var(--text);
    color: var(--bg);
    border-color: var(--text);
  }
  .leise {
    border: none;
    background: none;
    color: var(--text-still);
    font: inherit;
    font-size: 11.5px;
    padding: 3px 6px;
    border-radius: 6px;
    cursor: pointer;
  }
  .leise:hover {
    background: var(--linie);
    color: var(--text);
  }

  .kennungform {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .kennungform input {
    font: inherit;
    font-size: 12px;
    color: var(--text);
    background: var(--bg-seite);
    border: 1px solid var(--linie-stark);
    border-radius: 8px;
    padding: 5px 8px;
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
  .schalter[aria-pressed='true'] { background: var(--text); }
  .schalter[aria-pressed='true'] i { transform: translateX(14px); }

  /* On configured tiles, the status row is the expander. */
  .standknopf {
    border: none;
    background: none;
    font: inherit;
    padding: 0;
    text-align: left;
    cursor: pointer;
  }
  .winkel {
    flex: none;
    transition: transform 0.15s;
  }
  .winkel.auf { transform: rotate(180deg); }
  /* A count that is also the way there — brightness alone, no colour: this
     is a fact about the server, not a state of it. */
  .werkzeuglabel {
    font-size: 11.5px;
    color: var(--text-still);
    padding: 2px 0 0;
    border: none;
    background: none;
    font-family: inherit;
    text-align: left;
    cursor: pointer;
  }
  .werkzeuglabel:hover { color: var(--text); }

</style>
