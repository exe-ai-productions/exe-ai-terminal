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
  import Schriftzug from './Schriftzug.svelte'
  import Fenster from './Fenster.svelte'
  import MaskenEditor from './MaskenEditor.svelte'
  import Bildablage from './Bildablage.svelte'
  import Zahlenfeld from './Zahlenfeld.svelte'
  import Turbozeichen from './Turbozeichen.svelte'
  import { api } from '../lib/api.js'
  import { melde, zustand, chatsLaden } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import { seedlage } from '../lib/bildseed.svelte.js'

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
  /* The negative rides along in the same undo step — one rewrite, one
     way back, for both fields together. */
  let vorherigerNegativ = $state(null)

  const sprachmodellDa = $derived(zustand.modelle.length > 0)
  const kannVerbessern = $derived(sprachmodellDa && !verbessert && Boolean(prompt.trim()))

  /* Image-Turbo — the persistent picture server that draws faster. Its switch
     and the big animated gauge live in this window's header (top-right). State
     is polled only while the window is open. The gauge keeps its OWN colours
     (green→gold→red sweep); the green/blue status light is the tile icon in the
     plus-menu, not this gauge. */
  let turboZustand = $state('aus')
  let turboProgrammDa = $state(false)
  let turboBeschaeftigt = $state(false)
  const turboAn = $derived(turboZustand === 'bereit' || turboZustand === 'zeichnet')
  async function turboStandHolen() {
    try {
      const s = await api.turboStand()
      turboZustand = s.zustand ?? 'aus'
      turboProgrammDa = s.programm_da ?? false
    } catch {
      turboZustand = 'aus'
      turboProgrammDa = false
    }
  }
  async function turboSchalten() {
    if (turboBeschaeftigt) return
    turboBeschaeftigt = true
    try {
      if (turboZustand === 'aus' || turboZustand === 'fehler') {
        if (modell) await api.turboStarten(modell)
      } else {
        await api.turboStoppen()
      }
    } catch {
      /* the gauge colour reports the outcome; nothing to say here */
    }
    await turboStandHolen()
    turboBeschaeftigt = false
  }
  $effect(() => {
    if (!offen) return
    turboStandHolen()
    const takt = setInterval(turboStandHolen, 4000)
    return () => clearInterval(takt)
  })

  async function promptVerbessern() {
    if (!kannVerbessern) return
    verbessert = true
    const original = prompt
    const originalNegativ = negativ
    try {
      const antwort = await api.bildPromptVerbessern(prompt, negativ, zustand.modellId)
      prompt = antwort.prompt
      if (antwort.negativ) negativ = antwort.negativ
      vorherigerPrompt = original
      vorherigerNegativ = originalNegativ
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
    if (vorherigerNegativ !== null) {
      negativ = vorherigerNegativ
      vorherigerNegativ = null
    }
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
  /* The seed plan for a series: pick fresh every time, hold one, or walk
     up/down from the last drawn seed. A plan instead of a lone field,
     because twenty pictures in a row should not need somebody sitting at
     the machine retyping a number between draws. */
  let seedModus = $state('zufall')

  /* What the next draw actually sends. The walking modes continue from the
     seed of the LAST DRAWN picture (the server reports it) — before any
     picture exists they fall back to the field, then to "pick one". */
  function seedFuerLauf() {
    const feld = /^\d+$/.test(seed.trim()) ? Number(seed.trim()) : null
    if (seedModus === 'zufall') return -1
    if (seedModus === 'fest') return feld ?? seedlage.letzter ?? -1
    const basis = seedlage.letzter ?? feld
    if (basis === null) return -1
    return Math.max(0, basis + (seedModus === 'plus' ? 1 : -1))
  }

  function seedUebernehmen() {
    if (seedlage.letzter === null) return
    seed = String(seedlage.letzter)
    seedModus = 'fest'
  }
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
  /* The quality companions, folded away under "Advanced": most pictures need
     none of them, and a wall of dials on every draw is its own kind of
     wrong. An external VAE brings colour and detail back, clip-skip a few
     models want one CLIP layer skipped, and ADetailer redraws each face at
     full size. All optional — empty means the pass is simply off. */
  let vaeListe = $state([])
  let yoloListe = $state([])
  let vae = $state('')
  let clipSkip = $state(0)
  let adModell = $state('')
  let adPrompt = $state('')
  /* Highres fix: a second pass at a larger size for finer detail. Off by
     default — it roughly doubles the time. */
  /* One field instead of a switch and a second row: the scale IS the switch,
     the way the ADetailer picker works — "off" is one of its choices. A
     switch that only reveals a number costs a whole row to say what the
     number already says. */
  let hiresWahl = $state('')
  const hires = $derived(hiresWahl !== '')
  const hiresScale = $derived(Number(hiresWahl) || 2)
  /* A picture to start from. Without one the denoise slider has nothing to
     act on, so it stays out of reach. */
  let startbild = $state('')
  let startbildUrl = $state('')
  let staerke = $state(1)
  /* The mask: painted in its own editor, uploaded like any other picture,
     and it travels by name. Only ever alongside a starting image — without
     one there is nothing to mask. */
  let maske = $state('')
  let maskeUrl = $state('')
  let maskeOffen = $state(false)

  /* The starting values the picture panel set, class-aware: the fields
     follow the CHOSEN model, so an SDXL model opens at 1024/28 and an
     SD-1.5 at 512/22 instead of one number that starved every big model.
     Read when the window opens and whenever the model changes, but only
     until the first picture of the session is drawn — after that a window
     reopened mid-work should stand where it was left, not jump back. A
     resolution and steps still come from the model's class, and a per-model
     override wins; the merge happens on the server, this only applies the
     answer. Only the newest request may write: the first fire runs with an
     empty model (nothing chosen yet) and the model-list effect then sets the
     real model, firing a second request — without the guard the slow empty
     answer could land last and overwrite an SDXL model's 1024 with 512. */
  let unberuehrt = $state(true)
  let vorgabenLauf = 0
  $effect(() => {
    if (!offen || !unberuehrt) return
    const lauf = ++vorgabenLauf
    api
      .bildVorgaben(modell)
      .then((v) => {
        if (lauf !== vorgabenLauf || !v || typeof v !== 'object') return
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
        vaeListe = stand.vaes ?? []
        yoloListe = stand.yolos ?? []
        // A model the catalogue sent over wins over what stood here; the
        // wish is consumed so a later reopen keeps the user's own pick.
        if (zustand.bildModellWunsch && modelle.includes(zustand.bildModellWunsch)) {
          modell = zustand.bildModellWunsch
          zustand.bildModellWunsch = null
        } else if (!modell || !modelle.includes(modell)) {
          modell = modelle[0] ?? ''
        }
      })
      .catch(() => {
        modelle = []
        programmDa = false
      })
  })

  /* The last-chosen image model, shared so the plus-menu Image-Turbo toggle
     loads the model you were about to draw with. */
  $effect(() => {
    if (modell) zustand.bildModell = modell
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

  async function zeichnen() {
    if (!bereit) return
    /* No chat yet: then drawing OPENS one instead of refusing. Wanting a
       picture is a complete wish of its own — it must not depend on a chat
       model being loaded or a conversation having been started first. The
       chat is created without a model on purpose; it gets one the moment
       a message is sent in it. */
    let ziel = chatId
    if (!ziel) {
      const titel = prompt.trim().length > 40
        ? prompt.trim().slice(0, 40) + '…'
        : prompt.trim() || t('eingabe.bild_titel')
      try {
        const chat = await api.chatAnlegen({
          title: titel,
          endpoint_id: zustand.modellId || null,
        })
        ziel = chat.id
        zustand.aktiverChat = chat.id
        zustand.nachrichten = []
        chatsLaden()
      } catch (fehler) {
        melde(String(fehler.message || fehler), 'fehler')
        return
      }
    }
    /* The window STAYS open: pressing draw again queues the next picture, and
       the counter on the button climbs. It closes by a click into the main
       window behind it, once enough have been lined up. */
    unberuehrt = false
    losZeichnen({
      modell,
      chat_id: ziel,
      prompt: prompt.trim(),
      negativ: negativ.trim(),
      breite,
      hoehe,
      schritte,
      cfg,
      // The plan decides: fresh, held, or one step from the last drawn
      // seed. -1 keeps meaning "let it pick".
      seed: seedFuerLauf(),
      sampler,
      scheduler,
      loras: stapel.filter((e) => e.name).map((e) => ({ name: e.name, staerke: e.staerke })),
      startbild: startbild || null,
      staerke,
      maske: maske || null,
      // The quality companions. -1 clip-skip means "let the class decide";
      // empty names mean the pass is off.
      clip_skip: clipSkip > 0 ? clipSkip : -1,
      vae: vae || null,
      ad_modell: adModell || null,
      ad_prompt: adPrompt.trim(),
      hires,
      hires_scale: hiresScale,
    })
  }
</script>

<Fenster bind:offen titel="" art="bild" schrumpfen>
  {#snippet kopf()}
    <!-- The window's own controls, all in one corner: rewriting the prompt is
         about the whole window, not about the field it happens to change, and
         a button sitting on a field's label line pushes that line around. -->
    {#if vorherigerPrompt !== null}
      <button
        class="turbokopf"
        onclick={promptZurueck}
        title={t('bild.verbessern_zurueck')}
        aria-label={t('bild.verbessern_zurueck')}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 9h11a5 5 0 0 1 0 10h-6" />
          <path d="M8 5 4 9l4 4" />
        </svg>
      </button>
    {/if}
    <!-- Marked dimmed rather than truly disabled: a disabled button shows no
         tooltip, and the tooltip is the whole explanation of why it cannot be
         pressed. The click is refused in the handler. -->
    <button
      class="turbokopf"
      class:gesperrt={!kannVerbessern}
      aria-disabled={!kannVerbessern}
      onclick={promptVerbessern}
      title={sprachmodellDa ? t('bild.verbessern_tipp') : t('bild.verbessern_kein_modell')}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 3v3M12 18v3M5 12H2M22 12h-3M6.3 6.3l2 2M15.7 15.7l2 2M17.7 6.3l-2 2M8.3 15.7l-2 2" />
      </svg>
      <span class="turbowort">{verbessert ? t('bild.verbessern_laeuft') : t('bild.verbessern')}</span>
    </button>
    <!-- Image-Turbo lives in the header's top-right: the big animated gauge is
         the switch (grey off, its own sweep on). It keeps its own colours; the
         plus-menu tile icon is the green/blue status light. -->
    <button
      class="turbokopf"
      class:an={turboAn}
      type="button"
      disabled={!turboProgrammDa || turboBeschaeftigt}
      onclick={turboSchalten}
      title={turboProgrammDa ? t('bild.turbo.icon_hinweis') : t('bild.turbo.kein_programm')}
      aria-label={t(`bild.turbo.zustand_${turboZustand}`)}
    >
      <span class="turbowort">{t('bild.turbo.name')}</span>
      <Turbozeichen an={turboAn} groesse={24} />
    </button>
  {/snippet}
  <!-- The room's own heading: the house picture sign and the drawn word,
       the same pairing the mask editor wears. The box carries the word for a
       reader that cannot see the strokes. -->
  <div class="ueberschrift" aria-label={t('bild.titel')}>
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="8.5" cy="9.5" r="1.6" />
      <path d="M4 17l4.5-5 3.5 4 3-2.5L20 17" />
    </svg>
    <Schriftzug zug="bild_einstellungen" hoehe={15} />
  </div>

  {#if !programmDa}
    <!-- Honest instead of a button that fails at the server: without the
         generator there is nothing to configure here. -->
    <p class="leer">{t('bild.kein_programm')}</p>
  {:else if !modelle.length}
    <p class="leer">{t('bild.kein_modell')}</p>
  {:else}
    <!-- MOTIV — the one block that matters most, set apart at the top: the
         prompt, its negative, and the model that draws them. -->
    <div class="motiv">
      <span class="titel"><svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.4" y="2.4" width="19.2" height="19.2" rx="5.7" /><path d="M7.4 12 H16.6" /><path d="M12 7.4 V16.6" /></svg>{t('bild.prompt')}</span>
      <!-- No placeholder: the label above already says what belongs in here,
           and a sentence inside an empty field reads as content until it is
           clicked away. -->
      <textarea class="feldein gross" bind:value={prompt} rows="3" disabled={verbessert}></textarea>
      <label class="feld eng">
        <span><svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.4" y="2.4" width="19.2" height="19.2" rx="5.7" /><path d="M7.4 12 H16.6" /></svg>{t('bild.negativ')}</span>
        <!-- Same height as the field above: the two are a pair, and one
             standing lower than the other reads as the lesser of the two. -->
        <textarea class="feldein" bind:value={negativ} rows="3"></textarea>
      </label>
    </div>

    <div class="feld">
      <span><svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 L20.5 7.5 L12 12 L3.5 7.5 Z" /><path d="M3.5 7.5 V16 L12 20.5 L20.5 16 V7.5" /><path d="M12 12 V20.5" /></svg>{t('bild.modell')}</span>
      <Auswahlfeld bind:wert={modell} eintraege={alsAuswahl(modelle)} beschriftung={t('bild.modell')} />
    </div>

    <!-- Two columns from here down: the numbers on the left, the fold on the
         right, so the window is broad and short instead of one long tube. -->
    <div class="spalten">
      <div class="spalte">

    <!-- Measures & run: the numbers that shape the picture, under one head. -->
    <div class="abschnitt">
      <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="7.5" height="7.5" rx="2"/><rect x="13" y="3.5" width="7.5" height="7.5" rx="2"/><rect x="3.5" y="13" width="7.5" height="7.5" rx="2"/><rect x="13" y="13" width="7.5" height="7.5" rx="2"/></svg>
      {t('bild.gruppe_masse')}
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

    <!-- The reference picture fills the foot of the left column. It wears
         no heading of its own: the plaque names itself, mark and word in
         its middle, and the same words twice above one another would be
         one label too many. -->
    <div class="feld startabschnitt">
      <Bildablage
        url={startbildUrl}
        waehlen={startbildSetzen}
        loesen={startbildLoesen}
      />
    </div>

    <!-- The two things the reference picture is set with, on one line under
         it and each taking half of its width — the way the mask editor's own
         row ends flush with the picture above it. Both stay in place and grey
         out until there is a picture: a control that appears only once some
         earlier step succeeded is a control nobody knows exists. -->
    <div class="startzeile">
      <label class="startfeld" class:gesperrt={!startbild}>
        <span>{t('bild.staerke')}</span>
        <div class="lorazeile">
          <input class="staerke" type="range" min="0" max="1" step="0.05"
                 bind:value={staerke} disabled={!startbild} aria-label={t('bild.staerke')} />
          <span class="zahl">{staerke.toFixed(2)}</span>
        </div>
      </label>

      <div class="startfeld maskenfeld">
        {#if maskeUrl}
          <img class="vorschau" src={maskeUrl} alt={t('maske.titel')} />
        {/if}
        <button class="maskenknopf" disabled={!startbild} onclick={() => (maskeOffen = true)}>
          {maske ? t('maske.neu_zeichnen') : t('maske.zeichnen')}
        </button>
        {#if maske}
          <button class="weg" aria-label={t('warteschlange.entfernen')}
                  title={t('warteschlange.entfernen')} onclick={maskeLoesen}>✕</button>
        {/if}
      </div>
    </div>

      </div>
      <div class="spalte">

    <!-- Fine-tuning: the LoRA stack and the quality companions. No longer
         folded away — the second column gives it a home of its own, so it is
         always in view and everything fits in one window. -->
    <div class="abschnitt">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 6.75 H11.25 M17.25 6.75 H19.5"/><circle cx="14.25" cy="6.75" r="2.05"/><path d="M4.5 12 H6 M12 12 H19.5"/><circle cx="9" cy="12" r="2.05"/><path d="M4.5 17.25 H12.75 M18.75 17.25 H19.5"/><circle cx="15.75" cy="17.25" r="2.05"/></svg>
      {t('bild.gruppe_feinschliff')}
    </div>
    <div class="klappinhalt">
    <!-- The number and how the next draw picks it, side by side on one line
         — the same shape width and height wear in the column opposite. A plan
         rather than a lone field: twenty pictures in a row should not need
         somebody retyping a number between draws. -->
    <div class="raster">
      <label class="feld">
        <span>{t('bild.seed')}</span>
        <input class="feldein fest" bind:value={seed} placeholder={t('bild.seed_zufall')} inputmode="numeric" />
      </label>
      <div class="feld">
        <span>{t('bild.seed_modus')}</span>
        <Auswahlfeld bind:wert={seedModus} beschriftung={t('bild.seed_modus')}
                     eintraege={[{ wert: 'zufall', text: t('bild.seed_zufall') },
                                 { wert: 'fest', text: t('bild.seed_fest') },
                                 { wert: 'plus', text: t('bild.seed_plus') },
                                 { wert: 'minus', text: t('bild.seed_minus') }]} />
      </div>
    </div>
    <!-- The last drawn seed: one click takes it over and holds it, so
         "continue exactly here" is a deliberate act and chance stays the
         default. Only there once something has been drawn. -->
    {#if seedlage.letzter !== null}
      <div class="seedplan">
        <button class="seedletzter" onclick={seedUebernehmen}
                title={t('bild.seed_uebernehmen')}>
          {t('bild.seed_zuletzt', { zahl: seedlage.letzter })}
        </button>
      </div>
    {/if}

        <!-- The LoRA stack. A list rather than one picker: several apply at
             once, and the order they are added in is the order they act in. -->
        <div class="feld">
          <span><svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.1 6 L12 12 L4.1 18 Z" /><path d="M19.9 6 L12 12 L19.9 18 Z" /></svg>{t('bild.lora')}</span>
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
            <button class="maskenknopf" disabled={!loraListe.length}
                    onclick={() => (stapel = [...stapel, { name: loraListe[0], staerke: 0.7 }])}>
              {t('bild.lora_hinzufuegen')}
            </button>
            <button class="maskenknopf" onclick={() => api.bildBegleiterOrdner('lora').catch(() => {})}>
              {t('bild.lora_ordner')}
            </button>
          </div>
        </div>

        <div class="feld">
          <span><svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5.5 17.5 L12 5.5 L18.5 14.5 Z" stroke-width="1.2" /><path d="M5.5 17.5 h.01 M12 5.5 h.01 M18.5 14.5 h.01" stroke-width="3.6" /></svg>{t('bild.embedding')}</span>
          <div class="lorafuss">
            <button class="maskenknopf" onclick={() => api.bildBegleiterOrdner('embedding').catch(() => {})}>
              {t('bild.embedding_ordner')}
            </button>
          </div>
        </div>

        <div class="feld">
          <span><svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21 A9 9 0 1 1 21 11.25 C21 13.7 19.1 15.4 16.7 15.4 L14.4 15.4 C13 15.4 12.2 16.3 12.2 17.4 C12.2 18 12.4 18.5 12.8 18.9 C13.4 19.7 13 21 12 21 Z" /><circle cx="8.4" cy="10.5" r="1.05" /><circle cx="12.6" cy="7.5" r="1.05" /><circle cx="16.7" cy="10.5" r="1.05" /></svg>{t('bild.vae')}</span>
          <Auswahlfeld bind:wert={vae} eintraege={[{ wert: '', text: t('bild.vae_keins') }, ...alsAuswahl(vaeListe)]}
                       beschriftung={t('bild.vae')} />
        </div>
        <div class="feld">
          <span><svg class="feldzeichen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.75" y="3.75" width="16.5" height="16.5" rx="2.3" /><path d="M9.4 9.8 V11.6 M14.6 9.8 V11.6" /><path d="M9 14.6 Q12 16.9 15 14.6" /></svg>{t('bild.adetailer')}</span>
          <Auswahlfeld bind:wert={adModell} eintraege={[{ wert: '', text: t('bild.adetailer_keins') }, ...alsAuswahl(yoloListe)]}
                       beschriftung={t('bild.adetailer')} />
        </div>
        <label class="feld">
          <span>{t('bild.clip_skip')}</span>
          <Zahlenfeld bind:wert={clipSkip} min={0} max={12} schritt={1} nullwort={t('bild.clip_auto')} />
        </label>
        {#if adModell}
          <label class="feld">
            <span>{t('bild.ad_prompt')}</span>
            <input class="feldein" bind:value={adPrompt} placeholder={t('bild.ad_prompt_platzhalter')} />
          </label>
        {/if}

        <div class="feld">
          <span>{t('bild.hires')}</span>
          <Auswahlfeld bind:wert={hiresWahl} beschriftung={t('bild.hires')}
                       eintraege={[{ wert: '', text: t('bild.adetailer_keins') },
                                   { wert: '2', text: '2×' },
                                   { wert: '3', text: '3×' },
                                   { wert: '4', text: '4×' }]} />
        </div>
      </div>

      </div>
    </div>

    <div class="fussbalken">
      <button class="zeichnen" disabled={!bereit} onclick={zeichnen}>
        <!-- Where the bolt was: how many pictures are in the works, climbing
             with every press. Nothing there when none is running. -->
        {#if zustand.bildWarteschlange > 0}
          <span class="zeichenzahl">{zustand.bildWarteschlange}</span>
        {/if}
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
    color: var(--text-leise);
    font-size: 13.5px;
  }
  .feld,
  .klein {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 14px;
    min-width: 0;
  }
  /* Readable, not whispered: labels sit at --text-leise so the eye can
     actually find them, in ONE weight so nothing flickers bold-and-not. */
  .feld > span,
  .feldkopf > span,
  .klein > span {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-leise);
  }
  /* The motive block — prompt, its negative, the model — set apart at the
     top on the raised ground, because it is the part that decides the
     picture. Everything below configures; this is the picture itself. */
  .ueberschrift {
    display: flex;
    align-items: center;
    gap: 11px;
    color: var(--text);
  }
  /* No box of its own any more: the block was set apart because it carried
     its own controls, and those now sit in the window's corner with the
     others. What is left are two fields, and two fields need no frame to be
     read as two fields. */
  .motiv {
    /* Clears the controls riding in the window corner above: the block must
       start below their lower edge, never under them. */
    margin-top: 22px;
    margin-bottom: 16px;
  }
  /* The same label every other field in this window wears — the block lost
     its frame, so its heading has no reason left to be set apart from the
     one under it. A row, so the sign sits beside the word instead of against
     it. */
  .motiv .titel {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-leise);
  }
  .motiv .feld.eng {
    margin: 12px 0 0;
  }
  /* Every text field wears the house's own dark ground now, instead of the
     browser's white box: same shape as the number field, so the window
     reads as one surface rather than a page with holes punched in it. */
  .feldein {
    width: 100%;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 10px;
    color: var(--text);
    font: inherit;
    font-size: 13.5px;
    padding: 9px 11px;
    outline: none;
  }
  textarea.feldein {
    resize: none;
    line-height: 1.45;
  }
  .feldein.fest {
    font-family: var(--schrift-fest);
  }
  .feldein::placeholder {
    color: var(--text-still);
  }
  .feldein:focus {
    border-color: var(--text-still);
  }
  /* The label keeps the left edge it has in every other field; the buttons
     ride at the right end of the same line so nothing below shifts. */
  .feldkopf {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    min-height: 22px;
    margin-bottom: 6px;
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
    color: var(--text-leise);
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
  /* A section head: a house sign, then the group's name in the quiet label
     weight — a landmark the eye can navigate by without shouting. */
  .abschnitt {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-leise);
    margin: 0 0 12px;
  }
  /* The inpainting header drops to float level with Hires-Fix opposite it,
     and off the seed pills above. */
  /* The tile carries no label of its own, so it starts where the FIELDS in
     the column beside it start, not where their labels do: this gap is one
     label plus the air under it, which is exactly what a labelled field has
     above its own box. */
  .startabschnitt {
    margin-top: 19px;
  }
  .abschnitt svg {
    width: 15px;
    height: 15px;
    fill: none;
    stroke: var(--text-leise);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  /* The seed plan: small pills under the field, the active one filled —
     the same grammar the tool pills speak everywhere else. */
  /* Pulled up against the field they belong to, and held clear of whatever
     follows: they are part of the seed, not a row of their own. */
  .seedplan {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    /* Tight under the field they belong to. The gap below is measured, not
       guessed: it makes the seed and its pills fill exactly two rows of the
       rhythm this column shares with the one beside it, so everything below
       lands back on a line. */
    margin-top: 4px;
    margin-bottom: 41px;
  }
  .seedpille,
  .seedletzter {
    font: inherit;
    font-size: 12px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text-still);
    /* Controls, not pills: they set something, so they take the corner every
       other control in the window wears. */
    border-radius: 9px;
    padding: 4px 10px;
    cursor: pointer;
  }
  .seedpille.an {
    background: var(--linie-stark);
    color: var(--text);
  }
  .seedletzter {
    margin-left: auto;
    font-variant-numeric: tabular-nums;
  }
  .seedpille:hover,
  .seedletzter:hover {
    background: var(--linie);
  }
  /* One group, one size: four cells of equal width, so no number looks
     more important than another. */
  .raster {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 12px;
  }
  /* The one action, on its own bar so it is never lost among the fields. */
  .fussbalken {
    display: flex;
    justify-content: flex-end;
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid var(--linie);
  }
  .hinweis {
    margin: 4px 0 0;
    font-size: 11.5px;
    line-height: 1.45;
    color: var(--text-still);
  }
  /* No gap of its own: the fields carry their spacing themselves, and a gap
     on top of that would set this column on a different rhythm than the one
     beside it — the two would stop lining up row for row. */
  .klappinhalt {
    display: flex;
    flex-direction: column;
    gap: 0;
    /* No head start of its own: the section heading above already sets the
       distance, and anything added here would drop this column's first field
       below the one it stands beside. */
    margin-top: 0;
  }
  /* The Image-Turbo control in the window header: a pill with the label and
     the big gauge, the whole thing is the switch. */
  .turbokopf {
    display: inline-flex;
    align-items: center;
    /* The same height every control in the window stands at, header
       included — a taller button up there reads as a different kind of
       thing than the ones below it. */
    height: 36px;
    box-sizing: border-box;
    gap: 9px;
    border: 1px solid var(--linie-stark);
    /* A control, not a pill: it switches something on and off, so it takes
       the corner every other control in the window wears. */
    border-radius: 9px;
    padding: 6px 10px 6px 15px;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 13.5px;
    cursor: pointer;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }
  .turbokopf:hover:not(:disabled) {
    background: var(--linie);
    color: var(--text);
  }
  .turbokopf.an {
    color: var(--text);
    border-color: var(--kontrast, var(--linie-stark));
  }
  .turbokopf:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .turbowort {
    white-space: nowrap;
    letter-spacing: 0.01em;
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
  /* The one action, in the same shape every action button in the house
     wears — no colour of its own, so the window matches the rest of the
     terminal instead of shouting. */
  /* Two halves of one line, ending flush with the picture above — equal
     shares, so neither reads as the more important of the two. */
  /* A sign never shrinks with the row it sits in, and it never takes the
     label's letter-spacing. */
  .feldzeichen {
    flex: none;
    color: var(--text-leise);
  }
  .startzeile {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    margin-top: 12px;
  }
  .startfeld {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  /* The button's half: the button fills it, a mask preview and its remove
     cross ride beside it when there is a mask. */
  .maskenfeld {
    flex-direction: row;
    align-items: center;
  }
  .maskenfeld .maskenknopf { flex: 1 1 auto; }
  /* The slider's own row: the track fills what is left, the figure sits
     right against it — a wide gap there would read as two separate things. */
  .startfeld .lorazeile {
    gap: 8px;
    margin-bottom: 0;
  }
  .startfeld .zahl { width: auto; }

  /* The same timeline the mask editor wears: a hairline to travel along and
     the house playhead riding above it. Drawn from scratch because the
     browser's own slider cannot be reshaped; the element keeps its behaviour
     and gives up only its looks. */
  .staerke {
    appearance: none;
    -webkit-appearance: none;
    flex: 1 1 auto;
    min-width: 0;
    height: 12px;
    margin: 0;
    background: none;
    cursor: pointer;
  }
  .staerke::-webkit-slider-runnable-track {
    height: 2px;
    border-radius: 2px;
    background: var(--text-leise);
  }
  .staerke::-moz-range-track {
    height: 2px;
    border-radius: 2px;
    background: var(--text-leise);
  }
  /* Point down, sitting ON the line: a mark that straddles the line would
     hide the spot it marks. */
  .staerke::-webkit-slider-thumb {
    appearance: none;
    -webkit-appearance: none;
    width: 12px;
    height: 8px;
    margin-top: -7px;
    background: var(--text-leise);
    clip-path: polygon(0 0, 100% 0, 50% 100%);
  }
  .staerke::-moz-range-thumb {
    width: 12px;
    height: 8px;
    border: none;
    border-radius: 0;
    background: var(--text-leise);
    clip-path: polygon(0 0, 100% 0, 50% 100%);
  }
  .staerke:hover::-webkit-slider-thumb { background: var(--text); }
  .staerke:hover::-moz-range-thumb { background: var(--text); }
  /* The same weight as the window's own action button: opening the mask
     editor is a step of its own, not a footnote to the picture above it. */
  .maskenknopf {
    font: inherit;
    /* The same size the fields set their text in: equal height alone does not
       make two controls look equal — the writing inside has to match too. */
    font-size: 13.5px;
    border: 1px solid var(--linie-stark);
    /* And the same ground: a filled bright face reads as LARGER than an
       outlined dark one of exactly the same measure, which is why these
       buttons looked taller than the fields beside them however often the
       numbers said otherwise. Outlined like a field, filled only on hover. */
    background: var(--bg-erhoben);
    color: var(--text);
    border-radius: 10px;
    padding: 9px 18px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .maskenknopf:disabled {
    opacity: 0.4;
    cursor: default;
  }
  .maskenknopf:not(:disabled):hover { background: var(--linie-stark); }

  .zeichnen {
    font: inherit;
    font-size: 13.5px;
    height: 36px;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    border: 1px solid var(--linie-stark);
    background: var(--linie-stark);
    color: var(--text);
    border-radius: 10px;
    padding: 9px 18px;
    cursor: pointer;
    transition: background 0.12s;
  }
  /* Where the bolt sat: how many pictures are in the works, same monospace as
     every other figure in the window. */
  .zeichenzahl {
    display: inline-grid;
    place-items: center;
    min-width: 20px;
    height: 20px;
    padding: 0 5px;
    border-radius: 6px;
    background: var(--bg-erhoben);
    color: var(--text);
    font: 600 12px var(--schrift-fest, ui-monospace, monospace);
  }
  /* Two symmetric columns under the prompt — the gap between them is a row's
     own measure, so the two halves read as one grid. Align to the top so a
     collapsed fold does not stretch the shorter column. The row margins
     inside each column carry the vertical spacing, as everywhere else. */
  /* The two columns end on the same line: stretched to a common height, and
     the last field of the shorter one pushed down to meet it. Measured by the
     layout rather than by a number written here, so it holds at every picture
     shape the reference tile takes. */
  .spalten {
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 22px;
    align-items: stretch;
  }
  .spalte {
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .spalte .klappinhalt {
    flex: 1 1 auto;
  }
  /* One exact row height for every block in this column. Left of it the grid
     lays its rows out itself and lands on whole pixels; here the height comes
     from a label plus a field, and a fraction of a pixel in the label's line
     box was enough to push each row one pixel off its neighbour. Written
     down, both columns step the same. */
  .spalte .klappinhalt > .feld,
  .spalte .klappinhalt > .raster {
    min-height: 55px;
    box-sizing: border-box;
    margin-bottom: 14px;
  }
  /* Fields sitting INSIDE such a row carry no gap of their own — the row
     already holds one, and a second would make that row taller than the
     line it shares with the column beside it. */
  .spalte .klappinhalt > .raster > .feld {
    margin-bottom: 0;
  }
  /* Every button in this window stands as tall as a field, so a row of
     buttons and a row of fields read as the same kind of line. */
  .maskenknopf {
    height: 36px;
    box-sizing: border-box;
    padding: 0 18px;
  }
  .spalte .klappinhalt > :last-child {
    margin-top: auto;
    /* Nothing follows it, so the gap it carries for a neighbour would only
       lift it off the line it is meant to end on. */
    margin-bottom: 0;
  }
  /* Too narrow for two: fall back to one column so nothing is squeezed. */
  @media (max-width: 640px) {
    .spalten {
      grid-template-columns: 1fr;
    }
  }
  .zeichnen:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .zeichnen:not(:disabled):hover {
    background: var(--linie);
  }
</style>
