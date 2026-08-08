<script>
  import { fly } from 'svelte/transition'
  import { backOut } from 'svelte/easing'
  import Menueleiste from './teile/Menueleiste.svelte'
  import Seitenleiste from './teile/Seitenleiste.svelte'
  import Seitengriff from './teile/Seitengriff.svelte'
  import Nachricht from './teile/Nachricht.svelte'
  import Eingabeleiste from './teile/Eingabeleiste.svelte'
  import SystemPrompt from './teile/SystemPrompt.svelte'
  import ModelleLokal from './teile/ModelleLokal.svelte'
  import ModelleCloud from './teile/ModelleCloud.svelte'
  import Werkzeuge from './teile/Werkzeuge.svelte'
  import Frage from './teile/Frage.svelte'
  import Vorschaufenster from './teile/Vorschaufenster.svelte'
  import Bildschau from './teile/Bildschau.svelte'
  import { vorschau } from './lib/dateivorschau.svelte.js'
  import { ordnerListe } from './lib/arbeitsordner.svelte.js'
  import Meldungen from './teile/Meldungen.svelte'
  import Wortmarke from './teile/Wortmarke.svelte'
  import Ordnerpillen from './teile/Ordnerpillen.svelte'
  import Auftraege from './teile/Auftraege.svelte'
  import Agentenmarke from './teile/Agentenmarke.svelte'
  import Wasserzeichen from './teile/Wasserzeichen.svelte'
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
    werkzeugfrageBeantworten, frageBeantworten, seitenleisteSchalten,
  } from './lib/zustand.svelte.js'

  /* The mode lives here since the buttons moved from the menu bar into
     the settings window (3.11). It acts via an attribute on the root
     element — no component has to know which one currently applies. */
  let modus = $state(localStorage.getItem('modus') || 'auto')

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
    /* The document AFTER the chat: the documents table hangs off the chat
       (4.1). The server extracts the text right away and returns the meta
       card. */
    let dokument = null
    if (dokumentDatei) {
      try {
        dokument = (await api.dokumentHochladen(zustand.aktiverChat, dokumentDatei)).dokument
      } catch (fehler) {
        melde(String(fehler.message || fehler), 'fehler')
        return
      }
    }
    zustand.nachrichten.push({
      id: 'eigen-' + Date.now(), role: 'user', content: inhalt, bild, dokument,
    })
    runter(true)
    await antwortHolen(inhalt, bild, dokument?.id ?? null, denken, skill)
  }

  /* Image mode (image grill part 2): the raw prompt goes to the
     generator, question and image land as a message pair in the history —
     the server has already stored them, here we only catch up. */
  let bildGenerationId = null

  async function bildErzeugen(prompt) {
    if (!zustand.aktiverChat) {
      const titel = prompt.length > 40 ? prompt.slice(0, 40) + '…' : prompt
      const chat = await api.chatAnlegen({ title: titel, endpoint_id: zustand.modellId })
      zustand.aktiverChat = chat.id
      zustand.nachrichten = []
      await chatsLaden()
    }
    const chatId = zustand.aktiverChat
    zustand.nachrichten.push({ id: 'eigen-' + Date.now(), role: 'user', content: prompt })
    /* The waiting line sits in the answer bubble, where the thinking
       indicator usually is — not under the input field. IMPORTANT: fetch
       the object back out of the list after the push — only the list copy
       is reactive. Whoever keeps the raw object writes into the void (the
       image-only-appears-after-switching-chats bug). */
    zustand.nachrichten.push({ id: null, role: 'assistant', content: '', bildLaeuft: true, stats: {}, werkzeuge: [] })
    const platzhalter = zustand.nachrichten[zustand.nachrichten.length - 1]
    runter(true)
    bildGenerationId = crypto.randomUUID().replaceAll('-', '')
    try {
      const ergebnis = await api.bildGenerieren({
        chat_id: chatId, prompt, generation_id: bildGenerationId,
      })
      /* Whoever switches chats during generation is looking at a foreign
         list — then touch nothing. The pair lives on the server; the chat
         shows it on the next open. */
      if (zustand.aktiverChat !== chatId) return
      const stelle = zustand.nachrichten.indexOf(platzhalter)
      if (ergebnis.abgebrochen) {
        if (stelle !== -1) zustand.nachrichten.splice(stelle, 1)
        return
      }
      platzhalter.id = ergebnis.antwort_id
      platzhalter.bild = ergebnis.bild
      platzhalter.bildLaeuft = false
      runter(true)
    } catch (fehler) {
      const stelle = zustand.nachrichten.indexOf(platzhalter)
      if (stelle !== -1) zustand.nachrichten.splice(stelle, 1)
      melde(String(fehler.message || fehler), 'fehler')
    } finally {
      bildGenerationId = null
    }
  }

  /* The stop button of image generation: tells the server, which
     interrupts the generator — the waiting request above resolves itself
     as a result. */
  function bildStoppen() {
    if (bildGenerationId) api.bildStoppen(bildGenerationId).catch(() => {})
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
    zustand.laeuft = { abbruch, generationId: null }
    tempo = { zustand: 'prompt', wert: null }

    /* Real-time speed: sliding 2.5 s window instead
       of an average since start — the bar follows the moment, not the
       history. The ticker also measures BETWEEN chunks, so the bar
       visibly sinks during stalls instead of freezing. */
    const FENSTER_S = 2.5
    const zeiten = []
    let inhaltAngekommen = false
    let erstesHaeppchen = 0
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
          /* The server halts and waits. No toast for this — the box above
             the input field is conspicuous enough, and two notices for
             the same thing is one too many. */
          zustand.werkzeugfrage = {
            generationId: zustand.laeuft?.generationId,
            aufrufId: ereignis.aufruf_id,
            name: ereignis.name,
            argumente: ereignis.argumente,
            // Why this call is being asked about — empty when the tool is
            // simply configured to always ask.
            grund: ereignis.grund || '',
          }
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
        } else if (ereignis.typ === 'error') {
          melde(ereignis.text, 'fehler')
        } else if (ereignis.typ === 'stats') {
          platzhalter.stats = ereignis.daten || {}
        }
      }
    } catch (fehler) {
      if (fehler.name !== 'AbortError') melde(String(fehler.message || fehler), 'fehler')
    } finally {
      // If the answer aborts while the confirmation stands, nobody is
      // waiting for it anymore — the box has to go, otherwise it points
      // into the void.
      clearInterval(taktgeber)
      zustand.werkzeugfrage = null
      zustand.laeuft = null
      tempo = { zustand: 'bereit', wert: null }
      await chatsLaden()
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
    const uhr = setInterval(modelleLaden, 30000)
    return () => clearInterval(uhr)
  })

  // Jump to the end when switching chats.
  $effect(() => {
    zustand.aktiverChat
    runter(true)
  })
