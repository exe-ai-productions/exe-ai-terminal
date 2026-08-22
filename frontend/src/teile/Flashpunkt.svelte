<!-- Flash attention at a glance: a filled dot and one word, left of the
     server readout in the header. It is never switched here and never was —
     the server decides by itself whether it can use it, and this line only
     reports what it actually does. Grey while nothing runs (there is nothing
     to report yet), green while it is on, red while a running server does
     without it: that is the one case worth seeing, because it costs speed.

     Its own component beside `Serverpunkt.svelte`, polled on the same gentle
     beat: the header lives the whole session, and neither readout needs to
     race. -->
<script>
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'

  let laeuft = $state(false)
  let aktiv = $state(null)

  /* One mapping decides dot AND word — two separate ternary chains would
     drift apart on exactly the case that matters. */
  const lage = $derived(
    !laeuft || aktiv == null
      ? { punkt: 'still', wort: 'flash_unbekannt' }
      : aktiv
        ? { punkt: 'gruen', wort: 'flash_aktiv' }
        : { punkt: 'rot', wort: 'flash_inaktiv' },
  )

  $effect(() => {
    const holen = () =>
      api.runnerAuskunft()
        .then((a) => {
          laeuft = Boolean(a.laeuft)
          aktiv = a.flash_aktiv ?? null
        })
        .catch(() => {})
    holen()
    const takt = setInterval(holen, 5000)
    return () => clearInterval(takt)
  })
</script>

<span class="gruppe" title={t('modell.feld_flash')}>
  <Leuchtpunkt farbe={lage.punkt} groesse={9} />
  <span class="wort">{t('modell.feld_flash')}</span>
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
