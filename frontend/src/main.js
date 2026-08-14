import { mount } from 'svelte'
import App from './App.svelte'
import { texteLaden } from './lib/texte.svelte.js'
import './stil/global.css'
import './stil/codefarben.css'

/* Texts first, then the window.

   If we render first and the catalog arrives afterwards, the keys flash up
   for a moment ("chat.neu" instead of "Neuer Chat"). The catalogs are a few
   kilobytes and come from the same server as everything else — wait for
   them and you never see that state.

   Deliberately inside a function rather than a top-level `await`: the bundle
   is built for browsers that don't know top-level await, and the build
   breaks on it.

   If loading fails, the service isn't running — then the reason in plain
   text is more helpful than an empty window. */
async function starten() {
  const wurzel = document.getElementById('wurzel')
  try {
    await texteLaden()
  } catch (fehler) {
    wurzel.textContent = 'Der Dienst antwortet nicht: ' + (fehler?.message ?? fehler)
    throw fehler
  }
  return mount(App, { target: wurzel })
}

export default starten()
