# ARBEITSAUFTRAG: Eingebettetes MTP im Modell-Runner aktivieren (`--spec-type draft-mtp`)

Projekt: `/Volumes/4TB SSD/Projects/exe-ai-terminal/exe-ai-terminal`
(Branch `exe-ai`, Stand: alle 1255 Tests grün.)

## Hintergrund (so funktioniert es heute)

Der Modell-Runner startet `llama-server` (gebündelt: b10331, unter
`llama.cpp/`). Tempo-Module (MTP) laufen bisher nur als **getrennte
Drafter-Dateien** aus dem `mtp/`-Ordner. Neuere Modelle (z. B. die
Qwen3.6-MTP-GGUFs) tragen ihre MTP-Gewichte **in der Modelldatei selbst**.
Der gebündelte Server kann das: `--spec-type draft-mtp`. **Aber der
Standard ist `none`** — ohne Flag bleibt eingebautes MTP ungenutzt.

## Wichtig — der Blitz-Indikator bleibt unangetastet

`mtp_zustand()` in `app/modellrunner.py` (~Z. 396) liest den Zustand aus
der **Server-Antwort im Log** (Spekulations-Init-Zeile), nicht aus dem
gesendeten Flag. Genau deshalb kann der Blitz nicht fälschlich
dauerleuchten: Flag gesetzt ≠ aktiv; nur echte Server-Bestätigung schaltet
ihn. Diese Logik NICHT umbauen — nur prüfen, ob ihr Log-Muster auch die
Init-Zeile des `draft-mtp`-Modus erfasst (die Zeile kann anders lauten als
beim getrennten Drafter; dann das Muster erweitern, Semantik unverändert:
aktiv erst bei bestätigter Initialisierung).

## Umsetzung

1. **MTP-Erkennung:** Beim Start eines Modells die GGUF-Metadaten lesen
   und feststellen, ob die Datei eingebettete MTP-Gewichte trägt.
   Verlässlichen Marker am echten Qwen3.6-MTP-GGUF-Header ermitteln
   (Tensor-/Metadaten-Schlüssel) — NICHT am Dateinamen oder Repo-Namen
   festmachen. Eigenes Modul für die Erkennung (Hausregel: ein Modul pro
   Funktion).
2. **Flag setzen:** Nur wenn (a) das Modell eingebettetes MTP trägt und
   (b) **kein** getrennter Drafter gewählt ist → `--spec-type draft-mtp`
   an die Startargumente. Der bestehende Getrennter-Drafter-Pfad bleibt
   exakt wie er ist; niemals beide Mechanismen gleichzeitig.
3. **Kein Frontend-Umbau:** Der Blitz in der Chatleiste liest `mtp_aktiv`
   wie bisher.
4. **Nicht in diesem Auftrag:** Das Blitz-Zeichen auf der Katalogkarte von
   Qwen3.6 35B A3B bleibt AUS. Es kommt erst zurück, wenn der Messlauf
   (unten) echten Gewinn zeigt und Chris es freigibt.

## Hausregeln

Kommentare/Commits Englisch, keine Personen/Daten in Kommentaren, neue
Funktion = eigene Datei, vor jedem Commit
`.venv/bin/python3 -m pytest tests/ -q` (aktuell 1255 grün — so muss es
bleiben). Neue Tests für die Erkennung: echter MTP-Header → erkannt,
normaler Header → nicht erkannt, kaputter Header → sauber „nein" statt
Absturz.

## ZUM SCHLUSS — PFLICHT: Erst ausgiebig Tests fahren

Bevor irgendetwas Weiteres passiert: kein Release, kein Katalog-Umbau,
keine Badge. Konkret:

1. Volle Testsuite grün.
2. Praxislauf auf dem **Dev-Server (Port 8091, nie 8090)**:
   - MTP-Modell laden → Server-Log zeigt die Spekulations-Init, Blitz
     leuchtet.
   - Normales Modell laden → kein Flag, kein Blitz.
   - Modell mit getrenntem Drafter → alter Pfad unverändert, Blitz wie
     bisher.
   Das Qwen3.6-MTP-GGUF liegt noch nicht lokal — die kleinste Fassung
   reicht für den Test (`unsloth/Qwen3.6-35B-A3B-MTP-GGUF`,
   `Qwen3.6-35B-A3B-UD-IQ4_XS.gguf`, 18,2 GB); das Herunterladen gehört
   mit zum Testfahren.
3. Messlauf Tempo mit/ohne (gleicher Prompt, gleiche Einstellungen,
   Token/s notieren) und die Zahlen an Chris melden.

Erst nach seiner Freigabe geht es weiter.
