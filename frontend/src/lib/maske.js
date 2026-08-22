/*
  Turning what somebody painted into what the generator understands.

  The editor paints in a house colour at half opacity, because a mask you
  cannot see through is a mask you cannot aim. The generator wants
  something else entirely: a black and white picture, exactly the size of
  the starting image, where WHITE means "draw this again". Those are two
  different pictures of the same intention, and this is where one becomes
  the other.

  No library. A brush stroke is a line with round caps, and turning a
  painted layer into black and white is one pass over the pixels — both are
  a handful of lines against the canvas the browser already has. A
  dependency here would be carried into every installer on every platform
  for something the platform ships.
*/

/* Where the mask is painted, independent of how large it is shown. The
   editor scales its display to fit the window; the strokes are recorded
   here, at the starting image's own size, so nothing is lost to the
   scaling and the export needs no second resampling. */
export function malflaeche(breite, hoehe) {
  const flaeche = document.createElement('canvas')
  flaeche.width = Math.max(1, Math.round(breite))
  flaeche.height = Math.max(1, Math.round(hoehe))
  // Claimed on the first call, which is what fixes the layer's kind for
  // every later one: this layer is read back as well as drawn on (checking
  // whether anything is painted, inverting, exporting), and a layer told so
  // in advance keeps its pixels where reading them is cheap.
  flaeche.getContext('2d', { willReadFrequently: true })
  return flaeche
}

/* One stroke, from the last point to this one.

   Drawn as a line and not as a dot per event: a mouse moving quickly
   reports a handful of positions per second, and dots would leave a dotted
   trail with gaps a person never intended. Round caps and joins make the
   line behave like a brush.

   `radieren` paints with the same brush and takes away instead — the
   eraser is the brush, which is why it needs no separate machinery. */
export function strich(flaeche, von, bis, groesse, radieren = false) {
  const stift = flaeche.getContext('2d')
  stift.save()
  stift.globalCompositeOperation = radieren ? 'destination-out' : 'source-over'
  stift.strokeStyle = 'rgba(255,255,255,1)'
  stift.lineWidth = Math.max(1, groesse)
  stift.lineCap = 'round'
  stift.lineJoin = 'round'
  stift.beginPath()
  stift.moveTo(von.x, von.y)
  stift.lineTo(bis.x, bis.y)
  stift.stroke()
  stift.restore()
}

export function leeren(flaeche) {
  flaeche.getContext('2d').clearRect(0, 0, flaeche.width, flaeche.height)
}

/* Swap painted and unpainted: what was marked is released, what was left
   alone is marked — and on an empty layer this IS "fill everything", which
   is why no separate fill exists. Only the alpha channel decides, the same
   rule the export follows, so a mask survives any number of inversions
   unchanged. */
export function umkehren(flaeche) {
  const stift = flaeche.getContext('2d')
  const daten = stift.getImageData(0, 0, flaeche.width, flaeche.height)
  for (let i = 0; i < daten.data.length; i += 4) {
    const war = daten.data[i + 3] > 8
    daten.data[i] = 255
    daten.data[i + 1] = 255
    daten.data[i + 2] = 255
    daten.data[i + 3] = war ? 0 : 255
  }
  stift.putImageData(daten, 0, 0)
}

/* Has anything been painted at all?

   Asked before a mask is sent: an untouched layer would export as a
   completely black picture, and a completely black mask tells the
   generator to redraw nothing — a picture identical to the one it started
   from, with no hint as to why. */
export function bemalt(flaeche) {
  const daten = flaeche.getContext('2d').getImageData(0, 0, flaeche.width, flaeche.height).data
  for (let i = 3; i < daten.length; i += 4) {
    if (daten[i] > 8) return true
  }
  return false
}

/* The painted layer as the generator wants it: white where it was painted,
   black everywhere else, no transparency left.

   The alpha channel decides, not the colour. What the editor shows is a
   translucent house colour, and reading its RGB would make the threshold
   depend on which colour the theme happens to use. What was painted is
   what has alpha.
*/
export function alsSchwarzWeiss(flaeche) {
  const ziel = document.createElement('canvas')
  ziel.width = flaeche.width
  ziel.height = flaeche.height
  const stift = ziel.getContext('2d')
  const quelle = flaeche
    .getContext('2d')
    .getImageData(0, 0, flaeche.width, flaeche.height)
  const bild = stift.createImageData(flaeche.width, flaeche.height)
  for (let i = 0; i < quelle.data.length; i += 4) {
    const hell = quelle.data[i + 3] > 8 ? 255 : 0
    bild.data[i] = hell
    bild.data[i + 1] = hell
    bild.data[i + 2] = hell
    bild.data[i + 3] = 255
  }
  stift.putImageData(bild, 0, 0)
  return ziel
}

/* The finished mask as a file, ready to be uploaded like any other image.

   PNG and not JPEG: a mask is two values, and a lossy format would put
   grey along every edge — which the generator would read as "redraw this
   a bit", a thing that does not exist.
*/
export function alsDatei(flaeche, name = 'maske.png') {
  return new Promise((fertig, scheitern) => {
    alsSchwarzWeiss(flaeche).toBlob((brocken) => {
      if (!brocken) {
        scheitern(new Error('mask could not be encoded'))
        return
      }
      fertig(new File([brocken], name, { type: 'image/png' }))
    }, 'image/png')
  })
}

/* A point on the shown picture, translated to a point on the mask.

   The editor shows the picture scaled to the window, and it can be zoomed
   and dragged on top of that; the strokes belong to the picture's own
   pixels. Without this the mask would land offset and the wrong part of the
   picture would be redrawn — the kind of bug that looks like the generator
   misbehaving.

   Zoom and offset need no term of their own here. They are one transform on
   the box that carries picture and mask together, and a bounding rectangle
   is measured AFTER transforms: the rectangle read here is where the
   picture actually is on screen, at whatever size it is currently shown.
   Reading it fresh on every event is what keeps the aim true while zooming
   and dragging — and it is why the same rectangle also gives the scale for
   the brush ring.
*/
export function aufFlaeche(ereignis, anzeige, flaeche) {
  const kasten = anzeige.getBoundingClientRect()
  return {
    x: ((ereignis.clientX - kasten.left) / kasten.width) * flaeche.width,
    y: ((ereignis.clientY - kasten.top) / kasten.height) * flaeche.height,
  }
}
