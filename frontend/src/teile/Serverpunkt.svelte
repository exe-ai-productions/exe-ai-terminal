<!-- The model server at a glance: a filled dot and one word, right of the
     spacer in the header. Green while the server runs, grey while it does
     not — "off" is a fact about the machine, not a failure, and the colour
     table reserves red for something having gone wrong. Polled gently: the
     header lives the whole session, and this readout does not need to race. -->
<script>
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'

  let laeuft = $state(false)

  $effect(() => {
    const holen = () =>
      api.runnerAuskunft()
        .then((a) => (laeuft = Boolean(a.laeuft)))
        .catch(() => {})
    holen()
    const takt = setInterval(holen, 5000)
    return () => clearInterval(takt)
  })
</script>

<span class="gruppe">
  <Leuchtpunkt farbe={laeuft ? 'gruen' : 'still'} groesse={9} />
  <span class="wort">{laeuft ? t('kopf.bereit') : t('kopf.server_aus')}</span>
</span>

<style>
  .gruppe {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
  }
  .wort {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
</style>
