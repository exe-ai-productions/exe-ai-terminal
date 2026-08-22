# Handoff — System-Layout-Audit (21.08.2026)

## Anführung & Arbeitsweise (WICHTIG)

**Chris führt das komplette System-Layout-Audit an.** Es wird **nichts
eigenständig umgesetzt.** Jede Änderung wartet auf seine ausdrückliche
Ansage. In dieser Sitzung ist mehrfach genau das schiefgegangen: vorpreschen
statt warten. Nicht wiederholen.

## Nächster Schritt

**„Ordner öffnen" im Modellbereich vereinheitlichen.** Entscheidung von
Chris: **überall dasselbe Ordner-Öffnen-Symbol** setzen (nicht Text „Öffnen"
allein, nicht das Wort „Ordner"). Betrifft mindestens:
- `frontend/src/teile/Speicherortzeile.svelte` — der „Öffnen"-Knopf im
  Modelle-Rahmen
- `frontend/src/teile/Katalog.svelte` (~Zeile 490) — „Ordner öffnen" je
  Zubehör-Spalte
Beide sollen das gleiche Zeichen + gleiche Beschriftung tragen. **Erst mit
Chris klären, welches Wort/Zeichen genau — dann bauen.**

## Kontext

Lange Oberflächen-Politur. Zwei Bereiche:
1. **Maskeneditor → Maltool** + Bildfenster „IMAGE SETTINGS" auf ein Raster.
   **Bereits committet** als `887d8ca`.
2. **Lokal-Fenster „YOUR LOCAL MODELS"** (ModelleLokal, Modellserver,
   Servertafel, Kachel, Standpille, Schieberegler, App-Kopfleiste) stark
   überarbeitet. **NOCH NICHT committet** (~30 Dateien; muss vor dem
   Terminal-Handoff committet werden — Anweisung von Chris).

## Entscheidungen (nicht wieder aufmachen)

- **Statuswörter:** Server-Panels sagen **aktiv/inaktiv** (nicht verbunden).
  Cloud-Modelle behalten **verbunden/nicht verbunden** (dort geht es um eine
  echte Verbindung).
- **Kopfleiste:** nur zwei Zustände — `● Flash Attention │ ● Server inaktiv │
  Speicher <Pille>`. **Port** und **⌀ Speicher** stehen in der Panel-Zeile,
  NICHT im Header. Kurze Trennstriche (9 px) zwischen den Anzeigen.
- **Gruppen-Überschriften einwortig**, jede in einer gerahmten Box mit
  gezeichnetem Zeichen: **MODELLE** (Würfel) · **MODULE** (Steckmodul) ·
  **SPEICHER** (Speicherriegel, neu gezeichnet) · **NETZWERK**.
- **Module:** Tempo-Modul (Blitz, blau `#5b8dbe`), Vision-Modul (Auge,
  violett `#8d78bd`), Extended-Workflow-Modul (EEW-Monogramm in
  `currentColor`, NICHT das alte Lila). Alle drei zeigen **„leer"** als
  Leerwert.
- **„leer" bleibt nach Neuladen** — der Fix saß im **Backend**
  (`app/waechterwahl.py`): ein leerer Modellname ist jetzt eine bewusste
  Wahl und wird gespeichert, statt verworfen zu werden. Test
  `tests/test_waechter.py` entsprechend umgeschrieben.
- **CPU-Wert = Threads** (`--threads`), heißt **„CPU-Threads"**. Slider-Max =
  echte Kernzahl des PCs: `os.cpu_count()`, im Runner als Feld `kerne`
  ausgeliefert (`app/api/v1/runner.py`). 0 = automatisch.
- **GPU-Wert = „GPU-Layer"** (`--n-gpu-layers`, 99 = alle).
- **Kontext/GPU-Layer/CPU-Threads:** alle drei mit Slider **und** Zahlenfeld,
  gleich lang (Bahn 372 px, Feld 108 px).
- **Erweitert:** eine Zeile über volle Breite —
  `KV-Cache │ 8-Bit <Schalter>  ·  MoE-Experts on CPU <Schalter>  ·  Memory
  Lock <Schalter>`. Trennstriche wie in der Kopfleiste. Flash-Attention-Zeile
  hier **entfernt** (steht jetzt in der Kopfleiste).
- **Slider-Optik:** blaue Stufenmarken **entfernt** (sahen wie Grenze aus);
  Zeitleisten-Look mit Abspielkopf, wie Maskeneditor/Bildfenster. Kontext
  rastet weiter auf Zweierpotenzen, wer mehr will tippt ins Feld (bis
  1.048.576).
- **Ein einziges Ordnerzeichen:** `ordner-24.svg` **gelöscht**,
  `ordner-rund-24` in **„Ordner"** umbenannt und überall eingesetzt (Index +
  Galerie im Hauptkatalog gepflegt, `Hauszeichen.svelte` gedreht).
- **Hilfe (?) und Einstellungen (Zahnrad)** aus dem Header in die
  **Modul-Leiste** unten verschoben (Reihenfolge von oben: EW · ? · Zahnrad),
  Zeichen 31 px.
- **Kachel-Layout Lokal:** Reihenfolge SERVER oben, DYNAMISCHES VORLADEN
  darunter. Indikator (Leuchtpunkt) VOR dem Namen, kein Untertitel,
  Doppel-Chevron statt `→`. Katalog ist kein Dienst → sein Weg ist jetzt der
  Raster-Knopf am Ende des Modelle-Dropdowns.

## Verworfen (nicht erneut vorschlagen)

- CPU-Wert als **„CPU-Fäden"** (ausdrücklich abgelehnt) oder
  **„CPU-Schichten"** (sachlich falsch — es sind Threads, keine Schichten).
- Deutsche Übersetzungen für GPU-Layer / CPU-Threads / Memory Lock / MoE
  (bleiben englisch; i18n-Ausnahmen in `tests/test_i18n.py` eingetragen).
- „Nicht auslagern" / „Speicher festnageln" für `--mlock` → jetzt
  **„Memory Lock"**.

## Wo alles liegt

- Projekt/Branch:
  `/Volumes/4TB SSD/Projects/exe-ai-terminal/exe-ai-terminal` · `exe-ai`
- Hauptkatalog (kein Git):
  `/Volumes/4TB SSD/Exe System/Vektorkatalog/` (zeichen/, .index.json,
  katalog.html) — neue Zeichen dieser Sitzung: `speicherriegel.svg`,
  `weiter-pfeil.svg`; gelöscht: `ordner-24.svg`
- Dev-Dienst: uvicorn auf **8091** (verpackte App hält 8090). Nach
  Frontend-Bau: `cd frontend && npm run build`. Nach Katalog-Änderung Dienst
  neu starten (Texte kommen vom Backend).

## Was schiefging (Zeit gespart)

- Immer wieder eigenständig umgesetzt statt zu warten — Chris' oberste Regel.
- „8-Bit" rutschte als Untertitel unter das Wort, weil ein `<span>` in einem
  `<label>` die Helfer-Text-Regel erbt. Lösung: `<i>` statt `<span>`.
- Beim Verschieben von Kopfleisten-Elementen die Speicherpille versehentlich
  ganz entfernt — Transkription hatte „neben den Speicher" als „raus"
  gelesen. Wieder eingesetzt.
