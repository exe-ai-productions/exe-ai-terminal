# FOR FABLE — Werkzeugprotokoll, Mitschnitt, und zwei echte Fehler

**Stand: 2026-08-16.** Gefunden beim Versuch, aus dem laufenden Terminal
echtes Trainingsmaterial zu gewinnen.

Warum das gebraucht wird: Die alte Teststrecke der Exe-Modelle hält der
Prüfung nicht stand — Test B besteht zu 52 % aus einer einzigen Fehlerart
und ist bitgleich mit der Trainingsabspaltung des Wächters. Testfälle und
Wächter-Trainingsdaten sollen künftig aus **beobachteter Wirklichkeit**
entstehen statt aus einem Generator. Dafür muss man wissen, was das
Terminal aufzeichnet. Das steht hier.

---

## ⚠ Zuerst: eine Korrektur, damit niemand denselben Umweg geht

**Ich habe zwischenzeitlich behauptet, das Terminal speichere
Werkzeugschritte nicht. Das ist falsch.**

Der Irrtum entstand so: Die Tabelle `messages` hat eine Spalte `role` mit
`CHECK (role IN ('system','user','assistant','tool'))`. Ich habe nach
Zeilen mit `role='tool'` gesucht, keine gefunden — 142 Nachrichten, davon
71 `user` und 71 `assistant`, null `tool` — und daraus geschlossen, es
werde nichts aufgezeichnet.

**Richtig ist:** Werkzeugschritte werden **nicht als eigene Zeile**
gespeichert, sondern **im `stats_json` der Assistenten-Nachricht**, unter
dem Schlüssel `werkzeuge`. Die Rolle `tool` existiert nur im
Arbeitsspeicher, im Gespräch das an das Modell geht
(`app/api/v1/generierung.py`, `ChatNachricht(role="tool", …)` wird an
`anfrage.nachrichten` angehängt, nie an das Repository).

Wer also `role='tool'` abfragt, findet nichts und hält das Terminal für
blind. Es ist nicht blind.

---

## Wo die Daten wirklich stehen

`app/api/v1/generierung.py` baut während der Antwort eine Liste
`werkzeugprotokoll` (Zeile ~615, gefüllt bei ~792 und ~844):

```python
werkzeugprotokoll.append({
    "name": aufruf.name,
    "server": registry.server_von(aufruf.name) if registry else "",
    "argumente": aufruf.argumente,
    "fehlgeschlagen": fehlgeschlagen,
    "ergebnis": ergebnis[:2000],
    "bild": None,
})
```

Am Ende der Antwort landet sie in den Messwerten und wird mit der
Assistenten-Nachricht gespeichert (~928):

```python
if werkzeugprotokoll:
    messwerte["werkzeuge"] = werkzeugprotokoll
repositories.messages.inhalt_aktualisieren(
    platzhalter.id, content=…, reasoning=…, stats=messwerte, bild=…)
```

Gespeichert wird über `app/db/repositories/messages.py` in
`messages.stats_json`.

### Was schon dasteht — nachgezählt, nicht geschätzt

| Datenbank | |
|---|---|
| `~/Library/Application Support/Exe AI Terminal/data/exe-ai-terminal.db` | installierte App |
| `data/exe-ai-terminal.db` im Repo | Entwicklungsstand |

Beide zusammen, Stand 16.08.:

```
Werkzeugschritte insgesamt : 63
davon fehlgeschlagen       :  9

run_command   37    memory_save    7    web_search    5
read_webpage   3    write_file     3    list_dir      1
edit_file      1    read_file      1
```

Die gescheiterten Schritte sind brauchbares Material, zum Beispiel:

```
edit_file  {"old_text": "port = 8080", …}
  -> old_text was not found in '…/arbeitsordner/app/config.yaml'

read_file  {"path": "logs/dienst.bin"}
  -> '…/logs/dienst.bin' is a binary file, use run_command with a suitable tool instead.

list_dir   {"path": "."}
  -> No working folder is shared with this chat. Ask the user to share one …
```

### So kommt man dran

```python
import sqlite3, json
db = "…/exe-ai-terminal.db"
v = sqlite3.connect(f"file:{db}?mode=ro", uri=True)   # nur lesen, App darf laufen
for (s,) in v.execute("select stats_json from messages where stats_json like '%werkzeuge%'"):
    for w in json.loads(s).get("werkzeuge", []):
        if w.get("fehlgeschlagen"):
            print(w["name"], w["argumente"], w["ergebnis"])
```

Für eine konsistente Kopie bei laufender App: `sqlite3.Connection.backup()`
benutzen, nicht `cp` — sonst fehlt der WAL-Teil.

---

## Was dabei verlorengeht — die Grenzen der Datenbank

Diese vier Punkte sind der Grund, warum die Datenbank allein für
Trainingsdaten **nicht ganz** reicht. Ob das reicht oder nicht, ist eine
Entscheidung, keine Tatsache — deshalb hier die Fakten statt einer
Empfehlung.

**1. Das Ergebnis wird bei 2000 Zeichen abgeschnitten** (`ergebnis[:2000]`).
Bei langen Ausgaben — Testläufe, Tracebacks, `find`-Ergebnisse — fehlt das
Ende. Genau dort steht oft die eigentliche Fehlermeldung.

**2. Der Systemprompt wird nicht mitgespeichert.** Ein Werkzeugaufruf ist
ohne den Prompt, unter dem er entstand, nur halb interpretierbar — und der
Prompt hängt an Einstellungen, freigegebenen Ordnern und Werkzeugauswahl,
die sich ändern.

