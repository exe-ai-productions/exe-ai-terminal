/*
  What a run's state looks like as a colour.

  Two places draw this dot — the entry in the terminal panel and the mark on
  the rail beside the panel's sign — and they were computing it separately.
  They disagreed about exactly one case, which is the case where it matters:
  a run somebody stopped by hand showed grey inside the panel and red on the
  rail, so the strip claimed something had broken while the panel one click
  away said it had simply ended.

  One fact, one file, one answer. The house colours, unchanged:

    blau   it is working
    gruen  it finished
    still  it is over — stopped by hand, which is a fact, not a fault
    rot    it failed
*/

export function laufampel(zustand) {
  if (zustand === 'laeuft') return 'blau'
  if (zustand === 'fertig') return 'gruen'
  /* A run somebody stopped is not a run that broke. Grey says "over"
     without saying "wrong" — the same reading a stopped model server gets. */
  if (zustand === 'abgebrochen') return 'still'
  return 'rot'
}
