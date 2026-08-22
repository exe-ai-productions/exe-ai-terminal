<script>
  import { rollfade } from './lib/rollfade.js'
  import { untrack } from 'svelte'
  import { fly } from 'svelte/transition'
  import { backOut } from 'svelte/easing'
  import Menueleiste from './teile/Menueleiste.svelte'
  import Materiefeld from './teile/Materiefeld.svelte'
  import Himmelfeld from './teile/Himmelfeld.svelte'
  import Seitenleiste from './teile/Seitenleiste.svelte'
  import Seitengriff from './teile/Seitengriff.svelte'
  import Arbeitsleiste from './teile/Arbeitsleiste.svelte'
  import Modulrand from './teile/Modulrand.svelte'
  import Erststart from './teile/Erststart.svelte'
  import Begruessungsecke from './teile/Begruessungsecke.svelte'
  import Nachricht from './teile/Nachricht.svelte'
  import Eingabeleiste from './teile/Eingabeleiste.svelte'
  import SystemPrompt from './teile/SystemPrompt.svelte'
  import ModelleLokal from './teile/ModelleLokal.svelte'
  import Katalog from './teile/Katalog.svelte'
  import ModelleCloud from './teile/ModelleCloud.svelte'
  import Werkzeuge from './teile/Werkzeuge.svelte'
  import Frage from './teile/Frage.svelte'
  import Protokollfenster from './teile/Protokollfenster.svelte'
  import Bildschau from './teile/Bildschau.svelte'
  import Meldungen from './teile/Meldungen.svelte'
  import Wortmarke from './teile/Wortmarke.svelte'
  import Kontextnase from './teile/Kontextnase.svelte'
  import Ordnerpillen from './teile/Ordnerpillen.svelte'
  import Auftraege from './teile/Auftraege.svelte'
  import Agentenmarke from './teile/Agentenmarke.svelte'
  import Wasserzeichen from './teile/Wasserzeichen.svelte'
  import Bildwarteschlange from './teile/Bildwarteschlange.svelte'
  import Flashpunkt from './teile/Flashpunkt.svelte'
  import Serverpunkt from './teile/Serverpunkt.svelte'
  import Speicherpille from './teile/Speicherpille.svelte'
  import { api, antwortStrom } from './lib/api.js'
  import { t } from './lib/texte.svelte.js'

  /* Beta: whoever tries to open the editor anyway (from the task list,
     via a keyboard shortcut) gets an answer instead of silent nothing.
     Resetting is necessary because the variable would otherwise stay set
     and the window would pop open unasked when unlocking. */
  $effect(() => {
    if (zustand.features?.beta_lock && zustand.promptOffen) {
      zustand.promptOffen = false
      melde(t('beta.nur_vollversion'), 'hinweis')
    }
  })
  import {
    zustand, melde, aktualisiereMeldung, modelleLaden, featuresLaden, chatsLaden, aktuellerChat, neuerChat,
    werkzeugfrageBeantworten, benutzerfrageBeantworten, werkzeugImmerErlaubt, frageBeantworten, seitenleisteSchalten,
    chatFertigMerken, chatFertigGesehen, menueFensterOeffnen,
  } from './lib/zustand.svelte.js'
  import { begruessung, begruessungLaden } from './lib/begruessung.svelte.js'
  import { verbinden as terminalVerbinden } from './lib/terminalfenster.svelte.js'
  import { klangwahlLaden, klingen } from './lib/klaenge.svelte.js'
  import { dateienAus } from './lib/markdown.js'
  import { seedlage } from './lib/bildseed.svelte.js'
  import { standLaden as eewStandLaden } from './lib/eew.svelte.js'
  import { dockLaden, notizenLaden } from './lib/notizen.svelte.js'
  import { tabOeffnen } from './lib/vorschautabs.svelte.js'
  import { leiste, schalten as leisteSchalten } from './lib/arbeitsleiste.svelte.js'
  import Warteblasen from './teile/Warteblasen.svelte'
  import { anhalten, ausreihen, entfernen, haelt, loesen } from './lib/warteschlange.svelte.js'
  import { chatFehlerGesehen, chatFehlerMerken } from './lib/chatringe.svelte.js'
  import { befundSetzen, befundeLaden, befundeVergessen } from './lib/waechter.svelte.js'

  /* The terminal listens to the open chat: its runs, its lines. */
  $effect(() => {
    terminalVerbinden(zustand.aktiverChat)
  })

  /* Coming back to the window counts as seeing the open chat — its dot,
     if it earned one meanwhile, has said its piece. */
  $effect(() => {
    const zurueck = () => {
      chatFertigGesehen(zustand.aktiverChat)
      chatFehlerGesehen(zustand.aktiverChat)
    }
    window.addEventListener('focus', zurueck)
    return () => window.removeEventListener('focus', zurueck)
  })

  /* A run may have ended while this chat was closed. Fetched once on
     opening — from there the stream keeps the panel current. */
  $effect(() => {
    befundeLaden(zustand.aktiverChat)
  })

  /* Opening a chat is looking at it: whatever its row was reporting has
     been reported. The green mark is cleared where the chat is opened
     (`chatOeffnen`); the red one lives one module further out and is
     cleared here, so the state module does not have to know about it.

     The clearing runs untracked, and that is not a detail. Reading the
     list of red chats inside the effect would make the effect depend on
     it — so a run that fails in the OPEN chat would mark the row, wake
     this effect, and have the mark wiped again in the same breath. The
     red dot would then never appear for the chat one is sitting in, which
     is precisely the chat one wants to be told about. Only the switch of
     chats may trigger this. */
  $effect(() => {
    const chatId = zustand.aktiverChat
    untrack(() => chatFehlerGesehen(chatId))
  })

  /* The mode lives here since the buttons moved from the menu bar into
     the settings window (3.11). It acts via an attribute on the root
     element — no component has to know which one currently applies. */
  let modus = $state(localStorage.getItem('modus') || 'auto')
  begruessungLaden()

  $effect(() => {
    if (modus === 'auto') document.documentElement.removeAttribute('data-modus')
    else document.documentElement.setAttribute('data-modus', modus)
    localStorage.setItem('modus', modus)
  })
  let tempo = $state({ zustand: '', wert: null })
  /* Empty chat: the input sits centered below the wordmark and glides
     down to its usual place on send. */
  const nochLeer = $derived(!zustand.nachrichten.length)
  let verlauf = $state(null)
  let eingabe = $state(null)
  let menue = $state(null)
  // Running tool calls -> their notification, so the result rewrites the
  // same notification instead of creating a second one.
  const werkzeugMeldungen = new Map()

  /* Follow along, but only as long as the user is at the bottom. If they
     scroll up, following stops; once they reach the bottom again, it
     resumes.

     INTENT counts, not position: whoever scrolls up while streaming is
     initially still "near the end"
     — judged by position, the next chunk would pull them right back down,
     and they'd be fighting the auto-scroll. That's why the very first
     wheel tick upwards (or swipe) already ends the following; our own
     programmatic jump doesn't count as a user scroll. */
  let folgtMit = true
  let eigenScroll = false
  let beruehrungY = 0
  const NAH_AM_ENDE = 80

  function scrollGeprueft() {
    if (!verlauf) return
    if (eigenScroll) {
      eigenScroll = false
      return
    }
    folgtMit = verlauf.scrollHeight - verlauf.scrollTop - verlauf.clientHeight < NAH_AM_ENDE
  }
  function radGedreht(ereignis) {
    if (ereignis.deltaY < 0) folgtMit = false
  }
  function beruehrungBeginnt(ereignis) {
    beruehrungY = ereignis.touches[0].clientY
  }
  function beruehrungZieht(ereignis) {
    // Finger moving down = looking up.
    if (ereignis.touches[0].clientY > beruehrungY + 8) folgtMit = false
  }
  function runter(erzwingen = false) {
    if (!verlauf) return
    if (erzwingen) folgtMit = true
    if (!folgtMit) return
    requestAnimationFrame(() => {
      // Check again at execution time — the user may have bailed out in
      // the meantime.
      if (!folgtMit || !verlauf) return
      eigenScroll = true
      verlauf.scrollTop = verlauf.scrollHeight
    })
  }

  /* Keeps the view's floor glued to the list's end for a little while —
     one snap per frame. Used while a message grows in place (the picture
     frame's 75%→100% growth): with the bottom standing still, the growth
     reads upward instead of sliding out below. Bails out the moment the
     reader scrolls away, exactly like runter(). */
  function runterGleiten(dauer = 750) {
    if (!verlauf) return
    folgtMit = true
    const ende = performance.now() + dauer
    const halten = () => {
      if (!folgtMit || !verlauf) return
      /* Already at the floor: setting scrollTop would move nothing and fire
         no scroll event — but the eigenScroll latch would stay armed and
         swallow the reader's NEXT real scroll. Snap only when it snaps. */
      if (verlauf.scrollHeight - verlauf.scrollTop - verlauf.clientHeight <= 0) return
      eigenScroll = true
      verlauf.scrollTop = verlauf.scrollHeight
    }
    const schritt = () => {
      halten()
      if (performance.now() < ende) requestAnimationFrame(schritt)
    }
    requestAnimationFrame(schritt)
    /* Animation frames stand still while the window is hidden; a few plain
       timers hold the floor there too, so a picture finishing in a covered
       window still ends at the floor instead of just above it. */
    for (const zeit of [150, 400, dauer, dauer + 400]) setTimeout(halten, zeit)
  }

  const letzteAntwort = $derived(
    [...zustand.nachrichten].reverse().find((n) => n.role === 'assistant'),
  )
  const letzteFrage = $derived(
    [...zustand.nachrichten].reverse().find((n) => n.role === 'user'),
  )

  /* Send again beneath one's own bubble: same effect
     as regenerate beneath the answer — if an answer is there, it gets
     replaced; if it's missing (e.g. after an abort), it simply gets
     fetched. */
  async function frageNeuSenden() {
    if (zustand.laeuft) {
      melde(t('eingabe.laeuft_schon'))
      return
    }
    const letzte = zustand.nachrichten[zustand.nachrichten.length - 1]
    if (letzte && letzte.role === 'assistant' && letzte.id) {
      await neuErzeugen(letzte.id)
    } else {
      await antwortHolen(null)
    }
  }

  async function senden(inhalt, anhang = null, dokumentDatei = null, denken = null, skill = null) {
    /* A question from the model is waiting: then what was typed IS the
       answer, not a new message. Free text always counts — the buttons are
       an offer, not a cage. */
    if (
      zustand.benutzerfrage
      && zustand.benutzerfrage.chatId === zustand.aktiverChat
      && inhalt?.trim()
    ) {
      await benutzerfrageBeantworten(inhalt.trim())
      return
    }
    if (!zustand.modellId) {
      melde(t('fehler.kein_modell_verfuegbar'), 'fehler')
      return
    }
    /* The image first: if the upload fails, the chat stays untouched and
       the input is still there. */
    let bild = null
    if (anhang) {
      try {
        bild = (await api.bildHochladen(anhang)).bild
      } catch (fehler) {
        melde(String(fehler.message || fehler), 'fehler')
        return
      }
    }
    /* The title says what the chat is about, not which instruction was used
       to get there — so a picked skill is cut off the front of it. */
    const fuerTitel = skill ? inhalt.slice(skill.length + 1).trim() || inhalt : inhalt
    const ersterTitel =
      fuerTitel.length > 40
        ? fuerTitel.slice(0, 40) + '…'
        : fuerTitel || dokumentDatei?.name || t('eingabe.bild_titel')
    if (!zustand.aktiverChat) {
      const chat = await api.chatAnlegen({
        title: ersterTitel,
        endpoint_id: zustand.modellId,
      })
      zustand.aktiverChat = chat.id
      zustand.nachrichten = []
      await chatsLaden()
    } else if (!zustand.nachrichten.length) {
      /* A chat can now exist before the first message — setting a working
         folder creates one. It is still untitled
         at that point, so the first message gives it its name here, exactly
         as it would have on creation. */
      const chat = aktuellerChat()
      if (chat && chat.title === t('chat.unbenannt')) {
        chat.title = ersterTitel
        api
          .chatAendern(chat.id, { title: ersterTitel })
          .then(chatsLaden)
          .catch(() => {})
      }
    }
    /* The bubble goes up BEFORE the document upload. Extracting a large
       document — and, with the section search on, embedding it — happens
       inside that one request and takes real time. The view decides
       between greeting and conversation by the message list alone, so an
       empty list during that work showed a frozen-looking empty chat while
       the sidebar already carried the new conversation. The card starts
       with the file's own facts and a reading note; the server's meta card
       replaces it when the upload returns. */
    zustand.nachrichten.push({
      id: 'eigen-' + Date.now(),
      role: 'user',
      content: inhalt,
      bild,
      dokument: dokumentDatei
        ? {
            name: dokumentDatei.name,
            typ: (dokumentDatei.name.split('.').pop() || '').toLowerCase(),
            kb: Math.max(1, Math.round(dokumentDatei.size / 1024)),
            liest: true,
          }
        : null,
    })
    /* Mutations must land on the proxy the list holds, not on the raw
       object that went in — same pattern as the answer placeholder. */
    const eintrag = zustand.nachrichten[zustand.nachrichten.length - 1]
    runter(true)
    let dokument = null
    if (dokumentDatei) {
      try {
        dokument = (await api.dokumentHochladen(zustand.aktiverChat, dokumentDatei)).dokument
        eintrag.dokument = dokument
      } catch (fehler) {
        /* The upload failed: the bubble leaves again, so the chat shows
           exactly what the server knows — nothing. */
        zustand.nachrichten = zustand.nachrichten.filter((n) => n.id !== eintrag.id)
        melde(String(fehler.message || fehler), 'fehler')
        return
      }
    }
    await antwortHolen(inhalt, bild, dokument?.id ?? null, denken, skill)
  }

  /* A picture made on this machine, from the click to the frame.

     The window is already gone by the time this runs — it shrank away, and
     the work continues here where it can be seen and stopped. The waiting
     message is the SAME one the picture server's mode uses: one waiting
     mark for pictures, whoever draws them.

     The pair in the history is written by the server, so when the picture
     lands there is nothing to assemble — only to catch up. */
  let bildLokalLaeuft = $state(false)
  /* Pictures asked for while one is drawing wait here and run one after the
     other — pressing "draw" three times queues three, it does not throw two
     away. Not $state: only the count in the store drives the badge. */
  let bildQueue = []

  /* The count shown is every picture still to come — the one drawing now
     plus the ones queued behind it. The badge appears whenever it is at
     least one and vanishes when the last picture lands. */
  function bildZahlSetzen() {
    zustand.bildWarteschlange = bildQueue.length + (bildLokalLaeuft ? 1 : 0)
  }

  /* Enqueue and, if nothing is drawing yet, start working the queue off. */
  async function bildLokalZeichnen(wunsch) {
    bildQueue.push(wunsch)
    bildZahlSetzen()
    if (bildLokalLaeuft) return
    bildLokalLaeuft = true
    try {
      while (bildQueue.length) {
        const naechste = bildQueue.shift()
        bildZahlSetzen()
        await bildEinesZeichnen(naechste)
      }
    } finally {
      bildLokalLaeuft = false
      zustand.bildLaeuftChat = null
      zustand.bildMasse = null
      bildZahlSetzen()
    }
  }

  async function bildEinesZeichnen(wunsch) {
    const chatId = wunsch.chat_id
    const masse = { breite: wunsch.breite ?? 512, hoehe: wunsch.hoehe ?? 512 }
    /* The queue may reach this wish while ANOTHER chat is on screen. Then
       the visible list is a foreign one and gets nothing pushed into it —
       the working message belongs to the drawing chat and comes back
       through chatOeffnen the moment that chat is opened. Without this
       guard the pair appeared in whichever chat happened to be open. */
    let platzhalter = null
    if (zustand.aktiverChat === chatId) {
      zustand.nachrichten.push({ id: 'eigen-' + Date.now(), role: 'user', content: wunsch.prompt })
      /* IMPORTANT: fetch the object back OUT of the list after the push —
         only the list's copy is reactive. Whoever keeps the raw object writes
         into the void, which is the bug where the picture only appeared after
         switching chats. */
      zustand.nachrichten.push({
        id: null, role: 'assistant', content: '', bildLaeuft: true, stats: {}, werkzeuge: [],
        bildMasse: masse,
      })
      platzhalter = zustand.nachrichten[zustand.nachrichten.length - 1]
      runter(true)
    }
    // Remember which chat is drawing, so switching away and back can put the
    // working message (and its filling frame) back — it is not on the server.
    zustand.bildLaeuftChat = chatId
    zustand.bildMasse = masse
    try {
      const antwort = await api.bildZeichnen(wunsch)
      // The seed the picture was ACTUALLY drawn with — also when the server
      // picked it. The picture window shows it and the seed plan continues
      // from it.
      if (Number.isInteger(antwort?.seed)) seedlage.letzter = antwort.seed
      /* Whoever switched chats meanwhile is looking at a foreign list —
         then touch nothing. The pair lives on the server and shows itself
         the next time the chat is opened. */
      if (zustand.aktiverChat !== chatId) return
      /* The finished picture first lands in the SAME working message: the
         frame stays the same element, so it can grow smoothly from the 75%
         working size to the full display size with the picture inside.
         Only after that little growth does the list reconcile with the
         server — same content, so nothing visibly changes.

         Resolve the working message from the CURRENT list first: leaving
         and re-entering the chat replaces the list and re-creates the
         placeholder, and a write into the discarded object would leave the
         visible one drawing forever. */
      const ziel = zustand.nachrichten.includes(platzhalter)
        ? platzhalter
        : zustand.nachrichten.find((n) => n.bildLaeuft)
      if (ziel) {
        ziel.bildMasse = ziel.bildMasse ?? masse
        ziel.bild = antwort.bild
        ziel.stats = { ...ziel.stats, seed: antwort.seed }
        ziel.bildLaeuft = false
      }
      /* Glued to the floor for the growth's length: the frame's bottom
         stands, its top rises — the growth reads upward. */
      runterGleiten()
      /* From here on the picture is drawn and on screen. A reconcile that
         fails must not take it away again — the server has the pair, and
         the list heals on the next chat open. */
      try {
        await new Promise((frei) => setTimeout(frei, 700))
        if (zustand.aktiverChat !== chatId) return
        zustand.nachrichten = await api.nachrichten(chatId)
        /* The server's copy of the message does not know the ordered size.
           Hand it over, so the sized stage stays after the reconcile and the
           picture keeps its exact geometry — a natural-size re-render would
           reflow on image load and yank the view away from the picture. */
        const frisch = [...zustand.nachrichten].reverse()
          .find((n) => n.role === 'assistant' && n.bild === antwort.bild)
        if (frisch) frisch.bildMasse = masse
        /* A short glide, not one snap: the reconciled message renders its
           stats foot a frame later, and a single snap lands just above the
           true floor. */
        runterGleiten(300)
        await chatsLaden()
      } catch {
        /* the picture stands; the fresh list arrives with the next open */
      }
    } catch (fehler) {
      if (zustand.aktiverChat === chatId) {
        /* The visible placeholder may be a re-created twin of the captured
           one (chat left and re-entered) — remove whichever still claims to
           be drawing, or a dust frame stands in the chat forever. */
        const stelle = zustand.nachrichten.findIndex(
          (n) => n === platzhalter || (n.bildLaeuft && n.id === null),
        )
        if (stelle !== -1) zustand.nachrichten.splice(stelle, 1)
      }
      /* A stopped picture is not an error. It is what was just asked for,
         and the working message disappearing IS the answer. */
      if (fehler.status !== 499) melde(String(fehler.message || fehler), 'fehler')
    }
  }

  /* The stop button of image generation: tells the server, which
     interrupts the generator — the waiting request above resolves itself
     as a result. */
  function bildStoppen() {
    // Cancel everything, not only the one drawing: the queued ones were
    // asked for by the same hand and stopping means stopping.
    bildQueue = []
    bildZahlSetzen()
    if (bildLokalLaeuft) api.bildZeichnenStoppen().catch(() => {})
  }

  /* Regenerate the answer (3.4): delete the old one and recompute on the
     remaining history, without sending the question again. */
  async function neuErzeugen(messageId) {
    if (zustand.laeuft) {
      melde(t('eingabe.laeuft_schon'))
      return
    }
    try {
      await api.nachrichtLoeschen(zustand.aktiverChat, messageId)
    } catch {
      melde(t('nachricht.nicht_entfernt'), 'fehler')
      return
    }
    const stelle = zustand.nachrichten.findIndex((n) => n.id === messageId)
    if (stelle !== -1) zustand.nachrichten.splice(stelle, 1)
    await antwortHolen(null)
  }

  /* The queue moves on: whenever nothing is running, the open chat gets
     the next message waiting in it.

     Deliberately NOT awaited by its caller: the next send starts a run of
     its own, and awaiting it would nest one run inside the last one's
     stack for as long as the queue is.

     It always asks about the OPEN chat, never about the one whose run just
     ended. `senden` writes into the open history, so firing into a
     conversation nobody is looking at would put the bubble in the wrong
     place — and asking about the finished chat instead would leave a queue
     standing forever in the case that matters most: a run started in one
     chat, a message typed in another, and no switch afterwards to wake
     anything up. */
  function warteschlangeWeiter() {
    const chatId = zustand.aktiverChat
    if (!chatId || zustand.laeuft || haelt(chatId)) return
    const eintrag = ausreihen(chatId)
    if (!eintrag) return
    senden(eintrag.inhalt, eintrag.bild, eintrag.dokument, eintrag.denken, eintrag.skill)
  }

  /* The button on a held bubble. Sending by hand is also the answer to
     "and now?": the hold is lifted, and from here the line runs by itself
     again. */
  function warteschlangeLosschicken(eintrag) {
    if (zustand.laeuft) return
    entfernen(eintrag.id)
    loesen(eintrag.chatId)
    senden(eintrag.inhalt, eintrag.bild, eintrag.dokument, eintrag.denken, eintrag.skill)
  }

  async function antwortHolen(inhalt, bild = null, dokument = null, denken = null, skill = null) {
    /* A plain object is enough: as soon as it lies in a reactive list, it
       becomes reactive itself. Changes to it during streaming thus land
       in the window on their own. */
    zustand.nachrichten.push({
      id: null, role: 'assistant', content: '', reasoning: '', stats: {}, werkzeuge: [],
      /* If the question carried an image, the waiting line shows the eye
         mark — image recognition is recognizable as its own state. */
      vision: Boolean(bild),
    })
    const platzhalter = zustand.nachrichten[zustand.nachrichten.length - 1]

    const abbruch = new AbortController()
    zustand.laeuft = { abbruch, generationId: null, chatId: zustand.aktiverChat }
    tempo = { zustand: 'prompt', wert: null }

    /* Real-time speed: sliding 2.5 s window instead
       of an average since start — the bar follows the moment, not the
       history. The ticker also measures BETWEEN chunks, so the bar
       visibly sinks during stalls instead of freezing. */
    const FENSTER_S = 2.5
    const zeiten = []
    let inhaltAngekommen = false
    let erstesHaeppchen = 0
    let abgebrochen = false
    /* Whether this run ended cleanly decides whether the queue moves on.
       A stream-level error counts as failed even when text had already
       arrived: what comes after it is half an answer, and the next message
       would be asked against a state nobody has looked at. */
    let gescheitert = false
    const messen = () => {
      const jetzt = Date.now()
      while (zeiten.length && jetzt - zeiten[0] > FENSTER_S * 1000) zeiten.shift()
      /* We divide by the time that has actually elapsed — not stubbornly
         by 2.5. In the first seconds of an answer
         the window isn't even full yet; dividing by a fixed 2.5 showed
         about a fifth of the real speed there, and the bar crept up
         slowly instead of standing right away. The lower bound prevents
         the very first chunk from being divided by almost zero. */
      const spanne = Math.max(0.4, Math.min(FENSTER_S, (jetzt - erstesHaeppchen) / 1000))
      tempo = { zustand: 'laeuft', wert: Math.round((zeiten.length / spanne) * 10) / 10 }
    }
    const taktgeber = setInterval(() => {
      if (inhaltAngekommen) messen()
    }, 300)

    try {
      const koerper = { chat_id: zustand.aktiverChat, endpoint_id: zustand.modellId }
      if (inhalt) koerper.content = inhalt
      if (bild) koerper.bild = bild
      if (dokument) koerper.dokument = dokument
      // The thinking switch: only send along if it was actually toggled.
      if (typeof denken === 'boolean') koerper.thinking = denken
      // A picked skill: its instruction rides along with this one request.
      if (skill) koerper.skill = skill

      for await (const ereignis of antwortStrom(koerper, abbruch.signal)) {
        if (ereignis.typ === 'start') {
          zustand.laeuft.generationId = ereignis.generation_id
          platzhalter.id = ereignis.message_id
        } else if (ereignis.typ === 'reasoning') {
          /* Deliberately WITHOUT speed measurement:
             thinking is shown by the yellow dot, the bar only measures
             the answer text. */
          platzhalter.reasoning += ereignis.text
          runter()
        } else if (ereignis.typ === 'content') {
          platzhalter.content += ereignis.text
          inhaltAngekommen = true
          if (!erstesHaeppchen) erstesHaeppchen = Date.now()
          zeiten.push(Date.now())
          messen()
          runter()
        } else if (ereignis.typ === 'tool_confirm') {
          /* This chat may have given the tool a standing yes — then the
             call is answered on the spot instead of asking again what has
             been decided. */
          if (werkzeugImmerErlaubt(zustand.aktiverChat, ereignis.name)) {
            api.werkzeugBestaetigen(zustand.laeuft?.generationId, ereignis.aufruf_id, true).catch(() => {})
          } else {
            /* The server halts and waits. No toast for this — the box above
               the input field is conspicuous enough, and two notices for
               the same thing is one too many. */
            /* The program is waiting for an answer — the one case where a
               sound is worth it, because nothing moves until somebody
               comes back. */
            klingen('wartet')
            zustand.werkzeugfrage = {
              generationId: zustand.laeuft?.generationId,
              aufrufId: ereignis.aufruf_id,
              name: ereignis.name,
              argumente: ereignis.argumente,
              // The RUN's chat, not whatever is on screen: whoever switched
              // away must not find a foreign question hanging over their
              // input field.
              chatId: zustand.laeuft?.chatId ?? zustand.aktiverChat,
              // Why this call is being asked about — empty when the tool is
              // simply configured to always ask.
              grund: ereignis.grund || '',
              grundWert: ereignis.grund_wert || '',
            }
          }
        } else if (ereignis.typ === 'user_ask') {
          /* The model wants a decision that belongs to the user. The run
             stands still until it gets one. */
          klingen('wartet')
          /* The question also lands in the history like any other tool
             call: the server sends no tool_call for ask_user, so the entry
             is created here — the tool_result later fills it, and question
             plus answer stay visible as a block instead of vanishing. */
          platzhalter.werkzeuge.push({
            aufruf_id: ereignis.aufruf_id,
            name: 'ask_user',
            server: '',
            argumente: { question: ereignis.frage },
            ergebnis: null,
            fehlgeschlagen: false,
          })
          zustand.benutzerfrage = {
            generationId: zustand.laeuft?.generationId,
            aufrufId: ereignis.aufruf_id,
            frage: ereignis.frage,
            optionen: ereignis.optionen || [],
            // The RUN's chat, not whatever is on screen — the sidebar
            // lights the right row by it, and the box only shows there.
            chatId: zustand.laeuft?.chatId ?? zustand.aktiverChat,
            // Which question of this run this is — the box wears the
            // count as a small pill.
            nummer: platzhalter.werkzeuge.filter((w) => w.name === 'ask_user').length,
          }
          runter()
        } else if (ereignis.typ === 'tool_call') {
          /* Stays up until the result is in — then the same notification
             is rewritten instead of putting a second one next to it. */
          werkzeugMeldungen.set(
            ereignis.aufruf_id,
            melde(t('werkzeug.laeuft', { name: ereignis.name }), 'werkzeug', {
              dauerhaft: true,
              werkzeug: ereignis.name,
            }),
          )
          // Also attached to the message: the notification disappears
          // again, but the history should keep a traceable record of what
          // ran.
          platzhalter.werkzeuge.push({
            aufruf_id: ereignis.aufruf_id,
            name: ereignis.name,
            // Which server it came from — the catalogue picks the mark by it.
            server: ereignis.server || '',
            argumente: ereignis.argumente,
            ergebnis: null,
            fehlgeschlagen: false,
          })
          runter()
        } else if (ereignis.typ === 'tool_result') {
          const eintrag = platzhalter.werkzeuge.find(
            (w) => w.aufruf_id === ereignis.aufruf_id,
          )
          if (eintrag) {
            eintrag.ergebnis = ereignis.text
            eintrag.fehlgeschlagen = ereignis.fehlgeschlagen
          }
          // A tool has saved an image (Recraft & co.): attach it to the
          // answer immediately — same display as in image mode.
          if (ereignis.bild) platzhalter.bild = ereignis.bild
          const id = werkzeugMeldungen.get(ereignis.aufruf_id)
          werkzeugMeldungen.delete(ereignis.aufruf_id)
          if (id) {
            aktualisiereMeldung(id, {
              text: ereignis.fehlgeschlagen
                ? t('werkzeug.fehlgeschlagen', { name: ereignis.name })
                : t('werkzeug.fertig', { name: ereignis.name }),
              art: ereignis.fehlgeschlagen ? 'fehler' : 'erfolg',
            })
          }
        } else if (ereignis.typ === 'waechter') {
          /* A step failed and the guardian has something to say about it.
             Arrives twice for the same finding — bare when it happened,
             again with the suggestion once the model wrote one — which is
             why the store replaces by id instead of appending.

             The rail is NOT pushed forward for this. A suggestion is an
             offer; taking over the screen for an offer, in the middle of
             an answer one is reading, would be the guardian acting after
             all. The yellow dot on the strip is the whole announcement. */
          befundSetzen(zustand.laeuft?.chatId ?? zustand.aktiverChat, {
            id: ereignis.id,
            art: ereignis.art,
            werkzeug: ereignis.werkzeug,
            ergebnis: ereignis.ergebnis,
            vorschlag: ereignis.vorschlag ?? null,
          })
        } else if (ereignis.typ === 'error') {
          gescheitert = true
          melde(ereignis.text, 'fehler')
        } else if (ereignis.typ === 'stats') {
          platzhalter.stats = ereignis.daten || {}
        }
      }
    } catch (fehler) {
      abgebrochen = fehler.name === 'AbortError'
      gescheitert = !abgebrochen
      if (!abgebrochen) melde(String(fehler.message || fehler), 'fehler')
    } finally {
      // If the answer aborts while the confirmation stands, nobody is
      // waiting for it anymore — the box has to go, otherwise it points
      // into the void.
      clearInterval(taktgeber)
      zustand.werkzeugfrage = null
      zustand.benutzerfrage = null
      /* A document in the answer opens as a tab in the rail by itself —
         that is what the panel is for. The source is read out of the
         answer, not out of the page: the text is the truth, the rendered
         message only a picture of it. */
      for (const datei of dateienAus(platzhalter.content)) {
        tabOeffnen(zustand.laeuft?.chatId ?? zustand.aktiverChat, datei)
      }
      /* The finished dot: only when nobody was watching — someone sitting
         in this chat with the window in front saw the answer arrive, and
         whoever hit stop is not waiting for anything. */
      const fertigerChat = zustand.laeuft?.chatId
      if (
        !abgebrochen &&
        fertigerChat &&
        (fertigerChat !== zustand.aktiverChat || !document.hasFocus())
      ) {
        /* A run that fell over earns the same afterglow as one that came
           through, in the other colour: the list should say WHICH of the
           two happened over there, not merely that something did. */
        if (gescheitert) chatFehlerMerken(fertigerChat)
        else chatFertigMerken(fertigerChat)
      }
      zustand.laeuft = null
      tempo = { zustand: 'bereit', wert: null }
      await chatsLaden()
      /* A clean end lets the line move; a failed or stopped run holds it
         and says so at the bubble. Nobody fires the next message into a
         state that has just gone wrong. */
      if (fertigerChat && (abgebrochen || gescheitert)) anhalten(fertigerChat)
      warteschlangeWeiter()
    }
  }

  async function abbrechen() {
    if (!zustand.laeuft) return
    if (zustand.laeuft.generationId) {
      await api.abbrechen(zustand.laeuft.generationId).catch(() => {})
    }
    zustand.laeuft.abbruch.abort()
  }

  function tastatur(ereignis) {
    const halte = ereignis.metaKey || ereignis.ctrlKey
    if (halte && ereignis.key === 'n') {
      ereignis.preventDefault()
      neuerChat()
      eingabe?.fokus()
    } else if (halte && ereignis.key === ',') {
      ereignis.preventDefault()
      zustand.promptStart = 'darstellung'
      zustand.promptOffen = true
    } else if (halte && ereignis.key === 'b') {
      // The sidebar handle is invisible on purpose; without a key it would
      // not exist for anyone who never brushes the seam.
      ereignis.preventDefault()
      seitenleisteSchalten()
    } else if (halte && ereignis.key === 'j') {
      // The mirror of ⌘B: the work rail on the right.
      ereignis.preventDefault()
      leisteSchalten()
    } else if (halte && ereignis.key === 'k') {
      ereignis.preventDefault()
      document.getElementById('suchfeld')?.focus()
    } else if (ereignis.key === 'Escape') {
      // The prompt dialog has right of way — it lies above everything.
      if (zustand.frage) frageBeantworten(zustand.frage.eingabe != null ? null : false)
      else if (zustand.promptOffen) zustand.promptOffen = false
      else if (zustand.auftragStartenOffen) zustand.auftragStartenOffen = false
      else if (zustand.werkzeugfrage) werkzeugfrageBeantworten(false)
      else if (menue?.istOffen()) menue.schliessen()
      else if (zustand.laeuft) abbrechen()
    }
  }

  $effect(() => {
    modelleLaden()
    featuresLaden()
    chatsLaden()
    klangwahlLaden()
    notizenLaden()
    dockLaden()
    /* The rail draws Extended Workflow's state from the first frame, so it
       has to be known before anybody opens the settings. */
    eewStandLaden()
    const uhr = setInterval(modelleLaden, 30000)
    return () => clearInterval(uhr)
  })

  // Jump to the end when switching chats.
  $effect(() => {
    zustand.aktiverChat
    runter(true)
  })

  /* Two moments put the line in motion: switching into a chat that has
     somebody waiting, and a run coming to an end. Both are watched here,
     so neither has to remember to call the other.

     Everything else is read untracked on purpose. Firing takes the entry
     OUT of the queue, so an effect that also watched the queue would be
     woken by its own write — the classic self-feeding loop. */
  $effect(() => {
    void zustand.aktiverChat
    void zustand.laeuft
    untrack(warteschlangeWeiter)
  })
