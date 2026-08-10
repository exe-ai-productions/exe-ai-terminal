<script>
  /* Local models: what is running on this machine, and how it is set.

     Its own window because local is the normal case, not a special one. It
     shares nothing with the cloud window except the parameter panel — there
     is no key here, no catalogue to tick, nothing to download yet.

     Getting a model belongs here too, next to the running ones — as the
     last entry on the left, because it is the answer for a machine where
     the left list is still empty. What it cannot do yet is start one: that
     is the runner, and it does not exist. */
  import Fenster from './Fenster.svelte'
  import Standpille from './Standpille.svelte'
  import Schalter from './Schalter.svelte'
  import Parametertafel from './Parametertafel.svelte'
  import Modellsuche from './Modellsuche.svelte'
  import Modellserver from './Modellserver.svelte'
  import Schriftzug from './Schriftzug.svelte'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'
  import { modellwahl, auswahlLaden, istAn, schalten, lokale } from '../lib/modelle.svelte.js'
  import { stufeFuer } from '../lib/modellempfehlungen.js'

  let { offen = $bindable(false) } = $props()

  /* Which model the right half shows. Clicking left changes only the right
     half — it does NOT change what you are chatting with. Mixing the two
     would mean every glance at a setting silently switched models. */
  let gezeigt = $state(null)

  /* Not a model id and never colliding with one: an id always carries a
     provider or a path. */
  const HOLEN = 'holen'
  const SERVER = 'server'

  const modelle = $derived(lokale())
  const modell = $derived(modelle.find((m) => m.id === gezeigt) ?? modelle[0] ?? null)
  const anzahlAn = $derived(modelle.filter((m) => istAn(m.id)).length)

  $effect(() => {
    if (!offen) return
    if (!modellwahl.geladen) auswahlLaden()
    if (gezeigt === null) gezeigt = zustand.modellId || modelle[0]?.id || null
  })

  function kurz(zahl) {
    if (!zahl) return null
    if (zahl < 1000) return String(zahl)
    const k = zahl / 1000
    return (k >= 100 ? Math.round(k) : Math.round(k * 10) / 10) + 'k'
  }

  /* Engine names are names and stay untranslated; only the paraphrase for
     "anything speaking OpenAI's interface" is a sentence and goes through
     the catalogue. */
  /* The runner's report feeds the head and the journey: machine total,
     whether the server program is there, which files lie in the folder.
     Polled gently while the window is open, so a finished download moves
     the journey along without a reopen. */
  let auskunft = $state(null)
  const maschineGb = $derived(auskunft?.speicher_gb ?? null)
  $effect(() => {
    if (!offen) return
    const holen = () => api.runnerAuskunft().then((a) => (auskunft = a)).catch(() => {})
    holen()
    const takt = setInterval(holen, 3000)
    return () => clearInterval(takt)
  })

  /* The journey shows while nothing local answers: three stations from
     bare machine to running model. Each station reads its state from the
     report — done, up next, or waiting its turn. */
  const reise = $derived(modelle.length === 0)
  const serverDa = $derived(Boolean(auskunft?.programm))
  const dateienDa = $derived((auskunft?.modelle?.length ?? 0) > 0)
  const vorschlag = $derived(maschineGb ? (stufeFuer(maschineGb)?.modelle[0] ?? null) : null)

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
    <div class="links">
      {#if !reise}
        <div class="haus"><span class="hname">{t('modell.laeuft_gerade')}</span></div>
      {/if}
      {#if reise}
        <!-- The same tile a model will sit in: when the server comes up,
             only the lettering changes — the shape stays put. -->
        <div class="zeile stumm">
          <span class="lpunkt"></span>
          <div class="wer"><div class="mname">{t('modell.server_offline')}</div></div>
        </div>
      {/if}
      {#each modelle as m (m.id)}
        <div
          class="zeile"
          class:gewaehlt={m.id === modell?.id}
          class:aus={!istAn(m.id)}
          role="button"
          tabindex="0"
          onclick={() => (gezeigt = m.id)}
          onkeydown={(e) => { if (e.key === 'Enter') gezeigt = m.id }}
        >
          <span class="punkt" class:tot={!m.erreichbar}></span>
          <div class="wer">
            <div class="mname">{m.name}</div>
            <div class="mtut">
              {#if m.context_tokens}{kurz(m.context_tokens)} · {/if}
              {dialektName(m.dialekt)}
            </div>
          </div>
          <Schalter
            an={istAn(m.id)}
            beschriftung={m.name}
            onschalten={(an) => schalten(m.id, an)}
          />
        </div>
      {/each}

      <!-- Last on the left, and reachable even when nothing runs: on a fresh
           machine this is the only entry that leads anywhere. -->
      <div
        class="zeile holen"
        class:gewaehlt={gezeigt === HOLEN}
        role="button"
        tabindex="0"
        onclick={() => (gezeigt = HOLEN)}
        onkeydown={(e) => { if (e.key === 'Enter') gezeigt = HOLEN }}
      >
        <span class="plus" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round"><path d="M12 5 V19 M5 12 H19" /></svg>
        </span>
        <div class="wer"><div class="mname">{t('modell.holen')}</div></div>
      </div>
      <div
        class="zeile holen"
        class:gewaehlt={gezeigt === SERVER}
        role="button"
        tabindex="0"
        onclick={() => (gezeigt = SERVER)}
        onkeydown={(e) => { if (e.key === 'Enter') gezeigt = SERVER }}
      >
        <span class="plus" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6 L15 12 L9 18" /></svg>
        </span>
        <div class="wer"><div class="mname">{t('modell.server')}</div></div>
      </div>
    </div>

    <div class="rechts">
      {#if gezeigt === HOLEN}
        <Modellsuche />
      {:else if gezeigt === SERVER}
        <Modellserver />
      {:else if reise}
        <div class="reise">
          <div class="station" class:fertig={serverDa} class:dran={!serverDa}>
            <div class="nr">{#if serverDa}✓{:else}1{/if}</div>
            <div>
              <h3>{t('modell.server_holen')}</h3>
              <div class="satz">{t('modell.reise_server_satz')}</div>
            </div>
            <div class="tat">
              {#if serverDa}
                <span class="haken">{t('modell.reise_da')}</span>
              {:else}
                <button class="rknopf" onclick={() => (gezeigt = SERVER)}>{t('modell.server_holen')}</button>
              {/if}
            </div>
          </div>

          <div class="station" class:fertig={dateienDa} class:dran={serverDa && !dateienDa} class:wartet={!serverDa}>
            <div class="nr">{#if dateienDa}✓{:else}2{/if}</div>
            <div>
              <h3>{t('modell.holen')}</h3>
              <div class="satz">{t('modell.reise_modell_satz').replace('{gb}', maschineGb ?? '…')}</div>
            </div>
            <div class="tat">
              <button class="rknopf" class:still={!serverDa || dateienDa} onclick={() => (gezeigt = HOLEN)}>{t('modell.reise_stoebern')}</button>
            </div>
            {#if vorschlag && !dateienDa}
              <div class="vorschlag">
                <div>
                  <div class="v-name">{vorschlag.name}</div>
                  <div class="v-warum">{t('modell.' + vorschlag.warum)}</div>
                </div>
                <div class="v-gb">{vorschlag.groesse} GB</div>
              </div>
            {/if}
          </div>

          <div class="station" class:dran={dateienDa} class:wartet={!dateienDa}>
            <div class="nr">3</div>
            <div>
              <h3>{t('modell.reise_start')}</h3>
              <div class="satz">{t('modell.reise_start_satz')}</div>
            </div>
            <div class="tat">
              <button class="rknopf" class:still={!dateienDa} onclick={() => (gezeigt = SERVER)}>{t('modell.server')}</button>
            </div>
          </div>
        </div>
      {:else if modell}
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
      {:else}
        <p class="leer">{t('fehler.kein_modell_verfuegbar')}</p>
      {/if}
    </div>
  </div>
</Fenster>

<style>
  /* The head carries the drawn mark: terminal sign, stroke lettering, and
     the one sentence that says what Local means. The memory readout keeps
     its place on the right shoulder. */
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

  /* The honest lamp: red is the state "no server", the same ringed dot the
     menu bar wears. */
  /* The same ringed dot the menu bar wears — one lamp, one look. */
  .lpunkt {
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 99px;
    background: var(--rot);
    box-shadow: 0 0 0 1.5px var(--text);
    margin: 0 1px;
  }
  /* A statement, not a control: the tile keeps the shape of its future
     tenant and answers no clicks until one moves in. */
  .zeile.stumm {
    cursor: default;
    margin-bottom: 4px;
  }
  .zeile.stumm:hover {
    background: none;
  }

  /* The guided journey: three stations on one thread. Green means done,
     blue means up next, dimness means not your turn yet. */
  .reise {
    padding: 12px 8px 4px;
  }
  .station {
    display: grid;
    grid-template-columns: 36px 1fr auto;
    gap: 0 18px;
    position: relative;
    padding-bottom: 34px;
  }
  .station:last-child {
    padding-bottom: 2px;
  }
  .station::before {
    content: '';
    position: absolute;
    left: 16.5px;
    top: 38px;
    bottom: 4px;
    width: 1px;
    background: var(--linie-stark);
  }
  .station:last-child::before {
    display: none;
  }
  .nr {
    width: 34px;
    height: 34px;
    border-radius: 99px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1.5px solid var(--linie-stark);
    color: var(--text-still);
    font: 600 13px ui-monospace, SFMono-Regular, Menlo, monospace;
    background: var(--bg);
    position: relative;
    z-index: 1;
  }
  .station.fertig .nr {
    border-color: var(--gruen);
    color: var(--gruen);
  }
  .station.dran .nr {
    border-color: var(--blau);
    color: var(--blau);
  }
  .station h3 {
    font-size: 15.5px;
    font-weight: 600;
    margin: 0;
    padding-top: 6px;
  }
  .station.wartet h3,
  .station.wartet .satz {
    color: var(--text-still);
  }
  .satz {
    grid-column: 2;
    color: var(--text-leise);
    font-size: 13.5px;
    line-height: 1.55;
    margin-top: 4px;
    max-width: 460px;
  }
  .tat {
    padding-top: 3px;
  }
  .haken {
    display: inline-flex;
    align-items: center;
    color: var(--gruen);
    font-size: 12.5px;
    font-weight: 600;
    padding-top: 9px;
  }
  .rknopf {
    font: 600 12.5px inherit;
    font-family: inherit;
    color: var(--bg);
    background: var(--text);
    border: none;
    border-radius: 9px;
    padding: 8px 14px;
    cursor: pointer;
  }
  .rknopf.still {
    background: none;
    color: var(--text-leise);
    border: 1px solid var(--linie-stark);
  }
  .vorschlag {
    grid-column: 2;
    margin-top: 10px;
    display: flex;
    align-items: center;
    gap: 12px;
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 11px 14px;
    background: color-mix(in srgb, var(--blau) 7%, var(--bg));
    max-width: 430px;
  }
  .v-name {
    font-size: 13px;
    font-weight: 600;
  }
  .v-warum {
    font-size: 12px;
    color: var(--text-leise);
    margin-top: 1px;
  }
  .v-gb {
    margin-left: auto;
    font: 500 12px ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text-leise);
    white-space: nowrap;
  }

  /* The readout sits on the shoulder of the inner box, right-aligned: a
     loud label outside, the bare number in a stroked pill — the same
     stroke-on-dark look the tool chips in the chat wear. */
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
  .vramzeile .vramwort:first-child {
    margin-left: 0;
  }
  .vramwert {
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 4px 10px;
    font: 500 12.5px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text);
    white-space: nowrap;
  }

  .zaehler { font-size: 11.5px; color: var(--text-still); margin: -6px 0 10px; }
  /* The way out of an empty list. Marked off by a line above rather than a
     colour: it is a different kind of entry, not a different state. */
  .zeile.holen {
    color: var(--text-leise);
  }
  /* One line above the pair, not between them: they belong together — get a
     model, then start it. */
  .zeile.holen:first-of-type,
  .liste > .zeile.holen:nth-last-child(2) {
    margin-top: 6px;
    padding-top: 11px;
    border-top: 1px solid var(--linie);
  }
  .plus { display: inline-flex; flex: none; color: var(--text-still); }
  /* The height comes from the window kind (Fenster.svelte) — it used to
     stand in three files at once, which is how the settings window drifted
     away from the other three. Here the two halves only fill what the body
     gives them and scroll inside; the bars are invisible house-wide. */
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
  .haus { display: flex; align-items: center; gap: 8px; margin: 2px 8px 5px; }
  .hname {
    font-size: 10.5px;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 600;
  }
  .zeile {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 9px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .zeile:hover, .zeile.gewaehlt { background: var(--linie); }
  .wer { flex: 1; min-width: 0; }
  .mname {
    font-size: 12.5px;
    font-weight: 600;
    font-family: var(--schrift-fest);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .mtut {
    font-size: 11px;
    color: var(--text-still);
    margin-top: 1px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  /* Switched off stays visible, only quiet — you should see that it exists. */
  .zeile.aus .mname, .zeile.aus .mtut { opacity: 0.42; }

  /* Green means the server answers. It is a state, so it may carry colour. */
  .punkt { width: 7px; height: 7px; border-radius: 50%; background: var(--gruen); flex: none; }
  .punkt.tot { background: var(--linie-stark); }

  .rechts { flex: 1; padding: 14px 18px; min-width: 0; overflow-y: auto; }
  .kopfkarte {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--linie);
  }
  .min { flex: 1; min-width: 0; }
  .gross {
    font-size: 14px;
    font-weight: 600;
    font-family: var(--schrift-fest);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .unter { font-size: 11.5px; color: var(--text-still); margin-top: 2px; }
  .leer { color: var(--text-still); font-size: 13px; padding: 6px 4px; }

  @media (max-width: 720px) {
    .zwei { flex-direction: column; flex: none; }
    .links { width: 100%; border-right: none; border-bottom: 1px solid var(--linie); }
  }
</style>
