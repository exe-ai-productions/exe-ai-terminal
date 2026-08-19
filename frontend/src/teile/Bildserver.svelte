<script>
  /* The picture generator, as a tile beside the two real servers.

     And deliberately NOT pretending to be one. sd.cpp is not a service that
     stands and answers; it is a program that is called once per picture and
     is gone again. A tile with a start button that claimed a running server
     would be a tile that lies — and the first thing anybody would do is
     press it and wait for something that never appears.

     So the button is a TEST RUN: a small picture, at once, with what is
     configured. That answers the only question this tile exists for — does
     drawing work on this machine — and it answers it by doing the thing
     rather than by asserting it.

     The three states it can be in are the three that matter: ready, no
     model, or drawing right now.

     It stands in the shared shape of `Servertafel.svelte` like the two real
     servers, and that includes the model dropdown: with one model installed
     it shows one entry. A fixed line of text in the place where the other
     panels put a control made the page look like a different program. */
  import { api } from '../lib/api.js'
  import { BILDVORGABEN } from '../lib/bildvorgaben.js'
  import { t } from '../lib/texte.svelte.js'
  import { katalogOeffnen, melde, zustand } from '../lib/zustand.svelte.js'
  import Auswahlfeld from './Auswahlfeld.svelte'
  import Servertafel from './Servertafel.svelte'

  let stand = $state(null)
  let gewaehlt = $state('')

  /* What the picture window starts out with. Only the starting values —
     changing them here changes what the window OFFERS, never what it can
     do, and a picture already ordered is untouched. */
  /* Only the class-free defaults live here now — the sampler and scheduler.
     Resolution and steps belong to the model's class (an SDXL model opens at
     1024, an SD-1.5 at 512); a single global number for them could not be
     right for both, so the picture window sets them per model and this panel
     no longer offers a control that would do nothing. */
  let vorgaben = $state({ sampler: '', scheduler: '' })
  let vorgabenGeladen = $state(false)

  async function vorgabenLaden() {
    try {
      const antwort = await api.einstellungAufgeloest(BILDVORGABEN)
      const w = antwort?.wert
      if (w && typeof w === 'object') {
        // Only the two keys this panel still owns — a stored resolution from
        // before the class-aware defaults is left where it lies, ignored.
        if (typeof w.sampler === 'string') vorgaben.sampler = w.sampler
        if (typeof w.scheduler === 'string') vorgaben.scheduler = w.scheduler
      }
    } catch {
      /* No stored defaults is the normal first case, not an error. */
    } finally {
      vorgabenGeladen = true
    }
  }
  vorgabenLaden()

  function vorgabenSichern() {
    api.einstellungSetzen('global', BILDVORGABEN, $state.snapshot(vorgaben)).catch(() => {})
  }

  /* Saved when the numbers come to rest, not on every keystroke: a field
     being typed into passes through 5, 51, 512, and three writes for one
     answer is three chances for the last one to lose a race. */
  $effect(() => {
    const _ = [vorgaben.sampler, vorgaben.scheduler]
    if (!vorgabenGeladen) return
    const uhr = setTimeout(vorgabenSichern, 600)
    return () => clearTimeout(uhr)
  })
  /* Share the chosen model so the plus-menu Image-Turbo toggle starts the
     one you last picked here. */
  $effect(() => {
    if (gewaehlt) zustand.bildModell = gewaehlt
  })

  let probe = $state(null) // { bild, sekunden }
  let arbeitet = $state(false)

  /* The generator program, on a machine that does not have it yet. A fresh
     installation used to get a flat refusal here and nowhere to go with it —
     the panel said "not set up" and there was no step that would set it up.
     Now the same place carries the step, in the shape the model server
     panel already uses: one button, then a bar while it comes down. */
  let programmStand = $state(null)
  const programmLaedt = $derived(
    Boolean(programmStand) && !programmStand.fertig && !programmStand.fehler,
  )
  const programmFehlt = $derived(Boolean(stand) && !stand.programm_da)

  async function laden() {
    try {
      stand = await api.bildmodelle()
      if (!gewaehlt || !stand.modelle?.includes(gewaehlt)) gewaehlt = stand.modelle?.[0] ?? ''
      if (!stand.programm_da) programmStand = await api.bildProgrammStand()
    } catch {
      stand = null
    }
  }
  laden()

  /* Only while something is missing or moving. A panel that keeps asking
     after the answer stopped changing is a request every two seconds for
     nothing. */
  $effect(() => {
    if (!programmFehlt) return
    const takt = setInterval(laden, 2000)
    return () => clearInterval(takt)
  })

  function programmHolen() {
    api
      .bildProgrammHolen()
      .then((s) => (programmStand = s))
      .catch((fehler) => melde(String(fehler.message || fehler), 'fehler'))
  }

  const FARBE = { bereit: 'gruen', zeichnet: 'blau', kein_modell: 'still', kein_programm: 'rot' }
  const standfarbe = $derived(FARBE[stand?.stand] ?? 'still')

  async function probelauf() {
    if (arbeitet || !gewaehlt) return
    arbeitet = true
    probe = null
    const start = Date.now()
    try {
      /* Small and short on purpose: this is a proof that the chain works,
         not a picture anybody wants. Eight steps at 256 px is a few seconds
         even on a slow machine. */
      const ergebnis = await api.bildZeichnen({
        modell: gewaehlt,
        prompt: 'a simple red circle on white',
        breite: 256,
        hoehe: 256,
        schritte: 8,
        /* The run shows up in the open chat's little history, the picture
           does not land in the conversation: this is a proof that drawing
           works, not a picture anybody ordered. */
        lauf_chat: zustand.aktiverChat,
      })
      probe = { bild: ergebnis.bild, sekunden: Math.round((Date.now() - start) / 100) / 10 }
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    } finally {
      arbeitet = false
      laden()
    }
  }

  const auswahl = $derived((stand?.modelle ?? []).map((name) => ({ wert: name, text: name })))
  const samplerauswahl = $derived((stand?.sampler ?? []).map((n) => ({ wert: n, text: n })))