</script>

<svelte:window onkeydown={tastatur} />

<div class="fenster">
  <!-- The Dark-Matter field, behind everything; paints only under that skin. -->
  <Materiefeld />
  <Himmelfeld />
  <!-- The ONE header, the same single band the sibling programs wear: mark,
       menu, folders, then the status group pressed against the right edge —
       dot, memory pill, help, and the gear in its own slot flush at the
       corner. The old menu bar above it is gone; its items sit in here. -->
  <div class="kopfleiste">
    {#if zustand.bereich === 'auftraege'}
      <Agentenmarke groesse={26} beschriftung={t('jobs.kopf')} />
    {:else}
      <!-- The mark takes only its own width: the menu reads on right after
           the lettering, one line from left to right — no column split with
           the sidebar below. -->
      <div class="markenplatz">
        <Wortmarke />
      </div>
    {/if}
    <Menueleiste bind:this={menue} />
    {#if zustand.bereich !== 'auftraege'}
      <!-- The folders read on from the menu; min-width 0 so long names
           truncate inside their pills instead of stretching the header. -->
      <div class="ordnerecke">
        {#if !nochLeer}
          <Ordnerpillen ort="kopf" />
        {/if}
      </div>
    {/if}
    <div class="spacer"></div>
    <span class="kopfstatus">
      <!-- The picture count reflows in here on its own: it shows only
           while pictures are being made. -->
      <Bildwarteschlange />
      <Flashpunkt />
      <span class="statustrenner" aria-hidden="true"></span>
      <Serverpunkt />
      <span class="statustrenner" aria-hidden="true"></span>
      <!-- The figures name themselves, like the two readings before them. -->
      <span class="wort">{t('kopf.speicher')}</span>
    </span>
    <Speicherpille />

  </div>

  <div class="rumpf">
    <Seitenleiste />
    <!-- Sits on the seam and belongs to neither side. Invisible at rest. -->
    <Seitengriff />

    <main>
      <!-- Slides out from under the header — anchored in the CHAT area,
           not in the window: the center of the notification sits on the
           center of the chat column. -->
      <Meldungen />
      <!-- The context nose, for the same reason and in the same place: it
           hangs on the seam above the chat and has to sit over the middle
           of THAT column. Anchored in the window it would drift left by
           half the sidebar and never line up with the input below it. -->
      <Kontextnase />
      {#if zustand.bereich === 'auftraege'}
      <!-- The jobs view (6.5) displaces the chat including the input: a
           job isn't typed down here, it comes from the agent. -->
      <Auftraege />
      {:else}
      <!-- The wordmark doesn't just fold away on send: its symbol
           simultaneously grows large into the background and stays there.
           Same size and opacity as behind the
           agents — both sections carry their mark the same way. -->
      <Wasserzeichen blass sichtbar={!nochLeer}>
        <Wortmarke mitText={false} />
      </Wasserzeichen>

      <Begruessungsecke sichtbar={nochLeer} />

      <div class="verlauf" use:rollfade bind:this={verlauf} onscroll={scrollGeprueft}
           onwheel={radGedreht} ontouchstart={beruehrungBeginnt} ontouchmove={beruehrungZieht}>
        <div class="spur">
          {#each zustand.nachrichten as nachricht, i (nachricht.id ?? i)}
            <!-- "Feathering" entrance (3.11): rises and briefly overshoots
                 the target. Same motion language as the notifications. -->
            <div in:fly={{ y: 12, duration: 420, easing: backOut }}>
              <Nachricht
                {nachricht}
                istLetzte={letzteAntwort && nachricht.id === letzteAntwort.id}
                istLetzteFrage={letzteFrage && nachricht.id === letzteFrage.id}
                laeuft={Boolean(zustand.laeuft) && i === zustand.nachrichten.length - 1}
                {neuErzeugen}
                neuSenden={frageNeuSenden}
              />
            </div>
          {/each}
          <!-- What has been typed but not yet said. Sits at the end of the
               track, exactly where it will land once the line moves on. -->
          <Warteblasen losschicken={warteschlangeLosschicken} />
        </div>
      </div>

      <!-- Wordmark and input are ONE group in normal flow. Nothing is
           absolutely positioned: the empty space below shares the room
           with the history, which puts the group exactly in the middle.
           On send it shrinks to zero and pushes the group down. -->
      <div class="anlauf">
        <div class="marke" class:weg={!nochLeer}>
          <Wortmarke hoehe={55} zentriert />
        </div>
        <Eingabeleiste bind:this={eingabe} {senden} {abbrechen} {bildStoppen} bildZeichnen={bildLokalZeichnen} {bildLokalLaeuft} {tempo} schlank={nochLeer}
          gruss={nochLeer && begruessung.an ? t('eingabe.los') : null} />
      </div>

      <div class="unterraum" class:zu={!nochLeer}></div>
      {/if}
    </main>

    <!-- The work rail beside the chat: terminal, CLI, preview, note. Comes
         forward by itself when one of them has something to show. -->
    <Arbeitsleiste senden={(text) => senden(text)} />
    <!-- Its signs, at the very edge and always visible — panel open or
         shut. That strip is how the rail is found at all. -->
    <Modulrand />
  </div>
</div>

<!-- The one settings window: appearance, prompts, agents, tools and the
     two files. Since appearance lives here, it also has to
     open under the beta lock — locked then are only the entries that
     touch files; the effective half of the lock remains app/beta.py. -->
<SystemPrompt bind:offen={zustand.promptOffen} bind:modus />
<Erststart bind:modus />
<ModelleLokal bind:offen={zustand.lokalOffen} />
<Katalog bind:offen={zustand.katalogOffen} />
<ModelleCloud bind:offen={zustand.cloudOffen} />

<!-- The tools window. It knows one way out: to the connections, where a
     server is set up. Picking and switching stay here. -->
<Werkzeuge
  bind:offen={zustand.werkzeugeOffen}
  zuVerbindungen={() => {
    zustand.werkzeugeOffen = false
    zustand.promptStart = 'tools'
    zustand.promptOffen = true
  }}
/>

<!-- A picture at full size. It hangs here and not inside the message that
     owns it: a window covers the whole program, and fixed positioning only
     reaches that far when nothing above it holds it. -->
<Bildschau />

<!-- The house's prompt dialog — lies above everything, even the windows. -->
<Frage />

<!-- The server log, shown large. At the root for the same reason as the
     prompt: a window that must lie over everything cannot sit inside one. -->
<Protokollfenster />

<!-- Version and credit, quiet in the corner. The version comes from the
     service, so the corner can never disagree with /meta. -->
{#if zustand.version}
  <div
    class="signatur"
    aria-hidden="true"
    style="left: {zustand.seitenleisteEingeklappt ? 0 : zustand.seitenBreite}px;
           right: {(leiste.offen ? leiste.breite : 0) + 42}px"
  >
    V {zustand.version} · Developed by Christian Brunner
  </div>
{/if}

<style>
  .fenster {
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .kopfleiste {
    display: flex;
    align-items: center;
    gap: 12px;
    /* The sibling programs' single band, 44 px tall. The manual and the
       settings moved into the module rail, so what stands at the right edge
       now is what the header reports — and it keeps the same distance from
       the corner the rail's signs keep from theirs. */
    height: 44px;
    flex: none;
    padding: 0 2px 0 18px;
    /* Header band. Transparent by default, so light and dark keep showing the
       ground through it exactly as before. Under Dark Matter it takes a solid
       dark cap (--kopf-bg) and a soft shadow (--kopf-schatten) so the whole
       header lifts off the nebula with a hard lower edge instead of melting
       into the shimmer. position/z-index let the shadow fall on the content —
       and let the menu dropdown anchored in here stand above it. */
    background: var(--kopf-bg, transparent);
    border-bottom: 1px solid var(--linie);
    box-shadow: var(--kopf-schatten, none);
    position: relative;
    z-index: 3;
  }
  .spacer {
    flex: 1;
  }
  /* The status group left of the memory pill: dot and one quiet word,
     capped so a long text never pushes the pill around. */
  /* A hairline between two readouts that report different things: without
     it the dots and words run together into one sentence. */
  .kopfstatus .wort {
    flex: none;
    white-space: nowrap;
  }
  .statustrenner {
    flex: none;
    width: 1px;
    /* Well short of the line's own height, with air on both sides: a mark
       between two readings, not a rule drawn through the header. */
    height: 9px;
    margin: 0 4px;
    background: var(--linie-stark);
  }
  .kopfstatus {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    flex: 0 1 auto;
    min-width: 0;
    max-width: 42vw;
    font-size: 12.5px;
    color: var(--text-leise);
  }
  /* Only as wide as the mark itself: the menu items follow right after
     the lettering instead of waiting at the sidebar seam. */
  .markenplatz {
    flex: none;
    display: flex;
    align-items: center;
  }
  /* The folders start at that edge and take what they need. No
     margin-left: auto — they belong to the left half, reading on from the
     mark, not pressed against the far edge. min-width: 0 so long names
     truncate inside their pills instead of stretching the header. */
  .ordnerecke {
    min-width: 0;
    display: flex;
    align-items: center;
  }
  .rumpf {
    flex: 1;
    display: flex;
    min-height: 0;
    position: relative;
  }
  main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    /* Anchor for the watermark behind it. */
    position: relative;
  }
  /* History and input lie above the symbol — otherwise it swallows
     clicks and the text would sit behind it instead of in front. */
  .verlauf,
  .anlauf {
    position: relative;
    z-index: 1;
  }
  .verlauf {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    /* The paddings sit in the track, not here: with flex-basis 0,
       paddings count toward the minimum size, so the history would get
       52 pixels more than the space below and the centered group would
       sit 26 pixels too low. */
    /* Fade-out instead of a hard edge: the messages
       don't end abruptly above the input field but dissolve in a soft
       gradient. The mask sits on the container, not the content — when
       scrolling, the text emerges from the mist. */
    --auslauf: 64px;
    -webkit-mask-image: linear-gradient(
      to bottom, #000 calc(100% - var(--auslauf)), transparent
    );
    mask-image: linear-gradient(
      to bottom, #000 calc(100% - var(--auslauf)), transparent
    );
  }
  .spur {
    max-width: var(--chat-breite, 720px);
    margin: 0 auto;
    font-size: var(--chat-schrift, 14px);
    /* More air at the bottom than at the top: the last bubble has to be
       able to stand above the fade-out, otherwise its end would hang in
       the gradient permanently.

       The top has grown by the reach of the context nose, which hangs off
       the header into this field. Without it the first message would start
       underneath the nose and be read through it. */
    padding: 46px 28px 84px;
    display: flex;
    flex-direction: column;
    gap: 22px;
    min-width: 0;
  }
  .spur > :global(div) {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .anlauf {
    flex: none;
    display: flex;
    flex-direction: column;
  }
  .marke {
    /* Full width, otherwise the box shrinks to content width and the
       wordmark's optical compensation runs out of it — overflow then
       clips the drawing on the left. */
    width: 100%;
    display: flex;
    justify-content: center;
    overflow: hidden;
    max-height: 120px;
    opacity: 0.5;
    margin-bottom: 28px;
    transition: max-height var(--anlauf-dauer) var(--anlauf-schwung),
                opacity calc(var(--anlauf-dauer) * 0.5) ease,
                margin-bottom var(--anlauf-dauer) var(--anlauf-schwung);
  }
  .marke.weg {
    max-height: 0;
    opacity: 0;
    margin-bottom: 0;
  }
  .unterraum {
    flex: 1 1 0;
    transition: flex-grow var(--anlauf-dauer) var(--anlauf-schwung);
  }
  .unterraum.zu {
    flex-grow: 0;
  }
  @media (prefers-reduced-motion: reduce) {
    .marke,
    .unterraum {
      transition: none;
    }
  }

  @media (max-width: 720px) {
    .spur {
      padding: 46px 18px 26px;
    }
  }

  /* Version and credit. Fixed to the window corner, under everything that
     can be clicked — a signature, not a control. */
  /* Centred under the CHAT column, not under the window: the column's
     middle travels with the sidebar and the work rail, so the line stays
     centred while both open and close instead of drifting into the corner.
     Fixed to the bottom edge, so it never scrolls with the conversation. */
  .signatur {
    position: fixed;
    bottom: 7px;
    text-align: center;
    /* Above the windows (70), because it must not disappear under one — and
       harmless up there: it takes no clicks and is quiet enough to read
       past. */
    z-index: 80;
    font-size: 10.5px;
    letter-spacing: 0.02em;
    color: var(--text-still);
    opacity: 0.5;
    pointer-events: none;
    user-select: none;
  }
</style>
