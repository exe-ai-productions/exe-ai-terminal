import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

/*
  The build writes straight into ../static/app/, where FastAPI serves it from.
  No second web server is needed: one process, one port.

  While developing (npm run dev) Vite runs on 5173 and forwards everything
  under /api to the running service. That gives instant reloads without
  touching the server.
*/
export default defineConfig({
  plugins: [svelte()],
  base: '/app/',
  build: {
    outDir: '../static/app',
    emptyOutDir: true,
    // For a tool you host yourself, source maps are worth their weight: an
    // error report points at the real line instead of a number in the bundle.
    sourcemap: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8090',
      '/favicon.svg': 'http://127.0.0.1:8090',
      '/icons': 'http://127.0.0.1:8090',
    },
  },
})
