# Auftrag: anzeigen, WAS der Maler gerade tut

Stand: 21.08.2026. Umfang: die Phasenanzeige beim Bildermalen, sonst nichts.
Kein Release, kein GitHub-Push.

## WICHTIG: das richtige Repo

Gearbeitet und committet wird NUR hier:

    /Volumes/4TB SSD/Projects/exe-ai-terminal/exe-ai-terminal   (Branch: exe-ai)

NICHT in `exe-ai-terminal-labor`. NICHT in `~/ExePrivat`.

## Worum es geht

Heute sagt ein Bild in Arbeit nur eine Zahl: „14 von 28". Warum es bei
eingeschaltetem Gesichtsdetektor plötzlich dreimal so lange dauert, sieht
niemand. Der Maler sagt es aber die ganze Zeit — wir lesen es nur nicht.

## Befund (21.08.2026, am angehefteten Binary geprüft)

Geprüft wurde `libstable-diffusion.dylib` und `sd-cli` aus

    data/stable-diffusion.cpp/master-820-de298c2/

(angeheftete Version: `BAU` in `app/sddownload.py:54`)

Nachprüfbar mit:

```bash
strings -a data/stable-diffusion.cpp/master-820-de298c2/libstable-diffusion.dylib \
  | grep -iE "completed, taking|hires |ADetailer detected|apply_loras"
```

Diese Meldungen gibt der Maler zur Laufzeit aus:

| Meldung (Format im Binary) | Phase |
|---|---|
| `get_learned_condition completed, taking %.2fs` | Prompt gelesen |
| `apply_loras completed, taking %.2fs` | LoRA angewandt |
| `generating image: %i/%i - seed %lld` | Malgang beginnt |
| `sampling completed, taking %.2fs` | Malgang fertig |
| `hires: {enabled=%s, upscaler=%s, scale=%.2f, target=%dx%d, steps=%d, …}` | Hires-Einstellung |
| `hires %s upscale %lldx%lld -> %lldx%lld` | Hires vergrößert |
| `hires sampling %d/%d completed, taking %.2fs` | Hires malt |
| `ADetailer detected %zu object(s), taking %.2fs` | Detektor hat gefunden |
| `ADetailer detection %zu: object=%s, class_id=%d, confidence=%.3f, bbox=[…]` | je Fund |
| `decode_first_stage completed, taking %.2fs` | Bild wird entwickelt |

**Das Wertvollste davon ist `ADetailer detected N object(s)`** — genau der
Moment, in dem heute niemand versteht, warum es länger dauert. „2 Gesichter
gefunden, wird nachgeschärft" beantwortet das in einer Zeile.

## Warum das machbar ist

Der Ausgabestrom wird **schon zeilenweise gelesen** — beide Wege:

- `app/bildrunner.py:440` — `_zaehler_lesen()`, liest `ausgang.read(256)` in
  einer Schleife und sucht heute genau ein Muster:
  `_SCHRITT_MUSTER = re.compile(r"\|\s*(\d+)/(\d+)\s*-")` (Zeile 55)
- `app/bildturbo.py:305` — `_zaehler_lesen()`, dieselbe Bauart für den
  dauerhaften Server

Es kommen also **weitere Muster in eine vorhandene Schleife**. Kein neuer
Prozess, kein neuer Kanal, keine zweite Verbindung.

## Teil 1 — Phasen erkennen

Ein eigenes Modul, Hausregel „ein Modul pro Funktion":
`app/bildphasen.py`. Es bekommt eine Textzeile und gibt eine Phase zurück
oder nichts.

Eine Phase ist ein Schlüssel plus Werte, **kein fertiger Satz** — der Satz
gehört in die Übersetzungskataloge:

```python
{"phase": "detektor_gefunden", "anzahl": 2}
{"phase": "hires_vergroessert", "von": "512x512", "nach": "1024x1024"}
{"phase": "lora"}
```

**Die eiserne Regel:** Eine Zeile, die zu keinem Muster passt, ergibt
**nichts** — kein Raten, kein „vermutlich malt er gerade". Die Meldungen sind
Text eines fremden Programms, kein Vertrag; ein neuer Build kann sie ändern.
Was wir nicht sicher erkennen, zeigen wir nicht.

**Nie ausgeben:** Prompt, Seed, Dateipfade. Die stehen teils in denselben
Zeilen. Es wird ausschließlich die Phase gemeldet, nie der Inhalt.

## Teil 2 — die Phase weiterreichen

