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
  import { startAktion } from '../lib/startknopf.svelte.js'

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

  /* What the two new tiles report. The panels behind them fetch for
     themselves and update live — a snapshot taken only at opening left
     the tile saying "not running" while the panel next to it had long
     started the server. So the tiles follow the same rhythm as the
     reachability loop instead of trusting one old glance. */
  const BILDFARBE = { bereit: 'gruen', zeichnet: 'blau', kein_modell: 'still', kein_programm: 'rot' }
  let einbettungStand = $state(null)
  let bildStand = $state(null)
  $effect(() => {
    if (!offen) return
    const holen = () => {
      api.einbettungAuskunft().then((a) => (einbettungStand = a)).catch(() => {})
      api.bildmodelle().then((a) => (bildStand = a)).catch(() => {})
    }
    holen()
    const takt = setInterval(holen, 15_000)
    return () => clearInterval(takt)
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
    <div class="vramzeile">
        {#if maschineGb}
          <span class="vramwort">{t('modell.vram_label')}:</span>
          <span class="vramwert">{maschineGb} GB</span>
        {/if}
        {#if maschineGb && zustand.serverPlan}
          <span class="vramtrenner" aria-hidden="true"></span>
        {/if}
        {#if zustand.serverPlan}
          <span class="vramwort"><span class="mittel" aria-hidden="true">⌀</span>{t('modell.vram_erwartet')}:</span>
          <span class="vramwert">{zustand.serverPlan.gesamt.toFixed(1)} GB</span>
        {/if}
        <!-- Where the server answers, beside what it costs: both are facts
             about the same running thing, and the header had no business
             carrying one of them alone. A dash while nothing runs — the row
             must not jump when a server comes up. -->
        <span class="vramtrenner" aria-hidden="true"></span>
        <span class="vramwort">{t('kopf.port')}:</span>
        <span class="vramwert">{laeuft ? (auskunft?.port ?? '—') : '—'}</span>
      </div>
  </div>

  {#if !reise}
    <div class="zaehler">{t('modell.aktiv_zahl').replace('{zahl}', anzahlAn)}</div>
  {/if}

  <div class="zwei">
    <div class="links" use:rollfade>
      <div class="linksinhalt">
      <h4 class="abschnitt">{t('modell.einrichten')}</h4>
      <div class="kachelzeile">
        <Kachel
          titel={t('modell.server')}
          gewaehlt={gezeigt === SERVER}
          onclick={() => (gezeigt = SERVER)}
          ariaLabel={t('modell.server')}
        >
          {#snippet zeichen()}<Hauszeichen zeichen="server" groesse="gross" />{/snippet}
          {#snippet lampe()}<Leuchtpunkt farbe={laeuft ? 'gruen' : 'still'} groesse={7} />{/snippet}
          {#snippet rechts()}<svg class="pfeil" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7.5 6.75 L12.75 12 L7.5 17.25" /><path d="M13.5 6.75 L18.75 12 L13.5 17.25" /></svg>{/snippet}
        </Kachel>
      </div>
      <div class="kachelzeile">
        <Kachel
          titel={t('einbettungsserver.titel')}
          gewaehlt={gezeigt === EINBETTUNG}
          onclick={() => (gezeigt = EINBETTUNG)}
          ariaLabel={t('einbettungsserver.titel')}
        >
          {#snippet zeichen()}<Hauszeichen zeichen="einbettung" groesse="gross" />{/snippet}
          {#snippet lampe()}<Leuchtpunkt farbe={einbettungStand?.laeuft ? 'gruen' : 'still'} groesse={7} />{/snippet}
          {#snippet rechts()}<svg class="pfeil" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7.5 6.75 L12.75 12 L7.5 17.25" /><path d="M13.5 6.75 L18.75 12 L13.5 17.25" /></svg>{/snippet}
        </Kachel>
      </div>
      <div class="kachelzeile">
        <Kachel
          titel={t('bildserver.titel')}
          gewaehlt={gezeigt === BILD}
          onclick={() => (gezeigt = BILD)}
          ariaLabel={t('bildserver.titel')}
        >
          {#snippet zeichen()}<Hauszeichen zeichen="bild" groesse="gross" />{/snippet}
          {#snippet lampe()}<Leuchtpunkt farbe={BILDFARBE[bildStand?.stand] ?? 'still'} groesse={7} />{/snippet}
          {#snippet rechts()}<svg class="pfeil" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7.5 6.75 L12.75 12 L7.5 17.25" /><path d="M13.5 6.75 L18.75 12 L13.5 17.25" /></svg>{/snippet}
        </Kachel>
      </div>
      <h4 class="abschnitt zweit">{t('modell.laeuft_gerade')}</h4>
      {#if reise}
        <!-- A single dash while nothing is loaded: the heading already says
             what this place is for, and a sentence explaining the absence
             takes more room than the absence is worth. -->
        <p class="leerzeile" aria-label={t(ordnerLeer ? 'modell.kein_modell_satz' : 'modell.nichts_laeuft')}>—</p>
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
      </div>
      <!-- The one start/stop control for whichever server the rail shows,
           lifted out of the panel on the right into the base of the rail —
           full width, its label and light following the shown panel. -->
      {#if startAktion()}
        <button class="startknopf" disabled={startAktion().gesperrt} onclick={startAktion().onTat}>
          <Leuchtpunkt farbe={startAktion().punkt} groesse={8} />
          {startAktion().text}
        </button>
      {/if}
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
    display: inline-flex;
    align-items: baseline;
    gap: 5px;
    font-weight: 600;
    color: var(--text);
  }
  /* The header's own hairline: two readings side by side need the seam that
     says they are two. */
  .vramtrenner {
    flex: none;
    width: 1px;
    height: 9px;
    margin: 0 4px;
    background: var(--linie-stark);
  }
  /* The average sign is the whole difference between the two labels, and at
     the text's size it reads as a smudge — it gets a step of its own. */
  .mittel {
    font-size: 18px;
    line-height: 1;
    font-weight: 400;
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
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  /* The tiles scroll; the start button stays pinned to the foot of the rail. */
  .linksinhalt {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
  .startknopf {
    flex: none;
    margin-top: 10px;
    width: 100%;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font: inherit;
    font-size: 13.5px;
    padding: 11px 14px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--linie-stark);
    color: var(--text);
    cursor: pointer;
  }
  .startknopf:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .startknopf:not(:disabled):hover {
    background: var(--linie);
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