</script>

<Servertafel
  titel={t('bildserver.titel')}
  unter={t(`bildserver.stand_${stand?.stand ?? 'kein_programm'}`)}
  {standfarbe}
  standtext={stand?.stand === 'bereit' || stand?.stand === 'zeichnet'
    ? t('status.erreichbar')
    : t('status.nicht_erreichbar')}
  wofuer={t('bildserver.wofuer')}
  modelle={auswahl}
  bind:gewaehlt
  modellBeschriftung={t('bildserver.modell')}
  modellGesperrt={arbeitet}
  leerText={stand ? t('bildserver.kein_modell_lang') : ''}
  katalogTat={() => katalogOeffnen('bild')}
  speicherort="bildmodelle"
  onOrtGeaendert={laden}
  tatText={arbeitet ? t('bildserver.probe_laeuft') : t('bildserver.probelauf')}
  tatPunkt={arbeitet ? 'blau' : 'still'}
  tatGesperrt={arbeitet || !gewaehlt || programmFehlt}
  onTat={probelauf}
>
  {#snippet mitte()}
    {#if programmFehlt}
      <div class="holen">
        <p>{programmLaedt ? t('bildserver.generator_laedt') : t('bildserver.generator_satz')}</p>
        {#if programmLaedt}
          <div class="balkenzeile">
            <span class="balken"><i style="width:{Math.round(programmStand.anteil * 100)}%"></i></span>
            <span class="balkenzahl">{Math.round(programmStand.anteil * 100)} %</span>
          </div>
        {:else}
          <button class="hol" onclick={programmHolen}>{t('bildserver.generator_holen')}</button>
        {/if}
      </div>
    {/if}
    {#if vorgabenGeladen}
      <div class="vorgaben">
        <div class="gruppenname">{t('bildserver.vorgaben')}</div>
        <label>{t('bild.sampler')}
          <Auswahlfeld bind:wert={vorgaben.sampler} eintraege={samplerauswahl}
                       gesperrt={arbeitet} beschriftung={t('bild.sampler')}
                       gewaehlt={vorgabenSichern} />
        </label>
        <p class="masse_hinweis">{t('bildserver.masse_folgen_modell')}</p>
      </div>
    {/if}
    {#if probe}
      <div class="probe">
        <img src={api.bildAdresse(probe.bild)} alt={t('bildserver.probelauf')} />
        <span>{t('bildserver.probe_fertig', { s: probe.sekunden })}</span>
      </div>
    {/if}
  {/snippet}
</Servertafel>

<style>
  /* The missing generator, as a tile like everything else on this page —
     the sentence, then the one thing to do about it. */
  .holen {
    display: flex;
    flex-direction: column;
    gap: 10px;
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 12px 14px;
  }
  .holen p {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-still);
  }
  .hol {
    align-self: flex-start;
    font: inherit;
    font-size: 13px;
    border-radius: 9px;
    padding: 7px 14px;
    cursor: pointer;
    border: 1px solid var(--linie-stark);
    background: var(--linie-stark);
    color: var(--text);
  }
  .hol:hover {
    background: var(--linie);
  }
  .balkenzeile {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
  }
  .balken {
    flex: 1;
    height: 5px;
    border-radius: 99px;
    background: var(--linie);
    overflow: hidden;
  }
  .balken i {
    display: block;
    height: 100%;
    background: var(--blau);
    transition: width 0.3s;
  }
  .balkenzahl {
    font: 400 11px var(--schrift-fest);
    color: var(--text-still);
    white-space: nowrap;
  }
  .vorgaben {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .gruppenname {
    font: 600 11px var(--schrift);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-leise);
  }
  .vorgaben label {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    color: var(--text-leise);
    min-width: 0;
  }
  .masse_hinweis {
    margin: 8px 0 0;
    font-size: 11.5px;
    line-height: 1.45;
    color: var(--text-still);
  }
  .probe {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12.5px;
    color: var(--text-still);
  }
  /* The house frame, as on every other picture in the program. */
  .probe img {
    width: 96px;
    height: 96px;
    border-radius: 12px;
    border: 2px solid var(--linie-stark);
    object-fit: cover;
  }
</style>
