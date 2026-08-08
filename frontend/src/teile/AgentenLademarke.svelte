<script>
  /* The agent mark as a waiting indicator: same
     construction as the loading mark in the chat — the mark draws itself,
     then three dots trail off. Sits in the card of a running job behind
     the status and visibly says: an agent is working here right now.

     The paths are those of the agent mark (hat, pair of eyes, torso), the
     choreography is the chat's: drawing in three strokes, then the dots,
     then a breather and over again. Same duration as over there (3.4 s),
     so the two indicators never beat against each other. */
  import { t } from '../lib/texte.svelte.js'
</script>

<span class="denkt" aria-label={t('jobs.zustand.laeuft')}>
  <svg class="lademarke" viewBox="0 0 132 64" fill="none" stroke="currentColor"
       stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path class="strich hut" d="M18 24 V15 Q18 8 32 8 Q46 8 46 15 V24" stroke-width="5" style="--laenge:62" />
    <path class="strich krempe" d="M6 24 Q32 30 58 24" stroke-width="5" style="--laenge:54" />
    <path class="strich auge" d="M23 30 L27 33 L23 36" stroke-width="4.6" style="--laenge:12" />
    <path class="strich auge" d="M41 30 L37 33 L41 36" stroke-width="4.6" style="--laenge:12" />
    <path class="strich koerper" d="M8 60 V51 Q8 42 19 39.5 L32 47 L45 39.5 Q56 42 56 51 V60" stroke-width="5" style="--laenge:110" />
    <circle class="tupf t1" cx="92" cy="42" r="2.75" fill="currentColor" stroke="none" />
    <circle class="tupf t2" cx="106" cy="42" r="2.75" fill="currentColor" stroke="none" />
    <circle class="tupf t3" cx="120" cy="42" r="2.75" fill="currentColor" stroke="none" />
  </svg>
</span>

<style>
  .denkt {
    display: inline-flex;
    align-items: center;
    line-height: 1;
  }
  .lademarke {
    width: 43px;
    height: 21px;
    color: var(--text-still);
    animation: atemzug 3.4s linear infinite;
  }
  @keyframes atemzug {
    0%, 78% { opacity: 1; }
    96%, 100% { opacity: 0; }
  }
  .strich {
    stroke-dasharray: var(--laenge);
    stroke-dashoffset: var(--laenge);
  }
  .hut { animation: ziehen1 3.4s cubic-bezier(0.45, 0, 0.25, 1) infinite; }
  .krempe { animation: ziehen2 3.4s cubic-bezier(0.45, 0, 0.25, 1) infinite; }
  .auge { animation: ziehen3 3.4s cubic-bezier(0.45, 0, 0.25, 1) infinite; }
  .koerper { animation: ziehen4 3.4s cubic-bezier(0.45, 0, 0.25, 1) infinite; }
  @keyframes ziehen1 { 0% { stroke-dashoffset: var(--laenge); } 18%, 100% { stroke-dashoffset: 0; } }
  @keyframes ziehen2 { 0%, 12% { stroke-dashoffset: var(--laenge); } 26%, 100% { stroke-dashoffset: 0; } }
  @keyframes ziehen3 { 0%, 24% { stroke-dashoffset: var(--laenge); } 32%, 100% { stroke-dashoffset: 0; } }
  @keyframes ziehen4 { 0%, 28% { stroke-dashoffset: var(--laenge); } 40%, 100% { stroke-dashoffset: 0; } }

  .tupf {
    opacity: 0;
    transform-box: fill-box;
    transform-origin: center;
  }
  .t1 { animation: tupfen1 3.4s cubic-bezier(0.2, 0.9, 0.3, 1) infinite; }
  .t2 { animation: tupfen2 3.4s cubic-bezier(0.2, 0.9, 0.3, 1) infinite; }
  .t3 { animation: tupfen3 3.4s cubic-bezier(0.2, 0.9, 0.3, 1) infinite; }
  @keyframes tupfen1 { 0%, 42% { opacity: 0; transform: scale(0.35); } 50%, 100% { opacity: 1; transform: scale(1); } }
  @keyframes tupfen2 { 0%, 49% { opacity: 0; transform: scale(0.35); } 57%, 100% { opacity: 1; transform: scale(1); } }
  @keyframes tupfen3 { 0%, 56% { opacity: 0; transform: scale(0.35); } 64%, 100% { opacity: 1; transform: scale(1); } }

  /* Whoever can't tolerate motion gets the finished drawing at a standstill. */
  @media (prefers-reduced-motion: reduce) {
    .lademarke, .lademarke * { animation: none !important; }
    .strich { stroke-dashoffset: 0; }
    .tupf { opacity: 1; }
  }
</style>
