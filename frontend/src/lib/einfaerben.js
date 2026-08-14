/*
  Syntax colouring for everything that shows code: the chat's code blocks,
  the command in the tool prompt, later the terminal.

  This used to be a set of hand-written regular expressions. They were fine
  until they weren't — TypeScript generics, JSX, regex literals and `${…}`
  inside a template string are exactly the cases a pattern cannot tell apart
  from what surrounds it. highlight.js has maintained grammars for all of
  them, so that is what runs now. It is the one library added for this, and
  it is bundled whole: nothing is fetched at runtime, the program still
  works with the network unplugged.

  Only the core plus a curated set of languages is registered — the full
  package carries close to two hundred grammars, and the ones nobody writes
  in this program would only make the download heavier.

  IMPORTANT: highlight.js escapes by itself, so RAW code goes in. Handing it
  already-escaped text produced doubly escaped entities in the output.
*/

import hljs from 'highlight.js/lib/core'

import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import rust from 'highlight.js/lib/languages/rust'
import sql from 'highlight.js/lib/languages/sql'
import toml from 'highlight.js/lib/languages/ini'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('c', c)
hljs.registerLanguage('css', css)
hljs.registerLanguage('java', java)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('python', python)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('toml', toml)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('yaml', yaml)

/* What people actually type into a fence. `svelte` lands on the markup
   grammar — its script part comes out plainer than in a .js block, and that
   beats no colours at all. */
hljs.registerAliases(['sh', 'shell', 'zsh'], { languageName: 'bash' })
hljs.registerAliases(['py'], { languageName: 'python' })
hljs.registerAliases(['js', 'jsx', 'mjs'], { languageName: 'javascript' })
hljs.registerAliases(['ts', 'tsx'], { languageName: 'typescript' })
hljs.registerAliases(['yml'], { languageName: 'yaml' })
hljs.registerAliases(['html', 'svelte', 'vue', 'xhtml'], { languageName: 'xml' })
hljs.registerAliases(['md'], { languageName: 'markdown' })
hljs.registerAliases(['ini', 'conf'], { languageName: 'toml' })

function maskieren(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/**
 * Colours code as HTML. Unknown or missing language: escaped, no colours —
 * guessing the language got it wrong often enough to be worse than plain.
 */
export function hervorheben(code, sprache) {
  const name = String(sprache || '').toLowerCase()
  if (!name || !hljs.getLanguage(name)) return maskieren(code)
  try {
    return hljs.highlight(String(code), { language: name, ignoreIllegals: true }).value
  } catch {
    /* A grammar that trips over its input must not take the message with
       it — the code still has to be readable, just without colours. */
    return maskieren(code)
  }
}

export { maskieren }
