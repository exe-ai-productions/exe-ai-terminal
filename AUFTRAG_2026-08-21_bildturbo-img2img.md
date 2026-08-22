# Auftrag: Image-Turbo für Startbild, Maske, Hires-Fix und Clip-Skip öffnen

Stand: 21.08.2026. Umfang: genau die Teile unten, nicht mehr. Kein Release,
kein GitHub-Push, keine Änderung am Bildfenster-Layout — das entscheidet Chris
separat.

## WICHTIG: das richtige Repo

Gearbeitet und committet wird NUR hier:

    /Volumes/4TB SSD/Projects/exe-ai-terminal/exe-ai-terminal   (Branch: exe-ai)

NICHT in `exe-ai-terminal-labor`. NICHT in `~/ExePrivat`.

## Worum es geht

Heute fallen vier Dinge zwingend auf den langsamen `sd-cli`-Weg zurück, auch
wenn Image-Turbo läuft: **Startbild (img2img)**, **Maske (Inpainting)**,
**Hires-Fix** und **Clip-Skip**. Die Weiche steht in
`app/api/v1/bild.py:512`:

```python
turbo_faehig = not (
    auftrag.startbild or auftrag.maske or auftrag.hires or auftrag.clip_skip > 0
)
```

Der Kommentar darüber begründet das damit, diese Werte seien „keine sauberen
Per-Request-Felder im HTTP-Body dieses Servers". **Das stimmt für den heute
angehefteten Build nicht mehr.**

### Befund (21.08.2026, am echten Binary geprüft)

Geprüft wurde die Datei, die bei Chris tatsächlich liegt:

    ~/Library/Application Support/Exe AI Terminal/data/stable-diffusion.cpp/master-820-de298c2/sd-server

(angeheftete Version: `BAU = "master-820-de298c2"` in `app/sddownload.py:54`)

Nachprüfbar mit:

```bash
strings -a "$HOME/Library/Application Support/Exe AI Terminal/data/stable-diffusion.cpp/master-820-de298c2/sd-server" | grep -oE "/sdapi/v1/[a-z0-9_-]+" | sort -u
```

Ergebnis:

| Vorhanden im Binary | Bedeutung |
|---|---|
| `/sdapi/v1/img2img` | eigener Eingang neben `txt2img` |
| `init_images` | das Startbild |
| `denoising_strength` | unsere „Stärke" |
| `mask`, `inpainting_mask_invert` | die Maske samt Polaritätsschalter |
| `enable_hr`, `hr_scale`, `hr_steps`, `hr_upscaler` | Hires-Fix |
| `clip_skip` | Clip-Skip |

Die Feldnamen stehen im Binary in einem zusammenhängenden Parameterblock
(`… hr_steps, hr_upscaler, lora.path required, init_images, mask,
inpainting_mask_invert, extra_images …`), also im C++-Parser des Servers und
nicht bloß in der mitgelieferten Web-Oberfläche.

Der Server kann es also. Der Code fragt ihn nur nie danach.

## Teil 0 — Erst prüfen, dann bauen (Pflicht, nicht überspringen)

Bevor eine Zeile Produktivcode fällt: eine Probe gegen den laufenden Server.

1. Image-Turbo über die Oberfläche auf ein SD-1.5-Modell starten (oder
   `POST /api/v1/bild/turbo/start`).
2. Ein vorhandenes Bild aus dem Bilder-Ordner nach base64 wandeln und per
   `httpx`/`curl` an `http://127.0.0.1:8191/sdapi/v1/img2img` schicken:
   `{"prompt": ..., "init_images": ["<b64>"], "denoising_strength": 0.6,
   "steps": 20, "width": 512, "height": 512, "sampler_name": ...}`.
3. Zweiter Durchgang mit `"mask": "<b64 einer schwarz-weißen Maske>"`.

Festhalten (das sind die offenen Fragen, nicht Nebensache):

- **Kommt überhaupt ein Bild zurück** — oder antwortet der Server 404/500?
- **Maskenpolarität:** In `frontend/src/lib/maske.js` heißt **WEISS = „male
  das neu"**. Malt der Server dieselbe Stelle neu, oder genau die andere?
  Wenn andersherum: `inpainting_mask_invert` setzen — **nicht** die Maske im
  Frontend umdrehen, denn `sd-cli` erwartet die heutige Polarität weiter.
- **Größe:** Was macht der Server, wenn `width`/`height` nicht der Größe des
  Startbilds entsprechen — skalieren oder beschneiden? `sd-cli` verhält sich
  hier eventuell anders; ein Unterschied zwischen beiden Wegen ist ein Fehler,
  kein Detail.
- **Feldname der Maske:** `mask` bestätigen (nicht `mask_image`) — im Binary
  kommen beide Zeichenketten vor.
- Dasselbe kurz für `enable_hr` + `hr_scale` und für `clip_skip`.

Wenn ein Punkt nicht funktioniert, wird genau dieser Punkt **nicht** geöffnet
und bleibt in `turbo_faehig` stehen — lieber drei von vier sauber als vier
halb. Das Ergebnis der Probe kurz an Chris melden, bevor gebaut wird.

Chris' Datenordner ist heilig: nichts darin verändern, verschieben oder
löschen. Für die Probe ein Wegwerf-Bild nehmen. **Bild-Metadaten nie auslesen
oder ausgeben** — die Bytes wandern nur nach base64 und sonst nirgendwohin.

## Teil 1 — `app/bildturbo.py`: der zweite Eingang

`zeichnen()` schickt heute fest an `/sdapi/v1/txt2img` (Zeile 378). Das Modul
soll weiter „nur HTTP sprechen und die Parameternamen nicht kennen" — also
**nicht** im Modul auf `init_images` prüfen.

