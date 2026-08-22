# Auftrag: Maskeneditor zu einem richtigen Maleditor ausbauen

Stand: 21.08.2026. Umfang: der Maskeneditor, sonst nichts. Kein Release, kein
GitHub-Push, keine Änderung am Bildfenster außerhalb des Editors.

## WICHTIG: das richtige Repo

Gearbeitet und committet wird NUR hier:

    /Volumes/4TB SSD/Projects/exe-ai-terminal/exe-ai-terminal   (Branch: exe-ai)

NICHT in `exe-ai-terminal-labor`. NICHT in `~/ExePrivat`.

Betroffen sind im Wesentlichen zwei Dateien:

- `frontend/src/teile/MaskenEditor.svelte` (Fenster, Bedienung, CSS)
- `frontend/src/lib/maske.js` (Malfläche, Strich, Koordinaten, Export)

## Ist-Zustand (nachgemessen, 21.08.2026)

Der Editor öffnet als Fenster `art="vorschau"`, Breite 860 px. Von oben nach
unten:

1. Erklärsatz `maske.wofuer` — „Male die Stellen an, die neu gezeichnet werden
   sollen. Was du unberührt lässt, bleibt wie es ist."
2. Die Bühne: Bild und Malfläche exakt übereinander, Bild aktuell 695 × 695 px
   bei `max-height: 52vh`.
3. Werkzeugzeile: **Pinsel · Radiergummi · Pinselgröße (Regler + Zahl) ·
   Alles löschen** — alle in einer Reihe links.
4. Zweiter Erklärsatz `maske.qualitaet` — „Mit dem gewöhnlichen Modell geht
   das, aber man sieht es an den Übergängen …"
5. Fußzeile mit **Übernehmen**.

Was heute fehlt: Zoomen, Verschieben, Rückgängig.

## Teil 1 — Zoomen und Verschieben

**Die Fenstergröße bleibt, wie sie ist.** Gezoomt wird nur der Bildinhalt
innerhalb der Bühne.

- **Mausrad** zoomt. Auf den Zeiger zu, nicht auf die Bildmitte — sonst
  verliert man beim Hineinzoomen die Stelle, die man gerade treffen wollte.
- **Ziehen verschiebt** das Bild.
- Sinnvolle Grenzen: nicht kleiner als „ganz sichtbar", nach oben etwa 8-fach.
- Ein Weg zurück auf „ganz sichtbar" muss existieren (Knopf oder Doppelklick).

**Offene Frage an Chris — vor dem Bauen klären:** Ziehen ist heute Malen. Wie
soll das Verschieben ausgelöst werden?

  a) Leertaste halten und ziehen (wie in Bildprogrammen üblich)
  b) Mittlere Maustaste
  c) Ein eigenes Hand-Werkzeug neben Pinsel und Radiergummi
  d) Zweiter Finger / Trackpad-Geste

**Wichtig, sonst wird es unbrauchbar:** Beim Zoomen muss die Umrechnung von
Zeiger auf Malfläche mitwandern. Sie steht in `maske.js`:

```js
export function aufFlaeche(ereignis, anzeige, flaeche) {
  const kasten = anzeige.getBoundingClientRect()
  return {
    x: ((ereignis.clientX - kasten.left) / kasten.width) * flaeche.width,
    y: ((ereignis.clientY - kasten.top) / kasten.height) * flaeche.height,
  }
}
```

Das rechnet heute nur über den Kasten des Bildes und stimmt deshalb, solange
Bild und Malfläche deckungsgleich sind und nicht verschoben werden. Mit Zoom
und Versatz muss beides in die Rechnung. **Ebenso der Pinselring** — er wird
mit `groesse * massstab` gezeichnet, `massstab` kommt aus
`kasten.width / flaeche.width` und muss den Zoom mitnehmen.

Prüfen lässt sich das ohne Auge: an einer bekannten Bildschirmstelle malen,
danach den Schwerpunkt des Gemalten im Canvas auslesen und mit dem erwarteten
Punkt vergleichen — bei mehreren Zoomstufen und Versätzen.

## Teil 2 — Rückgängig und Wiederherstellen

Zwei Knöpfe, **im selben Stil wie Pinsel und Radiergummi**, aber auf der
**gegenüberliegenden Seite** der Werkzeugzeile.

- Ein Schritt ist ein abgeschlossener Strich (Zeiger runter bis Zeiger hoch),
  nicht jede einzelne Mausbewegung.
- Deaktiviert, wenn es nichts zurückzunehmen gibt.
- `Cmd+Z` und `Cmd+Shift+Z` sollten mitgehen.

