<script>
  import Werkzeugfrage from './Werkzeugfrage.svelte'
  import Arbeitsordner from './Arbeitsordner.svelte'
  import Benutzerfrage from './Benutzerfrage.svelte'
  import { dock, dockDatei } from '../lib/notizen.svelte.js'
  import Ordnerpillen from './Ordnerpillen.svelte'
  import Skillliste from './Skillliste.svelte'
  import Bildfenster from './Bildfenster.svelte'
  import Tempoanzeige from './Tempoanzeige.svelte'
  import Leuchtpunkt from './Leuchtpunkt.svelte'
  import { gefiltert, skillAmAnfang, skills, skillsLaden } from '../lib/skills.svelte.js'
  import { maskeOeffnen, ordnerListe } from '../lib/arbeitsordner.svelte.js'
  import { einreihen } from '../lib/warteschlange.svelte.js'
  import { api } from '../lib/api.js'
  import { t } from '../lib/texte.svelte.js'
  import {
    zustand, werkzeugfrageBeantworten, benutzerfrageBeantworten, melde, aktuellerChat,
  } from '../lib/zustand.svelte.js'

  let { senden, abbrechen, bildErzeugen, bildStoppen, bildZeichnen, bildLokalLaeuft = false, tempo, schlank = false, gruss = null } = $props()

  /* The three things the bar can be doing, in the house's colours: waiting
     for the first token is a wait, a running answer is a run, and anything
     else is simply ready. */
  const PUNKTFARBE = { bereit: 'gruen', prompt: 'gelb', laeuft: 'blau' }

  let text = $state('')
  let feld = $state(null)
  /* Vision: one image per message. The chip
     above the field shows it, ✕ removes it, it is sent along with the
     text. */
  let anhang = $state(null) // { datei, url }
  let menueOffen = $state(false)
  let dateiwahl = $state(null)
  /* Image mode (part 2): the raw prompt goes to the generator. On
     enabling, the image server is honestly checked — the red line says
     when none is there (reachability is the operator's/arbiter's
     business). */
  let bildmodus = $state(false)
  /* The parameter window for the picture made on this machine. */
  let bildfensterOffen = $state(false)
  /* Picture servers configured by the user. Empty on a normal installation,
     and then the image mode entry does not appear at all — one picture
     entry in the menu, not two that sound alike. Fetched when the menu
     opens rather than at startup: nobody needs it until then. */
  let eigeneBildserver = $state([])
  $effect(() => {
    if (!menueOffen) return
    api.bildEndpunkte().then((e) => (eigeneBildserver = e)).catch(() => (eigeneBildserver = []))
  })
  /* Their names, as one line. Built here rather than in the markup: an
     expression that wraps across lines reads to the house-rule test as
     hard-coded words, and it is easier to read here anyway. */
  const bildserverNamen = $derived(eigeneBildserver.map((e) => e.id).join(' · '))
  let bildserverDa = $state(true)
  let erzeugtGerade = $state(false)

  /* The slash list. It is open only while a slash stands at the very front
     and no space has followed the name yet — from the first space on, the
     rest of the line is the request and the list is in the way. */
  let skillDran = $state(0)
  const skillFilter = $derived(/^\/([a-z0-9-]*)$/.exec(text)?.[1] ?? null)
  const skillTreffer = $derived(skillFilter === null ? [] : gefiltert(skillFilter))
  const skillOffen = $derived(!bildmodus && skillTreffer.length > 0)

  $effect(() => {
    void skillFilter
    skillDran = 0
  })

  if (!skills.geladen) skillsLaden()

  function skillWaehlen(eintrag) {
    /* The trailing space is the point: it closes the list and starts the
       request, so picking and typing on are one movement. */
    text = `/${eintrag.name} `
    feld?.focus()
    hoeheAnpassen()
  }

  async function bildmodusSchalten() {
    menueOffen = false
    bildmodus = !bildmodus
    if (bildmodus) {
      anhangEntfernen()
      dokumentEntfernen()
      try {
        const endpunkte = await api.bildEndpunkte()
        bildserverDa = endpunkte.some((e) => e.erreichbar)
      } catch {
        bildserverDa = false
      }
      /* An unreachable server is a notice, not a label. It used to be a red
         line glued under the prompt, where it stayed for as long as the mode
         did — the house has one place for something that went wrong, and
         this is it. */
      if (!bildserverDa) melde(t('fehler.bildserver_fehlt'), 'fehler')
    }
    setTimeout(() => feld?.focus(), 60)
  }

  const laeuftGerade = $derived(Boolean(zustand.laeuft))

  /* The speed belongs to the run producing it, and a run belongs to one
     chat. `tempo` is app-wide, so standing in another conversation while an
     answer is written elsewhere would show that answer's numbers here, over
     a chat where nothing is happening. */
  const tempoHier = $derived(!zustand.laeuft || zustand.laeuft.chatId === zustand.aktiverChat)
  const ordnerAnzahl = $derived(ordnerListe().length)

  /* The thinking switch (interface milestone A: a light
     bulb with rays): only operable if the endpoint demonstrably supports
     switching — capabilities.thinking comes from the discovery's native
     detection, the config can override. The device remembers the choice
     per model; the default is ON. */
  const denkFaehig = $derived(
    Boolean(zustand.modelle.find((m) => m.id === zustand.modellId)?.capabilities?.thinking),
  )
  let denken = $state(true)
  $effect(() => {
    if (!zustand.modellId) return
    denken = localStorage.getItem('denken:' + zustand.modellId) !== 'aus'
  })
  function denkenSchalten() {
    if (!denkFaehig) return
    denken = !denken
    localStorage.setItem('denken:' + zustand.modellId, denken ? 'an' : 'aus')
  }

  const leer = $derived(!text.trim() && !anhang && !dokumentAnhang)
  /* The action button shows the stop sign only while a run has nothing to
     send beside it — with something in the field, sending (into the queue)
     is what the hand is after. Image generation is not queued and keeps
     its own stop. */
  const stoppt = $derived(erzeugtGerade || bildLokalLaeuft || (laeuftGerade && leer))
  const BILD_TYPEN = ['image/png', 'image/jpeg', 'image/webp']

  /* Document attachment (4.1): image OR document, never
     both — the first cut stays simple. No vision requirement: every
     model can read text. */
  let dokumentAnhang = $state(null)
  let dokumentwahl = $state(null)
  const DOKUMENT_ENDUNGEN = ['.pdf', '.txt', '.md']

  function istDokument(datei) {
    const name = (datei?.name || '').toLowerCase()
    return DOKUMENT_ENDUNGEN.some((endung) => name.endsWith(endung))
  }

  function dokumentSetzen(datei) {
    // The drop path also respects the feature switch from the config.
    if (!zustand.features.document_upload) return
    if (!datei || !istDokument(datei)) {
      if (datei) melde(t('fehler.dokument_typ'), 'fehler')
      return
    }
    anhangEntfernen()
    dokumentAnhang = { datei }
  }

  function dokumentEntfernen() {
    dokumentAnhang = null
  }

  const dokumentMeta = $derived(
    !dokumentAnhang
      ? ''
      : `${dokumentAnhang.datei.name.split('.').pop().toUpperCase()} · ${Math.max(1, Math.round(dokumentAnhang.datei.size / 1024))} KB`,
  )
  /* Only offer what the chosen model can actually see — the capability
     comes from the endpoint's configuration, never from guesswork. */
  const visionFaehig = $derived(
    Boolean(zustand.modelle.find((m) => m.id === zustand.modellId)?.capabilities?.vision),
  )

  function anhangSetzen(datei) {
    if (!datei || !BILD_TYPEN.includes(datei.type)) {
      if (datei) melde(t('fehler.bild_typ'), 'fehler')
      return
    }
    if (!visionFaehig) {
      melde(t('fehler.kein_vision'), 'hinweis')
      return
    }
    if (anhang) URL.revokeObjectURL(anhang.url)
    anhang = { datei, url: URL.createObjectURL(datei) }
    dokumentAnhang = null
  }

  function anhangEntfernen() {
    if (anhang) URL.revokeObjectURL(anhang.url)
    anhang = null
  }

  function einfuegen(ereignis) {
    const eintrag = [...(ereignis.clipboardData?.items || [])].find((e) =>
      e.type.startsWith('image/'),
    )
    if (!eintrag) return
    ereignis.preventDefault()
    anhangSetzen(eintrag.getAsFile())
  }

  async function fallenlassen(ereignis) {
    ereignis.preventDefault()
    /* A file dragged out of the document dock: only its id travels, and the
       dock hands over the file itself. From there it is an attachment like
       any other — the field does not need to know where it came from. */
    const ausDock = ereignis.dataTransfer?.getData('application/x-exe-dock')
    if (ausDock) {
      const eintrag = dock.liste.find((e) => e.id === ausDock)
      if (!eintrag) return
      const datei = await dockDatei(eintrag)
      if (istDokument(datei)) dokumentSetzen(datei)
      else anhangSetzen(datei)
      return
    }
    const datei = ereignis.dataTransfer?.files?.[0]
    if (!datei) return
    // The switch point: PDF/TXT/MD are documents, everything else tries
    // the image path.
    if (istDokument(datei)) dokumentSetzen(datei)
    else anhangSetzen(datei)
  }

  /* The field grows with the text. Reset to 'auto' first, otherwise
     scrollHeight only knows the previous state and the field never
     shrinks again on deletion. Scrolling only starts at 40 percent of
     the window height — before that there'd be a bar in the middle of
     the text. */
  function hoeheAnpassen() {
    if (!feld) return
    const hoechst = Math.round(window.innerHeight * 0.4)
    feld.style.height = 'auto'
    const gewuenscht = feld.scrollHeight
    feld.style.height = Math.min(gewuenscht, hoechst) + 'px'
    feld.style.overflowY = gewuenscht > hoechst ? 'auto' : 'hidden'
  }

  $effect(() => {
    text
    schlank
    hoeheAnpassen()
    /* Re-measure once the run-up is through: during the ride,
       scrollHeight delivers half-finished values, and the send arrow
       centers on the wrong height — only the first keystroke set it
       straight. This is rule 3.12 (never animate paddings along) from
       the other side: don't animate along AND measure once more after
       the ride. The bug had thus shown up three times. */
    const nachlauf = setTimeout(hoeheAnpassen, 850)
    return () => clearTimeout(nachlauf)
  })

  function taste(ereignis) {
    /* While the list is open the arrow keys and Enter belong to it. Escape
       gets out without clearing what was typed — the slash may well have
       been meant. */
    if (skillOffen) {
      if (ereignis.key === 'ArrowDown') {
        ereignis.preventDefault()
        skillDran = Math.min(skillDran + 1, skillTreffer.length - 1)
        return
      }
      if (ereignis.key === 'ArrowUp') {
        ereignis.preventDefault()
        skillDran = Math.max(skillDran - 1, 0)
        return
      }
      if (ereignis.key === 'Enter' || ereignis.key === 'Tab') {
        ereignis.preventDefault()
        skillWaehlen(skillTreffer[skillDran])
        return
      }
      if (ereignis.key === 'Escape') {
        ereignis.preventDefault()
        text += ' '
        return
      }
    }
    if (ereignis.key === 'Enter' && !ereignis.shiftKey) {
      ereignis.preventDefault()
      absenden()
    }
  }

  async function absenden() {
    const inhalt = text.trim()
    if (bildmodus) {
      /* `bildLokalLaeuft` as well as the local flag: a picture started from
         the picture window sets only the app-wide one, and the generator
         takes one job at a time. Without this the second order goes out,
         the service refuses it, and the refusal lands on top of the answer
         that was still being written. The stop button beside this already
         treats the two as one fact. */
      if (!inhalt || erzeugtGerade || bildLokalLaeuft || !bildserverDa) return
      erzeugtGerade = true
      text = ''
      try {
        await bildErzeugen(inhalt)
      } finally {
        erzeugtGerade = false
      }
      return
    }
    if (!inhalt && !anhang && !dokumentAnhang) return
    /* A run with no chat behind it: the chat was left with ⌘N or the "+"
       button while an answer was still going. Queueing here would file the
       message under no conversation at all — it would then be sent by
       nobody and shown in every new chat. The old refusal is the right
       answer in that corner, and the text stays in the field. */
    if (laeuftGerade && !zustand.aktiverChat) {
      melde(t('eingabe.laeuft_schon'))
      return
    }
    const bild = anhang?.datei ?? null
    const dokument = dokumentAnhang?.datei ?? null
    text = ''
    anhangEntfernen()
    dokumentEntfernen()
    /* The picked skill travels beside the message, not inside it. The
       "/name" stays in the text on purpose: it is what was typed, so it is
       what gets stored, and the chat still shows it after a reload. */
    const skill = skillAmAnfang(inhalt)?.name ?? null
    // The thinking switch only goes along if the model really has it.
    const auftrag = { inhalt, bild, dokument, denken: denkFaehig ? denken : null, skill }
    /* An answer is still running: the message lines up instead of being
       swallowed. The field empties either way, so typing on feels the same
       whether something runs or not.

       Unless the model is the one waiting: a standing question holds the
       run open, so `laeuftGerade` is true — but what was typed IS the
       answer to that question, not a new message. Queueing it would leave
       the run waiting for something that is sitting in a queue waiting for
       the run. `senden` knows what to do with it. */
    if (laeuftGerade && !zustand.benutzerfrage) {
      einreihen(zustand.aktiverChat, auftrag)
      return
    }
    senden(auftrag.inhalt, bild, dokument, auftrag.denken, skill)
  }

  export function fokus() {
    feld?.focus()
  }