Weg: der Aufrufer sagt, welcher Eingang gemeint ist, z. B. eine neue
Signatur `zeichnen(self, auftrag: dict, *, weg: str = "txt2img")` und die URL
daraus zusammengesetzt. Alternativ ein eigenes `zeichnen_bild()`, wenn das
sauberer wird — Hausregel „ein Modul pro Funktion" gilt für Module, nicht für
jede Methode; hier entscheidet, was kleiner ist.

Unverändert bleiben: Sperre, Zeitgrenze (`ZEICHENFRIST`), Abbruch-Verhalten
(`abbrechen` → `bild.abgebrochen`, stiller 499) und die base64-Rückgabe.

## Teil 2 — `app/api/v1/bild.py`: `_turbo_auftrag` erweitern

`_turbo_auftrag` (Zeile 601) baut den A1111-Body. Dazukommen:

- Startbild vorhanden → Datei-Bytes lesen, base64, `init_images: [<b64>]`,
  `denoising_strength: auftrag.staerke`
- Maske vorhanden → `mask: <b64>` (und `inpainting_mask_invert`, falls
  Teil 0 das ergeben hat)
- `auftrag.hires` → `enable_hr: true`, `hr_scale`, `hr_steps` (nur wenn > 0)
- `auftrag.clip_skip > 0` → `clip_skip`

Der Docstring der Funktion beschreibt heute ausdrücklich das Gegenteil
(„Starting image, mask, highres and clip-skip never reach this path at all")
— **der muss mit umgeschrieben werden**, sonst steht in einem halben Jahr
wieder ein Kommentar da, der lügt.

Dasselbe gilt für den langen Erklärkommentar über `turbo_faehig`
(Zeile ~500–512).

## Teil 3 — die Weiche aufmachen

`turbo_faehig` verliert genau die Bedingungen, die Teil 0 bestätigt hat.
Bleiben soll die Regel: **was der Turbo nicht sicher kann, geht weiter über
`sd-cli`** — ein stillschweigend fallengelassener Regler ist der schlimmste
Ausgang, schlimmer als langsam.

Zu prüfen dabei:

- `passt_zu()` (Zeile 131) vergleicht Modell, VAE, Detektor, Detektor-Prompt.
  Startbild, Maske, Hires und Clip-Skip sind **Per-Request**-Werte, keine
  Startflags — `passt_zu` darf davon nichts wissen und braucht **keine**
  Änderung. Bitte bewusst so lassen und nicht „der Vollständigkeit halber"
  ergänzen, sonst startet der Server bei jedem Bild neu.
- Der Fortschrittszähler in `zeichnen()` rechnet mit
  `paesse = 1 + (1 wenn Detektor)`. Mit Hires-Fix kommt ein weiterer
  Malgang dazu. Entweder mitzählen oder ehrlich lassen — aber ein Balken,
  der bei 100 % stehenbleibt und dann weitermalt, ist ein Balken, der lügt.

## Teil 4 — Tests

- `tests/test_bildturbo.py`: der neue Eingang wird angesprochen — Body mit
  `init_images` geht an `/sdapi/v1/img2img`, ohne an `/sdapi/v1/txt2img`.
  HTTP wird gemockt, kein echter Server im Test.
- Ein Test für `_turbo_auftrag`: Startbild + Maske + Stärke landen als
  base64 im Body; ohne Startbild taucht `denoising_strength` **nicht** auf.
- Ein Test für die Weiche: ein Auftrag mit Startbild bei laufendem Turbo geht
  über den Turbo — und ein Auftrag mit einer Fähigkeit, die Teil 0 verworfen
  hat, geht weiter über `sd-cli`.
- Die bestehende Regel bleibt: **Maske ohne Startbild wird verworfen**
  (`bild.py`, `maske = _startbild(...) if startbild else None`).

## Hausregeln-Kurzliste (gelten alle)

- Code, Kommentare, Commit-Nachrichten: **Englisch**. Keine Personennamen,
  keine Datumsstempel, keine Gesprächszitate in Kommentaren.
- Commits ohne jeden KI-Vermerk (kein Co-Authored-By, kein „Generated with").
- Vor jedem Commit: `.venv/bin/python3 -m pytest tests/ -q`.
  Bekannte Stolpersteine: `test_werkzeugkatalog` ist rot wegen Chris'
  privatem Mail-Server in der uncommitteten `mcp_servers.json` — das ist
  GEWOLLT, nicht fixen, `mcp_servers.json` nicht committen.
  `test_modellrunner` braucht Port 8099 frei.
- Frontend wird hier voraussichtlich **nicht** angefasst. Falls doch:
  `cd frontend && npm run build`, und neue Texte in `en.json` UND `de.json`,
  English first, deutsche Texte sagen „PC", nie „Maschine".
- `README.md` und `docs/site/` nicht anfassen.

## Fertig heißt

Teil 0 geprüft und gemeldet, die dabei bestätigten Fähigkeiten geöffnet, die
irreführenden Kommentare berichtigt, Tests grün (bis auf den bekannten
Mail-Roten), als saubere Commits auf `exe-ai`. Dann Chris Bescheid
geben — Release/Auslieferung entscheidet er separat.

## Was dieser Auftrag NICHT ist

- Kein neues Bedienelement, keine Layout-Änderung im Bildfenster.
- Kein Anheben von `BAU` auf einen neueren stable-diffusion.cpp-Build.
- Keine Änderung am `sd-cli`-Weg — der bleibt der maßgebliche Weg und muss
  weiter alles können, was er heute kann.
