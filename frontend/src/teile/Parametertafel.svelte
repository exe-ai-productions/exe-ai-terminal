<script>
  /* The right half of both model windows: the settings of one model.

     One component, used by the local window and the cloud one. A parameter is
     a parameter no matter where the model computes — two copies would drift
     apart the moment somebody changed a slider in one of them.

     Which knobs appear is decided by the backend, not here: the model brings
     its own list, and it only contains what the dialect really evaluates. */
  import { t } from '../lib/texte.svelte.js'
  import { melde } from '../lib/zustand.svelte.js'
  import {
    einstellungen, parameterLaden, parameterSetzen, parameterZuruecksetzen,
  } from '../lib/einstellungen.svelte.js'

  let { modell } = $props()

  let werte = $state({})
  let geladenesModell = null
  let sicherZeit

  /* What applies when nobody has set anything. Not sent to the server — this
     is only what the slider stands at before the first touch. */
  const VORGABEN = {
    temperature: 0.7, top_p: 0.95, max_tokens: 16384, top_k: 40, min_p: 0.05,
    repeat_penalty: 1, repeat_last_n: 64, presence_penalty: 0, frequency_penalty: 0,
    typical_p: 1, seed: -1,
  }

  $effect(() => {
    const kennung = modell?.id ?? null
    if (!kennung || kennung === geladenesModell) return
    geladenesModell = kennung
    parameterLaden(kennung)
  })

  $effect(() => {
    if (einstellungen.fuerModell !== modell?.id) return
    const frisch = {}
    for (const p of modell?.parameter ?? []) frisch[p.name] = gespeicherterWert(p)
    werte = frisch
  })

  function gespeicherterWert(p) {
    const gesetzt = einstellungen.parameter?.[p.name]
    if (gesetzt !== undefined && gesetzt !== null) return gesetzt
    return VORGABEN[p.name] ?? p.minimum
  }

  function wertVon(p) {
    return werte[p.name] ?? gespeicherterWert(p)
  }

  /* Where a value comes from. Without this the number stands there and nobody
     knows why — the cascade delivers the answer, so it may as well be shown. */
  function herkunftVon(p) {
    const woher = einstellungen.herkunft?.[p.name]
    if (!woher) return t('parameter.aus_vorgabe')
    if (woher.startsWith('modell:')) return t('parameter.aus_modell')
    if (woher.startsWith('chat:')) return t('parameter.aus_chat')
    return t('parameter.aus_global')
  }

  function setzen(p, wert) {
    werte[p.name] = wert
    if (!modell) return
    clearTimeout(sicherZeit)
    sicherZeit = setTimeout(async () => {
      try {
        await parameterSetzen(modell.id, p.name, wert)
      } catch {
        melde(t('parameter.nicht_gesichert'), 'fehler')
      }
    }, 350)
  }

  async function zuruecksetzen() {
    if (!modell) return
    try {
      await parameterZuruecksetzen(modell.id)
      const frisch = {}
      for (const p of modell?.parameter ?? []) frisch[p.name] = VORGABEN[p.name] ?? p.minimum
      werte = frisch
      melde(t('parameter.zurueckgesetzt'), 'erfolg')
    } catch {
      melde(t('parameter.nicht_gesichert'), 'fehler')
    }
  }

  const sichtbar = $derived((modell?.parameter || []).filter((p) => p.gruppe === 'sichtbar'))
  const weitere = $derived((modell?.parameter || []).filter((p) => p.gruppe === 'mehr'))
</script>

{#snippet regler(p)}
  {@const wert = wertVon(p)}
  {@const nachkomma = p.ganzzahl ? 0 : (String(p.schritt).split('.')[1]?.length ?? 0)}
  <div class="regler">
    <label for="pt-{p.name}">
      {p.label}<span class="hinweis">{p.hinweis}</span>
    </label>
    <input
      id="pt-{p.name}"
      type="range"
      min={p.minimum}
      max={p.maximum}
      step={p.schritt}
      value={wert}
      oninput={(e) => setzen(p, Number(e.currentTarget.value))}
    />
    <input
      class="zahl"
      value={Number(wert).toFixed(nachkomma)}
      onchange={(e) => {
        const zahl = Math.min(p.maximum, Math.max(p.minimum, Number(e.currentTarget.value) || 0))
        e.currentTarget.value = zahl.toFixed(nachkomma)
        setzen(p, zahl)
      }}
      aria-label={p.label}
    />
    <span class="woher">{herkunftVon(p)}</span>
  </div>
{/snippet}

<h4>{t('parameter.titel')}</h4>
<p class="reichweite">{t('parameter.gilt_fuer_modell')}</p>

<!-- All of them at once. The show-more button made the window jump in
     height every time you switched between a model and a provider; the panel
     scrolls instead, and the heading keeps the rare ones apart from the
     everyday ones. -->
{#each sichtbar as p (p.name)}
  {@render regler(p)}
{/each}

{#if weitere.length}
  <h4>{t('parameter.selten')}</h4>
  {#each weitere as p (p.name)}
    {@render regler(p)}
  {/each}
{/if}

<div class="fuss">
  <button class="textknopf" onclick={zuruecksetzen}>{t('parameter.zuruecksetzen')}</button>
</div>

<style>
  h4 {
    margin: 14px 0 2px;
    font-size: 10.5px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-still);
    font-weight: 600;
  }
  h4:first-child { margin-top: 4px; }
  .reichweite { margin: -1px 0 6px; font-size: 11.5px; color: var(--text-still); }

  .regler { display: flex; align-items: center; gap: 11px; padding: 8px 2px; }
  label { flex: 1; min-width: 0; font-size: 13px; }
  .hinweis { display: block; font-size: 11px; color: var(--text-still); margin-top: 1px; }
  input[type='range'] {
    -webkit-appearance: none;
    appearance: none;
    width: 104px;
    height: 3px;
    border-radius: 2px;
    background: var(--linie-stark);
    outline: none;
    flex: none;
  }
  input[type='range']::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 15px;
    height: 15px;
    border-radius: 50%;
    background: var(--bg-erhoben);
    border: 1.5px solid var(--text-leise);
    cursor: pointer;
    transition: transform 0.12s ease, border-color 0.12s;
  }
  input[type='range']:active::-webkit-slider-thumb {
    transform: scale(1.18);
    border-color: var(--text);
  }
  .zahl {
    width: 62px;
    flex: none;
    border: 1px solid var(--linie-stark);
    border-radius: 8px;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 12.5px;
    font-family: var(--schrift-fest);
    text-align: right;
    padding: 4px 8px;
    outline: none;
  }
  .zahl:focus { border-color: var(--text-still); }
  /* Says which level a value comes from — the cascade knows, so it shows. */
  .woher {
    width: 54px;
    flex: none;
    text-align: right;
    font-size: 10.5px;
    color: var(--text-still);
  }

  .fuss {
    display: flex;
    justify-content: flex-end;
    margin-top: 12px;
    padding-top: 11px;
    border-top: 1px solid var(--linie);
  }
  .textknopf {
    background: none;
    border: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    cursor: pointer;
    padding: 0;
  }
  .textknopf:hover { color: var(--text); }
</style>
