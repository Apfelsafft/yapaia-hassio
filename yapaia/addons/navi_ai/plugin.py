"""KI-Navigation addon – natural-language route planning via Claude/OpenAI/Ollama."""
from __future__ import annotations

import json
import re

import httpx

from app.addons.base import BaseAddon

_SYSTEM_PROMPT = """Du bist ein Navigationsassistent für eine Karten-App. Analysiere die Nutzeranfrage und antworte NUR mit einem gültigen JSON-Objekt – kein Markdown, keine Erklärungen, kein Text davor oder danach.

JSON-Schema:
{
  "destination": "Vollständige Adresse oder Ortsname des Ziels (Pflichtfeld)",
  "profile": "car|bike|foot|motorhome",
  "waypoints": ["optionale Zwischenstationen als Adressen oder Ortsnamen"],
  "avoid": ["highway|tolls|ferries|unpaved"],
  "prefer_scenic": false,
  "routing_strategy": "fastest|shortest|scenic",
  "notes": "Hinweise, die nicht direkt in Routenparameter umgewandelt wurden"
}

Regeln:
- destination immer setzen wenn ein Ort/Ziel erkennbar ist
- "Fahrrad", "Rad", "Radfahren", "Radtour" → profile: "bike"
- "zu Fuß", "wandern", "laufen", "Spaziergang" → profile: "foot"
- "Wohnmobil", "Camper", "Reisemobil" → profile: "motorhome"
- Ohne explizite Angabe → profile: "car"
- "keine Autobahn", "Landstraße" → avoid: ["highway"]
- "keine Maut", "mautfrei" → avoid: ["tolls"]
- "schnellste", "schnellster Weg" → routing_strategy: "fastest"
- "kürzeste", "kürzester Weg" → routing_strategy: "shortest"
- "schöne Route", "Natur", "landschaftlich", "malerisch", "entlang der ..." → prefer_scenic: true, routing_strategy: "scenic"
- waypoints nur setzen wenn explizit Zwischenziele genannt werden
- notes auf Deutsch, leer wenn keine besonderen Hinweise
"""

_DEFAULT_MODELS = {
    "claude": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.2",
}


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, even if wrapped in markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


class Plugin(BaseAddon):
    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    # ── LLM provider calls ────────────────────────────────────────────────────

    async def _call_claude(self, text: str, settings: dict) -> dict:
        api_key = settings.get("api_key", "").strip()
        model = settings.get("model", "").strip() or _DEFAULT_MODELS["claude"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 512,
                    "system": _SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": text}],
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            content = resp.json()["content"][0]["text"]
            return _extract_json(content)

    async def _call_openai(self, text: str, settings: dict) -> dict:
        api_key = settings.get("api_key", "").strip()
        model = settings.get("model", "").strip() or _DEFAULT_MODELS["openai"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "max_tokens": 512,
                    "response_format": {"type": "json_object"},
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _extract_json(content)

    async def _call_ollama(self, text: str, settings: dict) -> dict:
        base_url = (settings.get("ollama_url") or "http://localhost:11434").rstrip("/")
        model = settings.get("model", "").strip() or _DEFAULT_MODELS["ollama"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "stream": False,
                    "format": "json",
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return _extract_json(content)

    async def _parse(self, text: str, settings: dict) -> dict:
        provider = settings.get("provider", "claude")
        if provider == "openai":
            return await self._call_openai(text, settings)
        if provider == "ollama":
            return await self._call_ollama(text, settings)
        return await self._call_claude(text, settings)

    # ── HTTP handler ──────────────────────────────────────────────────────────

    async def handle_request(self, path, request, user, db, addon_settings):
        from fastapi.responses import JSONResponse

        if path == "parse" and request.method == "POST":
            try:
                body = await request.json()
            except Exception:
                return JSONResponse({"error": "Ungültiger Request-Body"}, status_code=400)

            text = (body.get("text") or "").strip()
            if not text:
                return JSONResponse({"error": "Kein Text angegeben"}, status_code=400)

            provider = addon_settings.get("provider", "claude")
            api_key = addon_settings.get("api_key", "").strip()
            if provider in ("claude", "openai") and not api_key:
                return JSONResponse(
                    {"error": f"Kein API-Schlüssel für {provider} konfiguriert. Bitte in den Add-on-Einstellungen eintragen."},
                    status_code=422,
                )

            try:
                result = await self._parse(text, addon_settings)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                try:
                    detail = e.response.json()
                    msg = (detail.get("error", {}) or {}).get("message") or str(detail)
                except Exception:
                    msg = e.response.text[:300]
                if status in (401, 403):
                    return JSONResponse({"error": f"Ungültiger API-Schlüssel. ({msg})"}, status_code=422)
                return JSONResponse({"error": f"KI-Provider-Fehler: HTTP {status} — {msg}"}, status_code=502)
            except httpx.ConnectError:
                return JSONResponse(
                    {"error": "Verbindung zum KI-Provider fehlgeschlagen. Ist der Server erreichbar?"},
                    status_code=502,
                )
            except json.JSONDecodeError:
                return JSONResponse(
                    {"error": "KI-Antwort konnte nicht als JSON geparst werden. Bitte erneut versuchen."},
                    status_code=502,
                )
            except Exception as e:
                return JSONResponse({"error": f"Fehler: {e}"}, status_code=500)

            # Normalise / fill defaults
            result.setdefault("destination", "")
            result.setdefault("profile", "car")
            result.setdefault("waypoints", [])
            result.setdefault("avoid", [])
            result.setdefault("prefer_scenic", False)
            result.setdefault("routing_strategy", "fastest")
            result.setdefault("notes", "")

            if not result["destination"]:
                return JSONResponse(
                    {"error": "Kein Ziel erkannt. Bitte konkretere Angabe machen."},
                    status_code=422,
                )

            return JSONResponse(result)

        return JSONResponse({"error": "Not found"}, status_code=404)
