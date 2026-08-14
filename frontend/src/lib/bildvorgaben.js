/*
  What the picture window starts out with.

  The picture panel sets these and the picture window reads them, and neither
  of the two should have to know the other's spelling of the key. One word,
  one file, and a rename cannot leave half the program looking for the old
  name.

  Only the STARTING values live here. What the window can do is the window's
  business — changing a default never narrows a control, it only decides
  where it stands when it opens.
*/

export const BILDVORGABEN = 'bild_vorgaben'
