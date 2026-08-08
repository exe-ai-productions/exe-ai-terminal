/*
  The shipped tool servers: what we offer to connect, and under which name.

  Its own module because two windows ask the same question. The connections
  gallery needs the address and the kind of sign-in; the tools window needs
  only the proper name — `notion` is what the file calls it, `Notion` is what
  it is called. Capitalising the id would work for exactly that one and turn
  SearXNG into Searxng.

  `vorauswahl` is the vetted allowlist per provider. `null` means "offer
  everything" for now — the lists come into being as the providers are tested
  one by one. Short lists on purpose: twenty tool descriptions ruin the hit
  rate of a small local model.
*/

export const SERVERKATALOG = [
  /* The search that ships with the program. `anmeldung: 'keine'` is the
     honest entry for a server that runs here: there is nothing to sign in
     to, no address to reach, no key to set — it is simply on. The name in
     the file is a plain id; the title is the product it belongs to. */
  { name: 'websuche', titel: 'Exe Web Search', url: null, anmeldung: 'keine', vorauswahl: null },
  /* Recraft preselection, set while testing: generate, image-to-image,
     background removal — and inpainting, because the second wish after every
     first image is "change the sunglasses". The rest stays selectable. */
  {
    name: 'recraft',
    titel: 'Recraft',
    url: 'https://mcp.recraft.ai/mcp',
    anmeldung: 'oauth',
    vorauswahl: ['generate_image', 'image_to_image', 'remove_background', 'inpaint_image'],
  },
  { name: 'notion', titel: 'Notion', url: 'https://mcp.notion.com/mcp', anmeldung: 'oauth', vorauswahl: null },
  { name: 'github', titel: 'GitHub', url: 'https://api.githubcopilot.com/mcp/', anmeldung: 'schluessel', api_key_env: 'GITHUB_TOKEN', vorauswahl: null },
  { name: 'figma', titel: 'Figma', url: 'https://mcp.figma.com/mcp', anmeldung: 'oauth', vorauswahl: null },
  { name: 'gmail', titel: 'Gmail', url: 'https://gmailmcp.googleapis.com/mcp/v1', anmeldung: 'oauth_kennung', vorauswahl: null },
  { name: 'huggingface', titel: 'Hugging Face', url: 'https://huggingface.co/mcp', anmeldung: 'schluessel', api_key_env: 'HF_TOKEN', vorauswahl: null },
]

/** The proper name of a server — its own id if we do not ship one. */
export function serverTitel(name) {
  return SERVERKATALOG.find((k) => k.name === name)?.titel || name
}
