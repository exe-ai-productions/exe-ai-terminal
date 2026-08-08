<script>
  /* The house's switch — one build, used everywhere.

     Two tones, and the difference matters: red says this is an
     intervention (suspending the system prompt), black says it is a
     preference (outline bubbles, a model in the quick picker). Whoever
     reaches for red should feel that something is being taken away.

     Its own component so the next switch is not drawn a second time with
     slightly different numbers. */
  let {
    an = false,
    /* 'eingriff' → red when on, 'vorliebe' → black. */
    art = 'vorliebe',
    beschriftung = '',
    gesperrt = false,
    onschalten = null,
  } = $props()
</script>

<button
  class="schalter"
  class:eingriff={art === 'eingriff'}
  aria-pressed={an}
  aria-label={beschriftung}
  disabled={gesperrt}
  onclick={(e) => { e.stopPropagation(); onschalten?.(!an) }}
><i></i></button>

<style>
  .schalter {
    position: relative;
    width: 38px;
    height: 22px;
    flex: none;
    border: none;
    padding: 0;
    border-radius: 11px;
    background: var(--linie-stark);
    cursor: pointer;
    transition: background 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .schalter i {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--bg-erhoben);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transition: transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
  }
  .schalter[aria-pressed='true'] {
    background: var(--text);
  }
  /* Red is reserved for taking something away, not for taste. */
  .schalter.eingriff[aria-pressed='true'] {
    background: var(--rot);
  }
  .schalter[aria-pressed='true'] i {
    transform: translateX(16px);
  }
  .schalter:disabled {
    opacity: 0.4;
    cursor: default;
  }
</style>
