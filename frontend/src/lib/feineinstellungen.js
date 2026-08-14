/*
  The name of the setting the engine levers are stored under.

  The model server panel writes it and reads it back, and the backend checks
  it under the same word (app/feineinstellungenwahl.py). One word, one file,
  so a rename cannot leave half the program looking for the old one — the
  same arrangement the picture window's defaults already have.
*/

export const FEINEINSTELLUNGEN = 'feineinstellungen'
