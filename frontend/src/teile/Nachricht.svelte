<script>
  import { rollfade } from '../lib/rollfade.js'
  import { slide } from 'svelte/transition'
  import { rendern } from '../lib/markdown.js'
  import { api } from '../lib/api.js'
  import { melde, zustand } from '../lib/zustand.svelte.js'
  import { t } from '../lib/texte.svelte.js'
  import { skillAmAnfang } from '../lib/skills.svelte.js'
  import { tabOeffnen } from '../lib/vorschautabs.svelte.js'
  import { bildZeigen } from '../lib/bildschau.svelte.js'
  import Werkzeugzeichen from './Werkzeugzeichen.svelte'
  import Wartezeile from './Wartezeile.svelte'
  import Bildfuellung from './Bildfuellung.svelte'

  let {
    nachricht, istLetzte = false, laeuft = false, neuErzeugen,
    istLetzteFrage = false, neuSenden,
  } = $props()

  let gedankeOffen = $state(false)
  // Which tool rows are unfolded, by position in the list.
  let offeneWerkzeuge = $state(new Set())

  const istVonMir = $derived(nachricht.role === 'user')

  /* The generated picture's display size, known BEFORE the picture exists:
     the ordered dimensions scaled into the 540 cap. While the painter works
     the frame stands at 75% of that; the moment the picture is there the
     same frame grows to the full size. Without known dimensions (messages
     from the server's history) the picture renders at its natural size as
     before and nothing animates. */
  const BILD_DECKEL = 540
  const bildFlaeche = $derived.by(() => {
    const b = nachricht.bildMasse?.breite, h = nachricht.bildMasse?.hoehe
    if (!b || !h) {
      if (!nachricht.bildLaeuft) return null
      // Working frame without known dimensions: 75% of the square cap.
      return { breite: Math.round(BILD_DECKEL * 0.75), seite: '1 / 1' }
    }
    const faktor = Math.min(1, BILD_DECKEL / b, BILD_DECKEL / h)
    const voll = Math.round(b * faktor)
    return {
      breite: nachricht.bildLaeuft ? Math.round(voll * 0.75) : voll,
      seite: `${b} / ${h}`,
    }
  })

  /* A picked skill stands in the text as it was typed, so it is stored and
     survives a reload. Here it is only drawn apart: the name as a pill, the
     rest as the request. Checked against the list — a slash that hits
     nothing was a slash, not a skill. */
  const skillTeil = $derived(istVonMir ? skillAmAnfang(nachricht.content) : null)
  const ohneSkill = $derived(
    skillTeil ? (nachricht.content || '').slice(skillTeil.name.length + 1).trim() : ''
  )

  /* The document meta card (4.1): comes ready-built from the server —
     only the facts line is assembled here (type · pages · size). */
  const dokument = $derived(nachricht.dokument || null)
  const dokumentZeile = $derived(
    !dokument
      ? ''
      : [
          (dokument.typ || '').toUpperCase(),
          dokument.seiten ? t('nachricht.dokument_seiten', { zahl: dokument.seiten }) : null,
          dokument.kb ? `${dokument.kb} KB` : null,
        ]
          .filter(Boolean)
          .join(' · '),
  )
  const hatInhalt = $derived(Boolean((nachricht.content || '').trim()))
  const html = $derived(hatInhalt ? rendern(nachricht.content) : '')
  const stats = $derived(nachricht.stats || {})

  /* An aborted or failed answer must not remain standing as an empty
     box (3.7) — it says what happened. */
  const grund = $derived(
    stats.fehler
      ? t('nachricht.fehlgeschlagen')
      : stats.abgebrochen
        ? t('nachricht.abgebrochen_leer')
        : t('nachricht.stumm'),
  )

  /* Tools that ran for this answer.

     During the answer, the event stream fills `nachricht.werkzeuge`;
     after a reload the same comes from the stored measurements. Older
     messages have no `ergebnis` there — then it just says the tool
     ran. */
  const werkzeuge = $derived(
    nachricht.werkzeuge?.length ? nachricht.werkzeuge : (stats.werkzeuge ?? []),
  )

  /* A foretaste in the header, so you don't have to unfold every row to
     see what was searched for. The first value suffices for that. */
  function vorschau(argumente) {
    const werte = Object.values(argumente ?? {})
    if (!werte.length) return ''
    const erster = typeof werte[0] === 'string' ? werte[0] : JSON.stringify(werte[0])
    return erster.length > 60 ? erster.slice(0, 60) + '…' : erster
  }

  function werkzeugKlappen(i) {
    // A new Set, otherwise Svelte doesn't notice the change.
    const naechste = new Set(offeneWerkzeuge)
    naechste.has(i) ? naechste.delete(i) : naechste.add(i)
    offeneWerkzeuge = naechste
  }

  /* Exactly TWO numbers: how fast it wrote and how long it took to the
     first token. The total duration used to be here too —
     removed: three numbers under every answer is one too
     many, and the total duration is only the sum of the two operations
     anyway.

     The wait time deliberately stands as its OWN number next to it and
     not inside the speed — exactly how llama.cpp, mlx and LM Studio
     separate it. It is the processing of the prompt: the longer the
     chat, the larger it gets, while the speed stays the same. Stirring
     both into one value was a calculation error, since fixed. */
  /* One decimal place suffices: three places read
     like measurement equipment, not like a footnote under an answer. */
  const zahl = (wert) => Number(wert).toFixed(1)

  /* The speed is NOT here. It stands live in the input bar, where it can be
     watched, and stays standing there after the run — under a finished
     answer it was a number nobody could act on, and it pushed the one
     figure that IS worth keeping, the wait for the first token, into second
     place. `tokens_pro_sekunde` keeps being measured and stored; the
     display up there is what reads it. */
  const messwerte = $derived(
    [
      stats.erstes_token_nach_sekunden
        ? t('nachricht.wartezeit_kurz', { zahl: zahl(stats.erstes_token_nach_sekunden) })
        : null,
      stats.abgebrochen ? t('nachricht.abgebrochen_kurz') : null,
      stats.fehler ? t('nachricht.fehler_kurz', { text: stats.fehler }) : null,
    ].filter(Boolean),
  )

  function kopieren() {
    navigator.clipboard
      .writeText(nachricht.content || '')
      .then(() => melde(t('nachricht.kopiert'), 'erfolg'))
  }

  function seedKopieren(seed) {
    navigator.clipboard
      .writeText(String(seed))
      .then(() => melde(t('nachricht.seed_kopiert'), 'erfolg'))
  }

  /* Buttons inside a rendered answer only come into being at render time,
     hence one delegated listener instead of individual bindings. */
  function antwortKlick(ereignis) {
    codeKopieren(ereignis)
    dateiOeffnen(ereignis)
  }

  function codeKopieren(ereignis) {
    const knopf = ereignis.target.closest?.('.code-kopieren')
    if (!knopf) return
    const code = knopf.closest('.codeblock').querySelector('code').textContent
    navigator.clipboard.writeText(code).then(() => melde(t('nachricht.code_kopiert'), 'erfolg'))
  }

  /* The file box carries its own source, hidden inside it. That is why the
     window needs nothing but the box that was clicked — no lookup, no second
     copy of the answer that could drift apart from what is on screen. The
     window itself hangs at the top of the program, not here. */
  function dateiOeffnen(ereignis) {
    const kasten = ereignis.target.closest?.('.dateikasten')
    if (!kasten) return
    /* Into the rail beside the chat, as a tab — not into a window over the
       whole program. Building a page means looking at it while the
       conversation goes on. */
    tabOeffnen(zustand.aktiverChat, {
      name: kasten.dataset.name || '',
      art: kasten.dataset.art || '',
      inhalt: kasten.querySelector('code')?.textContent || '',
    })
  }