**Offene Frage:** Wie viele Schritte? Vorschlag: 20. Der Verlauf hält
Bildkopien der Malfläche im Speicher — bei einem 1024er Bild sind das rund
4 MB je Schritt, 20 Schritte also etwa 80 MB. Wenn das zu viel ist, weniger
Schritte oder nur die Striche merken und neu zeichnen.

## Teil 3 — Aufräumen im Fenster

1. **Der zweite Erklärsatz (`maske.qualitaet`) fliegt raus.** Der Schlüssel
   kann in `de.json`/`en.json` bleiben oder mit weg — dann aber in beiden
   Katalogen.
2. **Das Bild wird größer.** So groß, dass Pinsel und Radiergummi unten links
   sauber darunter sitzen und der Abstand zwischen Bildunterkante und Knöpfen
   derselbe bleibt wie heute. Heute: Bild endet bei y=854, Werkzeuge beginnen
   bei y=867 — also **13 px Abstand**, der bleibt.
3. **Der Pinselgrößen-Regler wandert nach ganz oben**, auf die Höhe, wo der
   Bildrahmen anfängt. Er steht dann nicht mehr in der Werkzeugzeile.

Damit sieht die Zeile unter dem Bild so aus: links Pinsel · Radiergummi
(· Hand?), rechts Zurück · Vor. „Alles löschen" gehört auch irgendwohin —
Vorschlag: rechts zu Zurück/Vor, mit Abstand.

## Teil 4 — „alles, was ein Maskeditor braucht"

Chris' Worte. Was gemeint ist, muss **er** entscheiden — hier eine Liste zur
Auswahl, nicht zum Abarbeiten:

| Kandidat | Wofür | Aufwand |
|---|---|---|
| Weiche Kante | Übergang statt harter Schnitt, deutlich bessere Ergebnisse | klein |
| Maske umkehren | „alles außer dem, was ich gemalt habe" | klein |
| Alles füllen | ganze Fläche als Maske | winzig |
| Rechteck ziehen | gerade Kanten ohne Zittern | mittel |
| Maske aus- und einblenden | drunterschauen, ohne zu löschen | klein |
| Deckkraft der Tönung | dunkle Bilder unter blauer Maske | winzig |
| Maske sichern / laden | dieselbe Maske für mehrere Läufe | mittel |

**Erst fragen, dann bauen.** Ohne Antwort wird hier nichts gebaut.

## Was dieser Auftrag NICHT ist

- Keine Änderung an der Maskenpolarität. **WEISS heißt „male das neu"**, und
  das gilt für beide Wege: `sd-cli` erwartet es so, und der Turbo-Server
  wurde am 21.08. gegen das laufende Binary geprüft und verhält sich gleich.
  Wer das dreht, zerlegt beide Wege auf einmal.
- Keine Änderung an `alsDatei()` / dem Export der Maske.
- Kein Anfassen des Bildfensters außerhalb des Maskeneditors.
- Keine Änderung an `app/api/v1/bild.py` oder `app/bildturbo.py` — daran
  arbeitet gerade ein anderer Auftrag (Image-Turbo für img2img).

## Hausregeln-Kurzliste (gelten alle)

- Code, Kommentare, Commit-Nachrichten: **Englisch**. Keine Personennamen,
  keine Datumsstempel, keine Gesprächszitate in Kommentaren.
- Commits ohne jeden KI-Vermerk (kein Co-Authored-By, kein „Generated with").
- Bezeichner im Bestand bleiben deutsch — nicht umbenennen.
- Neue Oberflächentexte in `en.json` UND `de.json`, **English first**.
  Deutsche Texte sagen „PC", nie „Maschine".
- Keine sichtbaren Rollbalken. Keine Browser-Masken (`confirm`, `prompt`) —
  dafür gibt es `frage()` in `zustand.svelte.js`.
- Radius-Palette: 12 Kacheln, 9 Bedienelemente, 16 Fenster, 18 Eingabe,
  99 Pillen.
- Farbe bedeutet Zustand (grün fertig, gelb wartet, blau läuft, rot
  gescheitert). Ein Werkzeugknopf ist kein Zustand — der arbeitet mit
  Helligkeit.
- Nach jeder Änderung: `cd frontend && npm run build`, dann
  `.venv/bin/python3 -m pytest tests/ -q`.
- `README.md` und `docs/site/` nicht anfassen. `mcp_servers.json` ist seit
  dem 21.08. git-ignoriert und wird nie committet.

## Fertig heißt

Zoomen und Verschieben gehen und treffen genau (nachgemessen, nicht nach
Augenmaß), Rückgängig/Vor arbeiten strichweise, das Fenster ist aufgeräumt
wie in Teil 3, die in Teil 4 abgestimmten Zusätze sind drin, Tests grün,
saubere Commits auf `exe-ai`. Dann Chris Bescheid geben.
