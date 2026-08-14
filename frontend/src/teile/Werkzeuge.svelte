<script>
  /* The tools: everything the model can call, in one place.

     Same rule as the local and cloud windows: left the list, right whatever
     is selected. What appears on the right depends only on WHAT was clicked
     — a source brings its catalogue, a tool brings what it does.

     The built-in tool is the first source. It belongs in this list even
     though no server delivers it: from where the model stands there is no
     difference, and a list that leaves out the one tool that always works
     would be lying by omission.

     Picking and switching are two different things here, on purpose — see
     lib/werkzeuge.svelte.js. */
  import Fenster from './Fenster.svelte'
  import Standpille from './Standpille.svelte'
  import Schalter from './Schalter.svelte'
  import Ankreuzliste from './Ankreuzliste.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import Werkzeugzeichen from './Werkzeugzeichen.svelte'
  import { LOGOS } from '../lib/logos.js'
  import { rollfade } from '../lib/rollfade.js'
  import { t } from '../lib/texte.svelte.js'
  import { melde } from '../lib/zustand.svelte.js'
  import {
    werkzeugwahl, werkzeugeLaden, quellen, anzahlAn, EINGEBAUTE_NAMEN,
    istAn, schalten, istGewaehlt, katalogSchalten, katalogAlle,
  } from '../lib/werkzeuge.svelte.js'

  let { offen = $bindable(false), zuVerbindungen } = $props()

  /* What the right half shows: either a source or one of its tools. */
  let gezeigt = $state(null)

  const listen = $derived(quellen())
  const gewaehlteQuelle = $derived(
    listen.find((q) => q.id === gezeigt) ?? (gezeigt ? null : listen[0] ?? null),
  )
  const gewaehltesWerkzeug = $derived(
    gezeigt ? listen.flatMap((q) => q.werkzeuge).find((w) => w.name === gezeigt) ?? null : null,
  )
  const quelleDesWerkzeugs = $derived(
    gewaehltesWerkzeug ? listen.find((q) => q.id === gewaehltesWerkzeug.quelle) ?? null : null,
  )
  const aktiv = $derived(anzahlAn())

  function quellenName(quelle) {
    if (!quelle.eingebaut) return quelle.name
    const schluessel = EINGEBAUTE_NAMEN[quelle.id]
    return schluessel ? t(schluessel) : quelle.id
  }

  /* Why a source is quiet — the same distinction the gallery makes: switched
     off by hand is not the same as unreachable. */
  function stand(quelle) {
    if (quelle.laeuft) return null
    return quelle.enabled === false ? 'ausgeschaltet' : 'nicht_verbunden'
  }

  async function katalogKippen(eintrag, gewaehlt) {
    try {
      await katalogSchalten(gewaehlteQuelle.eintrag, eintrag.name, gewaehlt)
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  async function katalogGanz(alle) {
    try {
      await katalogAlle(gewaehlteQuelle.eintrag, alle)
    } catch {
      melde(t('fehler.allgemein'), 'fehler')
    }
  }

  $effect(() => {
    if (!offen) return
    if (!werkzeugwahl.geladen) werkzeugeLaden()
  })

  // Which source boxes are unfolded — every box starts folded, so the list
  // reads as sources first and commands on demand.
  let aufgeklappt = $state({})
</script>

<Fenster bind:offen titel={t('werkzeuge.titel')} art="liste">
  <div class="zaehler">
    {t('werkzeuge.aktiv_zahl')
      .replace('{zahl}', aktiv)
      .replace('{quellen}', listen.filter((q) => q.laeuft).length)}
  </div>

  <div class="zwei">
    <div class="links" use:rollfade>
      {#each listen as quelle (quelle.id)}
        <!-- A source and its tools in one raised box, like a settings group:
             the source carries the sign, name and its dotted status; each
             tool below it a name and a switch. -->
        <div class="qbox">
          <div
            class="qkopf"
            class:gewaehlt={quelle.id === gewaehlteQuelle?.id && !gewaehltesWerkzeug}
          >
          <button
            class="qeintrag"
            onclick={() => (gezeigt = quelle.id)}
          >
            <span class="qzeichen">
              {#if LOGOS[quelle.id]}
                <svg viewBox={LOGOS[quelle.id].vb} width="18" height="18">{@html LOGOS[quelle.id].html}</svg>
              {:else}
                <Werkzeugzeichen server={quelle.id} />
              {/if}
            </span>
            <div class="qmitte">
              <div class="qname">{quellenName(quelle)}</div>
              <div class="qsatz">
                {#if stand(quelle)}
                  {t(`werkzeuge.${stand(quelle)}`)}
                {:else}
                  {t('werkzeuge.von_zahl')
                    .replace('{an}', quelle.werkzeuge.filter((w) => istAn(w.name)).length)
                    .replace('{gesamt}', quelle.eingebaut
                      ? quelle.werkzeuge.length
                      : quelle.katalog.length)}
                {/if}
              </div>
            </div>
            <Leuchtpunkt
              farbe={quelle.laeuft ? 'gruen' : stand(quelle) === 'ausgeschaltet' ? 'gelb' : 'still'}
              groesse={7}
            />
          </button>
            {#if quelle.laeuft && quelle.werkzeuge.length}
              <button
                class="qklapp"
                class:auf={aufgeklappt[quelle.id]}
                onclick={() => (aufgeklappt[quelle.id] = !aufgeklappt[quelle.id])}
                aria-expanded={Boolean(aufgeklappt[quelle.id])}
                aria-label={aufgeklappt[quelle.id] ? t('werkzeuge.zuklappen') : t('werkzeuge.aufklappen')}
                title={aufgeklappt[quelle.id] ? t('werkzeuge.zuklappen') : t('werkzeuge.aufklappen')}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6" /></svg>
              </button>
            {/if}
          </div>

          {#if quelle.laeuft && aufgeklappt[quelle.id]}
            {#each quelle.werkzeuge as werkzeug (werkzeug.name)}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div
                class="weintrag"
                class:gewaehlt={werkzeug.name === gewaehltesWerkzeug?.name}
                class:aus={!istAn(werkzeug.name)}
                role="button"
                tabindex="0"
                onclick={() => (gezeigt = werkzeug.name)}
                onkeydown={(e) => { if (e.key === 'Enter') gezeigt = werkzeug.name }}
              >
                <span class="wname">{werkzeug.name}</span>
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <span onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
                  <Schalter
                    an={istAn(werkzeug.name)}
                    beschriftung={werkzeug.name}
                    onschalten={(an) => schalten(werkzeug.name, an)}
                  />
                </span>
              </div>
            {/each}
          {/if}
        </div>
      {:else}
        <p class="leer">{t('werkzeuge.keine_quelle')}</p>
      {/each}
    </div>

    <div class="rechts" use:rollfade>
      {#if gewaehltesWerkzeug}
        <div class="kopfkarte">
          <div class="min">
            <div class="gross">{gewaehltesWerkzeug.name}</div>
            <div class="unter">
              {quelleDesWerkzeugs ? quellenName(quelleDesWerkzeugs) : ''}
            </div>
          </div>
          <Standpille farbe={istAn(gewaehltesWerkzeug.name) ? 'blau' : 'still'}>
            {t(istAn(gewaehltesWerkzeug.name) ? 'werkzeuge.an' : 'werkzeuge.aus')}
          </Standpille>
        </div>

        {#if gewaehltesWerkzeug.beschreibung}
          <h4>{t('werkzeuge.was_es_tut')}</h4>
          <p class="fliess">{gewaehltesWerkzeug.beschreibung}</p>
        {/if}

        <h4>{t('werkzeuge.verhalten')}</h4>
        <!-- A statement, not a control. Whether a tool asks first stands in
             the server entry; a switch here would promise something this
             window cannot keep. Brightness only — this is a fact about the
             tool, not a state of it. -->
        <div class="regel">
          <div class="regeltext">
            {t('werkzeuge.fragt_vorher')}
            <span class="regelhinweis">
              {gewaehltesWerkzeug.needs_confirmation
                ? t('werkzeuge.fragt_vorher_hinweis')
                : t('werkzeuge.fragt_nicht_hinweis')}
            </span>
          </div>
          <span class="wert">
            {t(gewaehltesWerkzeug.needs_confirmation ? 'app.ja' : 'app.nein')}
          </span>
        </div>
      {:else if gewaehlteQuelle}
        <div class="kopfkarte">
          <div class="min">
            <div class="gross schrift">{quellenName(gewaehlteQuelle)}</div>
            <!-- A server REPORTS its tools; the built-in one does not report
                 anything, it simply is one. Counting it would also read
                 "1 Werkzeuge" — a plural over a single thing. -->
            <div class="unter">
              {gewaehlteQuelle.eingebaut
                ? t('werkzeuge.eingebaut_unter')
                : t('werkzeuge.gemeldet_zahl').replace('{zahl}', gewaehlteQuelle.katalog.length)}
            </div>
          </div>
          <Standpille farbe={gewaehlteQuelle.laeuft ? 'gruen' : 'still'}>
            {gewaehlteQuelle.laeuft
              ? t('status.erreichbar')
              : t(`werkzeuge.${stand(gewaehlteQuelle)}`)}
          </Standpille>
        </div>

        <!-- Only where there is something to pick. The built-in tool has no
             catalogue, and a search field over an empty list would promise a
             choice that does not exist. -->
        {#if gewaehlteQuelle.katalog.length}
          <h4>{t('liste.katalog')}</h4>
          <Ankreuzliste
            eintraege={gewaehlteQuelle.katalog}
            istAn={(e) => istGewaehlt(gewaehlteQuelle.eintrag, e.name)}
            onschalten={katalogKippen}
            onalle={katalogGanz}
          />
        {:else if gewaehlteQuelle.eingebaut}
          <p class="fliess">{t('werkzeuge.eingebaut_hinweis')}</p>
        {/if}

        {#if !gewaehlteQuelle.eingebaut}
          <button class="knopfleise" onclick={zuVerbindungen}>
            {t('werkzeuge.verbindung_einrichten')}
          </button>
        {/if}
      {:else}
        <p class="leer">{t('werkzeuge.keine_quelle')}</p>
      {/if}
    </div>
  </div>
</Fenster>

<style>
  .zaehler { font-size: 11.5px; color: var(--text-still); margin: -6px 0 10px; }
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

  /* Each source is a raised box; its tools sit inside it, divided by a line
     — the same shape the settings groups wear. */
  .qbox {
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg-erhoben);
    overflow: hidden;
    margin-top: 8px;
  }
  .qbox:first-child { margin-top: 0; }
  .qeintrag {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    text-align: left;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    padding: 9px 11px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .qzeichen {
    width: 28px;
    height: 28px;
    flex: none;
    border-radius: 8px;
    border: 1px solid var(--linie);
    display: grid;
    place-items: center;
    color: var(--text-leise);
  }
  .qzeichen :global(svg) { width: 18px; height: 18px; }
  .qmitte { flex: 1; min-width: 0; }
  .qname {
    font-size: 12.5px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .qsatz {
    font-size: 11px;
    color: var(--text-still);
    margin-top: 1px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .weintrag {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 11px 7px 14px;
    border-top: 1px solid var(--linie);
    cursor: pointer;
    transition: background 0.12s;
  }
  .weintrag:hover, .weintrag.gewaehlt { background: var(--linie); }
  .wname {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    font-family: var(--schrift-fest);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .weintrag.aus .wname { opacity: 0.42; }

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
  /* A source carries a name, not an identifier — the fixed-width face is for
     what the model types. */
  .gross.schrift { font-family: inherit; }
  .unter { font-size: 11.5px; color: var(--text-still); margin-top: 2px; }

  h4 {
    margin: 14px 0 6px;
    font-size: 10.5px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 600;
  }
  .fliess { font-size: 12.5px; color: var(--text-leise); margin: 10px 0 0; }

  .regel {
    display: flex;
    align-items: center;
    gap: 12px;
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 10px 12px;
  }
  .regeltext { flex: 1; min-width: 0; font-size: 12.5px; }
  .regelhinweis { display: block; font-size: 11px; color: var(--text-still); margin-top: 1px; }
  .wert { flex: none; font-size: 12.5px; color: var(--text-leise); }

  .knopfleise {
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12px;
    padding: 5px 11px;
    margin-top: 12px;
    cursor: pointer;
  }
  .knopfleise:hover { color: var(--text); border-color: var(--text-still); }

  .leer { color: var(--text-still); font-size: 13px; padding: 6px 4px; }

  @media (max-width: 720px) {
    .zwei { flex-direction: column; flex: none; }
    .links { width: 100%; border-right: none; border-bottom: 1px solid var(--linie); }
  }
  /* The fold control sits beside the source entry, never inside it — a
     button in a button is not a thing, and the entry keeps its whole face
     for choosing the source. */
  /* The highlight belongs to the whole head, not to the entry alone —
     otherwise the fold control keeps the raised colour and shows up as a
     darker rectangle beside the chosen source. */
  .qkopf {
    display: flex;
    align-items: stretch;
    transition: background 0.12s;
  }
  .qkopf:hover, .qkopf.gewaehlt { background: var(--linie); }
  .qkopf :global(.qeintrag) {
    flex: 1;
    min-width: 0;
  }
  .qklapp {
    flex: none;
    border: none;
    background: none;
    color: var(--text-still);
    padding: 0 12px 0 4px;
    cursor: pointer;
    display: grid;
    place-items: center;
  }
  .qklapp:hover {
    color: var(--text);
  }
  .qklapp svg {
    transition: transform 0.15s;
  }
  .qklapp.auf svg {
    transform: rotate(180deg);
  }
</style>
