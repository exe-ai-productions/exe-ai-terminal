/*
  Which model to suggest for how much memory — the curated list.

  Its own module because it is data, not markup, and because it is the one
  place a name has to be changed when a better model comes along. The search
  next to it finds everything; this list answers the question the search
  cannot: *which of these thousands is the one for my machine.*

  Four steps, by the memory the machine has. The step is deliberately the
  whole machine and not the free memory: a number that changes while you look
  at it cannot be the basis for a recommendation.

  `groesse` is the measured size of the file, not an estimate — a model needs
  its size in memory plus room for the conversation, so a step is only honest
  while the file stays clearly under it.

  Every entry is one GGUF file, and that is the whole point: one file can be
  fetched with one button and started with another. Nothing here asks anybody
  to open a terminal.

  `mmproj` is the model's vision projector as the repository names it,
  `mmproj_ziel` the name it gets in the local folder — carrying the model's
  own name, because several repositories call theirs plainly
  `mmproj-BF16.gguf` and two of those in one folder would overwrite each
  other. The download fetches it right after the model; the runner attaches
  it by that shared name.

  A step that loses its model keeps its place with `modelle: []`. An empty
  step says "we have not chosen yet", which is true; leaving it out entirely
  would say "there is nothing for your machine", which is not.
*/

/* The kinds the search offers. A format name is a name, like a tool name —
   it never goes through the translation catalogue.

   Only GGUF for now: it is the one the program can fetch as a single file
   and start by itself. MLX runs beautifully on this machine and is a poor
   thing to hand somebody else — it is a Python package, not a file. */
export const ARTEN = ['gguf']

/* Two families, chosen for one job: calling tools without drama. The small
   steps keep Bonsai — dense, and unbeatable per gigabyte. From 16 GB up the
   list switches to Gemma 4, the first generation of that line trained to
   call tools natively: dense models only, because a model where the whole
   brain answers every word stays on task through long agent runs, which is
   exactly where sparse expert models drift off and start talking to
   themselves. One family across three steps also means one temperament —
   whoever upgrades their machine meets a model they already know.

   Every file name and size below was checked against the repository it
   names. A recommendation that 404s looks like a broken program, not like a
   wrong list. */
export const EMPFEHLUNGEN = [
  {
    bis: 8,
    /* One bit per weight — every weight is a single yes or no instead of a
       number with a decimal point. That is what brings a 27B model down to a
       file this small; a step of 8 GB has no room for anything larger,
       because a model needs its size in memory and the conversation needs
       the rest. */
    modelle: [
      {
        id: 'prism-ml/Bonsai-27B-gguf',
        name: 'Bonsai 27B · 1 Bit',
        datei: 'Bonsai-27B-Q1_0.gguf',
        art: 'gguf',
        groesse: 3.8,
        mmproj: 'Bonsai-27B-mmproj-Q8_0.gguf',
        mmproj_ziel: 'Bonsai-27B-mmproj-Q8_0.gguf',
        warum: 'ein_bit',
      },
    ],
  },
  {
    bis: 16,
    modelle: [
      {
        id: 'unsloth/gemma-4-12B-it-qat-GGUF',
        name: 'Gemma 4 12B · 4 Bit QAT',
        datei: 'gemma-4-12B-it-qat-UD-Q4_K_XL.gguf',
        art: 'gguf',
        groesse: 6.3,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'gemma-4-12B-it-qat-mmproj-F16.gguf',
        warum: 'werkzeug_qat',
      },
      {
        id: 'prism-ml/Ternary-Bonsai-27B-gguf',
        name: 'Ternary Bonsai 27B · 2 Bit',
        datei: 'Ternary-Bonsai-27B-Q2_0.gguf',
        art: 'gguf',
        groesse: 7.2,
        mmproj: 'Ternary-Bonsai-27B-mmproj-Q8_0.gguf',
        mmproj_ziel: 'Ternary-Bonsai-27B-mmproj-Q8_0.gguf',
        warum: 'zwei_bit',
      },
    ],
  },
  {
    bis: 32,
    modelle: [
      {
        id: 'unsloth/gemma-4-31B-it-qat-GGUF',
        name: 'Gemma 4 31B · 4 Bit QAT',
        datei: 'gemma-4-31B-it-qat-UD-Q4_K_XL.gguf',
        art: 'gguf',
        groesse: 16.1,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'gemma-4-31B-it-mmproj-F16.gguf',
        warum: 'werkzeug_flaggschiff',
      },
    ],
  },
  {
    bis: 64,
    modelle: [
      {
        id: 'unsloth/gemma-4-31B-it-GGUF',
        name: 'Gemma 4 31B · 8 Bit',
        datei: 'gemma-4-31B-it-UD-Q8_K_XL.gguf',
        art: 'gguf',
        groesse: 35.0,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'gemma-4-31B-it-mmproj-F16.gguf',
        warum: 'werkzeug_acht_bit',
      },
    ],
  },
]

/** The step a machine with this much memory falls into. */
export function stufeFuer(gigabyte) {
  return EMPFEHLUNGEN.find((s) => gigabyte <= s.bis) ?? EMPFEHLUNGEN[EMPFEHLUNGEN.length - 1]
}
