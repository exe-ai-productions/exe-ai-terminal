/*
  Which of the five states a chat row shows when more than one is true.

  This is the whole decision, and it is deliberately its own file with no
  imports: it depends on nothing but four booleans, so it can be read in
  one breath and run in a test without the rest of the interface standing
  up around it.

  The order is the sentence: what needs a hand beats what is under way,
  and what went wrong beats what went well.

    gelb   somebody is waiting for you — a question, a confirmation
    blau   an answer is running here
    rot    a run failed and nobody has looked at it
    gruen  an answer finished and nobody has looked at it
    leer   nothing to report; a small quiet disc stands instead
*/

export function ringAus({ fragt = false, laeuft = false, fehler = false, fertig = false } = {}) {
  if (fragt) return 'gelb'
  if (laeuft) return 'blau'
  if (fehler) return 'rot'
  if (fertig) return 'gruen'
  return 'leer'
}
