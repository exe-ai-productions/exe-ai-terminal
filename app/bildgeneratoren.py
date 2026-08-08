"""Image generation.

An image endpoint is — like a model endpoint — just an address in
``config.yaml``: reachable or not, nothing is hardwired to a specific server
(guardrail: the as-shipped state runs without a remote image server).
Two dialects, both from day one:

* ``comfyui`` — speaks the ComfyUI API: submit a workflow in API format
  (``POST /prompt``), poll the history, fetch the finished image via
  ``/view``. The workflow comes from a file of the operator's with three
  placeholders ({{PROMPT}}, {{NEGATIV}}, {{SEED}}) — what the user types
  goes in raw, no embellishment.
* ``openai_images`` — ``POST /v1/images/generations`` with ``b64_json``.

Whether a language model has to make way on the target machine is up to the
operator — a GPU arbiter in front of ComfyUI can handle that by itself.
This code only asks: are you there, and will you paint me this?
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import random
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

# A generation is allowed to take a while — cold start of the generator included.
ZEIT_GESAMT = 600.0
ABFRAGE_ABSTAND = 1.5


class BildFehler(Exception):
    """The generation failed — with a readable reason."""


class BildAbbruch(Exception):
    """The user stopped it — not an error, just an ending."""


@dataclass
class BildErgebnis:
    daten: bytes
    endung: str  # ".png"


class BildGenerator:
    def __init__(self, eintrag, projektwurzel: Path) -> None:
        self.eintrag = eintrag
        self.projektwurzel = projektwurzel

    @property
    def id(self) -> str:
        return self.eintrag.id

    @property
    def dialect(self) -> str:
        return self.eintrag.dialect

    @property
    def _kopfzeilen(self) -> dict[str, str]:
        """Access key, in case the service demands one.

        Read fresh from the environment on every request, so a key changed in
        .env takes effect without a restart. If the variable is missing, the
        request goes out without the header and the service answers with
        401 - better a clear refusal than a silent workaround.
        """
        name = self.eintrag.api_key_env
        if not name:
            return {}
        wert = os.getenv(name, "").strip()
        return {"Authorization": f"Bearer {wert}"} if wert else {}

    async def erreichbar(self, timeout: float = 4.0) -> bool:
        pfad = "/system_stats" if self.dialect == "comfyui" else "/v1/models"
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=self._kopfzeilen) as client:
                antwort = await client.get(self.eintrag.base_url.rstrip("/") + pfad)
            return antwort.status_code == 200
        except httpx.HTTPError:
            return False

    async def erzeugen(
        self, prompt: str, stopp: asyncio.Event | None = None
    ) -> BildErgebnis:
        """`stopp` comes from the stop button: once set,
        the generation ends with BildAbbruch — and the generator really stops
        computing, not just the waiting."""
        if self.dialect == "comfyui":
            return await self._comfyui(prompt, stopp)
        return await self._openai(prompt, stopp)

    # --- ComfyUI ---------------------------------------------------------

    def _workflow_bauen(self, prompt: str) -> dict:
        # No shipped default any more. A ComfyUI workflow names the exact
        # checkpoints and loras of the machine it was built on, so one
        # travelling with the program would fail on every other machine while
        # claiming a model nobody has. Whoever runs ComfyUI has their own.
        if not self.eintrag.workflow:
            raise BildFehler(
                "Für ComfyUI fehlt der Workflow. Trage ihn beim Endpunkt ein: "
                "workflow: \"./mein-workflow.json\""
            )
        pfad = self.projektwurzel / self.eintrag.workflow
        try:
            vorlage = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as fehler:
            raise BildFehler(f"Workflow-Datei nicht lesbar: {fehler}") from fehler
        workflow = vorlage.get("workflow")
        if not isinstance(workflow, dict):
            raise BildFehler("Workflow-Datei: 'workflow' fehlt oder ist kein Objekt")
        negativ = vorlage.get("negativ", "")

        # Replace placeholders — via the JSON text form, so they work at any
        # spot in the workflow. The prompt is inserted JSON-encoded,
        # otherwise a quotation mark in the text breaks everything.
        text = json.dumps(workflow)
        text = text.replace('"{{SEED}}"', str(random.randrange(2**31)))
        text = text.replace("{{PROMPT}}", json.dumps(prompt, ensure_ascii=False)[1:-1])
        text = text.replace("{{NEGATIV}}", json.dumps(negativ, ensure_ascii=False)[1:-1])
        return json.loads(text)

    async def _comfyui(
        self, prompt: str, stopp: asyncio.Event | None = None
    ) -> BildErgebnis:
        basis = self.eintrag.base_url.rstrip("/")
        workflow = self._workflow_bauen(prompt)
        async with httpx.AsyncClient(timeout=ZEIT_GESAMT, headers=self._kopfzeilen) as client:
            try:
                antwort = await client.post(
                    basis + "/prompt",
                    json={"prompt": workflow, "client_id": uuid.uuid4().hex},
                )
            except httpx.HTTPError as fehler:
                raise BildFehler(f"ComfyUI nicht erreichbar: {fehler}") from fehler
            if antwort.status_code != 200:
                raise BildFehler(f"ComfyUI lehnt den Workflow ab: {antwort.text[:300]}")
            prompt_id = antwort.json().get("prompt_id")
            if not prompt_id:
                raise BildFehler("ComfyUI gab keine prompt_id zurück")

            frist = asyncio.get_event_loop().time() + ZEIT_GESAMT
            while asyncio.get_event_loop().time() < frist:
                await asyncio.sleep(ABFRAGE_ABSTAND)
                if stopp is not None and stopp.is_set():
                    # Both, in this order: remove from the queue (if not up
                    # yet) AND interrupt the running compute step — otherwise
                    # the GPU stubbornly keeps painting.
                    try:
                        await client.post(basis + "/queue", json={"delete": [prompt_id]})
                        await client.post(basis + "/interrupt")
                    except httpx.HTTPError:
                        pass  # We stop anyway — worst case the server finishes computing its image.
                    raise BildAbbruch()
                verlauf = (await client.get(basis + f"/history/{prompt_id}")).json()
                eintrag = verlauf.get(prompt_id)
                if not eintrag:
                    continue
                status = eintrag.get("status", {})
                if status.get("status_str") == "error":
                    meldungen = [
                        n.get("exception_message", "")
                        for n in status.get("messages", [])
                        if isinstance(n, dict)
                    ]
                    raise BildFehler(
                        "ComfyUI meldet einen Fehler: "
                        + (next(iter(meldungen), "") or "unbekannt")[:300]
                    )
                for ausgabe in (eintrag.get("outputs") or {}).values():
                    for bild in ausgabe.get("images", []):
                        geholt = await client.get(
                            basis + "/view",
                            params={
                                "filename": bild["filename"],
                                "subfolder": bild.get("subfolder", ""),
                                "type": bild.get("type", "output"),
                            },
                        )
                        if geholt.status_code == 200:
                            return BildErgebnis(daten=geholt.content, endung=".png")
            raise BildFehler("Zeitgrenze erreicht — die Erzeugung kam nicht zum Ende")

    # --- OpenAI images API -----------------------------------------------

    async def _openai(
        self, prompt: str, stopp: asyncio.Event | None = None
    ) -> BildErgebnis:
        basis = self.eintrag.base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=ZEIT_GESAMT, headers=self._kopfzeilen) as client:
            try:
                # The OpenAI images API knows no interrupting — stop here
                # means: wait no longer. The request runs as a task so the
                # stop event can throw it off.
                anfrage = asyncio.create_task(
                    client.post(
                        basis + "/v1/images/generations",
                        json={"prompt": prompt, "response_format": "b64_json"},
                    )
                )
                if stopp is None:
                    antwort = await anfrage
                else:
                    warten = asyncio.create_task(stopp.wait())
                    fertig, _ = await asyncio.wait(
                        {anfrage, warten}, return_when=asyncio.FIRST_COMPLETED
                    )
                    if anfrage not in fertig:
                        anfrage.cancel()
                        raise BildAbbruch()
                    warten.cancel()
                    antwort = anfrage.result()
            except httpx.HTTPError as fehler:
                raise BildFehler(f"Bildserver nicht erreichbar: {fehler}") from fehler
        if antwort.status_code != 200:
            raise BildFehler(f"Bildserver: {antwort.text[:300]}")
        daten = antwort.json().get("data") or []
        if not daten or "b64_json" not in daten[0]:
            raise BildFehler("Bildserver gab kein Bild zurück")
        return BildErgebnis(daten=base64.b64decode(daten[0]["b64_json"]), endung=".png")


def konfiguration_pruefen(text: str) -> str | None:
    """Validates raw ``bild_server.json`` content for the form.

    Same design as with ``mcp_servers.json``: it is saved regardless, but
    the UI says immediately what needs fixing.
    """
    from pydantic import ValidationError

    from app.config import BildEndpunktConfig

    try:
        rohdaten = json.loads(text)
    except json.JSONDecodeError as fehler:
        return f"kein gültiges JSON: {fehler}"
    if not isinstance(rohdaten, dict):
        return "die oberste Ebene muss ein Objekt sein"
    eintraege = rohdaten.get("bildServer")
    if not isinstance(eintraege, list):
        return "'bildServer' fehlt oder ist keine Liste"
    for stelle, felder in enumerate(eintraege, start=1):
        if not isinstance(felder, dict):
            return f"Eintrag {stelle}: muss ein Objekt sein"
        try:
            BildEndpunktConfig(**felder)
        except ValidationError as fehler:
            erster = fehler.errors()[0]
            feld = ".".join(str(t) for t in erster.get("loc", []))
            return f"Eintrag {stelle} ('{felder.get('id', '?')}'): {feld}: {erster.get('msg')}"
    return None


def generatoren(config) -> list[BildGenerator]:
    """The enabled image generators from config.yaml.

    They live there instead of in a separate file: one
    configuration, one editor tab. A change only takes effect
    after a restart — like everything else in config.yaml.
    """
    from app.config import PROJEKT_WURZEL

    return [
        BildGenerator(eintrag, PROJEKT_WURZEL)
        for eintrag in config.image_servers
        if eintrag.enabled
    ]
