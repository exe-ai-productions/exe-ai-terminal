<script>
  /* The model picker in the input bar.

     Just a shell around `StilleWahl`: the dropdown, its
     alignment and its look live there **once**. Before, the same
     machinery sat twice in the house — here and in the job dialog — and
     would have had to be maintained twice.

     What this shell contributes is the hookup to the global state:
     `modellWaehlen` writes the choice into the state and remembers it in
     device storage.

     The list is the server's answer, unchanged: `zustand.modelle` goes in
     raw. Nothing is hard-coded here and nothing gets renamed — what the
     model query doesn't provide isn't displayed. */
  import StilleWahl from './StilleWahl.svelte'
  import { zustand, modellWaehlen } from '../lib/zustand.svelte.js'
  import { sichtbare, modellwahl, auswahlLaden } from '../lib/modelle.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  /* `kopf`: the spot top right in the header — more
     room for the name, menu right-aligned to the button.

     `leiste`: the status block at the foot of the sidebar. It used to be
     framed there, to pair up with the collapse toggle beside it; that toggle
     is gone and the frame with it. The picker now carries the context bar
     directly underneath and needs no outline of its own — a box inside a box
     is one line too many. A long name truncates instead of pushing the
     numbers away. */
  let { klein = false, kopf = false, leiste = false } = $props()

  /* Only what the user wants to see. Switching a model off in the model
     window takes it out of here — that is the whole point of the switch.

     Filtered even before the selection has arrived: unfiltered means every
     model of every catalogue, and one provider alone reports 124. A short
     flash of a list nobody picked is worse than a list that fills in a
     moment later. */
  $effect(() => {
    if (!modellwahl.geladen) auswahlLaden()
  })
  const angeboten = $derived(sichtbare())
</script>

<StilleWahl
  wert={zustand.modellId}
  onwahl={modellWaehlen}
  eintraege={angeboten}
  {klein}
  rechts={kopf}
  maxBreite={kopf ? '340px' : leiste ? '100%' : '33%'}
  leerText={t('fehler.kein_modell_verfuegbar')}
  beschriftung={t('modell.titel')}
/>
