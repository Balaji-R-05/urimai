"""
HTTP client for the Urimai server.
The bot never decides anything itself.
"""

from __future__ import annotations

import config
import httpx


class BackendError(RuntimeError):
    pass


class Backend:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=config.BACKEND_URL, timeout=config.BACKEND_TIMEOUT_SEC
        )

    async def _post(self, path: str, **kwargs) -> dict:
        """
        Send a POST request to the backend and return the JSON response.
        """
        try:
            response = await self.client.post(path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise BackendError(f"{path}: {type(e).__name__}: {e}") from e

    async def chat(self, session_id: str, message: str, lang: str) -> dict:
        """
        Send a message to the backend and get a response.
        """
        return await self._post(
            "/api/chat",
            json={
                "session_id": session_id,
                "message": message[:2000],
                "lang": lang,
                "channel": "telegram",
            },
        )

    async def answer(self, session_id: str, field: str, value, skip: bool, lang: str) -> dict:
        """
        Send an answer to the backend.
        """
        return await self._post(
            "/api/answer",
            json={
                "session_id": session_id,
                "field": field,
                "value": value,
                "skip": skip,
                "lang": lang,
                "channel": "telegram",
            },
        )

    async def feedback(self, scheme_id: str, lang: str, text: str | None = None) -> None:
        """
        Reports an issue with a scheme's info.
        """
        await self._post("/api/feedback", json={"scheme_id": scheme_id, "lang": lang, "text": text})

    async def reset(self, session_id: str) -> None:
        """
        Reset the session, deleting all answers and profile.
        """
        await self._post("/api/session/reset", json={"session_id": session_id})

    async def report(self, session_id: str, lang: str) -> bytes | None:
        """
        PDF report bytes, or None when the session has no profile yet.
        """
        try:
            response = await self.client.get(
                f"/api/session/{session_id}/report",
                params={"lang": lang}
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as e:
            raise BackendError(f"report: {type(e).__name__}: {e}") from e

    async def transcribe(self, audio: bytes, lang: str) -> str:
        """
        Transcribe the given audio bytes to text.
        """
        data = await self._post(
            "/api/transcribe",
            files={"file": ("voice.ogg", audio, "audio/ogg")},
            data={"lang": lang},
        )
        return (data.get("text") or "").strip()

    async def health(self) -> dict:
        """
        Check the health of the backend.
        """
        try:
            response = await self.client.get("/api/health")
            return response.json()
        except (httpx.HTTPError, ValueError) as e:  # ValueError: non-JSON response body
            raise BackendError(str(e)) from e

    async def aclose(self) -> None:
        await self.client.aclose()
