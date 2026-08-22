<script>
  /* A number field with the house's own steppers.

     The browser's native spinners cannot be styled and sit in the fields
     like a foreign body next to the select chevrons. So the input hides
     them and carries two chevron buttons of its own — same stroke, same
     colour as every other arrow in these forms. */
  let {
    wert = $bindable(0),
    min = 0,
    max = 999999,
    schritt = 1,
    id = '',
    gesperrt = false,
    /* A word shown INSTEAD of the zero — for fields where 0 does not mean
       zero but "the program decides" (clip-skip). Empty: plain numbers. */
    nullwort = '',
  } = $props()

  let fokus = $state(false)
  const wortDa = $derived(Boolean(nullwort) && !fokus && Number(wert) === 0)

  function setzen(neu) {
    wert = Math.min(max, Math.max(min, neu))
  }

  /* Typed input commits through the same clamp as the chevrons — an empty
     or out-of-range field would otherwise travel to the server as it is
     and come back as a validation error. */
  function eingerastet() {
    setzen(Number(wert) || min)
  }
</script>

<div class="zahl" class:gesperrt>
  {#if wortDa}
    <span class="nullwort">{nullwort}</span>
  {/if}
  <input
    {id}
    type="number"
    class:versteckt={wortDa}
    bind:value={wert}
    {min}
    {max}
    step={schritt}
    disabled={gesperrt}
    onchange={eingerastet}
    onfocus={() => (fokus = true)}
    onblur={() => (fokus = false)}
  />
  <span class="treppe">
    <button
      type="button"
      tabindex="-1"
      aria-label="+"
      disabled={gesperrt}
      onclick={() => setzen((Number(wert) || 0) + schritt)}
    >
      <svg width="11" height="7" viewBox="0 0 12 8" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 6.5 6 1.5l5 5" />
      </svg>
    </button>
    <button
      type="button"
      tabindex="-1"
      aria-label="−"
      disabled={gesperrt}
      onclick={() => setzen((Number(wert) || 0) - schritt)}
    >
      <svg width="11" height="7" viewBox="0 0 12 8" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 1.5 6 6.5l5-5" />
      </svg>
    </button>
  </span>
</div>

<style>
  .zahl {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    /* The one height every long control in the house stands at, and the
       palette's corner for a control — so a row of fields, pickers and
       buttons reads as one line of equals. */
    height: 36px;
    border: 1px solid var(--linie-stark);
    border-radius: 9px;
    background: var(--bg);
  }
  input {
    flex: 1;
    min-width: 0;
    border: none;
    background: none;
    color: var(--text);
    font: 400 13.5px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    padding: 6px 4px 6px 10px;
    text-align: right;
    outline: none;
    appearance: textfield;
  }
  input::-webkit-inner-spin-button,
  input::-webkit-outer-spin-button {
    appearance: none;
    margin: 0;
  }
  /* While the word stands in, the zero steps aside; a click on the field
     brings the number back for typing. */
  input.versteckt {
    color: transparent;
  }
  .nullwort {
    position: absolute;
    right: 34px;
    font: 400 13.5px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
    color: var(--text-still);
    pointer-events: none;
  }
  .gesperrt input {
    color: var(--text-still);
  }
  .treppe {
    display: flex;
    flex-direction: column;
    flex: none;
    padding: 2px 6px 2px 2px;
  }
  .treppe button {
    display: inline-flex;
    border: none;
    background: none;
    padding: 1px 2px;
    color: var(--text-still);
    cursor: pointer;
  }
  .treppe button:hover {
    color: var(--text);
  }
  .treppe button:disabled {
    color: var(--linie-stark);
    cursor: default;
  }
</style>