</script>

<!-- Dragging is caught by the WHOLE window: whoever
     aims off-target should not get a new browser window with the image
     but the attachment — dragging in anywhere suffices, as one is used
     to. -->
<svelte:window
  onresize={hoeheAnpassen}
  onclick={() => (menueOffen = false)}
  ondragover={(e) => e.preventDefault()}
  ondrop={fallenlassen}
/>

<!-- The parameter window for the picture made on this machine. Lives here
     because it is opened from the plus menu, and hands its finished pair up
     to the chat, which is the only place that owns the history. -->
<Bildfenster bind:offen={bildfensterOffen} chatId={zustand.aktiverChat} zeichnen={bildZeichnen} />

<div class="zone" class:schlank>
  <!-- Hangs above the field and is exactly as wide. Nothing shifts: the
       zone sits at the bottom edge anyway, the box grows upward into the
       history. -->
  {#if zustand.werkzeugfrage}
    <div class="frageplatz">
      <Werkzeugfrage frage={zustand.werkzeugfrage} antworten={werkzeugfrageBeantworten} />
    </div>
  {/if}

  <!-- The model's own question, in the same spot: it waits for an answer
       just as the confirmation does. -->
  {#if zustand.benutzerfrage}
    <div class="frageplatz">
      <Benutzerfrage frage={zustand.benutzerfrage} antworten={benutzerfrageBeantworten} />
    </div>
  {/if}

  <!-- The slash list hangs off the same kind of anchor as the menu: zero
       pixels tall, as wide as the field, growing upward into the history.
       Inside the field it would be clipped by overflow:hidden. -->
  <div class="menueplatz">
    {#if skillOffen}
      <Skillliste eintraege={skillTreffer} dran={skillDran} waehlen={skillWaehlen} />
    {/if}
  </div>

  <!-- The menu anchor: zero pixels tall, exactly as wide as the field —
       same construction as the confirmation slot. The menu itself hangs
       absolutely off it and grows upward, flush with the field's outer
       edge (approved mockup). Not inside the field: overflow:hidden
       would clip it. -->
  <div class="menueplatz">
  <div class="klappmenue" class:offen={menueOffen} role="menu" onclick={(e) => e.stopPropagation()}>
    <button
      role="menuitem"
      class:gesperrt={!visionFaehig}
      onclick={() => {
        if (!visionFaehig) return
        menueOffen = false
        dateiwahl?.click()
      }}
    >
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round">
        <rect x="3" y="5" width="18" height="14" rx="3" />
        <circle cx="8.5" cy="10" r="1.6" />
        <path d="M21 16 L15.5 11 L7 19" />
      </svg>
      <span>
        {t('eingabe.anhaengen')}
        <span class="menuehinweis">
          {visionFaehig ? t('eingabe.anhang_hinweis') : t('fehler.kein_vision')}
        </span>
      </span>
    </button>
    <!-- Documents (4.1): no vision requirement — every model can read
         text. The dog-ear is the same icon as with the Notion tools.
         The entry only appears if the feature is on in the config
         (interface milestone C) — the API additionally locks down
         itself. -->
    {#if zustand.features.document_upload}
    <button
      role="menuitem"
      onclick={() => {
        menueOffen = false
        dokumentwahl?.click()
      }}
    >
      <svg width="17" height="17" viewBox="0 0 64 64" fill="none" stroke="currentColor"
           stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M16 8 H38 L48 18 V56 H16 Z" />
        <path d="M38 8 V18 H48" stroke-width="4.5" />
        <path d="M25 34 H39 M25 44 H39" stroke-width="4.5" />
      </svg>
      <span>
        {t('eingabe.dokument_anhaengen')}
        <span class="menuehinweis">{t('eingabe.dokument_hinweis')}</span>
      </span>
    </button>
    {/if}
    <!-- The working folder: this is where the model is
         given a place to work. Same drawer as the attachments — everything
         you hand the chat lives in one menu. The hint line carries how many
         folders are shared, so the entry says the state even when the pills
         are out of sight. -->
    <button
      role="menuitem"
      onclick={() => {
        menueOffen = false
        maskeOeffnen()
      }}
    >
      <svg width="17" height="17" viewBox="0 0 64 64" fill="none" stroke="currentColor"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M11 50 V14 H27 L32 21 H53 V50 Z" stroke-width="5" />
        <path d="M11 26 H53" stroke-width="4.5" />
      </svg>
      <span>
        {t('arbeitsordner.titel')}
        <span class="menuehinweis">
          {ordnerAnzahl
            ? t('arbeitsordner.anzahl').replace('{anzahl}', ordnerAnzahl)
            : t('arbeitsordner.keiner')}
        </span>
      </span>
    </button>
    <!-- The picture made HERE. Its own entry beside the image mode above:
         that one talks to a picture server, this one runs a program on this
         machine with nothing leaving it — and it has six numbers, which is
         why it opens a window instead of switching the input field. -->
    <button
      role="menuitem"
      onclick={() => {
        menueOffen = false
        bildfensterOffen = true
      }}
    >
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <circle cx="8.5" cy="9.5" r="1.6" />
        <path d="M4 17l4.5-5 3.5 4 3-2.5L20 17" />
      </svg>
      <span>
        {t('bild.titel')}
        <span class="menuehinweis">{t('bild.hier_hinweis')}</span>
      </span>
    </button>
    <!-- Image mode belongs to a picture server somebody configured
         themselves. Without one it is not a feature that is switched off,
         it is a feature that does not apply — and standing beside "make a
         picture" it read like its twin. -->
    {#if zustand.features.image_generation && eigeneBildserver.length}
    <button role="menuitem" onclick={bildmodusSchalten}>
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20 4 C14 6 9 10 7.5 14.5 C6.8 16.6 8 18 10 17.5 C14.5 16 18 11 20 4 Z" />
        <path d="M9 17.5 C8 19.5 7 20.5 4 21 C5.5 18.5 5.5 17.5 6.5 15.5" />
      </svg>
      <span>
        {t('eingabe.bildmodus')}
        <!-- The name of the server it talks to. "Raw prompt to the
             generator" said what it does technically and nothing about
             which of the two entries this is. -->
        <span class="menuehinweis">{bildserverNamen}</span>
      </span>
      {#if bildmodus}<span class="haken">✓</span>{/if}
    </button>
    {/if}
  </div>
  </div>
  <input
    type="file"
    accept="image/png,image/jpeg,image/webp"
    bind:this={dateiwahl}
    onchange={(e) => { anhangSetzen(e.currentTarget.files?.[0]); e.currentTarget.value = '' }}
    hidden
  />
  <input
    type="file"
    accept=".pdf,.txt,.md"
    bind:this={dokumentwahl}
    onchange={(e) => { dokumentSetzen(e.currentTarget.files?.[0]); e.currentTarget.value = '' }}
    hidden
  />

  <!-- The folders stand here only while the chat is still empty — this is
       where they are set, before there is anything to say. With the first
       message they fly up into the header and live there from then on.
       The mask itself stays mounted either way; it is opened from the plus
       menu here and from the plus among the pills up there. -->
  {#if schlank}
    <Ordnerpillen ort="leiste" />
  {/if}
  <Arbeitsordner />

  {#if anhang || dokumentAnhang}
    <!-- The attachment docks ABOVE the field: one
         spot for both modes — in the centered start, the chip in the
         field collided with the plus. Documents wear the dog-ear instead
         of the mini preview. -->
    <div class="anhangplatz">
      {#if anhang}
        <div class="anhang">
          <img src={anhang.url} alt="" />
          <span class="anhangname">{anhang.datei.name}</span>
          <button class="anhang-x" onclick={anhangEntfernen}
                  aria-label={t('eingabe.anhang_entfernen')}>✕</button>
        </div>
      {:else}
        <div class="anhang">
          <svg class="dok-zeichen" width="22" height="22" viewBox="0 0 64 64" fill="none"
               stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M16 8 H38 L48 18 V56 H16 Z" />
            <path d="M38 8 V18 H48" stroke-width="4.5" />
            <path d="M25 34 H39 M25 44 H39" stroke-width="4.5" />
          </svg>
          <span class="anhangname">
            {dokumentAnhang.datei.name}
            <span class="dok-meta">{dokumentMeta}</span>
          </span>
          <button class="anhang-x" onclick={dokumentEntfernen}
                  aria-label={t('eingabe.dokument_entfernen')}>✕</button>
        </div>
      {/if}
    </div>
  {/if}

  <div class="eingabe" class:im-bildmodus={bildmodus}>
    <!-- In the centered start state, the footer is folded shut; this
         button keeps the field operable anyway without making it
         two-lined. -->
    {#if schlank}
      <button class="schlank-knopf" class:leer onclick={absenden}
              title={t('eingabe.senden')} aria-label={t('eingabe.senden')}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 19V5M5 12l7-7 7 7" />
        </svg>
      </button>
      <!-- The plus in the centered start too: the
           first question WITH an image is a core entry point. Mirror
           image of the arrow. -->
      <button
        class="plus schlank-plus"
        class:offen={menueOffen}
        aria-expanded={menueOffen}
        aria-label={t('eingabe.anhaengen')}
        onclick={(e) => { e.stopPropagation(); menueOffen = !menueOffen }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
      </button>
    {/if}

    <textarea
      bind:this={feld}
      bind:value={text}
      rows="1"
      placeholder={bildmodus ? t('eingabe.bild_platzhalter') : (gruss || t('eingabe.platzhalter'))}
      onkeydown={taste}
      onpaste={einfuegen}
      aria-label={t('eingabe.nachricht')}
    ></textarea>

    <!-- While a generation runs, the waiting line stands in the answer
         bubble — not here. `erzeugtGerade` only
         blocks double-sending. -->

    <div class="fuss">
      <!-- The plus: ONE button the menu grows out of. It
           rotates into an ×, the entries stagger in — the approved
           mockup, one to one. -->
      <div class="linkegruppe">
      <button
        class="plus"
        class:offen={menueOffen}
        aria-expanded={menueOffen}
        aria-label={t('eingabe.anhaengen')}
        onclick={(e) => { e.stopPropagation(); menueOffen = !menueOffen }}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14" /></svg>
      </button>

      <!-- The thinking switch (a light bulb that builds up
           its rays when turned on). Off = a quiet ghost of the shape, on
           = the drawing builds up in blue and dismantles backwards when
           turned off. Non-switchable models: grayed out with a hint. -->
      <button
        class="denkknopf"
        class:an={denkFaehig && denken}
        class:gesperrt={!denkFaehig}
        onclick={denkenSchalten}
        title={!denkFaehig
          ? t('eingabe.denken_gesperrt')
          : denken
            ? t('eingabe.denken_an')
            : t('eingabe.denken_aus')}
        aria-pressed={denkFaehig ? denken : undefined}
        aria-label={t('eingabe.denken')}
      >
        <svg viewBox="0 0 64 64" fill="none" stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
          <g class="geist" stroke="currentColor">
            <circle cx="32" cy="26" r="13" stroke-width="5" />
            <path d="M26 46 H38 M27 53 H37" stroke-width="4.5" />
          </g>
          <g class="aktiv" stroke="currentColor">
            <circle class="strich" cx="32" cy="26" r="13" stroke-width="5" style="--laenge:82" />
            <path class="strich s2" d="M26 46 H38" stroke-width="4.5" style="--laenge:12" />
            <path class="strich s3" d="M27 53 H37" stroke-width="4.5" style="--laenge:10" />
            <path class="strich s4" d="M32 3 V9" stroke-width="4.5" style="--laenge:6" />
            <path class="strich s4" d="M15 9 L20 14" stroke-width="4.5" style="--laenge:7" />
            <path class="strich s4" d="M49 9 L44 14" stroke-width="4.5" style="--laenge:7" />
          </g>
        </svg>
      </button>
      </div>

      <div class="rechts">
        <!-- The live speed, in the fluid bar's old spot. It appears with
             the first measurement and goes when the answer is through —
             an idle display saying "0" would be a display saying nothing.
             The status dot beside it is untouched. -->
        <!-- Keyed on the conversation: the display keeps the last measured
             figure standing after a run, and that figure belongs to the chat
             it was measured in. Switching chats builds the component anew,
             which is what makes a chat that has never run anything show
             nothing at all. -->
        {#key zustand.aktiverChat}
          <Tempoanzeige wert={tempoHier ? tempo.wert : null} laeuft={tempoHier && tempo.zustand === 'laeuft'} />
        {/key}
        <span class="punkt"><Leuchtpunkt farbe={PUNKTFARBE[tempo.zustand] ?? 'still'} groesse={9} /></span>

        <!-- One button, two jobs: send while nothing runs — otherwise
             stop. In the same spot so the hand doesn't wander, and both
             can never stand there at once. Applies equally to image
             generation: if it runs, it gets
             stopped.
             With something in the field it stays the send button even
             during a run: the message then lines up in the queue. Whoever
             types and then reaches for the arrow means to send, not to
             abort — and an empty field is the unmistakable sign for stop. -->
        <button
          class="aktion"
          class:stoppt={stoppt}
          class:leer={!laeuftGerade && !erzeugtGerade && leer}
          onclick={() => (erzeugtGerade || bildLokalLaeuft ? bildStoppen() : stoppt ? abbrechen() : absenden())}
          title={stoppt ? t('eingabe.abbrechen_tipp') : t('eingabe.senden')}
          aria-label={stoppt ? t('eingabe.abbrechen') : t('eingabe.senden')}
        >
          <span class="ring"></span>
          <svg class="pfeil" width="15" height="15" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
          <span class="wuerfel"></span>
        </button>
      </div>
    </div>
  </div>

  <!-- The model picker lives top right in the
       header — down here it appears nowhere anymore, not
       even centered in the empty chat: ONE selection, ONE place. -->
</div>

<style>
  .zone {
    flex: none;
    padding: 10px 0 22px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
  /* One width for both — the confirmation stands flush above the field. */
  .eingabe,
  .frageplatz {
    width: min(560px, 78%);
    max-width: 100%;
    min-width: 0;
  }

  /* The anchor for the plus menu: invisible, costs no space (the
     negative margin swallows the zone gap, same construction as the
     start row). */
  .menueplatz {
    position: relative;
    width: min(560px, 78%);
    max-width: 100%;
    height: 0;
    margin-bottom: -8px;
  }
  /* The menu grows out of the plus: opacity, lift and growth at once,
     200 ms in the house easing. left: -1px puts the outer edge on the
     field's outer edge — both borders line up (approved mockup). */
  .klappmenue {
    position: absolute;
    left: -1px;
    bottom: 8px;
    min-width: 220px;
    background: var(--bg-erhoben);
    border: 1px solid var(--linie-stark);
    border-radius: 12px;
    padding: 5px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.2);
    transform-origin: bottom left;
    opacity: 0;
    transform: translateY(6px) scale(0.92);
    pointer-events: none;
    transition: opacity 0.2s cubic-bezier(0.2, 0.9, 0.3, 1),
                transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
    z-index: 30;
  }
  .klappmenue.offen {
    opacity: 1;
    transform: none;
    pointer-events: auto;
  }
  .klappmenue button {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    text-align: left;
    border: none;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 13.5px;
    padding: 8px 11px;
    border-radius: 8px;
    cursor: pointer;
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.18s cubic-bezier(0.2, 0.9, 0.3, 1),
                transform 0.18s cubic-bezier(0.2, 0.9, 0.3, 1),
                background 0.12s;
  }
  .klappmenue.offen button {
    opacity: 1;
    transform: none;
    transition-delay: 0.03s, 0.03s, 0s;
  }
  .klappmenue button:hover {
    background: var(--linie);
  }
  .klappmenue svg {
    flex: none;
    color: var(--text-leise);
  }
  .menuehinweis {
    display: block;
    font-size: 11.5px;
    color: var(--text-still);
  }
  .klappmenue button.gesperrt {
    opacity: 0.45;
    cursor: default;
  }
  .klappmenue button.gesperrt:hover {
    background: none;
  }

  /* The plus: padding 0 is the difference between centered and crooked —
     browsers give buttons paddings of their own. */
  .plus {
    width: 28px;
    height: 28px;
    padding: 0;
    box-sizing: border-box;
    flex: none;
    border: 1px solid var(--linie-stark);
    border-radius: 99px;
    background: none;
    color: var(--text-leise);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background 0.15s, color 0.15s,
                transform 0.22s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .plus:hover {
    background: var(--linie);
    color: var(--text);
  }
  .plus.offen {
    transform: rotate(45deg);
    background: var(--linie);
    color: var(--text);
  }

  /* Image mode: the bar wears blue (approved mockup). */
  .eingabe.im-bildmodus {
    border-color: var(--blau);
    box-shadow: 0 0 0 1px var(--blau) inset;
  }
  .haken {
    margin-left: auto;
    color: var(--blau);
    font-weight: 700;
  }
  /* The attachment chip docks ABOVE the field — one
     spot for both modes, flush with the field's left edge. Its own
     background, because it now sits on the page, no longer in the box. */
  .anhangplatz {
    margin-bottom: 8px;
  }
  /* Same frame as the folder pills and the tool prompt: three things hang
     above this field, and they have to read as one family. This one kept the
     darker line from before and fell out of the row. */
  .anhang {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: 100%;
    border: 1px solid var(--text-leise);
    border-radius: 12px;
    background: var(--bg-erhoben);
    padding: 4px 8px 4px 4px;
  }
  .anhang img {
    width: 34px;
    height: 34px;
    border-radius: 7px;
    object-fit: cover;
    flex: none;
  }
  .dok-zeichen {
    flex: none;
    color: var(--text-still);
    margin: 4px 2px 4px 6px;
  }
  .dok-meta {
    display: block;
    font-size: 11px;
    color: var(--text-still);
  }
  .anhangname {
    font-size: 12.5px;
    color: var(--text-leise);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .anhang-x {
    border: none;
    background: none;
    color: var(--text-still);
    font: inherit;
    font-size: 13px;
    padding: 2px 6px;
    border-radius: 6px;
    cursor: pointer;
    flex: none;
  }
  .anhang-x:hover {
    background: var(--linie);
    color: var(--text);
  }

  @media (prefers-reduced-motion: reduce) {
    .klappmenue, .klappmenue button, .plus { transition: none; }
  }
  .eingabe {
    position: relative;
    border: 1px solid var(--linie-stark);
    border-radius: 18px;
    background: var(--bg-erhoben);
    padding: 10px 12px 8px;
    overflow: hidden;
    transition: border-color 0.15s;
  }
  .eingabe:focus-within {
    border-color: var(--text-still);
  }
  textarea {
    width: 100%;
    max-width: 100%;
    border: none;
    outline: none;
    resize: none;
    background: none;
    color: var(--text);
    font: inherit;
    line-height: 1.55;
    padding: 2px 2px 8px;
    display: block;
    overflow-x: hidden;
    overflow-y: hidden;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  textarea::placeholder {
    color: var(--text-still);
  }
  .fuss {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    /* Can fold shut when the bar stands centered. The paddings are
        deliberately NOT animated along: the text field's height is
        computed from scrollHeight, and during a running animation a
        half-finished value would come out — the row then only jolted
        into place on the first keystroke. */
    max-height: 40px;
    opacity: 1;
    overflow: hidden;
    transition: max-height var(--anlauf-dauer, 800ms) var(--anlauf-schwung, ease),
                opacity calc(var(--anlauf-dauer, 800ms) * 0.5) ease
                  calc(var(--anlauf-dauer, 800ms) * 0.45);
  }
  .zone.schlank .fuss {
    max-height: 0;
    opacity: 0;
    transition-delay: 0s, 0s;
  }
  .zone.schlank .eingabe {
    padding: 8px 12px;
  }
  .zone.schlank textarea {
    /* Room for the plus on the left, for the arrow on the right. */
    padding: 2px 34px 2px 34px;
  }
  .schlank-plus {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
  }
  .schlank-plus.offen {
    transform: translateY(-50%) rotate(45deg);
  }
  .schlank-knopf {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 28px;
    height: 28px;
    flex: none;
    border: none;
    border-radius: 50%;
    padding: 0;
    cursor: pointer;
    display: grid;
    place-items: center;
    background: var(--text);
    color: var(--bg);
    transition: opacity 0.16s ease, background 0.16s;
  }
  .schlank-knopf:hover { opacity: 0.88; }
  .schlank-knopf.leer {
    background: var(--linie-stark);
    color: var(--text-still);
    cursor: default;
  }
  .schlank-knopf.leer:hover { opacity: 1; }
  /* Centered in the empty chat. The negative margin when folding shut
     swallows the zone's gap (gap: 8px) — otherwise a strip would remain
     at the bottom and the input bar would sit eight pixels higher than
     before. */
  .rechts {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: var(--text-leise);
  }
  /* The thinking switch: the same shell as the plus. Two layers — the
     ghost (always there, very quiet) and the active drawing in blue,
     which builds up on switching on (bulb, base, the rays last) and
     dismantles backwards on switching off (rays first). */
  .linkegruppe {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: none;
  }
  .denkknopf {
    width: 28px;
    height: 28px;
    padding: 0;
    box-sizing: border-box;
    border-radius: 99px;
    border: 1px solid var(--linie-stark);
    background: none;
    color: var(--text-still);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    cursor: pointer;
    transition: border-color 0.2s, background 0.15s;
  }
  .denkknopf:hover { background: var(--linie); }
  .denkknopf.an { border-color: var(--blau); }
  .denkknopf.gesperrt { opacity: 0.4; cursor: default; }
  .denkknopf.gesperrt:hover { background: none; }
  .denkknopf svg { width: 15px; height: 15px; overflow: visible; }
  .denkknopf .geist { color: var(--text-still); opacity: 0.4; }
  /* The blue layer is COMPLETELY invisible in the off state — hidden
     strokes with round caps otherwise paint dots at the stroke starts.
     Immediately visible on switching on; on
     switching off, only hide after the teardown. */
  .denkknopf .aktiv {
    color: var(--blau);
    opacity: 0;
    transition: opacity 0s linear 0.65s;
  }
  .denkknopf.an .aktiv {
    opacity: 1;
    transition: opacity 0s;
  }
  .denkknopf .aktiv .strich {
    stroke-dasharray: var(--laenge);
    stroke-dashoffset: var(--laenge);
    transition: stroke-dashoffset 0.55s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .denkknopf.an .aktiv .strich { stroke-dashoffset: 0; }
  .denkknopf.an .aktiv .s2 { transition-delay: 0.12s; }
  .denkknopf.an .aktiv .s3 { transition-delay: 0.2s; }
  .denkknopf.an .aktiv .s4 { transition-delay: 0.3s; }
  @media (prefers-reduced-motion: reduce) {
    .denkknopf .aktiv .strich { transition: none !important; }
  }

  .punkt {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .aktion {
    width: 32px;
    height: 32px;
    flex: none;
    border-radius: 50%;
    border: none;
    padding: 0;
    cursor: pointer;
    display: grid;
    place-items: center;
    position: relative;
    background: var(--text);
    color: var(--bg);
    transition: opacity 0.16s ease, transform 0.1s ease, background 0.16s;
  }
  .aktion:hover { opacity: 0.88; }
  .aktion:active { transform: scale(0.94); }
  .aktion.leer {
    background: var(--linie-stark);
    color: var(--text-still);
    cursor: default;
  }
  .aktion.leer:hover { opacity: 1; }
  .pfeil, .wuerfel {
    transition: opacity 0.14s ease, transform 0.18s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .wuerfel {
    position: absolute;
    width: 10px;
    height: 10px;
    border-radius: 2.5px;
    background: currentColor;
    opacity: 0;
    transform: scale(0.6);
  }
  .aktion.stoppt { background: none; color: var(--text-leise); }
  .aktion.stoppt:hover { color: var(--text); }
  .aktion.stoppt .pfeil { opacity: 0; transform: scale(0.6); }
  .aktion.stoppt .wuerfel { opacity: 1; transform: none; }
  .ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 1.5px solid var(--linie-stark);
    border-top-color: var(--blau);
    opacity: 0;
    transition: opacity 0.16s;
  }
  .aktion.stoppt .ring {
    opacity: 1;
    animation: dreht 1.4s linear infinite;
  }
  @keyframes dreht {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 720px) {
    .eingabe,
    .frageplatz { width: 92%; }
  }
</style>