</script>

{#if istVonMir}
  <div class="von-mir" class:mit-bild={nachricht.bild} class:mit-dokument={dokument}>
    {#if dokument}
      <!-- Document (4.1): compact card instead of file content — the
           dog-ear is familiar from the Notion tools. The dashed line
           appears ONLY if content was actually truncated. -->
      <div class="dok-karte">
        <svg class="dok-zeichen" width="22" height="22" viewBox="0 0 64 64" fill="none"
             stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M16 8 H38 L48 18 V56 H16 Z" />
          <path d="M38 8 V18 H48" stroke-width="4.5" />
          <path d="M25 34 H39 M25 44 H39" stroke-width="4.5" />
        </svg>
        <span class="dok-name">
          {dokument.name}
          {#if dokumentZeile}<span class="dok-fakten">{dokumentZeile}</span>{/if}
        </span>
      </div>
      {#if nachricht.content}<div class="bildtext">{nachricht.content}</div>{/if}
      {#if dokument.gekuerzt}
        <div class="dok-gekuerzt">{t('nachricht.dokument_gekuerzt')}</div>
      {/if}
    {:else if nachricht.bild}
      <!-- The attachment travels into the speech bubble (vision): evenly
           framed in the bubble, one click enlarges. -->
      <div class="bildrahmen">
        <button class="bildknopf" onclick={() => bildZeigen(api.bildAdresse(nachricht.bild))}
                aria-label={t('nachricht.bild_vergroessern')}>
          <img class="bildanhang" src={api.bildAdresse(nachricht.bild)} alt="" loading="lazy" />
        <span class="bildecke rechts" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10 4 H4 V10" />
            <path d="M14 20 H20 V14" />
          </svg>
        </span>
      </button>
      <a class="bildecke links" href={api.bildAdresse(nachricht.bild)} download
         aria-label={t('nachricht.bild_sichern')}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 4 V15" />
          <path d="M7 11 L12 16 L17 11" />
          <path d="M4 20 H20" />
        </svg>
      </a>
      </div>
      {#if nachricht.content}<div class="bildtext">{nachricht.content}</div>{/if}
    {:else if skillTeil}
      <!-- Brightness only, no colour: which instruction was used is a fact
           about the message, not a state it is in. -->
      <span class="skillpille">/{skillTeil.name}</span>{#if ohneSkill}{' '}{ohneSkill}{/if}
    {:else}{nachricht.content}{/if}
  </div>
  <!-- The same actions as under the answers, just under one's own
       bubble: copy always, send-again only on the last
       question — in the middle it would devalue the history after it. -->
  <div class="fuss meine">
    <button class="tat" title={t('nachricht.kopieren')} aria-label={t('nachricht.kopieren')} onclick={kopieren}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 012-2h10" />
      </svg>
    </button>
    {#if istLetzteFrage}
      <button class="tat" title={t('nachricht.neu_senden')} aria-label={t('nachricht.neu_senden')}
              onclick={() => neuSenden?.()}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round">
          <path d="M20 11a8 8 0 10-2.3 5.7M20 5v6h-6" />
        </svg>
      </button>
    {/if}
  </div>
{:else}
  <div class="von-ki">
    {#if nachricht.bild || nachricht.bildLaeuft}
      <!-- A generated image: the light-edge frame, the picture rounded into
           it, and a foot strip that carries what used to sit ON the picture —
           save on the left, the seed (with a quick copy) in the middle, and
           enlarge on the right. The seed comes from the message's own stats.
           The SAME frame already stands while the painter works: the liquid
           fill inside at 75% size, growing to the full size with the picture
           the moment it is finished — one element, so the growth is smooth. -->
      {#if nachricht.bildLaeuft}
        <div class="bild-kopf">{t('nachricht.bild_laeuft')}</div>
      {/if}
      <div class="erzeugt">
        {#if bildFlaeche}
          <div class="erzeugt-flaeche" class:mitfuss={Boolean(nachricht.bild)}
               style={`width:${bildFlaeche.breite}px;aspect-ratio:${bildFlaeche.seite}`}>
            {#if nachricht.bild}
              <button class="erzeugt-bild gefuellt" onclick={() => bildZeigen(api.bildAdresse(nachricht.bild))}
                      aria-label={t('nachricht.bild_vergroessern')}>
                <!-- The painter may snap ordered dimensions to its grid; the
                     stage follows the REAL picture once it is here, so cover
                     never crops a sliver off a rounded edge. -->
                <img class="gemalt" src={api.bildAdresse(nachricht.bild)} alt="" loading="lazy"
                     onload={(e) => {
                       const b = e.currentTarget.naturalWidth, h = e.currentTarget.naturalHeight
                       if (b && h && nachricht.bildMasse
                           && (nachricht.bildMasse.breite !== b || nachricht.bildMasse.hoehe !== h)) {
                         nachricht.bildMasse = { breite: b, hoehe: h }
                       }
                     }} />
              </button>
            {:else}
              <Bildfuellung fuellen />
            {/if}
          </div>
        {:else}
          <button class="erzeugt-bild" onclick={() => bildZeigen(api.bildAdresse(nachricht.bild))}
                  aria-label={t('nachricht.bild_vergroessern')}>
            <img class="bildanhang" src={api.bildAdresse(nachricht.bild)} alt="" loading="lazy" />
          </button>
        {/if}
        {#if nachricht.bild}
        <div class="erzeugt-fuss">
          <a class="fusstat" href={api.bildAdresse(nachricht.bild)} download
             aria-label={t('nachricht.bild_sichern')} title={t('nachricht.bild_sichern')}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 4 V15" /><path d="M7 11 L12 16 L17 11" /><path d="M4 20 H20" />
            </svg>
          </a>
          <span class="fussmitte">
            {#if nachricht.stats?.seed != null}
              <button class="seedkopie" onclick={() => seedKopieren(nachricht.stats.seed)}
                      title={t('nachricht.seed_kopieren')}>
                <span class="seedwert">{t('nachricht.seed_label', { zahl: nachricht.stats.seed })}</span>
                <svg class="kopfzeichen" width="13" height="13" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15 V5 a2 2 0 0 1 2-2 h10" />
                </svg>
              </button>
            {/if}
          </span>
          <button class="fusstat" onclick={() => bildZeigen(api.bildAdresse(nachricht.bild))}
                  aria-label={t('nachricht.bild_vergroessern')} title={t('nachricht.bild_vergroessern')}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10 4 H4 V10" /><path d="M14 20 H20 V14" />
            </svg>
          </button>
        </div>
        {/if}
      </div>
    {/if}
    {#if nachricht.reasoning}
      <button class="gedanke-kopf" class:offen={gedankeOffen} onclick={() => (gedankeOffen = !gedankeOffen)}>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M9 6l6 6-6 6" />
        </svg>
        {t('nachricht.gedankengang')}
      </button>
      {#if gedankeOffen}
        <div class="gedanke-text" transition:slide={{ duration: 200 }}>{nachricht.reasoning}</div>
      {/if}
    {/if}

    <!-- What the model used, before the answer — in the order it
         happened. Folded, a quiet line; unfolded, what actually came
         back. -->
    {#each werkzeuge as werkzeug, i (i)}
      <button
        class="gedanke-kopf werkzeug"
        class:offen={offeneWerkzeuge.has(i)}
        class:misslungen={werkzeug.fehlgeschlagen}
        onclick={() => werkzeugKlappen(i)}
      >
        <!-- The tool's icon: while the call is still
             running, it draws itself in a loop; afterwards it stands
             still. The text stays — it says WHAT was asked, and is the
             click target. -->
        <Werkzeugzeichen
          name={werkzeug.name}
          server={werkzeug.server ?? ''}
          laeuft={werkzeug.ergebnis === null && !werkzeug.fehlgeschlagen}
        />
        <span class="wz-name">{werkzeug.name}</span>
        {#if vorschau(werkzeug.argumente)}
          <span class="wz-vorschau">{vorschau(werkzeug.argumente)}</span>
        {/if}
        {#if werkzeug.fehlgeschlagen}<span class="wz-marke">{t('werkzeug.marke_fehlgeschlagen')}</span>{/if}
      </button>
      {#if offeneWerkzeuge.has(i)}
        <div class="gedanke-text werkzeug-text" use:rollfade transition:slide={{ duration: 200 }}>
          {#if Object.keys(werkzeug.argumente ?? {}).length}
            <dl class="wz-argumente">
              {#each Object.entries(werkzeug.argumente) as [schluessel, wert] (schluessel)}
                <dt>{schluessel}</dt>
                <dd>{typeof wert === 'string' ? wert : JSON.stringify(wert)}</dd>
              {/each}
            </dl>
          {/if}
          {#if werkzeug.ergebnis}
            <div class="wz-ergebnis">{werkzeug.ergebnis}</div>
          {:else}
            <p class="wz-leer">
              {werkzeug.ergebnis === null ? t('werkzeug.laeuft_noch') : t('werkzeug.nichts_mitgeschrieben')}
            </p>
          {/if}
        </div>
      {/if}
    {/each}

    {#if hatInhalt}
      <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
      <div class="antwort" onclick={antwortKlick}>{@html html}</div>
      {#if laeuft}
        <!-- The model has already said something but keeps working (e.g.
             interim update, then the next search): the working mark
             returns instead of staying silent. -->
        <div class="weiterarbeit">
          <Wartezeile
            art={nachricht.vision ? 'vision' : 'antwort'}
            beschriftung={t('status.erzeugt_antwort')}
          />
        </div>
      {/if}
    {:else if laeuft && !nachricht.bildLaeuft}
      <!-- While nothing is there yet: show that work is happening. The
           empty-answer notice would be wrong here — it just isn't
           finished yet. Without text: that an answer
           is coming explains itself. A working picture already shows its
           own frame above; a second status mark would contradict it. -->
      <Wartezeile
        art={nachricht.vision ? 'vision' : 'antwort'}
        beschriftung={t('status.erzeugt_antwort')}
      />
    {:else if !nachricht.bild && !nachricht.bildLaeuft}
      <!-- An image answer has empty text — that is its normal state, not
           a "wrote nothing". The frame of a running picture stands above
           already; it needs no second word down here. -->
      <div class="abgebrochen">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round">
          <circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" />
        </svg>
        {grund}
      </div>
    {/if}

    <div class="fuss">
      {#each messwerte as wert}<span>{wert}</span>{/each}
      {#if laeuft}<span class="platzhalter"></span>{/if}
      <button class="tat" title={t('nachricht.kopieren')} aria-label={t('nachricht.kopieren')} onclick={kopieren}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 012-2h10" />
        </svg>
      </button>
      <!-- Regenerate exists only on the last answer: recomputing one in
           the middle would invalidate everything after it (3.4). -->
      {#if istLetzte && nachricht.id}
        <button class="tat" title={t('nachricht.neu_erzeugen')} aria-label={t('nachricht.neu_erzeugen')}
                onclick={() => neuErzeugen(nachricht.id)}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round">
            <path d="M20 11a8 8 0 10-2.3 5.7M20 5v6h-6" />
          </svg>
        </button>
      {/if}
    </div>
  </div>
{/if}


<style>
  .von-mir {
    align-self: flex-end;
    max-width: 76%;
    /* The one surface the user may recolour; the ink flips with the
       ground's luminance so no choice can make it unreadable. The chain:
       the user's own pick wins, else a theme's own default (Dark Matter ships
       a lavender here), else the plain house bubble. */
    background: var(--blase-eigen, var(--blase-eigen-standard, var(--blase)));
    color: var(--blase-eigen-text, var(--blase-eigen-text-standard, inherit));
    border-radius: 16px;
    padding: 10px 15px;
    line-height: 1.55;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    min-width: 0;
  }
  /* The picked instruction, marked off from the request. Its own background
     rather than a colour: colour means state, and this is a fact. */
  .skillpille {
    display: inline-block;
    background: color-mix(in srgb, var(--text) 10%, transparent);
    border-radius: 99px;
    padding: 1px 8px 2px;
    font-size: 0.88em;
    line-height: 1.35;
    white-space: nowrap;
  }
  /* With an image, the bubble becomes a frame: an even 5px all around,
     the image carries the inner rounding — perfectly aligned instead of
     indented. */
  /* A picture brings its own edge, so the bubble stops drawing a second one
     around it. Two frames around one picture read as a frame around a
     frame — and the inner one is then the only one that means anything. */
  .von-mir.mit-bild {
    padding: 0;
    background: none;
  }
  /* Document bubble (4.1): the card carries the border, the bubble only
     gives a narrow frame — same logic as with the image. */
  .von-mir.mit-dokument {
    padding: 6px;
  }
  .dok-karte {
    display: flex;
    align-items: center;
    gap: 9px;
    border: 1px solid var(--linie);
    border-radius: 11px;
    background: var(--bg-erhoben);
    padding: 7px 13px 7px 9px;
    font-size: 12.5px;
    color: var(--text-leise);
    white-space: normal;
  }
  .dok-zeichen {
    flex: none;
    color: var(--text-still);
  }
  .dok-name {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .dok-fakten {
    display: block;
    font-size: 11px;
    color: var(--text-still);
  }
  .dok-gekuerzt {
    font-size: 11.5px;
    color: var(--text-still);
    border: 1px dashed var(--linie-stark);
    border-radius: 8px;
    padding: 3px 9px;
    margin: 6px 7px 3px;
    white-space: normal;
    width: fit-content;
  }
  /* The frame around a picture.

     It is not drawn — it is the edge of the box the picture sits in. That is
     why it fits every format by itself and why 2 px stay 2 px whether the
     picture is a stamp or fills the window: a stroke that is part of a
     symbol shrinks with the symbol, an edge does not.

     `line-height: 0` and a picture set to `block` are what make the picture
     start at the first pixel inside the edge. A picture is inline by default
     and then sits on a text baseline, which leaves a gap of a few pixels
     under it — with a frame around it, that gap is all you see. */
  /* The frame belongs to the box, not to the button: one of the two marks
     inside it is a link and may not sit inside a button. */
  .bildrahmen {
    position: relative;
    width: fit-content;
    border: 2px solid var(--linie-stark);
    border-radius: 0;
    line-height: 0;
  }
  .bildknopf {
    display: block;
    border: none;
    background: none;
    padding: 0;
    line-height: 0;
    cursor: zoom-in;
  }
  .bildanhang {
    display: block;
    /* Larger preview (L): min() keeps it within the bubble on a narrow
       window, so it grows on a wide screen but never overflows. */
    max-width: min(540px, 100%);
    max-height: 540px;
    border-radius: 0;
  }

  /* The mark sits IN the picture, in the lower right corner, because that is
     where the frame would otherwise say nothing. A separate control outside
     would need its own edge — and then there really are two frames. */
  /* Both marks sit IN the picture, in the two lower corners, because that
     is where the frame would otherwise say nothing. Controls placed outside
     would need an edge of their own — and then there are two frames again.
     Enlarge on the right, save on the left, as far apart as the frame
     allows: two marks side by side get hit by accident. */
  .bildecke {
    position: absolute;
    bottom: 0;
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    color: #fff;
    background: rgba(0, 0, 0, 0.42);
    opacity: 0.85;
    transition: opacity 0.12s, background 0.12s;
  }
  .bildecke.rechts { right: 0; }
  .bildecke.links { left: 0; }
  .bildrahmen:hover .bildecke,
  .bildecke:focus-visible {
    opacity: 1;
    background: rgba(0, 0, 0, 0.62);
  }
  /* Standing under a picture without the bubble around it, the caption
     needs its own quiet ground — otherwise it floats on the page. */
  .bildtext {
    margin-top: 6px;
    padding: 7px 12px;
    background: var(--blase);
    border-radius: 12px;
  }
  /* The generated picture's frame: a one-pixel light edge (brighter at the
     top, as if lit from above), the picture rounded into it, and a foot strip
     below for save / seed / enlarge. fit-content so the frame hugs the
     picture at whatever size it came out, up to the image's 540 cap. */
  .erzeugt {
    width: fit-content;
    max-width: 100%;
    margin-bottom: 6px;
    padding: 1px;
    border-radius: 11px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.02) 42%, rgba(0, 0, 0, 0.4));
    box-shadow: 0 14px 34px -16px rgba(0, 0, 0, 0.6);
  }
  .erzeugt-bild {
    display: block;
    border: none;
    background: none;
    padding: 0;
    line-height: 0;
    cursor: zoom-in;
    /* Rounded top corners only — the bottom meets the foot strip. overflow
       clips the picture into the radius, trimming just the corner. */
    border-radius: 10px 10px 0 0;
    overflow: hidden;
  }
  /* The sized stage inside the frame, same element in both states: liquid
     fill while the painter works, the picture when it is done. Its width is
     set inline (75% growing to 100%), the height follows the ordered aspect
     ratio — so the one transition on width IS the whole growth. */
  .erzeugt-flaeche {
    position: relative;
    max-width: 100%;
    border-radius: 10px;
    overflow: hidden;
    background: var(--bg-erhoben);
    transition: width 0.55s ease, border-radius 0.3s ease;
  }
  /* With the foot strip below, the bottom corners belong to the strip. */
  .erzeugt-flaeche.mitfuss { border-radius: 10px 10px 0 0; }
  .erzeugt-bild.gefuellt {
    width: 100%;
    height: 100%;
    border-radius: 0;
  }
  .gemalt {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  @media (prefers-reduced-motion: reduce) {
    .erzeugt-flaeche { transition: none; }
  }
  .erzeugt-fuss {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 6px;
    background: var(--bg-erhoben);
    border-radius: 0 0 10px 10px;
  }
  .fusstat {
    flex: none;
    display: grid;
    place-items: center;
    width: 28px;
    height: 26px;
    border: none;
    background: none;
    color: var(--text-still);
    border-radius: 7px;
    cursor: pointer;
    text-decoration: none;
    transition: background 0.12s, color 0.12s;
  }
  .fusstat:hover {
    background: var(--linie);
    color: var(--text);
  }
  /* The seed sits centred and spreads only as wide as it needs; the two
     icons hold the ends. */
  .fussmitte {
    flex: 1;
    min-width: 0;
    display: flex;
    justify-content: center;
  }
  .seedkopie {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    max-width: 100%;
    border: none;
    background: none;
    color: var(--text-still);
    font: 400 11.5px var(--schrift-fest, ui-monospace, monospace);
    padding: 3px 9px;
    border-radius: 7px;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .seedkopie:hover {
    background: var(--linie);
    color: var(--text);
  }
  .seedwert {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .seedkopie .kopfzeichen {
    flex: none;
    opacity: 0.8;
  }
  .von-ki {
    max-width: 92%;
    overflow-wrap: anywhere;
    min-width: 0;
  }
  .gedanke-kopf {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font: inherit;
    font-size: 12.5px;
    color: var(--text-still);
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    margin-bottom: 7px;
  }
  .gedanke-kopf svg {
    transition: transform 0.18s;
  }
  .gedanke-kopf.offen svg {
    transform: rotate(90deg);
  }
  .gedanke-text {
    font-size: 13px;
    line-height: 1.6;
    color: var(--text-leise);
    border-left: 2px solid var(--linie-stark);
    padding: 2px 0 2px 12px;
    margin-bottom: 12px;
    white-space: pre-wrap;
  }
  /* Tool rows inherit the reasoning style: same language, one pattern.
     They are distinguished only by the blue color edge when unfolded —
     the same one tools show in the notifications too. */
  .werkzeug {
    /* flex instead of inline-flex: multiple calls should stack, otherwise
       they line up side by side as inline elements. */
    display: flex;
    width: fit-content;
    max-width: 100%;
    min-width: 0;
    text-align: left;
  }
  .werkzeug .wz-name {
    font-family: var(--schrift-fest);
    font-size: 11.5px;
  }
  .werkzeug .wz-vorschau {
    color: var(--text-still);
    opacity: 0.85;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
  .werkzeug .wz-marke {
    color: var(--rot);
    flex: none;
  }
  .werkzeug.misslungen .wz-name {
    color: var(--rot);
  }
  .werkzeug-text {
    border-left-color: var(--blau);
    max-height: 40vh;
    overflow-y: auto;
    overflow-x: hidden;
  }
  .wz-argumente {
    margin: 0 0 8px;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 1px 10px;
    font-size: 12px;
  }
  .wz-argumente dt {
    color: var(--text-still);
    font-family: var(--schrift-fest);
    font-size: 11px;
    white-space: nowrap;
  }
  .wz-argumente dd {
    margin: 0;
    min-width: 0;
    overflow-wrap: anywhere;
  }
  /* The result is a tool's raw text, not prose — fixed width keeps hit
     lists and tables readable. */
  .wz-ergebnis {
    font-family: var(--schrift-fest);
    font-size: 11.8px;
    line-height: 1.55;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    padding-top: 8px;
    border-top: 1px solid var(--linie);
  }
  .wz-argumente + .wz-ergebnis {
    margin-top: 0;
  }
  .wz-leer {
    margin: 0;
    color: var(--text-still);
  }

  .antwort {
    line-height: 1.65;
  }
  /* The waiting indicators (logo and image sign alike) live in the
     Wartezeile — row, size, timing and spot are set only there. */

  /* The image-generation status stands exactly at the spot of the
     reasoning TEXT: same type, same spacing, and indented left by
     chevron width + gap (12px + 5px) — the column lines up in all three
     waiting states. */
  .bild-kopf {
    font-size: 12.5px;
    color: var(--text-still);
    padding-left: 17px;
    margin-bottom: 7px;
  }

  /* Outline instead of fill (3.11). Sits as an attribute on the root
     element so the rule applies in one place — same construction as with
     the mode. */
  :global(:root[data-blasen='kontur']) .von-mir {
    background: transparent;
    color: inherit;
    box-shadow: inset 0 0 0 1px var(--blase-eigen, var(--blase-eigen-standard, var(--linie-stark)));
  }
  /* Keeps the footer at height so the text doesn't jump when finishing. */
  .platzhalter {
    display: inline-block;
    height: 1em;
  }

  .abgebrochen {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12.5px;
    color: var(--text-still);
    border: 1px dashed var(--linie-stark);
    border-radius: 9px;
    padding: 5px 10px;
  }
  .fuss {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-top: 10px;
    font-size: 12px;
    color: var(--text-still);
  }
  /* The returning working mark needs air to the interim text. */
  .weiterarbeit {
    margin-top: 12px;
  }
  .fuss .tat {
    border: none;
    background: none;
    color: var(--text-still);
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    display: inline-flex;
  }
  /* Under one's own bubble: right-aligned like the bubble itself, a bit
     closer — there are no measurements here, only the actions. */
  .fuss.meine {
    align-self: flex-end;
    margin-top: 6px;
    gap: 6px;
  }
  .fuss .tat:hover {
    background: var(--linie);
    color: var(--text);
  }

  /* Markdown output. :global, because the HTML comes into being at
     runtime and Svelte only hands its classes to the markup it sees at
     build time. */
  .antwort :global(> *:first-child) { margin-top: 0; }
  .antwort :global(> *:last-child) { margin-bottom: 0; }
  .antwort :global(p) { margin: 0 0 0.85em; }
  .antwort :global(h2) { font-size: 1.22em; font-weight: 600; margin: 1.4em 0 0.5em; letter-spacing: -0.01em; }
  .antwort :global(h3) { font-size: 1.08em; font-weight: 600; margin: 1.3em 0 0.45em; }
  .antwort :global(h4), .antwort :global(h5) { font-size: 1em; font-weight: 600; margin: 1.2em 0 0.4em; }
  .antwort :global(ul), .antwort :global(ol) { margin: 0 0 0.85em; padding-left: 1.35em; }
  .antwort :global(li) { margin: 0.22em 0; }
  .antwort :global(blockquote) {
    margin: 0 0 0.85em; padding: 0.1em 0 0.1em 0.9em;
    border-left: 2px solid var(--linie-stark); color: var(--text-leise);
  }
  .antwort :global(hr) { border: none; border-top: 1px solid var(--linie); margin: 1.4em 0; }
  .antwort :global(a) { color: inherit; text-underline-offset: 3px; text-decoration-color: var(--text-still); }
  .antwort :global(table) {
    border-collapse: collapse; margin: 0 0 0.95em; font-size: 0.94em; display: block; overflow-x: auto;
  }
  .antwort :global(th), .antwort :global(td) { border: 1px solid var(--linie); padding: 6px 11px; text-align: left; }
  .antwort :global(th) { font-weight: 600; background: var(--bg-seite); }
  .antwort :global(code) {
    font-family: var(--schrift-fest); font-size: 0.9em;
    background: var(--blase); padding: 1.5px 5px; border-radius: 5px;
  }
  .antwort :global(.codeblock) {
    margin: 0 0 0.95em; border: 1px solid var(--linie); border-radius: 12px;
    overflow: hidden; background: var(--code-grund);
  }
  .antwort :global(.code-kopf) {
    display: flex; align-items: center; justify-content: space-between; padding: 6px 12px;
    border-bottom: 1px solid var(--linie); font-size: 11.5px; color: var(--text-still); background: var(--bg-seite);
  }
  .antwort :global(.code-kopieren) {
    border: none; background: none; color: var(--text-still); font: inherit; font-size: 11.5px;
    cursor: pointer; padding: 2px 6px; border-radius: 5px;
  }
  .antwort :global(.code-kopieren:hover) { background: var(--linie); color: var(--text); }
  /* Numbers and code side by side, the numbers in a column of their own so
     a selection cannot pick them up. */
  .antwort :global(.codeblock pre) {
    margin: 0; padding: 13px 15px; overflow-x: auto;
    display: flex; gap: 12px; align-items: flex-start;
  }
  .antwort :global(.code-nummern) {
    flex: none;
    user-select: none;
    -webkit-user-select: none;
    text-align: right;
    padding-right: 12px;
    border-right: 1px solid var(--linie);
    color: var(--text-still);
    font-family: var(--schrift-fest);
    font-size: 12.8px;
    line-height: 1.6;
    white-space: pre;
  }
  .antwort :global(.codeblock pre code) { flex: 1; min-width: 0; }
  .antwort :global(.codeblock code) {
    background: none; padding: 0; border-radius: 0; font-size: 12.8px; line-height: 1.6;
    color: var(--code-vordergrund);
  }
  /* The file box.

     Built as the sibling of the document card above: same sheet with a
     folded corner, same gap, same quiet frame. A file handed in and a file
     handed back are the same kind of thing, and they should not look like
     two different inventions.

     It stands as wide as it needs and no wider — a box that stretches
     across the whole answer reads as a section, not as one object you can
     pick up. */
  .antwort :global(.dateikasten) { margin: 0 0 0.95em; }
  .antwort :global(.datei-knopf) {
    display: flex;
    align-items: center;
    gap: 9px;
    max-width: 100%;
    border: 1px solid var(--linie);
    border-radius: 12px;
    background: var(--bg-erhoben);
    color: var(--text-leise);
    font: inherit;
    font-size: 12.5px;
    text-align: left;
    padding: 8px 14px 8px 10px;
    cursor: pointer;
    transition: border-color 0.12s, background 0.12s;
  }
  .antwort :global(.datei-knopf:hover) {
    border-color: var(--linie-stark);
    background: var(--blase);
  }
  .antwort :global(.datei-zeichen) { flex: none; color: var(--text-still); }
  .antwort :global(.datei-text) { min-width: 0; }
  .antwort :global(.datei-name) {
    display: block;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  /* Kind and weight are facts, so they work with brightness alone. */
  .antwort :global(.datei-fakten) {
    display: block;
    font-size: 11px;
    color: var(--text-still);
  }
  .antwort :global(.datei-hinweis) {
    flex: none;
    margin-left: 14px;
    font-size: 11.5px;
    color: var(--text-still);
  }
  .antwort :global(.datei-knopf:hover .datei-hinweis) { color: var(--text-leise); }

  /* The colours themselves live in stil/codefarben.css — one set of rules
     for every place that shows code, so the chat and the tool prompt can
     never drift apart. */
</style>
