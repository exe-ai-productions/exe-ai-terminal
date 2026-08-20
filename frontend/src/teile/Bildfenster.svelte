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
  import Schalter from './Schalter.svelte'
  import Fenster from './Fenster.svelte'
  import MaskenEditor from './MaskenEditor.svelte'
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
  let hires = $state(false)
  let hiresScale = $state(2)
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
        if (!modell || !modelle.includes(modell)) modell = modelle[0] ?? ''
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

<Fenster bind:offen titel={t('bild.titel')} art="bild" schrumpfen>
  {#snippet kopf()}
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
      <Turbozeichen an={turboAn} groesse={28} />
    </button>
  {/snippet}
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
      <div class="feldkopf">
        <span class="titel">{t('bild.prompt')}</span>
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
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M12 3v3M12 18v3M5 12H2M22 12h-3M6.3 6.3l2 2M15.7 15.7l2 2M17.7 6.3l-2 2M8.3 15.7l-2 2" />
            </svg>
            {verbessert ? t('bild.verbessern_laeuft') : t('bild.verbessern')}
          </button>
        </div>
      </div>
      <textarea class="feldein gross" bind:value={prompt} rows="3" disabled={verbessert}
                placeholder={t('bild.prompt_platzhalter')}></textarea>
      <label class="feld eng">
        <span>{t('bild.negativ')}</span>
        <textarea class="feldein" bind:value={negativ} rows="2"></textarea>
      </label>
    </div>

    <div class="feld">
      <span>{t('bild.modell')}</span>
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

    <label class="feld">
      <span>{t('bild.seed')}</span>
      <input class="feldein fest" bind:value={seed} placeholder={t('bild.seed_zufall')} inputmode="numeric" />
    </label>
    <!-- The seed plan, worn as small pills like the LoRA stack: how the
         next draw picks its seed. Beside it the last drawn seed — one
         click takes it over and holds it, so "continue exactly here" is a
         deliberate act and chance stays the default. -->
    <div class="seedplan">
      {#each [['zufall', t('bild.seed_zufall')], ['fest', t('bild.seed_fest')], ['plus', t('bild.seed_plus')], ['minus', t('bild.seed_minus')]] as [wert, name]}
        <button class="seedpille" class:an={seedModus === wert}
                onclick={() => (seedModus = wert)}>{name}</button>
      {/each}
      {#if seedlage.letzter !== null}
        <button class="seedletzter" onclick={seedUebernehmen}
                title={t('bild.seed_uebernehmen')}>
          {t('bild.seed_zuletzt', { zahl: seedlage.letzter })}
        </button>
      {/if}
    </div>

    <!-- Start from a picture (inpainting): it fills the foot of the left
         column. Pushed down so its heading floats level with Hires-Fix
         across in the right column, and not glued to the seed pills. -->
    <div class="abschnitt startabschnitt">
      <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="M4 17l4.5-5 3.5 4 3-2.5L20 17"/></svg>
      {t('bild.gruppe_startbild')}
    </div>
    <div class="feld">
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

      <label class="feld" class:gesperrt={!startbild}>
        <span>{t('bild.staerke')}</span>
        <div class="lorazeile">
          <input class="staerke" type="range" min="0" max="1" step="0.05"
                 bind:value={staerke} disabled={!startbild} aria-label={t('bild.staerke')} />
          <span class="zahl">{staerke.toFixed(2)}</span>
        </div>
        <p class="hinweis">{t('bild.staerke_hinweis')}</p>
      </label>
    {/if}

      </div>
      <div class="spalte">

    <!-- Fine-tuning: the LoRA stack and the quality companions. No longer
         folded away — the second column gives it a home of its own, so it is
         always in view and everything fits in one window. -->
    <div class="abschnitt">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 L20.5 7.5 L12 12 L3.5 7.5 Z"/><path d="M3.5 7.5 V16 L12 20.5 L20.5 16 V7.5"/><path d="M12 12 V20.5"/></svg>
      {t('bild.gruppe_feinschliff')}
    </div>
    <div class="klappinhalt">
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
            <button class="klein-knopf" onclick={() => api.bildBegleiterOrdner('lora').catch(() => {})}>
              {t('bild.lora_ordner')}
            </button>
          </div>
          <p class="hinweis">{t('bild.lora_eine_staerke')}</p>
        </div>

        <div class="feld">
          <span>{t('bild.embedding')}</span>
          <div class="lorafuss">
            <button class="klein-knopf" onclick={() => api.bildBegleiterOrdner('embedding').catch(() => {})}>
              {t('bild.embedding_ordner')}
            </button>
          </div>
          <p class="hinweis">{t('bild.embedding_hinweis')}</p>
        </div>

        <div class="feld">
          <span>{t('bild.vae')}</span>
          <Auswahlfeld bind:wert={vae} eintraege={[{ wert: '', text: t('bild.vae_keins') }, ...alsAuswahl(vaeListe)]}
                       beschriftung={t('bild.vae')} />
        </div>
        <label class="feld">
          <span>{t('bild.clip_skip')}</span>
          <Zahlenfeld bind:wert={clipSkip} min={0} max={12} schritt={1} nullwort={t('bild.clip_auto')} />
        </label>
        <div class="feld">
          <span>{t('bild.adetailer')}</span>
          <Auswahlfeld bind:wert={adModell} eintraege={[{ wert: '', text: t('bild.adetailer_keins') }, ...alsAuswahl(yoloListe)]}
                       beschriftung={t('bild.adetailer')} />
        </div>
        {#if adModell}
          <label class="feld">
            <span>{t('bild.ad_prompt')}</span>
            <input class="feldein" bind:value={adPrompt} placeholder={t('bild.ad_prompt_platzhalter')} />
          </label>
        {/if}

        <div class="feld">
          <div class="schalterzeile">
            <span>{t('bild.hires')}</span>
            <Schalter an={hires} beschriftung={t('bild.hires')} onschalten={() => (hires = !hires)} />
          </div>
          {#if hires}
            <label class="klein" style="margin-top:10px">
              <span>{t('bild.hires_faktor')}</span>
              <Zahlenfeld bind:wert={hiresScale} min={1} max={4} schritt={1} />
            </label>
          {/if}
          <p class="hinweis">{t('bild.hires_hinweis')}</p>
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
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-leise);
  }
  /* The motive block — prompt, its negative, the model — set apart at the
     top on the raised ground, because it is the part that decides the
     picture. Everything below configures; this is the picture itself. */
  .motiv {
    background: var(--bg-seite);
    border: 1px solid var(--linie);
    border-radius: 12px;
    padding: 14px;
    /* Clears the Image-Turbo pill riding in the window corner above: the
       box must start below the pill's lower edge, never under it. The margin
       collapses with the title's 12px bottom margin — only the larger of the
       two survives, so this value IS the whole title-to-box distance. */
    margin-top: 22px;
    margin-bottom: 16px;
  }
  .motiv .feldkopf .titel {
    color: var(--text);
    font-size: 13px;
    font-weight: 600;
    text-transform: none;
    letter-spacing: 0.01em;
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
  .startabschnitt {
    margin-top: 34px;
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
  .seedplan {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 6px;
  }
  .seedpille,
  .seedletzter {
    font: inherit;
    font-size: 12px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text-still);
    border-radius: 99px;
    padding: 3px 10px;
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
  .klappinhalt {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-top: 14px;
  }
  .schalterzeile {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  /* The Image-Turbo control in the window header: a pill with the label and
     the big gauge, the whole thing is the switch. */
  .turbokopf {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    padding: 6px 10px 6px 15px;
    background: none;
    color: var(--text-leise);
    font: inherit;
    font-size: 13px;
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
  .zeichnen {
    font: inherit;
    font-size: 13.5px;
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
  .spalten {
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 22px;
    align-items: start;
  }
  .spalte {
    min-width: 0;
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
