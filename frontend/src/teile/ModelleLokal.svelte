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
  import { t } from '../lib/texte.svelte.js'
  import { zustand } from '../lib/zustand.svelte.js'
  import { modellwahl, auswahlLaden, istAn, schalten, lokale } from '../lib/modelle.svelte.js'

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
  const dialektName = (d) =>
    d === 'openai' ? t('modell.eigener_unter') : ({ llama_cpp: 'llama.cpp', mlx: 'MLX' }[d] ?? d)
</script>

<Fenster bind:offen titel={t('menue.lokal')} art="liste">
  <div class="zaehler">{t('modell.aktiv_zahl').replace('{zahl}', anzahlAn)}</div>

  <div class="zwei">
    <div class="links">
      <div class="haus"><span class="hname">{t('modell.laeuft_gerade')}</span></div>
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
      {:else}
        <p class="leer">{t('modell.kein_lokaler_server')}</p>
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
