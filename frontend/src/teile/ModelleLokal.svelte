<script>
  import { rollfade } from '../lib/rollfade.js'
  /* Local models: what runs on this machine, and how it is set.

     Its own window because local is the normal case. The left column shows
     what runs now as tiles, then a "Set up" pair — the catalogue, where a
     model comes from, and the model server, where one is started. The right
     column shows the server (its status card and form, or the first-run
     steps), or the parameters of a model clicked on the left.

     Getting a model is no longer a row here: the catalogue is its own
     window, opened by its tile. The red "server offline" tile is gone; an
     empty list is one honest sentence. */
  import Fenster from './Fenster.svelte'
  import Standpille from './Standpille.svelte'
  import Schalter from './Schalter.svelte'
  import Parametertafel from './Parametertafel.svelte'
  import Modellserver from './Modellserver.svelte'
  import Einbettungsserver from './Einbettungsserver.svelte'
  import Bildserver from './Bildserver.svelte'
  import Schriftzug from './Schriftzug.svelte'
  import Kachel from './Kachel.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import Hauszeichen from './Hauszeichen.svelte'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { ausFenster } from '../lib/fensterweg.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'
  import { modellwahl, auswahlLaden, istAn, schalten, lokale } from '../lib/modelle.svelte.js'

  let { offen = $bindable(false) } = $props()

  /* Which the right half shows: the server, or a clicked model's
     parameters. Clicking left never changes what you are chatting with. */
  /* The three kinds of server, each with its own tile, its own folder and
     its own port. One tile for all of them was how an embedding model ended
     up in the language model's picker and its start ran against a port that
     was already taken. */
  const SERVER = 'server'
  const EINBETTUNG = 'einbettung'
  const BILD = 'bild'
  let gezeigt = $state(SERVER)

  /* What the two new tiles report, fetched when the window opens. The
     panels behind them fetch for themselves; the tiles only need the one
     line each that says where things stand. */
  const BILDFARBE = { bereit: 'gruen', zeichnet: 'blau', kein_modell: 'still', kein_programm: 'rot' }
  let einbettungStand = $state(null)
  let bildStand = $state(null)
  $effect(() => {
    if (!offen) return
    api.einbettungAuskunft().then((a) => (einbettungStand = a)).catch(() => {})
    api.bildmodelle().then((a) => (bildStand = a)).catch(() => {})
  })

  const modelle = $derived(lokale())
  const modell = $derived(modelle.find((m) => m.id === gezeigt) ?? null)
  const anzahlAn = $derived(modelle.filter((m) => istAn(m.id)).length)
  const reise = $derived(modelle.length === 0)

  $effect(() => {
    if (!offen) return
    if (!modellwahl.geladen) auswahlLaden()
  })

  function kurz(zahl) {
    if (!zahl) return null
    if (zahl < 1000) return String(zahl)
    const k = zahl / 1000
    return (k >= 100 ? Math.round(k) : Math.round(k * 10) / 10) + 'k'
  }

  /* The runner's report feeds the head and the action tiles: machine total,
     whether the server runs, on which port, with which speed module. */
  let auskunft = $state(null)
  const maschineGb = $derived(auskunft?.speicher_gb ?? null)
  const laeuft = $derived(Boolean(auskunft?.laeuft))
  /* A fresh machine has nothing in the folder; a machine with files but no
     running server is a different, quieter state. The two get different
     words below. */
  const ordnerLeer = $derived((auskunft?.modelle?.length ?? 0) === 0)
  $effect(() => {
    if (!offen) return
    const holen = () => api.runnerAuskunft().then((a) => (auskunft = a)).catch(() => {})
    holen()
    const takt = setInterval(holen, 3000)
    return () => clearInterval(takt)
  })

  const dialektName = (d) =>
    d === 'openai' ? t('modell.eigener_unter') : ({ llama_cpp: 'llama.cpp', mlx: 'MLX' }[d] ?? d)

  /* The running server carries the blue speed-module bolt when a module is
     active — blue is the house colour for running. */
  const mtpAktiv = (m) => m.anbieter === 'runner' && Boolean(auskunft?.drafter)
</script>