</script>

<svelte:window onkeydown={tastatur} />

<div class="fenster">
  <Menueleiste
    bind:this={menue}
    einstellungenOeffnen={() => {
      zustand.promptStart = 'darstellung'
      zustand.promptOffen = true
    }}
  />

  <!-- The header says which half of the program you are in: in the agent
       section it carries the agent mark, otherwise the wordmark. -->
  <div class="kopfleiste">
    {#if zustand.bereich === 'auftraege'}
      <Agentenmarke groesse={26} beschriftung={t('jobs.kopf')} />
    {:else}
      <!-- The mark keeps the width of the sidebar, so the folders next to it
           start exactly at its edge and not right after the lettering —
           the header then reads in the same two
           columns as everything below it. Collapsed, the rail is narrower
           than the mark itself, so the block shrinks to the mark and no
           further; it travels with the same timing as the bar. -->
      <div class="markenplatz" class:schmal={zustand.seitenleisteEingeklappt}>
        <Wortmarke />
      </div>
      <!-- The header belongs to the working folders.
           The model picker used to sit top right; it moved down into the
           foot of the sidebar so this whole width is free. The folders fly
           in here from above the input field as soon as the first message
           is out — before that they stand down there, where they were set. -->
      <div class="ordnerecke">
        {#if !nochLeer}
          <Ordnerpillen ort="kopf" />
        {/if}
      </div>
    {/if}
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

      <div class="verlauf" bind:this={verlauf} onscroll={scrollGeprueft}
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
        <Eingabeleiste bind:this={eingabe} {senden} {abbrechen} {bildErzeugen} {bildStoppen} {tempo} schlank={nochLeer} />
      </div>

      <div class="unterraum" class:zu={!nochLeer}></div>
      {/if}
    </main>
  </div>
</div>

<!-- The one settings window: appearance, prompts, agents, tools and the
     two files. Since appearance lives here, it also has to
     open under the beta lock — locked then are only the entries that
     touch files; the effective half of the lock remains app/beta.py. -->
<SystemPrompt bind:offen={zustand.promptOffen} bind:modus />
<ModelleLokal bind:offen={zustand.lokalOffen} />
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

<!-- A file from an answer, shown in full. It hangs here and not inside the
     message that owns it: a window covers the whole program, and fixed
     positioning only reaches that far when nothing above it holds it. -->
<Vorschaufenster
  bind:offen={vorschau.offen}
  name={vorschau.name}
  art={vorschau.art}
  inhalt={vorschau.inhalt}
  chatId={zustand.aktiverChat}
  ordner={ordnerListe()}
/>

<!-- A picture at full size. Same reason it hangs here as the window above. -->
<Bildschau />

<!-- The house's prompt dialog — lies above everything, even the windows. -->
<Frage />

<!-- Version and credit, quiet in the corner. The version comes from the
     service, so the corner can never disagree with /meta. -->
{#if zustand.version}
  <div class="signatur" aria-hidden="true">
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
    height: 52px;
    flex: none;
    padding: 0 18px;
    border-bottom: 1px solid var(--linie);
  }
  /* The model-picker corner: presses itself against the right edge,
     opposite the wordmark. min-width: 0 so long model names truncate
     instead of pushing. */
  /* 248 px is the sidebar, minus the header's own 18 px of padding — that
     puts the right edge of this block exactly on the bar's dividing line.
     Collapsed the rail is 50 px, narrower than the mark, so the block stops
     at the mark instead. Same timing as the bar, or the two would slide
     apart while moving. */
  .markenplatz {
    flex: none;
    width: 230px;
    display: flex;
    align-items: center;
    transition: width 0.22s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .markenplatz.schmal {
    width: 168px;
  }
  @media (prefers-reduced-motion: reduce) {
    .markenplatz { transition: none; }
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
    max-width: 720px;
    margin: 0 auto;
    /* More air at the bottom than at the top: the last bubble has to be
       able to stand above the fade-out, otherwise its end would hang in
       the gradient permanently. */
    padding: 26px 28px 84px;
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
      padding: 26px 18px;
    }
  }

  /* Version and credit. Fixed to the window corner, under everything that
     can be clicked — a signature, not a control. */
  .signatur {
    position: fixed;
    right: 12px;
    bottom: 7px;
    z-index: 5;
    font-size: 10.5px;
    letter-spacing: 0.02em;
    color: var(--text-still);
    opacity: 0.8;
    pointer-events: none;
    user-select: none;
  }
</style>
