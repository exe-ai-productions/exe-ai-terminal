<script>
  /* The corner greeting — top left of the empty chat, under the head bar.

     The name wears the user's own message colour (white when none is
     chosen): that colour already means "you" in the chat, so the accent
     comes from the house instead of decorating. The split marker keeps the
     name a separate span however the translation arranges the sentence. */
  import { zustand } from '../lib/zustand.svelte.js'
  import { begruessung, grussSchluessel } from '../lib/begruessung.svelte.js'
  import { t, texte } from '../lib/texte.svelte.js'

  let { sichtbar = false } = $props()

  const MARKE = '\u0000'
  const teile = $derived.by(() => {
    const satz = t(grussSchluessel(), { name: MARKE })
    const [vor, nach] = satz.split(MARKE)
    return { vor, nach: nach ?? '' }
  })
  const datum = $derived(
    new Date().toLocaleDateString(texte.sprache === 'de' ? 'de-DE' : 'en-GB', {
      weekday: 'long', day: 'numeric', month: 'long',
    })
  )
</script>

{#if sichtbar && begruessung.an && begruessung.name}
  <div class="ecke">
    <div class="zeile">{teile.vor}<b style:color={zustand.blasenfarbe || 'var(--text)'}>{begruessung.name}</b>{teile.nach}</div>
    <div class="datum">{datum}</div>
  </div>
{/if}

<style>
  .ecke {
    position: absolute;
    top: 14px;
    left: 20px;
    z-index: 2;
    pointer-events: none;
  }
  .zeile {
    font-size: 14px;
    color: var(--text-leise);
  }
  .zeile b {
    font-weight: 600;
  }
  .datum {
    font-size: 11.5px;
    color: var(--text-still);
    margin-top: 1px;
  }
</style>