<Fenster bind:offen art="liste">
  <div class="markenkopf" role="heading" aria-level="2" aria-label={t('menue.lokal')}>
    <div class="marke">
      <div class="markenzeile">
        <svg viewBox="0 0 100 100" width="42" height="42" fill="none" stroke="currentColor"
             stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="23.5" y="28.5" width="53" height="43" rx="11" />
          <path d="M34.7 42.2 L47.8 50 L34.7 57.8" />
          <path d="M51 57.5 H64.5" />
        </svg>
        <Schriftzug zug="lokale_modelle" hoehe={19} />
      </div>
      <div class="markensatz">{t('modell.lokal_satz')}</div>
    </div>
    {#if maschineGb || zustand.serverPlan}
      <div class="vramzeile">
        {#if maschineGb}
          <span class="vramwort">{t('modell.vram_label')}:</span>
          <span class="vramwert">{maschineGb} GB</span>
        {/if}
        {#if zustand.serverPlan}
          <span class="vramwort">{t('modell.vram_erwartet')}:</span>
          <span class="vramwert">{zustand.serverPlan.gesamt.toFixed(1)} GB</span>
        {/if}
      </div>
    {/if}
  </div>

  {#if !reise}
    <div class="zaehler">{t('modell.aktiv_zahl').replace('{zahl}', anzahlAn)}</div>
  {/if}

  <div class="zwei">
    <div class="links" use:rollfade>
      <h4 class="abschnitt">{t('modell.laeuft_gerade')}</h4>
      {#if reise}
        <p class="leerzeile">{t(ordnerLeer ? 'modell.kein_modell_satz' : 'modell.nichts_laeuft')}</p>
      {:else}
        {#each modelle as m (m.id)}
          <div class="kachelzeile">
            <Kachel
              titel={m.name}
              gewaehlt={m.id === gezeigt}
              onclick={() => (gezeigt = m.id)}
              ariaLabel={m.name}
            >
              {#snippet marke()}
                <Leuchtpunkt farbe={m.erreichbar ? 'gruen' : 'still'} groesse={8} />
              {/snippet}
              {#snippet unter()}
                {#if m.context_tokens}{kurz(m.context_tokens)} · {/if}{dialektName(m.dialekt)}
                {#if mtpAktiv(m)}
                  <span class="mtp" title={t('modell.mtp_aktiv')}><Hauszeichen zeichen="blitz" groesse="klein" /></span>
                {/if}
              {/snippet}
              {#snippet rechts()}
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <span onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
                  <Schalter an={istAn(m.id)} beschriftung={m.name} onschalten={(an) => schalten(m.id, an)} />
                </span>
              {/snippet}
            </Kachel>
          </div>
        {/each}
      {/if}

      <h4 class="abschnitt zweit">{t('modell.einrichten')}</h4>
      <div class="kachelzeile">
        <Kachel
          titel={t('modell.katalog')}
          onclick={() => ausFenster(
            () => { offen = false; zustand.katalogOffen = true },
            () => { zustand.katalogOffen = false; offen = true },
          )}
          ariaLabel={t('modell.katalog')}
        >
          {#snippet zeichen()}<Hauszeichen zeichen="raster" groesse="mittel" />{/snippet}
          {#snippet unter()}
            {ordnerLeer && maschineGb ? t('modell.katalog_unter_erst', { gb: maschineGb }) : t('modell.katalog_unter')}
          {/snippet}
          {#snippet rechts()}<span class="pfeil">→</span>{/snippet}
        </Kachel>
      </div>
      <div class="kachelzeile">
        <Kachel
          titel={t('modell.server')}
          gewaehlt={gezeigt === SERVER}
          onclick={() => (gezeigt = SERVER)}
          ariaLabel={t('modell.server')}
        >
          {#snippet zeichen()}<Hauszeichen zeichen="server" groesse="mittel" />{/snippet}
          {#snippet unter()}
            <Leuchtpunkt farbe={laeuft ? 'gruen' : 'still'} groesse={6} />
            {laeuft ? t('modell.server_unter_an', { port: auskunft.port }) : t('modell.server_unter_aus')}
          {/snippet}
          {#snippet rechts()}<span class="pfeil">→</span>{/snippet}
        </Kachel>
      </div>
      <div class="kachelzeile">
        <Kachel
          titel={t('einbettungsserver.titel')}
          gewaehlt={gezeigt === EINBETTUNG}
          onclick={() => (gezeigt = EINBETTUNG)}
          ariaLabel={t('einbettungsserver.titel')}
        >
          {#snippet zeichen()}<Hauszeichen zeichen="einbettung" groesse="mittel" />{/snippet}
          {#snippet unter()}
            <Leuchtpunkt farbe={einbettungStand?.laeuft ? 'gruen' : 'still'} groesse={6} />
            {einbettungStand?.laeuft
              ? t('einbettungsserver.laeuft', { port: einbettungStand.port })
              : t('einbettungsserver.aus')}
          {/snippet}
          {#snippet rechts()}<span class="pfeil">→</span>{/snippet}
        </Kachel>
      </div>
      <div class="kachelzeile">
        <Kachel
          titel={t('bildserver.titel')}
          gewaehlt={gezeigt === BILD}
          onclick={() => (gezeigt = BILD)}
          ariaLabel={t('bildserver.titel')}
        >
          {#snippet zeichen()}<Hauszeichen zeichen="bild" groesse="mittel" />{/snippet}
          {#snippet unter()}
            <Leuchtpunkt farbe={BILDFARBE[bildStand?.stand] ?? 'still'} groesse={6} />
            {t(`bildserver.stand_${bildStand?.stand ?? 'kein_programm'}`)}
          {/snippet}
          {#snippet rechts()}<span class="pfeil">→</span>{/snippet}
        </Kachel>
      </div>
    </div>

    <div class="rechts" use:rollfade>
      {#if modell}
        <div class="kopfkarte">
          <div class="min">
            <div class="gross">{modell.name}</div>
            <div class="unter">
              {#if modell.context_tokens}{kurz(modell.context_tokens)} {t('modell.kontext')} · {/if}
              {dialektName(modell.dialekt)}
            </div>
          </div>
          <Standpille farbe={modell.erreichbar ? 'gruen' : 'still'}>
            {modell.erreichbar ? t('status.erreichbar') : t('status.nicht_erreichbar')}
          </Standpille>
        </div>
        <Parametertafel {modell} />
      {:else if gezeigt === EINBETTUNG}
        <Einbettungsserver />
      {:else if gezeigt === BILD}
        <Bildserver />
      {:else}
        <Modellserver />
      {/if}
    </div>
  </div>
</Fenster>

<style>
  .markenkopf {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin: 6px 0 10px;
  }
  .markenzeile {
    display: flex;
    align-items: center;
    gap: 15px;
    color: var(--text);
  }
  .markensatz {
    color: var(--text-still);
    font-size: 13.5px;
    margin-top: 9px;
  }
  .vramzeile {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 8px;
    margin: -4px 0 8px;
  }
  .vramwort {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text);
  }
  .vramwort + .vramwert {
    margin-right: 10px;
  }
  .vramwert {
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 4px 10px;
    font: 500 12.5px/1.2 var(--schrift-fest);
    color: var(--text);
    white-space: nowrap;
  }

  .zaehler {
    font-size: 11.5px;
    color: var(--text-still);
    margin: -6px 0 10px;
  }

  .zwei {
    display: flex;
    gap: 0;
    border: 1px solid var(--linie);
    border-radius: 12px;
    overflow: hidden;
    flex: 1;
    min-height: 0;
  }
  .links {
    width: 268px;
    flex: none;
    border-right: 1px solid var(--linie);
    background: var(--bg-seite);
    padding: 10px 8px;
    overflow-y: auto;
  }
  .abschnitt {
    font-size: 10.5px;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 600;
    margin: 2px 4px 8px;
  }
  .abschnitt.zweit {
    margin-top: 16px;
  }
  .kachelzeile {
    margin: 0 2px 7px;
  }
  .leerzeile {
    font-size: 12px;
    color: var(--text-still);
    padding: 4px 6px 8px;
    line-height: 1.5;
  }
  .mtp {
    display: inline-flex;
    color: var(--blau);
  }
  .pfeil {
    color: var(--text-still);
    font-size: 12px;
  }

  .rechts {
    flex: 1;
    padding: 14px 18px;
    min-width: 0;
    overflow-y: auto;
  }
  .kopfkarte {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--linie);
  }
  .min {
    flex: 1;
    min-width: 0;
  }
  .gross {
    font-size: 14px;
    font-weight: 600;
    font-family: var(--schrift-fest);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .unter {
    font-size: 11.5px;
    color: var(--text-still);
    margin-top: 2px;
  }

  @media (max-width: 720px) {
    .zwei {
      flex-direction: column;
      flex: none;
    }
    .links {
      width: 100%;
      border-right: none;
      border-bottom: 1px solid var(--linie);
    }
  }
</style>
