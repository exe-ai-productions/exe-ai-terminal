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

/* The catalogue's three tabs. Each is its own search on the server side
   (see app/api/v1/modellsuche.py) and its own curated list here — a chat
   model, an embedding model and an image model are different things to
   run, and a merged list offers each one where it cannot work. */
export const ARTEN = ['chat', 'einbettung', 'bild', 'zubehoer']

/* Where each accessory kind is downloaded to — a sub-folder of its server, so
   each folder shows only its own kind and the file appears where it belongs at
   once. VAE, LoRA and the face detector are image-side; a drafter and a
   projector are chat-side and also carry the companion role that writes the
   folder manifest. */
export const ZUBEHOER_ZIEL = {
  vae: { art: 'bild', unterordner: 'vae' },
  lora: { art: 'bild', unterordner: 'lora' },
  adetailer: { art: 'bild', unterordner: 'adetailer' },
  mmproj: { art: 'chat', unterordner: 'vision', rolle: 'mmproj' },
  mtp: { art: 'chat', unterordner: 'mtp', rolle: 'mtp' },
}

/* The accessory tab shows one column per kind, in this order. A generic
   mechanism, not a special case per tab: the gallery filters the cards by
   `sorte` into these columns and puts an "open folder" button on each. */
export const SPALTEN_ZUBEHOER = ['lora', 'vae', 'adetailer', 'mtp', 'mmproj']

/* Which server folder each accessory column opens, and on which side. */
export const ZUBEHOER_ORDNER = {
  lora: { seite: 'bild', unter: 'lora' },
  vae: { seite: 'bild', unter: 'vae' },
  adetailer: { seite: 'bild', unter: 'adetailer' },
  mtp: { seite: 'chat', unter: 'mtp' },
  mmproj: { seite: 'chat', unter: 'vision' },
}

/* The tabs whose search box does something. The two curated tabs (empty here)
   hide the box entirely — a search that always returns nothing is worse than
   no box. */
export const SUCHBARE_ARTEN = ['chat', 'einbettung', 'bild']

/* The colour each accessory kind wears on its card. The design rule of the
   house: one capability, one colour, EVERYWHERE. MTP is blue, exactly the
   blue of its speed-module bolt (--blau, #5b8dbe); mmproj is violet, exactly
   the violet of the vision eye in the input bar (--violett, #8d78bd) — so
   tag and live indicator read as one thing wherever they appear. */
export const SORTE_FARBE = {
  lora: '#bd7a53',
  vae: '#4e8f8b',
  adetailer: '#b56d84',
  mtp: '#5b8dbe',
  mmproj: '#8d78bd',
}

/* The capability colours — same guide, one capability, one colour,
   everywhere: bulb gold, bolt blue, eye violet, wrench olive, wherever
   they appear. EEW never appears here — its lilac monogram carries its
   own colours. */
export const FAEHIGKEIT_FARBE = {
  gluehbirne: '#c9a227',
  blitz: '#5b8dbe',
  auge: '#8d78bd',
  werkzeug: '#9aa05e',
}

/* The i18n key for each accessory kind's label — one place, so the card and
   the detail view cannot disagree and a new kind is added once. */
