/*
  Which embedded mark a search hit carries.

  The mark answers what model family a hit is, not who uploaded it: people
  search by family name, and most GGUF builds come from quantisers — a Qwen
  build under an unsloth name still reads as Qwen. The small line under the
  model name keeps naming the publisher, so nobody is claimed to be the
  maker. Only families with an original vector in lib/logos.js appear here;
  everything else stays the honest dashed letter, a mark is never guessed.

  Matched against name and publisher in one pass: the family word usually
  sits in the model name, and for first-party repositories it is the
  organisation name itself.
*/

import { LOGOS } from './logos.js'

/* Mistral names its sizes and trades by their own words, all of one
   house. List order decides nothing — see the position rule below. The
   long words may sit anywhere in a name (codellama, tinyllama); the short
   ones marked strict must start the name or follow a separator, because
   they hide inside other words — "phi-" inside Delphi, "ibm-" inside
   libm. A bare "meta" stays out entirely, it would claim MetaMath. */
const FAMILIEN = [
  ['qwen', 'qwen'],
  ['qwq', 'qwen'],
  ['qvq', 'qwen'],
  ['deepseek', 'deepseek'],
  ['mistral', 'mistral'],
  ['mixtral', 'mistral'],
  ['ministral', 'mistral'],
  ['magistral', 'mistral'],
  ['devstral', 'mistral'],
  ['codestral', 'mistral'],
  ['mathstral', 'mistral'],
  ['pixtral', 'mistral'],
  ['gemma', 'google'],
  ['llama', 'meta'],
  ['phi-', 'microsoft', true],
  ['phi3', 'microsoft', true],
  ['phi4', 'microsoft', true],
  ['bitnet', 'microsoft'],
  ['microsoft', 'microsoft'],
  ['gpt-oss', 'openai'],
  ['gpt2', 'openai', true],
  ['gpt-2', 'openai', true],
  ['whisper', 'openai'],
  ['openai', 'openai'],
  ['granite', 'ibm'],
  ['ibm-', 'ibm', true],
  ['smollm', 'huggingface'],
  ['smolvlm', 'huggingface'],
  ['kimi', 'kimi'],
  ['moonshot', 'kimi'],
  ['cohere', 'cohere'],
  ['command-r', 'cohere'],
  ['c4ai', 'cohere'],
  ['aya-', 'cohere', true],
  ['glm', 'zhipu'],
  ['zhipu', 'zhipu'],
  ['zai-org', 'zhipu'],
  ['grok', 'grok'],
  ['nemotron', 'nvidia'],
  ['nvidia', 'nvidia'],
  ['bonsai', 'prism'],
  ['prism', 'prism'],
  ['olmo', 'allenai', true],
  ['molmo', 'allenai'],
  ['tulu', 'allenai', true],
  ['allenai', 'allenai'],
  ['openelm', 'apple'],
  ['fastvlm', 'apple'],
  ['apple', 'apple', true],
  ['mimo', 'xiaomi', true],
  ['xiaomi', 'xiaomi'],
  ['exaone', 'lg'],
  ['hermes', 'nous'],
  ['nous', 'nous', true],
]

/* The first occurrence a strict word may count is one at a word start —
   the beginning, or right after a character that separates words. */
function stelleVon(heu, wort, streng) {
  let von = 0
  for (;;) {
    const i = heu.indexOf(wort, von)
    if (i < 0) return -1
    if (!streng || i === 0 || !/[a-z0-9]/.test(heu[i - 1])) return i
    von = i + 1
  }
}

/** The embedded mark for a model name plus publisher, or null. The
    earliest family word in the name wins: a DeepSeek distill onto a Qwen
    base names DeepSeek first and is DeepSeek's model, not Qwen's. */
export function modellMarke(name, anbieter) {
  const heu = `${name || ''} ${anbieter || ''}`.toLowerCase()
  let beste = null
  for (const [wort, marke, streng] of FAMILIEN) {
    const stelle = stelleVon(heu, wort, streng)
    if (stelle >= 0 && (beste === null || stelle < beste.stelle)) beste = { stelle, marke }
  }
  return beste ? LOGOS[beste.marke] : null
}
