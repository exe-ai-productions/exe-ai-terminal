/*
  A soft edge for the house's invisible scrolling.

  The bars are invisible house-wide, so a full list ends in a hard cut
  through whatever row happens to sit there — which reads as a mistake,
  not as "there is more". This action lays a mask over the scroller:
  content melts out at an edge exactly while more of it lies beyond that
  edge, and the melt vanishes the moment the end is reached. The fade
  itself is the scroll hint, no bar needed.

  Self-contained on purpose: the mask is written inline, so no stylesheet
  has to know about it, and any scroller can wear it with one `use:`.
*/

// Tall enough to read as a melt, flat enough to steal no row.
const KANTE = 26

export function rollfade(knoten) {
  let angefragt = false

  const setzen = () => {
    angefragt = false
    const oben = knoten.scrollTop > 2
    const unten = knoten.scrollTop + knoten.clientHeight < knoten.scrollHeight - 2
    if (!oben && !unten) {
      knoten.style.webkitMaskImage = ''
      knoten.style.maskImage = ''
      return
    }
    const teile = [
      oben ? `transparent, black ${KANTE}px` : 'black',
      unten ? `black calc(100% - ${KANTE}px), transparent` : 'black',
    ]
    const maske = `linear-gradient(to bottom, ${teile.join(', ')})`
    knoten.style.webkitMaskImage = maske
    knoten.style.maskImage = maske
  }

  // One measurement per frame, however many signals arrive.
  const anstossen = () => {
    if (angefragt) return
    angefragt = true
    requestAnimationFrame(setzen)
  }

  knoten.addEventListener('scroll', anstossen, { passive: true })
  const groesse = new ResizeObserver(anstossen)
  groesse.observe(knoten)
  // Rows fold open and closed inside the scroller; the mask has to follow
  // the content, not just the box.
  const inhalt = new MutationObserver(anstossen)
  inhalt.observe(knoten, { childList: true, subtree: true })
  setzen()

  return {
    destroy() {
      knoten.removeEventListener('scroll', anstossen)
      groesse.disconnect()
      inhalt.disconnect()
    },
  }
}
