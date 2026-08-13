// svelte-check needs this file to recognise the project — the build itself
// runs through vite.config.js and is not affected by anything here.
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte"

export default { preprocess: vitePreprocess() }
