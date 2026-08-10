/* A rough answer to "will this fit?" before the server starts.

   The model needs its file size in memory. The conversation on top — the
   KV cache — grows with context length AND with model size; the factor
   below is a rule of thumb calibrated against published f16 cache sizes:
   roughly 8 KB per token of context for every gigabyte of model file. It
   is an estimate and is shown as one — the point is the order of
   magnitude, not the decimal. */
export function speicherSchaetzung(modellGb, kontext, drafterGb = 0) {
  const kv = (kontext * 8 * modellGb) / 1e6
  return {
    modell: modellGb,
    drafter: drafterGb,
    kv,
    gesamt: modellGb + drafterGb + kv,
  }
}
