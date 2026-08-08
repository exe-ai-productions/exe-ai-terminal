// svelte-check braucht diese Datei, um das Projekt zu erkennen —
// der Build laeuft ueber vite.config.js und aendert sich hier nicht.
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte"

export default { preprocess: vitePreprocess() }
