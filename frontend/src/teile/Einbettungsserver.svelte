<script>
  /* The embedding server, switched from here.

     Built as a small sibling of the model server's panel next door, not as
     a second version of it: this server has one setting — which model — and
     a form with a context size, a layer count and a draft model would be
     four fields pretending to matter.

     What it is FOR belongs on the panel, because it is the one thing that
     is not obvious: nothing breaks by leaving it off. Long documents are
     cut up either way; a running server only saves the model load on every
     question. Somebody who does not know that reads a stopped server as a
     broken feature.

     The shape it stands in belongs to `Servertafel.svelte`, shared with
     the other two server panels — this file only says what goes in it. */
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import { katalogOeffnen, melde } from '../lib/zustand.svelte.js'
  import Servertafel from './Servertafel.svelte'
  import Zahlenfeld from './Zahlenfeld.svelte'

  let auskunft = $state(null)
  let gewaehlt = $state('')
  /* The one number this panel has. Deliberately the only one: passages are
     small and fixed, so a context slider here would be knowledge that is not
     knowledge. */
  let port = $state(8081)
  let arbeitet = $state(false)

  async function laden() {
    try {
      auskunft = await api.einbettungAuskunft()
      if (auskunft?.port) port = auskunft.port
      if (!gewaehlt || !auskunft.modelle.includes(gewaehlt)) {
        gewaehlt = auskunft.modell || auskunft.modelle[0] || ''
      }
    } catch {
      auskunft = null
    }
  }
  laden()

  async function schalten() {
    if (arbeitet) return
    arbeitet = true
    try {
      auskunft = auskunft?.laeuft
        ? await api.einbettungStoppen()
        : await api.einbettungStarten(gewaehlt, port)
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    } finally {
      arbeitet = false
    }
  }

  const laeuft = $derived(Boolean(auskunft?.laeuft))
  const bereit = $derived(Boolean(gewaehlt) && Boolean(auskunft?.programm))

  const auswahl = $derived((auskunft?.modelle ?? []).map((name) => ({ wert: name, text: name })))
</script>

<Servertafel
  titel={t('einbettungsserver.titel')}
  unter={laeuft ? t('einbettungsserver.laeuft', { port: auskunft.port }) : t('einbettungsserver.aus')}
  standfarbe={laeuft ? 'gruen' : 'still'}
  standtext={laeuft ? t('status.erreichbar') : t('status.nicht_erreichbar')}
  wofuer={t('einbettungsserver.wofuer')}
  modelle={auswahl}
  bind:gewaehlt
  modellBeschriftung={t('einbettungsserver.modell')}
  modellGesperrt={laeuft}
  leerText={auskunft ? t('einbettungsserver.kein_modell') : ''}
  katalogTat={() => katalogOeffnen('einbettung')}
  speicherort="einbettung"
  tatText={laeuft ? t('einbettungsserver.stoppen') : t('einbettungsserver.starten')}
  tatPunkt={laeuft ? 'gruen' : 'still'}
  tatGesperrt={arbeitet || (!laeuft && !bereit)}
  onTat={schalten}
>
  {#snippet mitte()}
    <div class="feld">
      <span>{t('einbettungsserver.port')}</span>
      <Zahlenfeld bind:wert={port} gesperrt={laeuft} min={1024} max={65535} />
    </div>
  {/snippet}
</Servertafel>

<style>
  .feld {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .feld > span {
    font-size: 12px;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--text-still);
  }
</style>
