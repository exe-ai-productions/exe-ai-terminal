/* The last seed a picture was actually drawn with.

   The server answers every draw with the seed it used — also when it was
   asked to pick one. Kept here so the picture window can show it and the
   seed plan (fixed, one up, one down) has a point to continue from; thrown
   to nobody else. Null until the first picture of the session. */
export const seedlage = $state({ letzter: null })