**3. Es gibt keinen Zeitstempel je Schritt**, nur einen je Nachricht. Bei
mehreren Werkzeugrunden in einer Antwort ist die Reihenfolge erhalten, die
Dauer nicht.

**4. Die Werkzeugliste des Laufs fehlt.** Welche Werkzeuge dem Modell
überhaupt angeboten wurden, steht nicht dabei. Für die Frage „hätte es das
richtige Werkzeug greifen können?" ist das nötig.

---

## Der Mitschnitt als zweite Quelle

Auf dem Desktop liegt `Exe-Terminal-mitschneiden.command`. Es setzt sich
als Zwischenstation zwischen Terminal und Modellserver:

```
Terminal  ──>  Skript (Port 8110)  ──>  Modellserver
                    └──> Exe-Mitschnitt/mitschnitt-<datum>.jsonl
```

Es zeichnet **alles roh auf** — vollständige Anfrage, vollständige Antwort,
bei gestreamten Antworten zusätzlich den rohen Strom. **Keine Einordnung,
keine Auswahl, kein Weglassen.** Das ist Absicht: wer beim Sammeln schon
aussortiert, schreibt seine Erwartung in die Daten, und genau daran ist die
alte Testmenge gescheitert.

Damit sind alle vier Lücken oben geschlossen: der Systemprompt steht in
jeder Anfrage, die Werkzeugliste auch, nichts wird abgeschnitten, und jeder
Austausch hat Zeit und Dauer.

**Einrichten:** Skript starten, im Terminal die Modell-Adresse auf
`http://127.0.0.1:8110/v1` umstellen. Am Programm wird nichts geändert.
Zum Beenden Adresse zurückstellen.

**Geprüft am 16.08.:** normale Anfrage mit Werkzeugschritt durch,
gestreamte Antwort mit 11 SSE-Brocken durch und vollständig aufgezeichnet,
`GET /v1/models` durch.

**Offene Entscheidung für dich:** Datenbank auslesen (einfach, historische
Daten sofort da, vier Lücken) oder Mitschnitt (vollständig, braucht eine
Umstellung und läuft nur, solange er läuft) — oder beides, und die
Datenbank als Rückfall.

---

## Zwei echte Fehler im Terminal, nebenbei gefunden

Beides in `app/tools/shell.py`, Funktion `greift_nach_draussen()`. **Keine
Testartefakte — sie treffen den Betrieb.** Stehen auch im Notion-Bauplan.

### 1. Ein Leerzeichen im freigegebenen Ordner blockiert Befehle

Die Funktion zerlegt den Befehl mit `shlex.split()` und prüft jedes
pfadförmige Wort. Ein freigegebener Ordner mit Leerzeichen zerfällt dabei:

```
run_command("cd /Volumes/4TB SSD/Spielplatz/lager && find . …")
→ Not executed — reaches /Volumes/4TB, outside the shared folders.
```

Die Arbeits-SSD dieses Rechners heißt „4TB SSD". Jeder Nutzer mit einem
Leerzeichen im Ordnernamen bekommt legitime Befehle abgelehnt.

### 2. `2>/dev/null` und `./skript.sh` lösen den Fehlalarm aus

Die Umleitung wird als Dateizugriff gelesen, der relative Pfad als
absoluter:

```
grep -r -i "auswertung" . 2>/dev/null   → reaches /dev/null, outside …
./run_tests.sh                          → reaches /run_tests.sh, outside …
```

`2>/dev/null` steht in einem großen Teil aller Shell-Befehle. Im Betrieb
feuert das ständig.

**Gemessen:** Von 7 Ablehnungen in einem Probelauf waren **5 Fehlalarme**;
die übrigen 2 waren echt (`grep -r /` und `find /` — das Modell wollte
wirklich die ganze Platte durchsuchen).

Der Kommentar in der Funktion nennt die Heuristik selbst eine Stolperdraht-
Lösung und ihre Grenze („was sie nicht sehen kann, ist ein zur Laufzeit
gebauter Pfad"). Diese beiden Fälle sind aber keine Grenze der Heuristik,
sondern schlicht Fehlalarme.

---

## Wo der Rest liegt

| Was | Wo |
|---|---|
| Vollständiges Handoff zum Teststrecken-Neubau | `/Volumes/4TB SSD/Exe System/Handoffs/HANDOFF_2026-08-16_pruefstand-neubau_2.md` |
| Der Neubau selbst, mit Regeln und Protokoll | `/Volumes/4TB SSD/Exe-Training-Main/Pruefstand/` |
| Alte Teststrecke, eingefroren und geprüft | `/Volumes/4TB SSD/Exe-Training-Main/Archiv/Teststrecke-v1-2026-08-16/` |
| Alle Messwerte der Modelle | `/Volumes/4TB SSD/Exe-Training-Main/Benchmark/MESSWERTE.md` |
| Mitschnitt-Skript | `~/Desktop/Exe-Terminal-mitschneiden.command` |

---

## Eine Regel, die hier gilt und teuer erkauft ist

**Jede Behauptung braucht einen Prüfbefehl. Sonst steht „ungeprüft" dabei.**

Dieses Dokument hat seinen eigenen Anlass: Ich habe „das Terminal speichert
das nicht" gesagt, ohne den Speicherpfad im Code zu verfolgen — und lag
falsch. Vorher war schon zweimal etwas als „sicher" gemeldet worden, was es
nicht war. Die Zahlen oben sind deshalb alle nachgezählt, und die Befehle
dafür stehen dabei.