`self._fortschritt` trägt heute `{anteil, schritt, gesamt}`. Dazu kommt
`phase` (Schlüssel) und optional die Werte. `GET /api/v1/bild/fortschritt`
(`app/api/v1/bild.py:387`, Antwortmodell `FortschrittAntwort`) reicht sie
mit durch.

Beide Runner müssen dasselbe Feld füllen, sonst zeigt der eine Weg etwas und
der andere nicht.

## Teil 3 — anzeigen

Die Zeile erscheint **unter** der Zeichenanimation, wo heute nur die Zahl
steht. Kurz, ruhig, eine Zeile:

- „LoRA wird angewandt"
- „2 Gesichter gefunden — wird nachgeschärft"
- „Wird auf 1024 × 1024 vergrößert"
- „Bild wird entwickelt"

Texte in `en.json` UND `de.json`, **English first**. Deutsche Texte sagen
„PC", nie „Maschine". Zahl im Text über Platzhalter, nicht zusammengebaut.

**Nicht** blinken, nicht springen: eine unbekannte Zeile lässt die letzte
Phase stehen, statt auf leer zu fallen.

## Teil 4 — der Balken

Ein Balken, der bei 100 % stehenbleibt und dann weitermalt, lügt. Zwei Wege,
**Chris entscheiden lassen**:

  a) **Ein Gesamtbalken** über alle Gänge (heute schon so gedacht:
     `erwartete_paesse` in `bildrunner.py`), dazu die Phasenzeile als Text.
  b) **Balken je Gang**, der bei jedem Gang neu bei 0 beginnt, und die
     Phasenzeile sagt, welcher Gang läuft („Hires 7/8").

Vorschlag: **a**. Der Gesamtbalken existiert schon, und die Phasenzeile
erklärt die Sprünge — das ist der kleinere Eingriff.

Hinweis: Ein anderer Auftrag (Image-Turbo für img2img) hat die Zählung der
Gänge bereits um den Hires-Gang erweitert. **Vorher den Stand ansehen**, nicht
doppelt bauen.

## Teil 5 — Tests

Das Erkennen ist reine Textarbeit und ohne Maler prüfbar:

- Für **jede** Meldung aus der Tabelle oben eine echte Beispielzeile →
  erwartete Phase.
- Eine Zeile, die zu nichts passt → **nichts** zurück.
- Eine Zeile mit Prompt und Seed → die Phase kommt, der Prompt **nicht**.
- Für beide Runner: die Phase landet in `_fortschritt` und kommt am
  Endpunkt an. HTTP und Prozess gemockt, kein echter Maler im Test.

## Was dieser Auftrag NICHT ist

- Kein Anheben von `BAU` auf einen neueren stable-diffusion.cpp-Build.
- Keine Änderung an der Zählung selbst, außer sie ist für Teil 4 nötig.
- Kein Weiterreichen von Prompt, Seed oder Pfaden an die Oberfläche.
- Keine Änderung am Maskeneditor (eigener Auftrag) und keine an
  `_turbo_auftrag` / `turbo_faehig` (eigener Auftrag).

## Hausregeln-Kurzliste (gelten alle)

- Code, Kommentare, Commit-Nachrichten: **Englisch**. Keine Personennamen,
  keine Datumsstempel, keine Gesprächszitate in Kommentaren.
- Commits ohne jeden KI-Vermerk (kein Co-Authored-By, kein „Generated with").
- Ein Modul pro Funktion. Bezeichner im Bestand bleiben deutsch.
- Oberflächentexte nie fest im Code, immer in beide Kataloge, English first.
- Ein Download wird **geladen**, nie „geholt" — gilt auch für neue Texte.
- Farbe bedeutet Zustand: blau läuft, grün fertig, gelb wartet, rot
  gescheitert. Eine Phasenzeile ist eine Tatsache — die arbeitet mit
  Helligkeit, nicht mit Farbe.
- Nach jeder Änderung: `cd frontend && npm run build`, dann
  `.venv/bin/python3 -m pytest tests/ -q`.
- `README.md` und `docs/site/` nicht anfassen. `mcp_servers.json` ist seit
  dem 21.08. git-ignoriert und wird nie committet.

## Fertig heißt

Phasen werden erkannt und geprüft, beide Wege melden dieselben, die Zeile
steht unter der Animation, der Balken lügt nicht mehr, Tests grün, saubere
Commits auf `exe-ai`. Dann Chris Bescheid geben.
