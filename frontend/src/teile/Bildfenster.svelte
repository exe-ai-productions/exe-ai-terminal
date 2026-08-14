<script>
  /* The parameter window for a picture made on this machine.

     A dialog rather than a mode of the input field, and that is the whole
     difference to the image mode next to it: the cloud generators take a
     sentence and decide everything else themselves, so a line in the input
     field is the right shape for them. A local generator has six numbers
     that change what comes out, and six numbers do not belong on one line
     above the send button.

     The defaults are the ones that give a usable picture on the first try
     with an SD-1.5-class model. Whoever wants to tune knows what the
     sliders mean; whoever does not should be able to type a sentence and
     press the button. */
  import Auswahlfeld from './Auswahlfeld.svelte'
  import Fenster from './Fenster.svelte'
  import MaskenEditor from './MaskenEditor.svelte'
  import Zahlenfeld from './Zahlenfeld.svelte'
  import { api } from '../lib/api.js'
  import { BILDVORGABEN } from '../lib/bildvorgaben.js'
  import { melde, zustand } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'

  /* The chat the picture belongs to. Passed in rather than read from the
     state here: this window is opened from the input field, which knows
     which conversation it is standing in — and by the time the picture is
     done, the open chat may be another one. */
  let { offen = $bindable(false), chatId = null, zeichnen: losZeichnen } = $props()

  /* The picker takes {wert,text}; these lists are plain names. */
  const alsAuswahl = (namen) => (namen ?? []).map((n) => ({ wert: n, text: n }))

  let prompt = $state('')
  let negativ = $state('')

  /* Rewriting the prompt with the loaded language model.

     Picture models read English far more reliably than anything else, and
     they read a list of concrete phrases better than a sentence — both of
     which the language model already on this machine can do in one pass.

     `vorherigerPrompt` is one step of undo and deliberately no more: the
     question this answers is "that was worse, give me mine back", and that
     question is only ever asked about the last rewrite. `null` means there
     is nothing to go back to, which is why an empty original still counts
     as something. */
  let verbessert = $state(false)
  let vorherigerPrompt = $state(null)

  const sprachmodellDa = $derived(zustand.modelle.length > 0)
  const kannVerbessern = $derived(sprachmodellDa && !verbessert && Boolean(prompt.trim()))

  async function promptVerbessern() {
    if (!kannVerbessern) return
    verbessert = true
    const original = prompt
    try {
      const antwort = await api.bildPromptVerbessern(prompt, zustand.modellId)
      prompt = antwort.prompt
      vorherigerPrompt = original
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    } finally {
      verbessert = false
    }
  }

  function promptZurueck() {
    if (vorherigerPrompt === null) return
    prompt = vorherigerPrompt
    vorherigerPrompt = null
  }
  /* 512 is what the first model was trained on; 1024 stays available and
     costs both time and quality on it. */
  let breite = $state(512)
  let hoehe = $state(512)
  let schritte = $state(20)
  let cfg = $state(7)
  /* Empty means: let the generator pick. Kept as text, not as -1, because
     an empty field says "whatever" more clearly than a magic number. */
  let seed = $state('')
  let modelle = $state([])
  let modell = $state('')
  let programmDa = $state(true)
  /* The lists come from the shipped binary, not from a copy kept here: a
     sampler this build does not know is answered with a usage message that
     reaches the user as "could not be drawn". */
  let samplerListe = $state([])
  let schedulerListe = $state([])
  let sampler = $state('euler_a')
  let scheduler = $state('karras')
  /* The LoRA stack, in the order it was built — that order is what the
     prompt carries. One strength per entry, because that is all sd.cpp
     applies. */
  let loraListe = $state([])
  let stapel = $state([])
  /* A picture to start from. Without one the denoise slider has nothing to
     act on, so it stays out of reach. */
  let startbild = $state('')
  let startbildUrl = $state('')
  let staerke = $state(1)
  let startwahl = $state(null)
  /* The mask: painted in its own editor, uploaded like any other picture,
     and it travels by name. Only ever alongside a starting image — without
     one there is nothing to mask. */
  let maske = $state('')
  let maskeUrl = $state('')
  let maskeOffen = $state(false)

  /* The starting values the picture panel set. Read when the window opens,
     and only into fields nobody has touched in this session — a window
     reopened mid-work should stand where it was left, not jump back to a
     default. */
  let unberuehrt = $state(true)
  $effect(() => {
    if (!offen || !unberuehrt) return
    api
      .einstellungAufgeloest(BILDVORGABEN)
      .then((antwort) => {
        const v = antwort?.wert
        if (!v || typeof v !== 'object') return
        if (v.breite) breite = v.breite
        if (v.hoehe) hoehe = v.hoehe
        if (v.schritte) schritte = v.schritte
        if (v.sampler) sampler = v.sampler
        if (v.scheduler) scheduler = v.scheduler
      })
      .catch(() => {})
  })

  /* Fetched when the window opens rather than at startup: it is a look at
     the filesystem, and nobody needs it until this window is up. */
  $effect(() => {
    if (!offen) return
    api
      .bildmodelle()
      .then((stand) => {
        modelle = stand.modelle
        programmDa = stand.programm_da
        samplerListe = stand.sampler ?? []
        schedulerListe = stand.scheduler ?? []
        loraListe = stand.loras ?? []
        if (!modell || !modelle.includes(modell)) modell = modelle[0] ?? ''
      })
      .catch(() => {
        modelle = []
        programmDa = false
      })
  })

  const bereit = $derived(Boolean(prompt.trim() && modell && programmDa))

  /* The chosen picture is uploaded like any other attachment and travels
     by the name this server gave it — a path from the window never becomes
     a path on disk. */
  async function startbildSetzen(datei) {
    if (!datei) return
    try {
      const ergebnis = await api.bildHochladen(datei)
      startbild = ergebnis.bild
      startbildUrl = api.bildAdresse(ergebnis.bild)
      // A starting picture that is fully painted over is no starting
      // picture; the useful half of the range begins here.
      if (staerke >= 1) staerke = 0.6
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

  function startbildLoesen() {
    startbild = ''
    startbildUrl = ''
    staerke = 1
    // The mask belonged to that picture. Keeping it would aim it at
    // whatever comes next.
    maskeLoesen()
  }

  function maskeLoesen() {
    maske = ''
    maskeUrl = ''
  }

  /* What the editor hands back is a finished black and white PNG. It goes
     up the same path every attachment goes up, and comes back as a name. */
  async function maskeFertig(datei) {
    try {
      const ergebnis = await api.bildHochladen(datei)
      maske = ergebnis.bild
      maskeUrl = api.bildAdresse(ergebnis.bild)
    } catch (fehler) {
      melde(String(fehler.message || fehler), 'fehler')
    }
  }

  function zeichnen() {
    if (!bereit) return
    /* No chat, no home for the picture. Starting anyway is how a run ends
       up working for nobody — nowhere to show itself, nothing to stop it,
       and a window left standing on "drawing…" for five minutes. */
    if (!chatId) {
      melde(t('bild.erst_chat'), 'hinweis')
      return
    }
    /* The window hands the request up and goes. It does not wait for the
       picture: drawing takes half a minute, and a dialog that stands there
       through it has taken the screen for something the chat shows better. */
    offen = false
    unberuehrt = false
    losZeichnen({
      modell,
      chat_id: chatId,
      prompt: prompt.trim(),
      negativ: negativ.trim(),
      breite,
      hoehe,
      schritte,
      cfg,
      // Anything that is not a whole number means "let it pick". `Number`
      // on a typo gives NaN, JSON turns that into null, and the server
      // answers 422 — a rejection for a field that was meant to be
      // optional.
      seed: /^\d+$/.test(seed.trim()) ? Number(seed.trim()) : -1,
      sampler,
      scheduler,
      loras: stapel.filter((e) => e.name).map((e) => ({ name: e.name, staerke: e.staerke })),
      startbild: startbild || null,
      staerke,
      maske: maske || null,
    })
  }
</script>

<Fenster bind:offen titel={t('bild.titel')} art="frage" schrumpfen>
  {#if !programmDa}
    <!-- Honest instead of a button that fails at the server: without the
         generator there is nothing to configure here. -->
    <p class="leer">{t('bild.kein_programm')}</p>
  {:else if !modelle.length}
    <p class="leer">{t('bild.kein_modell')}</p>
  {:else}
    <div class="feld">
      <div class="feldkopf">
        <span>{t('bild.prompt')}</span>
        <!-- Two buttons that belong to the field, not to the window: they
             sit on its own line so the label keeps its place and the row
             of parameters below is not pushed out of line. -->
        <div class="promptknoepfe">
          {#if vorherigerPrompt !== null}
            <button
              class="promptknopf"
              onclick={promptZurueck}
              title={t('bild.verbessern_zurueck')}
              aria-label={t('bild.verbessern_zurueck')}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M4 9h11a5 5 0 0 1 0 10h-6" />
                <path d="M8 5 4 9l4 4" />
              </svg>
            </button>
          {/if}
          <!-- Marked dimmed rather than truly disabled: a disabled button
               shows no tooltip, and the tooltip is the whole explanation of
               why it cannot be pressed. The click is refused in the handler. -->
          <button
            class="promptknopf wort"
            class:gesperrt={!kannVerbessern}
            aria-disabled={!kannVerbessern}
            onclick={promptVerbessern}
            title={sprachmodellDa ? t('bild.verbessern_tipp') : t('bild.verbessern_kein_modell')}
          >
            {verbessert ? t('bild.verbessern_laeuft') : t('bild.verbessern')}
          </button>
        </div>
      </div>
      <textarea bind:value={prompt} rows="3" disabled={verbessert}></textarea>
    </div>

    <label class="feld">
      <span>{t('bild.negativ')}</span>
      <textarea bind:value={negativ} rows="2"></textarea>
    </label>

    <div class="feld">
      <span>{t('bild.modell')}</span>
      <Auswahlfeld bind:wert={modell} eintraege={alsAuswahl(modelle)} beschriftung={t('bild.modell')} />
    </div>

    <!-- Two by two: the pair that belongs together stands together, and
         every cell is the same size. -->
    <div class="raster">
      <label class="klein">
        <span>{t('bild.breite')}</span>
        <Zahlenfeld bind:wert={breite} min={256} max={1536} schritt={64} />
      </label>
      <label class="klein">
        <span>{t('bild.hoehe')}</span>
        <Zahlenfeld bind:wert={hoehe} min={256} max={1536} schritt={64} />
      </label>
      <label class="klein">
        <span>{t('bild.schritte')}</span>
        <Zahlenfeld bind:wert={schritte} min={1} max={80} schritt={1} />
      </label>
      <label class="klein">
        <span>{t('bild.cfg')}</span>
        <Zahlenfeld bind:wert={cfg} min={0} max={30} schritt={1} />
      </label>
    </div>

    <div class="raster">
      <div class="klein">
        <span>{t('bild.sampler')}</span>
        <Auswahlfeld bind:wert={sampler} eintraege={alsAuswahl(samplerListe)} beschriftung={t('bild.sampler')} />
      </div>
      <div class="klein">
        <span>{t('bild.scheduler')}</span>
        <Auswahlfeld bind:wert={scheduler} eintraege={alsAuswahl(schedulerListe)} beschriftung={t('bild.scheduler')} />
      </div>
    </div>

    <label class="feld">
      <span>{t('bild.seed')}</span>
      <input bind:value={seed} placeholder={t('bild.seed_zufall')} inputmode="numeric" />
    </label>

    <!-- The LoRA stack. A list rather than one picker: several apply at
         once, and the order they are added in is the order they act in. -->
    <div class="feld">
      <span>{t('bild.lora')}</span>
      {#if !loraListe.length}
        <p class="hinweis">{t('bild.lora_keine')}</p>
      {/if}
      {#each stapel as eintrag, i (i)}
        <div class="lorazeile">
          <Auswahlfeld bind:wert={eintrag.name} eintraege={alsAuswahl(loraListe)} beschriftung={t('bild.lora')} />
          <input class="staerke" type="range" min="0" max="2" step="0.05"
                 bind:value={eintrag.staerke} aria-label={t('bild.lora_staerke')} />
          <span class="zahl">{eintrag.staerke.toFixed(2)}</span>
          <button class="weg" aria-label={t('warteschlange.entfernen')}
                  title={t('warteschlange.entfernen')}
                  onclick={() => (stapel = stapel.filter((_, n) => n !== i))}>✕</button>
        </div>
      {/each}
      <div class="lorafuss">
        <button class="klein-knopf" disabled={!loraListe.length}
                onclick={() => (stapel = [...stapel, { name: loraListe[0], staerke: 0.7 }])}>
          {t('bild.lora_hinzufuegen')}
        </button>
        <button class="klein-knopf" onclick={() => api.loraOrdnerOeffnen().catch(() => {})}>
          {t('bild.lora_ordner')}
        </button>
      </div>
      <!-- Said out loud rather than quietly dropped: this generator has one
           strength per LoRA. -->
      <p class="hinweis">{t('bild.lora_eine_staerke')}</p>
    </div>

    <!-- Start from a picture. With one, the slider below decides how much
         of it survives; without one it has nothing to act on. -->
    <div class="feld">
      <span>{t('bild.startbild')}</span>
      <div class="lorazeile">
        {#if startbildUrl}
          <img class="vorschau" src={startbildUrl} alt={t('bild.startbild')} />
        {/if}
        <button class="klein-knopf" onclick={() => startwahl?.click()}>
          {startbild ? t('bild.startbild_waehlen') : t('bild.startbild_keins')}
        </button>
        {#if startbild}
          <button class="weg" aria-label={t('warteschlange.entfernen')}
                  title={t('warteschlange.entfernen')}
                  onclick={startbildLoesen}>✕</button>
        {/if}
      </div>
      <input class="versteckt" type="file" accept="image/png,image/jpeg,image/webp"
             bind:this={startwahl} onchange={(e) => startbildSetzen(e.currentTarget.files?.[0])} />
    </div>

    <!-- The mask lives with the starting image: it says which part of THAT
         picture gets drawn again, so without one there is nothing to
         paint on. -->
    {#if startbild}
      <div class="feld">
        <span>{t('maske.titel')}</span>
        <div class="lorazeile">
          {#if maskeUrl}
            <img class="vorschau" src={maskeUrl} alt={t('maske.titel')} />
          {/if}
          <button class="klein-knopf" onclick={() => (maskeOffen = true)}>
            {maske ? t('maske.neu_zeichnen') : t('maske.zeichnen')}
          </button>
          {#if maske}
            <button class="weg" aria-label={t('warteschlange.entfernen')}
                    title={t('warteschlange.entfernen')} onclick={maskeLoesen}>✕</button>
          {/if}
        </div>
        <p class="hinweis">{t('maske.wofuer')}</p>
      </div>
    {/if}

    <label class="feld" class:gesperrt={!startbild}>
      <span>{t('bild.staerke')}</span>
      <div class="lorazeile">
        <input class="staerke" type="range" min="0" max="1" step="0.05"
               bind:value={staerke} disabled={!startbild} aria-label={t('bild.staerke')} />
        <span class="zahl">{staerke.toFixed(2)}</span>
      </div>
      <p class="hinweis">{t('bild.staerke_hinweis')}</p>
    </label>

    <div class="fuss">
      <button class="zeichnen" disabled={!bereit} onclick={zeichnen}>
        {t('bild.erzeugen')}
      </button>
    </div>
  {/if}
</Fenster>

<!-- Its own window, on top of this one: painting needs the picture large,
     and a canvas squeezed between two sliders is a canvas nobody can aim. -->
<MaskenEditor bind:offen={maskeOffen} bildUrl={startbildUrl} fertig={maskeFertig} />

<style>
  .leer {
    margin: 0;
    padding: 8px 0 4px;
    color: var(--text-still);
    font-size: 13.5px;
  }
  .feld,
  .klein {
    display: flex;
    flex-direction: column;
    gap: 5px;
    margin-bottom: 12px;
    min-width: 0;
  }
  .feld > span,
  .feldkopf > span,
  .klein > span {
    font-size: 12px;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--text-still);
  }
  /* The label keeps the left edge it has in every other field; the buttons
     ride at the right end of the same line so nothing below shifts. */
  .feldkopf {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 22px;
  }
  .promptknoepfe {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .promptknopf {
    font: inherit;
    font-size: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: none;
    color: var(--text-still);
    padding: 4px;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .promptknopf.wort {
    padding: 4px 10px;
  }
  .promptknopf:not(.gesperrt):hover {
    background: var(--linie);
    color: var(--text);
  }
  /* Dimmed rather than hidden: a button that is not there explains nothing,
     and its tooltip is where the explanation lives. */
  .promptknopf.gesperrt {
    opacity: 0.45;
    cursor: default;
  }
  textarea,
  input,
  textarea:focus,
  input:focus {
    outline: none;
    border-color: var(--linie-stark);
  }
  /* One group, one size: four cells of equal width, so no number looks
     more important than another. */
  .raster {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 12px;
  }
  .fuss {
    display: flex;
    justify-content: flex-end;
    margin-top: 4px;
  }
  .hinweis {
    margin: 4px 0 0;
    font-size: 11.5px;
    line-height: 1.45;
    color: var(--text-still);
  }
  .lorazeile {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }
  /* The picker takes the room the row has left over. */
  .lorazeile :global(.feldplatz) {
    flex: 1;
    min-width: 0;
  }
  .staerke {
    flex: none;
    width: 110px;
    padding: 0;
    border: none;
    background: none;
    accent-color: var(--text-leise);
  }
  .zahl {
    flex: none;
    width: 34px;
    font-size: 12px;
    color: var(--text-still);
    font-variant-numeric: tabular-nums;
  }
  .vorschau {
    width: 40px;
    height: 40px;
    border-radius: 9px;
    border: 2px solid var(--linie-stark);
    object-fit: cover;
    flex: none;
  }
  .lorafuss {
    display: flex;
    gap: 6px;
  }
  .klein-knopf,
  .weg {
    font: inherit;
    font-size: 12px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text-still);
    border-radius: 9px;
    padding: 4px 10px;
    cursor: pointer;
  }
  .weg {
    border-color: transparent;
    padding: 4px 8px;
    flex: none;
  }
  .klein-knopf:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .klein-knopf:not(:disabled):hover,
  .weg:hover {
    background: var(--linie);
    color: var(--text);
  }
  /* A control that cannot act must look like it. */
  .gesperrt > span,
  .gesperrt .zahl {
    opacity: 0.5;
  }
  .versteckt {
    display: none;
  }
  .zeichnen {
    font: inherit;
    font-size: 13px;
    border: 1px solid var(--linie-stark);
    background: var(--linie-stark);
    color: var(--text);
    border-radius: 9px;
    padding: 7px 16px;
    cursor: pointer;
  }
  .zeichnen:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .zeichnen:not(:disabled):hover {
    background: var(--linie);
  }
</style>
