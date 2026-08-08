import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

/*
  Gebaut wird direkt nach ../static/app/ — von dort liefert FastAPI aus, ohne
  dass ein zweiter Webserver nötig wäre. Ein Prozess, ein Port, wie im Grill
  entschieden.

  Beim Entwickeln (npm run dev) läuft Vite auf 5173 und reicht alles unter
  /api an den laufenden Dienst weiter. Damit ist sofortiges Neuladen möglich,
  ohne den Server anzufassen.
*/
export default defineConfig({
  plugins: [svelte()],
  base: '/app/',
  build: {
    outDir: '../static/app',
    emptyOutDir: true,
    // Für ein Werkzeug, das man selbst betreibt, sind Quellkarten Gold wert:
    // ein Fehlerbericht zeigt die echte Zeile statt einer Zahl im Bündel.
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
