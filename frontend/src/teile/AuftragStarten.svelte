<script>
  /* Start dialog for jobs — the rest of 6.5.

     Built from the house's one window kit: frame from
     `Fenster`, task field from `WachsendesFeld` (grows with the text,
     monospace, no scrollbars — same mechanics as in the system-prompt
     window), selection rows from `StilleWahl`. This component now only
     assembles and starts.

     Pick an agent (only playable ones — broken files don't show up in
     /agents anyway, see 6.3), pick a model (only what is currently
     reachable), type in the task. After starting, the view switches to
     the jobs section and unfolds the new card right away.

     The button to open it sits in the sidebar — where "Neuer Chat" is
     for the chats. That's why the open state lives in the shared state,
     not here. */
  import Fenster from './Fenster.svelte'
  import WachsendesFeld from './WachsendesFeld.svelte'
  import StilleWahl from './StilleWahl.svelte'
  import Agentenmarke from './Agentenmarke.svelte'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { zustand, bereichWechseln, auftraegeLaden, melde } from '../lib/zustand.svelte.js'

  let { offen = $bindable(false) } = $props()

  let agenten = $state([])
  let agentName = $state('')
  let aufgabe = $state('')
  let endpointId = $state('')
  let startet = $state(false)

  const agent = $derived(agenten.find((a) => a.name === agentName) || null)

  /* Only what is currently reachable can compute. A model that is in the
     configuration but doesn't answer doesn't belong in the selection —
     otherwise the job only fails after the click. */
  const verfuegbar = $derived(zustand.modelle.filter((m) => m.erreichbar))
  const keinModell = $derived(verfuegbar.length === 0)

  $effect(() => {
    if (!offen) return
    agentName = ''
    aufgabe = ''
    api
      .agenten()
      .then((daten) => {
        agenten = daten
        if (daten.length) agentName = daten[0].name
      })
      .catch(() => melde(t('agenten.nicht_geladen'), 'fehler'))
  })

  /* Model preselection: what's in the agent, otherwise the one last used
     in the chat, otherwise the first reachable one. Always only from
     what actually answers. */
  $effect(() => {
    if (!offen) return
    const kandidaten = [agent?.model, zustand.modellId, verfuegbar[0]?.id]
    endpointId = kandidaten.find((id) => id && verfuegbar.some((m) => m.id === id)) || ''
  })

  /* From the empty dialog straight into the prompt window: this dialog
     closes, the other opens. Both open states live in the shared state
     precisely so one window can open the other. */
  function agentAnlegen() {
    offen = false
    zustand.promptOffen = true
  }

  async function starten() {
    if (!agentName || !aufgabe.trim() || !endpointId) return
    startet = true
    try {
      const daten = { agent: agentName, task: aufgabe.trim(), endpoint_id: endpointId }
      const auftrag = await api.auftragStarten(daten)
      offen = false
      bereichWechseln('auftraege')
      await auftraegeLaden()
      zustand.auftragAusgewaehlt = auftrag.id
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    } finally {
      startet = false
    }
  }
</script>

{#snippet marke()}
  <Agentenmarke groesse={17} />
{/snippet}

<Fenster bind:offen titel={t('jobs.starten')} art="frage" symbol={marke}>
  {#if keinModell}
    <!-- Without a reachable model, no agent can compute. Saying so here
         is more honest than offering a start button that fails at the
         server afterwards. -->
    <p class="leer">{t('jobs.kein_modell')}</p>
  {:else if !agenten.length}
    <!-- Avoid dead ends: the notice points to the prompt window, so a
         path there leads from here too. -->
    <p class="leer">{t('jobs.keine_agenten')}</p>
    <button class="knopf ganz" onclick={agentAnlegen}>{t('jobs.zum_prompt_fenster')}</button>
  {:else}
    <!-- Quiet rows like the model picker in the input bar: no frame,
         just name and chevron. -->
    <div class="zeile">
      <span class="beschriftung">{t('jobs.agent_waehlen')}</span>
      <StilleWahl
        bind:wert={agentName}
        eintraege={agenten}
        leerText={t('jobs.keine_agenten')}
        beschriftung={t('jobs.agent_waehlen')}
      />
    </div>

    {#if agent?.schedule}
      <!-- The alarm clock (6.7): a quiet row says this agent also runs on
           its own. The pause after three failures wears the yellow of the
           waiting cards — same meaning: you are needed here. -->
      <p class="hinweis-zeile">{t('jobs.wecker_zeile', { zeit: agent.schedule })}</p>
      {#if agent.schedule_paused}
        <p class="wecker-pause">{t('jobs.wecker_pausiert')}</p>
      {/if}
    {/if}

    <div class="zeile">
      <span class="beschriftung">{t('jobs.modell_waehlen')}</span>
      <StilleWahl
        bind:wert={endpointId}
        eintraege={verfuegbar}
        leerText={t('fehler.kein_modell_verfuegbar')}
        beschriftung={t('jobs.modell_waehlen')}
      />
    </div>

    {#if agent?.model}
      <p class="hinweis-zeile">{t('jobs.modell_aus_agent', { modell: agent.model })}</p>
    {/if}

    <WachsendesFeld
      bind:wert={aufgabe}
      platzhalter={t('jobs.aufgabe_platzhalter')}
      beschriftung={t('jobs.aufgabe_platzhalter')}
    />
  {/if}

  <div class="fuss">
    <button class="knopf" onclick={() => (offen = false)}>{t('app.abbrechen')}</button>
    <!-- Without agents or without a reachable model there is nothing to
         start here: then the reason is stated above, and this button
         would just be dead weight. -->
    {#if agenten.length && !keinModell}
      <button
        class="knopf wichtig"
        disabled={!agentName || !endpointId || !aufgabe.trim() || startet}
        onclick={starten}
      >{t('jobs.starten')}</button>
    {/if}
  </div>
</Fenster>

<style>
  .leer {
    color: var(--text-still);
    font-size: 13px;
    margin: 0 0 12px;
  }
  .zeile {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 8px 0;
  }
  .beschriftung {
    font-size: 13px;
  }
  .hinweis-zeile {
    color: var(--text-still);
    font-size: 11.5px;
    margin: -4px 0 8px;
  }
  .wecker-pause {
    color: var(--gelb);
    border: 1px solid var(--gelb);
    background: color-mix(in srgb, var(--gelb) 12%, var(--bg));
    border-radius: 9px;
    font-size: 11.5px;
    padding: 6px 10px;
    margin: 0 0 8px;
  }
  .fuss {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 14px;
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
  .knopf:disabled {
    opacity: 0.5;
    cursor: default;
    transform: none;
  }
  .knopf.ganz {
    width: 100%;
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
</style>
