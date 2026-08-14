<script>
  import { rollfade } from '../lib/rollfade.js'
  /* Cloud providers: key, catalogue, parameters.

     One rule holds this window and the local one together: left the list,
     right whatever is selected. What appears on the right depends only on
     WHAT was clicked, not on which window you are in — a provider brings its
     key and its catalogue, a model brings its parameters.

     A provider with a catalogue starts EMPTY. OpenAI reports 124 models,
     most of them for speech, images or embeddings; a preselection would be a
     list nobody ordered. */
  import Fenster from './Fenster.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import Standpille from './Standpille.svelte'
  import Schalter from './Schalter.svelte'
  import Parametertafel from './Parametertafel.svelte'
  import Ankreuzliste from './Ankreuzliste.svelte'
  import Anbietermaske from './Anbietermaske.svelte'
  import { t } from '../lib/texte.svelte.js'
  import {
    modellwahl, auswahlLaden, istAn, schalten, anbieter,
    istGewaehlt, katalogVon, katalogSchalten, katalogAlle,
  } from '../lib/modelle.svelte.js'

  let { offen = $bindable(false) } = $props()

  /* What the right half shows: either a provider or one of its models. */
  let gezeigt = $state(null)

  /* Not a provider id and never colliding with one — an id is a name
     from the configuration, this is a word of ours. */
  const HINZU = 'hinzufuegen'

  const haeuser = $derived(anbieter())
  const gewaehltesHaus = $derived(
    haeuser.find((h) => h.id === gezeigt) ?? (gezeigt ? null : haeuser[0] ?? null),
  )
  const gewaehltesModell = $derived(
    gezeigt ? haeuser.flatMap((h) => h.modelle).find((m) => m.id === gezeigt) ?? null : null,
  )
  const anzahlGewaehlt = $derived(haeuser.reduce((summe, h) => summe + h.modelle.length, 0))
  const katalog = $derived(gewaehltesHaus ? katalogVon(gewaehltesHaus.id) : [])

  $effect(() => {
    if (!offen) return
    if (!modellwahl.geladen) auswahlLaden()
  })
</script>

