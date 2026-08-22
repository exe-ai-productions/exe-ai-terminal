# Auftrag: Bild-Embeddings — Verdrahtung + Ordner-öffnen-Knopf

Stand: 20.08.2026. Abgesegnet von Chris. Umfang: genau die zwei Teile unten,
nicht mehr. Kein Release, kein Versions-Hub, kein GitHub-Push — das macht
eine andere Session auf Chris' Ansage.

## WICHTIG: das richtige Repo

Gearbeitet und committet wird NUR hier:

    /Volumes/4TB SSD/Projects/exe-ai-terminal/exe-ai-terminal   (Branch: exe-ai)

NICHT in `exe-ai-terminal-labor` (wird demnächst gelöscht; heute musste ein
dort gelandeter Commit mühsam rübergeholt werden). NICHT in `~/ExePrivat`
(eigene Entwicklungslinie, dient hier nur als Quelle).

## Worum es geht

Der Bildgenerator kann Embeddings (Textual-Inversion-Dateien) nutzen —
aufgerufen im Prompt über den **Dateinamen ohne Endung**. Die Verdrahtung
dafür existiert bereits in der ExePrivat-Linie, fehlt aber im offiziellen
Repo. Und es fehlt jede Oberfläche: ohne einen Weg zum Ordner ist die
Funktion unsichtbar und damit praktisch nicht vorhanden.

Zum Testen liegen bei Chris zwei echte Embeddings:

    ~/Library/Application Support/Exe AI Terminal/data/bildmodelle/embedding/
      Stable_Yogis_PDXL_Negatives-neg.safetensors
      Stable_Yogis_Realism_Positives_V1.safetensors

Chris' Datenordner ist heilig: nichts darin verändern, verschieben oder
löschen. Anschauen zum Prüfen ist okay. Bild-Metadaten nie auslesen.

## Teil 1 — Verdrahtung aus ExePrivat holen

Quelle: Commit `e14340d` im Repo `/Users/exodie/ExePrivat/exe-ai-terminal`
(„Point the picture paths at an embeddings folder", 26 Zeilen):

- `app/bildrunner.py` — sd-cli bekommt `--embd-dir <ordner>`, wenn der
  Ordner existiert
- `app/bildturbo.py` — der Turbo-Server bekommt dasselbe Flag
- `app/bildwahlen.py` — der Unterordner-Name (`embedding` unter dem
  Bildmodell-Ordner) als Konstante
- `app/api/v1/bild.py` — reicht den Ordner an den Auftrag durch

**Achtung, gelernt vom Bildcleaner heute:** die zwei Repos haben KEINE
gemeinsame Git-Historie und die Dateien sind teils anders aufgebaut. Weg:
ExePrivat als Remote hinzufügen, fetchen, `git cherry-pick e14340d`,
Konflikte von Hand lösen und dabei prüfen, ob jede Änderung in unserer
Struktur an der richtigen Stelle landet — nicht blind übernehmen. Danach
Remote wieder entfernen.

## Teil 2 — „Ordner öffnen"-Knopf im Bild-Panel

Ein Knopf im Bild-Server-Panel der Lokal-Seite, der den Embedding-Ordner im
Finder öffnet. Das Muster existiert fertig im Haus:

- Backend-Vorbild: `POST /api/v1/runner/folder` in `app/api/v1/runner.py`
  nutzt `ordner_oeffnen` aus `app/ordner_dialog.py` (Fehlerfall 501 mit
  Satz, siehe `tests/test_runner_api.py::test_ohne_dateimanager_kommt_ein_satz`)
- Neue Funktion = eigenes Modul bzw. eigener Endpunkt, nicht irgendwo
  reinquetschen (Hausregel Modularität); wenn es einen bestehenden
  Bild-Ordner-Endpunkt gibt, dessen Muster folgen
- Der Knopf öffnet den Ordner und legt ihn vorher an, falls er fehlt
  (`mkdir -p`-Verhalten) — sonst öffnet der Erstnutzer ins Leere
- Frontend: Bild-Panel in `frontend/src/teile/` (Lokal-Seite; das Panel,
  das auch einstellt, womit das Bildfenster öffnet)

### i18n (Pflichtweg)

- Texte in `app/locales/en.json` UND `de.json`, English first — der
  englische Text ist die Quelle, der deutsche die Übersetzung, nie wörtlich
  rückwärts. Deutsche Texte sagen „PC", nie „Maschine".
- Nach Katalog-Änderung: `tests/test_i18n.py` muss grün sein.
- Sinnvoll auch ein kurzer Hinweistext am Panel, dass Embeddings im Prompt
  über den Dateinamen ohne Endung angesprochen werden — sonst weiß das
  wieder niemand.

## Hausregeln-Kurzliste (gelten alle)

- Code, Kommentare, Commit-Nachrichten: Englisch. Keine Personennamen,
  keine Datumsstempel, keine Gesprächszitate in Kommentaren.
- Commits ohne jeden KI-Vermerk (kein Co-Authored-By, kein „Generated
  with"). Autor ist das Projekt.
- Vor jedem Commit: `.venv/bin/python3 -m pytest tests/ -q`.
  Bekannte Stolpersteine: `test_werkzeugkatalog` ist rot wegen Chris'
  privatem Mail-Server in der uncommitteten `mcp_servers.json` — das ist
  GEWOLLT, nicht fixen, `mcp_servers.json` nicht committen.
  `test_modellrunner` braucht Port 8099 frei.
- Frontend-Änderungen: `cd frontend && npm run build`.
- `README.md` und `docs/site/` liegen absichtlich im Baum (GitHub-Seite) —
  nicht anfassen, nicht löschen.

## Fertig heißt

Beide Teile gebaut, Tests grün (bis auf den bekannten Mail-Roten), Frontend
gebaut, als saubere Commits auf `exe-ai`. Dann Chris Bescheid
geben — Release/Auslieferung entscheidet er separat.