export const SORTE_LABEL = {
  vae: 'katalog.sorte_vae',
  lora: 'katalog.sorte_lora',
  adetailer: 'katalog.sorte_adetailer',
  mmproj: 'katalog.sorte_mmproj',
  mtp: 'katalog.sorte_mtp',
}

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
    /* The MoE flagship: its tempo module rides INSIDE the file (no
       separate drafter to fetch), the vision projector comes along with
       the build. Repository, file names, sizes and context verified
       against Hugging Face. The bolt badge stays off until the runner is
       MEASURED engaging the embedded module — a badge that promises speed
       nobody wired would be a lie. */
    id: 'qwen36-35b',
    name: 'Qwen3.6 35B A3B',
    von: 'Alibaba',
    logo: 'Q',
    marke: 'qwen',
    satz: 'katalog.satz_qwen36',
    langsatz: 'katalog.lang_qwen36',
    faehigkeiten: ['werkzeug', 'auge'],
    kontext: 262144,
    fassungen: [
      {
        id: 'unsloth/Qwen3.6-35B-A3B-MTP-GGUF',
        name: '4-Bit · UD-Q4_K_XL',
        datei: 'Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf',
        groesse: 22.9,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'Qwen3.6-35B-A3B-mmproj-F16.gguf',
        bis: 32,
      },
      {
        id: 'unsloth/Qwen3.6-35B-A3B-MTP-GGUF',
        name: '8-Bit · Q8_0',
        datei: 'Qwen3.6-35B-A3B-Q8_0.gguf',
        groesse: 37.8,
        mmproj: 'mmproj-F16.gguf',
        mmproj_ziel: 'Qwen3.6-35B-A3B-mmproj-F16.gguf',
        bis: 64,
      },
    ],
  },
  {
    /* The agent coder — the strongest open tool-calling coder in its
       weight class, and a terminal is exactly its habitat. Repository and
       files verified against Hugging Face. */
    id: 'qwen3-coder-30b',
    name: 'Qwen3 Coder 30B A3B',
    von: 'Alibaba',
    logo: 'Q',
    marke: 'qwen',
    satz: 'katalog.satz_qwencoder',
    langsatz: 'katalog.lang_qwencoder',
    faehigkeiten: ['werkzeug'],
    kontext: 262144,
    fassungen: [
      {
        id: 'unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF',
        name: '4-Bit · UD-Q4_K_XL',
        datei: 'Qwen3-Coder-30B-A3B-Instruct-UD-Q4_K_XL.gguf',
        groesse: 17.7,
        bis: 32,
      },
      {
        id: 'unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF',
        name: '8-Bit · Q8_0',
        datei: 'Qwen3-Coder-30B-A3B-Instruct-Q8_0.gguf',
        groesse: 32.5,
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
    faehigkeiten: ['werkzeug', 'auge', 'blitz'],
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
  /* The Exe row: our three models side by side, in this order — the core,
     the small one, the guardian. */
  {
    id: 'exe-core',
    name: 'Exe Core Dynamic',
    von: 'Exe',
    logo: '>',
    marke: 'exe',
    satz: 'katalog.satz_execore',
    langsatz: 'katalog.lang_execore',
    faehigkeiten: ['eew', 'werkzeug', 'auge'],
    kontext: 262144,
    fassungen: [
      { id: 'exeterminal/Exe-Core-Dynamic-V1-GGUF', name: '6-Bit · Q6_K', datei: 'Exe-Core-Dynamic-v1-Q6_K.gguf', groesse: 22.4 },
      { id: 'exeterminal/Exe-Core-Dynamic-V1-GGUF', name: '5-Bit · Q5_K_M', datei: 'Exe-Core-Dynamic-v1-Q5_K_M.gguf', groesse: 19.5 },
      { id: 'exeterminal/Exe-Core-Dynamic-V1-GGUF', name: '4-Bit · Q4_K_M', datei: 'Exe-Core-Dynamic-v1-Q4_K_M.gguf', groesse: 16.8 },
      { id: 'exeterminal/Exe-Core-Dynamic-V1-GGUF', name: '4-Bit I-Quant · IQ4_XS', datei: 'Exe-Core-Dynamic-v1-IQ4_XS.gguf', groesse: 15.4 },
      { id: 'exeterminal/Exe-Core-Dynamic-V1-GGUF', name: '2-Bit · Q2_K', datei: 'Exe-Core-Dynamic-v1-Q2_K.gguf', groesse: 10.9, notnagel: true },
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
    faehigkeiten: ['eew', 'werkzeug', 'gluehbirne'],
    kontext: 128000,
    fassungen: [
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '8-Bit · Q8_0', datei: 'Exe-Turbo-S-v3-Q8_0.gguf', groesse: 9.01 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '6-Bit · Q6_K', datei: 'Exe-Turbo-S-v3-Q6_K.gguf', groesse: 6.96 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '5-Bit · Q5_K_M', datei: 'Exe-Turbo-S-v3-Q5_K_M.gguf', groesse: 6.03 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '4-Bit · Q4_K_M', datei: 'Exe-Turbo-S-v3-Q4_K_M.gguf', groesse: 5.16 },
      { id: 'exeterminal/Exe-Turbo-S-V3-GGUF', name: '3-Bit I-Quant · IQ3_M', datei: 'Exe-Turbo-S-v3-IQ3_M.gguf', groesse: 3.78 },
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
    faehigkeiten: ['eew', 'werkzeug', 'auge', 'blitz'],
    kontext: 4096,
    fassungen: [
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '8-Bit · Q8_0', datei: 'Exe-Guard-Dynamic-Q8_0.gguf', groesse: 3.06 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '6-Bit · Q6_K', datei: 'Exe-Guard-Dynamic-Q6_K.gguf', groesse: 2.36 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '4-Bit · Q4_K_M', datei: 'Exe-Guard-Dynamic-Q4_K_M.gguf', groesse: 1.8 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '4-Bit I-Quant · IQ4_XS', datei: 'Exe-Guard-Dynamic-IQ4_XS.gguf', groesse: 1.62 },
      { id: 'exeterminal/Exe-Guard-Dynamic-GGUF', name: '2-Bit · Q2_K', datei: 'Exe-Guard-Dynamic-Q2_K.gguf', groesse: 1.19, notnagel: true },
    ],
  },
]

/* The embedding catalogue — small single-purpose models for the embedding
   server. Same care as the chat list: every repository, file name, size
   and context checked against Hugging Face. One
   build per card — an embedding model is fetched once and forgotten, a
   row of quants would be noise. */
export const KATALOG_EINBETTUNG = [
  {
    id: 'emb-qwen3', name: 'Qwen3 Embedding 0.6B', von: 'Alibaba',
    logo: 'Q', marke: 'qwen', faehigkeiten: [], kontext: 32768,
    satz: 'katalog.satz_emb_qwen3',
    fassungen: [{ id: 'Qwen/Qwen3-Embedding-0.6B-GGUF', name: '8-Bit · Q8_0', datei: 'Qwen3-Embedding-0.6B-Q8_0.gguf', groesse: 0.64 }],
  },
  {
    id: 'emb-nomic', name: 'Nomic Embed v1.5', von: 'Nomic AI',
    logo: 'N', marke: null, faehigkeiten: [], kontext: 2048,
    satz: 'katalog.satz_emb_nomic',
    fassungen: [{ id: 'nomic-ai/nomic-embed-text-v1.5-GGUF', name: '8-Bit · Q8_0', datei: 'nomic-embed-text-v1.5.Q8_0.gguf', groesse: 0.15 }],
  },
  {
    id: 'emb-gemma', name: 'EmbeddingGemma 300M', von: 'Google',
    logo: 'G', marke: 'google', faehigkeiten: [], kontext: 2048,
    satz: 'katalog.satz_emb_gemma',
    fassungen: [{ id: 'unsloth/embeddinggemma-300m-GGUF', name: '8-Bit · Q8_0', datei: 'embeddinggemma-300M-Q8_0.gguf', groesse: 0.33 }],
  },
  {
    id: 'emb-bgem3', name: 'BGE-M3', von: 'BAAI',
    logo: 'B', marke: null, faehigkeiten: [], kontext: 8192,
    satz: 'katalog.satz_emb_bgem3',
    fassungen: [{ id: 'gpustack/bge-m3-GGUF', name: '8-Bit · Q8_0', datei: 'bge-m3-Q8_0.gguf', groesse: 0.64 }],
  },
  {
    id: 'emb-mxbai', name: 'mxbai-embed-large', von: 'Mixedbread',
    logo: 'M', marke: null, faehigkeiten: [], kontext: 512,
    satz: 'katalog.satz_emb_mxbai',
    fassungen: [{ id: 'ChristianAzinn/mxbai-embed-large-v1-gguf', name: '8-Bit · Q8_0', datei: 'mxbai-embed-large-v1.Q8_0.gguf', groesse: 0.36 }],
  },
  {
    id: 'emb-minilm', name: 'All-MiniLM L6 v2', von: 'Sentence Transformers',
    logo: 'S', marke: null, faehigkeiten: [], kontext: 512,
    satz: 'katalog.satz_emb_minilm',
    fassungen: [{ id: 'second-state/All-MiniLM-L6-v2-Embedding-GGUF', name: '8-Bit · Q8_0', datei: 'all-MiniLM-L6-v2-Q8_0.gguf', groesse: 0.03 }],
  },
]

/* The image catalogue — single-file checkpoints for the local drawer
   (sd.cpp), each repository and file name checked against the real thing
   on Hugging Face (verified 2026-08-17). Not the chat card's shape: an
   image model has no context window and no KV cache, so a card carries its
   CLASS (which decides the resolution it opens at) and one file, not a row
   of GGUF builds. `bild: true` tells the card to draw itself that way.

   Two rows by intent: the first three are photoreal, the last three are the
   stylised ones. safetensors is the standard form — full quality, exactly
   what ComfyUI runs. `datei` is the exact file the download fetches into the
   image folder. `vae` names a companion for a model shipped without one. */
export const KATALOG_BILD = [
  {
    id: 'cyberrealistic-xl', name: 'CyberRealistic XL', von: 'Cyberdelia',
    logo: 'C', marke: null, bild: true, klasse: 'sdxl',
    satz: 'katalog.satz_cyberrealisticxl',
    fassungen: [{
      id: 'cyberdelia/CyberRealisticXL', name: 'safetensors',
      datei: 'CyberRealisticXLPlay_V10.0_FP16.safetensors', groesse: 6.9,
    }],
  },
  {
    id: 'juggernaut-xl', name: 'Juggernaut XL', von: 'RunDiffusion',
    logo: 'J', marke: null, bild: true, klasse: 'sdxl',
    satz: 'katalog.satz_juggernautxl',
    fassungen: [{
      id: 'RunDiffusion/Juggernaut-XL-v9', name: 'safetensors',
      datei: 'Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors', groesse: 7.1,
    }],
  },
  {
    id: 'realistic-vision', name: 'Realistic Vision', von: 'SG161222',
    logo: 'R', marke: null, bild: true, klasse: 'sd15',
    satz: 'katalog.satz_realisticvision',
    fassungen: [{
      id: 'SG161222/Realistic_Vision_V6.0_B1_noVAE', name: 'safetensors',
      datei: 'Realistic_Vision_V6.0_NV_B1_fp16.safetensors', groesse: 2.1,
    }],
  },
  {
    id: 'anything-v5', name: 'Anything v5', von: 'Community',
    logo: 'A', marke: null, bild: true, klasse: 'sd15',
    satz: 'katalog.satz_anythingv5',
    fassungen: [{
      id: 'genai-archive/anything-v5', name: 'safetensors',
      datei: 'anything-v5.safetensors', groesse: 2.1,
    }],
  },
  {
    id: 'toonyou', name: 'ToonYou', von: 'Bradcatt',
    logo: 'T', marke: null, bild: true, klasse: 'sd15',
    satz: 'katalog.satz_toonyou',
    fassungen: [{
      id: 'frankjoshua/toonyou_beta6', name: 'safetensors',
      datei: 'toonyou_beta6.safetensors', groesse: 2.3,
    }],
  },
  {
    id: 'animagine-xl', name: 'Animagine XL', von: 'Cagliostro Lab',
    logo: 'A', marke: null, bild: true, klasse: 'sdxl',
    satz: 'katalog.satz_animaginexl',
    fassungen: [{
      id: 'cagliostrolab/animagine-xl-3.1', name: 'safetensors',
      datei: 'animagine-xl-3.1.safetensors', groesse: 6.9,
    }],
  },
]

/* The accessories: small companion files, not models. Each carries a `sorte`
   that decides its column, its tag colour and the folder it lands in
   (ZUBEHOER_ZIEL). `bild: true` reuses the single-file card layout. Every
   repository and file name was checked against Hugging Face; a `ziel` is set
   whenever two repositories name their file the same, and the drafter/projector
   `ziel` names obey the runner's name heuristic so the bond holds without a
   manifest. Names are kept short so a card never wraps. */
const _zub = (id, name, von, logo, sorte, repo, datei, groesse, ziel, klasse) => ({
  id, name, von, logo, marke: null, bild: true, zubehoer: true, sorte,
  // The model class this file belongs to — 'sd15' | 'sdxl', or nothing for
  // the class-neutral kinds (detectors work on any picture; drafters and
  // projectors are bound to their chat model by name instead). The card
  // wears it as a pill, so nobody pairs an SD-1.5 file with an XL model
  // again without noticing (house rule after exactly that mishap).
  ...(klasse ? { klasse } : {}),
  satz: `katalog.satz_zub_${sorte}`,
  fassungen: [{ id: repo, name: 'Datei', datei, ...(ziel ? { ziel } : {}), groesse }],
})

export const KATALOG_ZUBEHOER = [
  // — LoRA —
  _zub('lora-lcm-15', 'LCM', 'Latent Consistency', 'L', 'lora',
    'latent-consistency/lcm-lora-sdv1-5', 'pytorch_lora_weights.safetensors', 0.14, 'lcm-lora-sdv1-5.safetensors', 'sd15'),
  _zub('lora-hyper-15', 'Hyper-SD', 'ByteDance', 'B', 'lora',
    'ByteDance/Hyper-SD', 'Hyper-SD15-8steps-lora.safetensors', 0.27, null, 'sd15'),
  _zub('lora-lcm-xl', 'LCM', 'Latent Consistency', 'L', 'lora',
    'latent-consistency/lcm-lora-sdxl', 'pytorch_lora_weights.safetensors', 0.39, 'lcm-lora-sdxl.safetensors', 'sdxl'),
  _zub('lora-light-xl', 'Lightning', 'ByteDance', 'B', 'lora',
    'ByteDance/SDXL-Lightning', 'sdxl_lightning_8step_lora.safetensors', 0.39, null, 'sdxl'),
  // Quality detailers, straight from the author's own repositories.
  _zub('lora-multidet-xl', 'Multi Detailer', 'Stable Yogi', 'Y', 'lora',
    'Stableyogi/Detailers', 'Super_Multi_Detailer_By_Stable_Yogi_A1.safetensors', 0.23, null, 'sdxl'),
  _zub('lora-skindet-15', 'Skin Detailer', 'Stable Yogi', 'Y', 'lora',
    'Stableyogi/Super-Skin-Detailer', 'Super_Skin_Detailer_By_Stable_Yogi_SD0_V1.safetensors', 0.12, null, 'sd15'),
  // — VAE —
  _zub('vae-mse-15', 'MSE', 'Stability AI', 'S', 'vae',
    'stabilityai/sd-vae-ft-mse-original', 'vae-ft-mse-840000-ema-pruned.safetensors', 0.34, null, 'sd15'),
  _zub('vae-ema-15', 'EMA', 'Stability AI', 'S', 'vae',
    'stabilityai/sd-vae-ft-ema-original', 'vae-ft-ema-560000-ema-pruned.safetensors', 0.34, null, 'sd15'),
  _zub('vae-fp16-xl', 'fp16-fix', 'madebyollin', 'M', 'vae',
    'madebyollin/sdxl-vae-fp16-fix', 'sdxl_vae.safetensors', 0.34, 'sdxl-vae-fp16-fix.safetensors', 'sdxl'),
  _zub('vae-orig-xl', 'Original', 'Stability AI', 'S', 'vae',
    'stabilityai/sdxl-vae', 'sdxl_vae.safetensors', 0.34, 'sdxl-vae-original.safetensors', 'sdxl'),
  // — ADetailer —
  // The raw Bingsu .pt files use a torch pickle the generator cannot read;
  // the catalogue hands out the same weights repackaged as safetensors from
  // the house repository, so every card downloads a file that actually loads.
  // (The person segmentation model stays out: never converted, never tested.)
  _zub('ad-face-n', 'Gesichter v8n', 'Bingsu', 'B', 'adetailer',
    'exeterminal/adetailer-yolov8-safetensors', 'face_yolov8n.safetensors', 0.01),
  _zub('ad-face-s', 'Gesichter v8s', 'Bingsu', 'B', 'adetailer',
    'exeterminal/adetailer-yolov8-safetensors', 'face_yolov8s.safetensors', 0.02),
  _zub('ad-hand-n', 'Hände v8n', 'Bingsu', 'B', 'adetailer',
    'exeterminal/adetailer-yolov8-safetensors', 'hand_yolov8n.safetensors', 0.01),
  // — MTP (drafter) —
  _zub('mtp-gemma-12', 'Gemma 4 12B', 'Unsloth', 'U', 'mtp',
    'unsloth/gemma-4-12B-it-qat-GGUF', 'MTP/mtp-gemma-4-12B-it-Q4_0.gguf', 0.25, 'mtp-gemma-4-12B-it.gguf'),
  // — Vision (mmproj) —
  _zub('mm-gemma-12', 'Gemma 4 12B', 'Unsloth', 'U', 'mmproj',
    'unsloth/gemma-4-12B-it-qat-GGUF', 'mmproj-F16.gguf', 0.18, 'gemma-4-12B-it-mmproj-F16.gguf'),
  _zub('mm-qwen-35', 'Qwen3.6 35B', 'Unsloth', 'U', 'mmproj',
    'unsloth/Qwen3.6-35B-A3B-MTP-GGUF', 'mmproj-F16.gguf', 0.9, 'Qwen3.6-35B-A3B-mmproj-F16.gguf'),
]

/* One table carries all lists, keyed by the same names as ARTEN — so the tabs,
   the lookup and the per-kind data cannot disagree. */
const KATALOGE = {
  chat: KATALOG, einbettung: KATALOG_EINBETTUNG, bild: KATALOG_BILD, zubehoer: KATALOG_ZUBEHOER,
}

/** The curated list for a catalogue tab — what `Katalog.svelte` shows when
    that tab is open. Falls back to the chat list for an unknown key so a
    typo never renders an empty gallery silently. */
export const katalogFuer = (art) => KATALOGE[art] ?? KATALOG

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
    call the onboarding makes. Returns { karte, fassung } or null.

    Builds marked `notnagel` (the 2-bit last resorts) never carry the
    recommendation: a card may offer them for a hand-picked download, but
    the machine's FIRST model must not be a quant its own card warns
    about. */
export function empfehlungFuer(gigabyte) {
  const empfehlbar = (karte) => ({
    ...karte,
    fassungen: karte.fassungen.filter((f) => !f.notnagel),
  })
  const kandidaten = KATALOG.map(empfehlbar).filter((k) => k.fassungen.length)
  const passend = kandidaten.filter((k) => kartePasst(k, gigabyte))
  const pool = passend.length ? passend : kandidaten
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
