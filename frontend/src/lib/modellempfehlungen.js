/*
  The curated catalogue — which model to suggest for a machine, and in
  which build.

  Its own module because it is data, not markup, and the one place a name
  changes when a better model comes along. The search next to it finds
  everything; this list answers what the search cannot: *which of the
  thousands is the one for my machine.*

  A card is a MODEL, not a file. One card can carry several builds
  (`fassungen`) — a 4-bit that fits a laptop and an 8-bit that wants a
  workstation — and the one that suits the machine is pre-picked. Every
  build is one GGUF file that can be fetched with one button and started
  with another; nothing here asks anybody to open a terminal.

  Each build carries the exact companion names, all checked against the
  repository they name — a recommendation that 404s looks like a broken
  program, not a wrong list:
    `mmproj` is the vision projector as the repository names it,
    `mmproj_ziel` the name it gets locally (several repositories call
    theirs plainly `mmproj-F16.gguf`, and two of those in one folder would
    overwrite each other).
    `drafter` is the speed module that makes answers faster — a prediction
    module (mtp) trained alongside the model, or a tiny sibling where the
    family ships one, never a mid-sized model. `drafter_ziel` names it
    locally, `drafter_repo` says where it lives when that is not the
    model's own repository.
    `bis` is the memory step the build is the pick for.

  Only four cards are truly curated today. More arrive by data care, never
  by guessing — a card whose repository or file name was not verified is
  left out on purpose.
*/

import { speicherSchaetzung } from './speicherschaetzung.js'

/* The kinds the search offers. A format name is a name, like a tool name —
   it never goes through the translation catalogue. Only GGUF for now: the
   one the program can fetch as a single file and start by itself. */
export const ARTEN = ['gguf']

/* The context the fit estimate assumes — the everyday case, not the model's
   ceiling. A build "fits" when its file plus a conversation of this size
   plus its speed module stay under the machine's memory. */
const STANDARD_KONTEXT = 32768

/* A rough weight for a speed module that rides along — a few hundred
   megabytes. The estimate is an order of magnitude, not a decimal. */
const DRAFTER_GB = 0.4

/* The machine sizes an honest "needs a bigger machine" rounds up to. */
const MASCHINEN = [8, 16, 32, 64, 128]