<Fenster bind:offen titel={t('modell.cloud_titel')} art="liste">
  <div class="zaehler">{t('liste.gewaehlt_zahl').replace('{zahl}', anzahlGewaehlt)}</div>

  <div class="zwei">
    <div class="links">
      {#each haeuser as haus (haus.id)}
        <div
          class="anbieter"
          class:gewaehlt={haus.id === gewaehltesHaus?.id && !gewaehltesModell}
          role="button"
          tabindex="0"
          onclick={() => (gezeigt = haus.id)}
          onkeydown={(e) => { if (e.key === 'Enter') gezeigt = haus.id }}
        >
          <!-- Grey and not the empty dot: a provider that does not answer is
               a fact about this row, so it keeps the same disc size as one
               that does. The empty dot is a size smaller, and two sizes down
               one list read as two kinds of thing. -->
          <span class="punkt"><Leuchtpunkt farbe={haus.erreichbar ? 'gruen' : 'still'} groesse={7} /></span>
          <div class="wer">
            <div class="aname">{haus.name}</div>
            <div class="atut" class:fehlt={haus.schluessel_env && !haus.schluessel_gesetzt}>
              {#if haus.schluessel_env && !haus.schluessel_gesetzt}
                {t('modell.schluessel_fehlt')}
              {:else}
                {t('modell.von_zahl')
                  .replace('{gewaehlt}', haus.modelle.length)
                  .replace('{gesamt}', haus.katalog)}
              {/if}
            </div>
          </div>
        </div>

        {#each haus.modelle as m (m.id)}
          <div
            class="zeile"
            class:gewaehlt={m.id === gewaehltesModell?.id}
            class:aus={!istAn(m.id)}
            role="button"
            tabindex="0"
            onclick={() => (gezeigt = m.id)}
            onkeydown={(e) => { if (e.key === 'Enter') gezeigt = m.id }}
          >
            <div class="wer"><div class="mname">{m.name}</div></div>
            <Schalter
              an={istAn(m.id)}
              beschriftung={m.name}
              onschalten={(an) => schalten(m.id, an)}
            />
          </div>
        {/each}
      {:else}
        <p class="leer">{t('modell.kein_anbieter_kurz')}</p>
      {/each}

      {#if haeuser.length}
        <!-- Same place as "Get a model" in the local window, so the way in
             has to be learnt only once. -->
        <div
          class="zeile dazu"
          class:gewaehlt={gezeigt === HINZU}
          role="button"
          tabindex="0"
          onclick={() => (gezeigt = HINZU)}
          onkeydown={(e) => { if (e.key === 'Enter') gezeigt = HINZU }}
        >
          <span class="plus" aria-hidden="true">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2.5" stroke-linecap="round"><path d="M12 5 V19 M5 12 H19" /></svg>
          </span>
          <div class="wer"><div class="mname">{t('modell.anbieter_hinzufuegen')}</div></div>
        </div>
      {/if}
    </div>

    <div class="rechts" use:rollfade>
      {#if gewaehltesModell}
        <div class="kopfkarte">
          <div class="min">
            <div class="gross">{gewaehltesModell.name}</div>
            <div class="unter">{gewaehltesModell.anbieter_name || gewaehltesModell.anbieter}</div>
          </div>
          <Standpille farbe={gewaehltesModell.erreichbar ? 'gruen' : 'still'}>
            {gewaehltesModell.erreichbar
              ? t('status.erreichbar')
              : t('status.nicht_erreichbar')}
          </Standpille>
        </div>
        <Parametertafel modell={gewaehltesModell} />
      {:else if gewaehltesHaus}
        <div class="kopfkarte">
          <div class="min">
            <div class="gross">{gewaehltesHaus.name}</div>
            <div class="unter">
              {t('modell.gemeldet_zahl').replace('{zahl}', gewaehltesHaus.katalog)}
            </div>
          </div>
          <Standpille farbe={gewaehltesHaus.erreichbar ? 'gruen' : 'still'}>
            {gewaehltesHaus.erreichbar ? t('status.erreichbar') : t('status.nicht_erreichbar')}
          </Standpille>
        </div>

        {#if gewaehltesHaus.schluessel_env}
          <h4>{t('modell.schluessel')}</h4>
          <!-- The name of the variable, never the key itself: the interface
               has no login, so no secret is ever shown here. Red, like in the
               connections gallery: a missing key does not resolve by waiting,
               somebody has to put it in the .env. -->
          <div class="schluessel" class:fehlt={!gewaehltesHaus.schluessel_gesetzt}>
            <span class="ampel"><Leuchtpunkt farbe={gewaehltesHaus.schluessel_gesetzt ? 'gruen' : 'rot'} groesse={7} /></span>
            <code>{gewaehltesHaus.schluessel_env}</code>
            <span class="stand">
              {gewaehltesHaus.schluessel_gesetzt
                ? t('modell.schluessel_gesetzt')
                : t('modell.schluessel_fehlt')}
            </span>
          </div>
        {/if}

        <!-- Only where there is something to pick. A provider that reports a
             single model has no catalogue, and an empty list with a search
             field over it would promise a choice that does not exist. -->
        {#if katalog.length}
          <h4>{t('liste.katalog')}</h4>
          <Ankreuzliste
            eintraege={katalog}
            istAn={istGewaehlt}
            istFest={(m) => m.angeheftet}
            onschalten={katalogSchalten}
            onalle={(alle) => katalogAlle(gewaehltesHaus.id, alle)}
          />
        {/if}
      {:else if gezeigt === HINZU || !haeuser.length}
        {#if gezeigt === HINZU}
          <Anbietermaske fertig={() => (gezeigt = null)} />
        {:else}
          <!-- The empty half offers the way instead of repeating the notice
               that already stands on the left. A dashed edge says the same
               as the empty memory steps: nothing here yet, but something can
               go here. -->
          <button class="kachel" onclick={() => (gezeigt = HINZU)}>
            <span class="kreuz">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2.2" stroke-linecap="round"><path d="M12 5 V19 M5 12 H19" /></svg>
            </span>
            <b>{t('modell.anbieter_hinzufuegen')}</b>
            <span>{t('modell.anbieter_erklaerung')}</span>
          </button>
        {/if}
      {/if}
    </div>
  </div>
</Fenster>

<style>
  .zaehler { font-size: 11.5px; color: var(--text-still); margin: -6px 0 10px; }
  .zeile.dazu {
    margin-top: 6px; padding-top: 11px;
    border-top: 1px solid var(--linie); color: var(--text-leise);
  }
  .plus { display: inline-flex; flex: none; color: var(--text-still); }

  /* The tile fills the empty half without making the window any taller —
     the window sizes are settled and one that grows for a single purpose is
     how four different windows begin. */
  .kachel {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 11px;
    /* The half it fills is a plain block, so the tile takes its edges from
       explicit sizes — a flex share would only measure its own content. */
    width: 100%; height: 100%;
    border: 1px dashed var(--linie-stark); border-radius: 14px;
    background: none; color: var(--text-leise); font: inherit;
    padding: 24px 20px; cursor: pointer;
    transition: border-color 0.12s, color 0.12s, background 0.12s;
  }
  .kachel:hover { border-color: var(--text); color: var(--text); background: var(--blase); }
  .kachel b { font-size: 14px; font-weight: 600; }
  .kachel > span:last-child {
    font-size: 12.5px; color: var(--text-still); text-align: center;
    max-width: 34ch; line-height: 1.5;
  }
  .kreuz {
    width: 34px; height: 34px; border-radius: 99px;
    border: 1px solid currentColor; display: grid; place-items: center;
  }
  /* The height belongs to the window kind and lives in Fenster.svelte — it
     stood in three files at once, and that is exactly how the settings
     window drifted 279 px away from the other three. Here the two halves
     only fill what the body gives them and scroll inside; the bars are
     invisible everywhere in the house anyway. */
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

  .anbieter {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 9px;
    margin-top: 6px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .anbieter:first-child { margin-top: 0; }
  .anbieter:hover, .anbieter.gewaehlt { background: var(--linie); }
  .aname { font-size: 12.5px; font-weight: 600; }
  .atut { font-size: 11px; color: var(--text-still); margin-top: 1px; }
  /* Red, not yellow: a missing key is not something that resolves by
     waiting — somebody has to put it in the .env. The connections gallery
     said red for the same fact while this window said yellow; two colours
     for one state is worse than either of them. */
  .atut.fehlt { color: var(--rot); }

  .zeile {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 9px 7px 26px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .zeile:hover, .zeile.gewaehlt { background: var(--linie); }
  .wer { flex: 1; min-width: 0; }
  .mname {
    font-size: 13.5px;
    font-family: var(--schrift-fest);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .zeile.aus .mname { opacity: 0.42; }

  .punkt { flex: none; display: inline-flex; align-items: center; }

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
  .unter { font-size: 12.5px; color: var(--text-leise); margin-top: 2px; }

  h4 {
    margin: 14px 0 6px;
    font-size: 11.5px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-leise);
    font-weight: 600;
  }

  .schluessel {
    display: flex;
    align-items: center;
    gap: 9px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    padding: 7px 11px;
    font-size: 12.5px;
  }
  .schluessel code { font-family: var(--schrift-fest); font-size: 12px; color: var(--text-leise); }
  .ampel { flex: none; display: inline-flex; align-items: center; }
  .stand { margin-left: auto; font-size: 11px; color: var(--gruen); }
  .schluessel.fehlt .stand { color: var(--rot); }

  .leer { color: var(--text-still); font-size: 13px; padding: 6px 4px; }

  @media (max-width: 720px) {
    .zwei { flex-direction: column; flex: none; }
    .links { width: 100%; border-right: none; border-bottom: 1px solid var(--linie); }
  }
</style>
