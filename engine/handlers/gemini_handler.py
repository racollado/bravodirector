"""
Gemini Handler — AI text generation via Google's Gemini API (google-genai SDK).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GeminiHandler:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self._api_key = api_key
        self._model_name = model
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
            logger.info("Gemini client initialized (model: %s)", self._model_name)
        except Exception as e:
            logger.error("Failed to initialize Gemini client: %s", e)

    async def generate_async(self, prompt: str) -> Optional[str]:
        if not self._client:
            logger.error("Gemini client not available")
            return None

        try:
            logger.info("Gemini generation started (prompt: %.80s...)", prompt)
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
            )
            text = response.text.strip() if response.text else None
            if text:
                logger.info("Gemini generation complete (%d chars)", len(text))
            return text
        except Exception as e:
            logger.error("Gemini generation failed: %s", e)
            return None

    def generate_sync(self, prompt: str) -> Optional[str]:
        if not self._client:
            return None
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
            )
            return response.text.strip() if response.text else None
        except Exception as e:
            logger.error("Gemini sync generation failed: %s", e)
            return None