export const KATALOG = [
  {
    id: 'gemma-4-31B',
    name: 'Gemma 4 31B',
    von: 'Google',
    logo: 'G',
    marke: 'google',
    satz: 'katalog.satz_gemma31',
    langsatz: 'katalog.lang_gemma31',
    faehigkeiten: ['winkel', 'auge', 'blitz'],
    kontext: 131072,
    fassungen: [
      {
        id: 'unsloth/gemma-4-31B-it-qat-GGUF',
        name: '4-Bit QAT',
        datei: 'gemma-4-31B-it-qat-UD-Q4_K_XL.gguf',
        groesse: 16.1,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'gemma-4-31B-it-mmproj-F16.gguf',
        drafter: 'mtp-gemma-4-31B-it.gguf',
        drafter_ziel: 'mtp-gemma-4-31B-it-qat.gguf',
        warum: 'werkzeug_flaggschiff',
        bis: 32,
      },
      {
        id: 'unsloth/gemma-4-31B-it-GGUF',
        name: '8-Bit',
        datei: 'gemma-4-31B-it-UD-Q8_K_XL.gguf',
        groesse: 35.0,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'gemma-4-31B-it-mmproj-F16.gguf',
        drafter: 'mtp-gemma-4-31B-it.gguf',
        drafter_ziel: 'mtp-gemma-4-31B-it.gguf',
        warum: 'werkzeug_acht_bit',
        bis: 64,
      },
    ],
  },
  {
    id: 'gemma-4-12B',
    name: 'Gemma 4 12B',
    von: 'Google',
    logo: 'G',
    marke: 'google',
    satz: 'katalog.satz_gemma12',
    langsatz: 'katalog.lang_gemma12',
    faehigkeiten: ['winkel', 'auge', 'blitz'],
    kontext: 131072,
    fassungen: [
      {
        id: 'unsloth/gemma-4-12B-it-qat-GGUF',
        name: '4-Bit QAT',
        datei: 'gemma-4-12B-it-qat-UD-Q4_K_XL.gguf',
        groesse: 6.3,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'gemma-4-12B-it-qat-mmproj-F16.gguf',
        drafter: 'mtp-gemma-4-12B-it.gguf',
        drafter_ziel: 'mtp-gemma-4-12B-it.gguf',
        warum: 'werkzeug_qat',
        bis: 16,
      },
    ],
  },
  {
    id: 'ternary-bonsai-27B',
    name: 'Ternary Bonsai 27B',
    von: 'Prism ML',
    logo: 'B',
    marke: 'prism',
    satz: 'katalog.satz_ternary',
    langsatz: 'katalog.lang_ternary',
    faehigkeiten: ['winkel', 'auge'],
    kontext: 65536,
    fassungen: [
      {
        id: 'prism-ml/Ternary-Bonsai-27B-gguf',
        name: '2 Bit',
        datei: 'Ternary-Bonsai-27B-Q2_0.gguf',
        groesse: 7.2,
        mmproj: 'Ternary-Bonsai-27B-mmproj-Q8_0.gguf',
        mmproj_ziel: 'Ternary-Bonsai-27B-mmproj-Q8_0.gguf',
        warum: 'zwei_bit',
        bis: 16,
      },
    ],
  },
  {
    id: 'exe-guard-dynamic',
    name: 'Exe Guard Dynamic',
    von: 'Exe',
    logo: '>',
    marke: 'exe',
    satz: 'katalog.satz_exeguard',
    langsatz: 'katalog.lang_exeguard',
    faehigkeiten: ['eew', 'winkel', 'auge', 'blitz'],
    kontext: 4096,
    fassungen: [
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '8-Bit · Q8_0', datei: 'Exe-Guard-Dynamic-Q8_0.gguf', groesse: 3.06 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '6-Bit · Q6_K', datei: 'Exe-Guard-Dynamic-Q6_K.gguf', groesse: 2.36 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '4-Bit · Q4_K_M', datei: 'Exe-Guard-Dynamic-Q4_K_M.gguf', groesse: 1.8 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '4-Bit I-Quant · IQ4_XS', datei: 'Exe-Guard-Dynamic-IQ4_XS.gguf', groesse: 1.62 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '2-Bit · Q2_K', datei: 'Exe-Guard-Dynamic-Q2_K.gguf', groesse: 1.19 },
    ],
  },
  {
    id: 'exe-turbo-s',
    name: 'Exe Turbo S',
    von: 'Exe',
    logo: '>',
    marke: 'exe',
    satz: 'katalog.satz_exeturbo',
    langsatz: 'katalog.lang_exeturbo',
    faehigkeiten: ['eew', 'winkel', 'gluehbirne'],
    kontext: 128000,
    fassungen: [
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '8-Bit · Q8_0', datei: 'Exe-Turbo-S-v3-Q8_0.gguf', groesse: 9.01 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '6-Bit · Q6_K', datei: 'Exe-Turbo-S-v3-Q6_K.gguf', groesse: 6.96 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '5-Bit · Q5_K_M', datei: 'Exe-Turbo-S-v3-Q5_K_M.gguf', groesse: 6.03 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '4-Bit · Q4_K_M', datei: 'Exe-Turbo-S-v3-Q4_K_M.gguf', groesse: 5.16 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '3-Bit I-Quant · IQ3_M', datei: 'Exe-Turbo-S-v3-IQ3_M.gguf', groesse: 3.78 },
    ],
  },
]

/** The memory a build needs to run at the everyday context, in GB. */
export function bedarf(fassung) {
  const beifahrer = fassung.drafter ? DRAFTER_GB : 0
  return speicherSchaetzung(fassung.groesse, STANDARD_KONTEXT, beifahrer).gesamt
}

/** Does this build run comfortably on a machine with this much memory? */
export function passt(fassung, gigabyte) {
  return gigabyte != null && bedarf(fassung) <= gigabyte
}

/** The smallest standard machine size that runs this build. */
export function brauchtMaschine(fassung) {
  const b = bedarf(fassung)
  return MASCHINEN.find((m) => m >= b) ?? MASCHINEN[MASCHINEN.length - 1]
}

/** The build to pre-pick for a machine: the best (largest) that fits, or —
    when none fits — the smallest, so the choice is honest rather than
    empty. */
export function passendeFassung(karte, gigabyte) {
  const passend = karte.fassungen.filter((f) => passt(f, gigabyte))
  const pool = passend.length ? passend : karte.fassungen
  const groesser = passend.length
    ? (a, b) => (b.groesse > a.groesse ? b : a)
    : (a, b) => (b.groesse < a.groesse ? b : a)
  return pool.reduce(groesser)
}

/** Does the card fit the machine at all — has it a build that runs? */
export function kartePasst(karte, gigabyte) {
  return karte.fassungen.some((f) => passt(f, gigabyte))
}

/** The one card to suggest for a fresh machine: the most capable that
    fits, so the first model is the best the machine can carry — the same
    call the onboarding makes. Returns { karte, fassung } or null. */
export function empfehlungFuer(gigabyte) {
  const passend = KATALOG.filter((k) => kartePasst(k, gigabyte))
  const pool = passend.length ? passend : KATALOG
  let beste = null
  for (const karte of pool) {
    const fassung = passendeFassung(karte, gigabyte)
    if (!beste || fassung.groesse > beste.fassung.groesse) beste = { karte, fassung }
  }
  return beste
}

/** Kept as a pure recommender: the card recommended for this much memory.
    The onboarding reads it to name a first model for the machine. */
export function stufeFuer(gigabyte) {
  return empfehlungFuer(gigabyte)?.karte ?? null
}
