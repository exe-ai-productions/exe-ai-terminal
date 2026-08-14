# Where these sounds come from

The three notification sounds are built from one recorded balafon note — a
wooden bar struck with a soft mallet. Pitch and rhythm were derived from that
single recording; nothing here is synthesised.

**Source:** Versilian Community Sample Library (VCSL), balafon, soft mallet.

**Licence:** CC0 1.0 — public domain dedication. No attribution is required
and the files may be shipped with this program. This note is kept anyway, so
that anybody asking where an audio file in an installer came from gets an
answer instead of a guess.

**The three signals**

| File | Meaning | Notes |
|---|---|---|
| `fertig.wav` | The answer is there | D5 → G5, a rising fourth |
| `wartet.wav` | The program is waiting for the user | E5 twice, like a knock |
| `fehler.wav` | Something failed | G4 → F4 → E♭4, three steps down |

Mono, 48 kHz, 16 bit. They are played only while the window is in the
background — see `frontend/src/lib/klaenge.js`.
