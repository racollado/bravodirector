"""
Replicate Handler — unified interface for AI media generation via Replicate.

Covers:
  - Music generation (Stable Audio, etc.)
  - Sound effects (AudioGen / text-to-SFX on Replicate)
  - TTS / voice generation (minimax, ElevenLabs, etc.)
  - Video generation (Veo, Sora, etc.)

All models are called through the `replicate` Python SDK. Results are
downloaded to the local assets directory for playback.
"""

import asyncio
import logging
import os
import shutil
import ssl
from pathlib import Path
from typing import Any, Optional

import aiohttp
import certifi

logger = logging.getLogger(__name__)

ASSETS_DIR = Path("./assets")


class ReplicateHandler:
    def __init__(self, api_token: str):
        self._token = api_token
        os.environ["REPLICATE_API_TOKEN"] = api_token
        self._replicate = None
        self._init_client()

    def _init_client(self):
        try:
            import replicate
            self._replicate = replicate
            logger.info("Replicate client initialized")
        except Exception as e:
            logger.error("Failed to initialize Replicate: %s", e)

    # ------------------------------------------------------------------
    # Music generation
    # ------------------------------------------------------------------

    @staticmethod
    def _music_api_input(model: str, prompt: str, duration: int, action: Optional[dict] = None) -> dict:
        """Build Replicate `input` dict for the chosen music model (schemas differ)."""
        action = action or {}
        m = (model or "").lower()

        # Google Lyria: prompt only; optional images. Fixed clip length (30s or ~3min Pro).
        if "lyria" in m:
            inp: dict[str, Any] = {"prompt": prompt}
            imgs = action.get("images")
            if imgs:
                if isinstance(imgs, str):
                    inp["images"] = [s.strip() for s in imgs.split(",") if s.strip()]
                elif isinstance(imgs, list):
                    inp["images"] = imgs
            return inp

        # Stability Stable Audio 2.x: prompt + duration (seconds), optional diffusion controls
        inp = {
            "prompt": prompt,
            "duration": int(duration),
        }
        if action.get("steps") is not None:
            inp["steps"] = int(action["steps"])
        if action.get("cfg_scale") is not None:
            inp["cfg_scale"] = float(action["cfg_scale"])
        if action.get("seed") not in (None, ""):
            try:
                inp["seed"] = int(action["seed"])
            except (TypeError, ValueError):
                pass
        return inp

    async def generate_music(
        self,
        model: str,
        prompt: str,
        duration: int = 90,
        fallback: Optional[str] = None,
        output_file: Optional[str] = None,
        action: Optional[dict] = None,
    ) -> Optional[str]:
        """Generate music and return the local file path."""
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = ASSETS_DIR / "audio"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"generated_music_{_safe_id(prompt)}.wav"

        api_input = self._music_api_input(model, prompt, duration, action)
        try:
            logger.info("Music API input for %s: %s", model, api_input)
            result = await self._run_model(model, api_input)

            if result:
                await self._download(result, output_path)
                logger.info("Music generated: %s", output_path)
                return str(output_path)
        except Exception as e:
            logger.error("Music generation failed: %s", e)

        if fallback and os.path.exists(fallback):
            logger.warning("Using fallback audio: %s", fallback)
            shutil.copy2(fallback, output_path)
            return str(output_path)

        return None

    # ------------------------------------------------------------------
    # Sound effects (AudioGen — e.g. sepal/audiogen on Replicate)
    # ------------------------------------------------------------------

    @staticmethod
    def _sfx_api_input(prompt: str, duration: int, action: Optional[dict] = None) -> dict:
        """Build Replicate `input` for text-to-SFX models (schemas may differ slightly)."""
        action = action or {}
        dur = max(1, min(10, int(duration)))
        inp: dict[str, Any] = {"prompt": prompt, "duration": dur}
        if action.get("temperature") is not None:
            inp["temperature"] = float(action["temperature"])
        if action.get("top_k") is not None:
            inp["top_k"] = int(action["top_k"])
        if action.get("top_p") is not None:
            inp["top_p"] = float(action["top_p"])
        if action.get("classifier_free_guidance") is not None:
            inp["classifier_free_guidance"] = float(action["classifier_free_guidance"])
        fmt = action.get("output_format")
        if fmt not in (None, ""):
            inp["output_format"] = str(fmt).lower().strip()
        return inp

    async def generate_sfx(
        self,
        model: str,
        prompt: str,
        duration: int = 3,
        fallback: Optional[str] = None,
        output_file: Optional[str] = None,
        action: Optional[dict] = None,
    ) -> Optional[str]:
        """Generate a short sound effect (AudioGen) and return the local file path."""
        action = action or {}
        fmt = str(action.get("output_format", "wav")).lower().strip()
        ext = "mp3" if fmt == "mp3" else "wav"

        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = ASSETS_DIR / "audio"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"generated_sfx_{_safe_id(prompt)}.{ext}"

        api_input = self._sfx_api_input(prompt, duration, action)
        try:
            logger.info("SFX (AudioGen) API input for %s: %s", model, api_input)
            result = await self._run_model(model, api_input)
            url = _replicate_result_to_audio_url(result)
            if url:
                await self._download(url, output_path)
                logger.info("SFX generated: %s", output_path)
                return str(output_path)
        except Exception as e:
            logger.error("SFX generation failed: %s", e)

        if fallback and os.path.exists(fallback):
            logger.warning("Using fallback audio: %s", fallback)
            shutil.copy2(fallback, output_path)
            return str(output_path)

        return None

    # ------------------------------------------------------------------
    # TTS generation
    # ------------------------------------------------------------------

    async def generate_tts(
        self,
        model: str,
        text: str,
        subtitle_enable: bool = True,
        voice: str = "default",
        output_file: Optional[str] = None,
    ) -> Optional[dict]:
        """Generate TTS audio. Returns dict with audio_path and word_timestamps."""
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = ASSETS_DIR / "audio"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"generated_tts_{_safe_id(text[:30])}.wav"

        try:
            input_params = {"text": text, "subtitle_enable": subtitle_enable}
            if voice and voice != "default":
                input_params["voice"] = voice

            result = await self._run_model(model, input_params)

            if not result:
                return None

            logger.info("TTS raw result type=%s: %s", type(result).__name__, repr(result)[:500])

            # Handle different result formats
            audio_url = None
            word_timestamps = []

            if isinstance(result, dict):
                audio_url = (
                    result.get("audio_file")
                    or result.get("audio")
                    or result.get("audio_url")
                    or result.get("audio_out")
                    or result.get("output")
                )
                word_timestamps = (
                    result.get("word_timestamps")
                    or result.get("timestamps")
                    or result.get("words")
                    or []
                )
                if not audio_url:
                    for v in result.values():
                        v_str = str(v) if v else ""
                        if v_str.startswith("http") and any(ext in v_str for ext in (".mp3", ".wav", ".ogg", ".flac")):
                            audio_url = v_str
                            break
            elif isinstance(result, str):
                audio_url = result
            elif hasattr(result, "url"):
                audio_url = str(result.url)
            elif hasattr(result, "__iter__"):
                for item in result:
                    item_str = str(item) if item else ""
                    if item_str.startswith("http"):
                        audio_url = item_str
                        break

            logger.info("TTS extracted audio_url=%s, %d word_timestamps", audio_url, len(word_timestamps))

            if audio_url:
                await self._download(audio_url, output_path)

            # Group word timestamps into sentence-like chunks for caption display
            caption_chunks = self._group_words_into_chunks(word_timestamps, text)

            return {
                "audio_path": str(output_path) if audio_url else None,
                "word_timestamps": caption_chunks,
            }
        except Exception as e:
            logger.error("TTS generation failed: %s", e)
            return None

    def _group_words_into_chunks(self, word_timestamps: list, full_text: str) -> list[dict]:
        """Group word-level timestamps into sentence-level chunks for captioning."""
        if not word_timestamps:
            # Fallback: split text into sentences and estimate timing
            import re
            sentences = re.split(r'(?<=[.!?])\s+', full_text)
            estimated = []
            duration_per_char = 0.06  # rough estimate
            current_time = 0.0
            for sent in sentences:
                if sent.strip():
                    estimated.append({
                        "text": sent.strip(),
                        "start": current_time,
                        "end": current_time + len(sent) * duration_per_char,
                    })
                    current_time += len(sent) * duration_per_char + 0.3
            return estimated

        # Group by sentence boundaries
        import re
        chunks = []
        current_words = []
        current_start = None

        for wt in word_timestamps:
            word = wt.get("word", wt.get("text", ""))
            start = wt.get("start", wt.get("start_time", 0))
            end = wt.get("end", wt.get("end_time", 0))

            if current_start is None:
                current_start = start
            current_words.append(word)

            if re.search(r'[.!?]$', word):
                chunks.append({
                    "text": " ".join(current_words),
                    "start": current_start,
                    "end": end,
                })
                current_words = []
                current_start = None

        if current_words:
            chunks.append({
                "text": " ".join(current_words),
                "start": current_start or 0,
                "end": word_timestamps[-1].get("end", word_timestamps[-1].get("end_time", 0)),
            })

        return chunks

    # ------------------------------------------------------------------
    # Video generation
    # ------------------------------------------------------------------

    async def generate_video(
        self,
        model: str,
        prompt: str,
        duration: int = 5,
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a video and return the local file path."""
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = ASSETS_DIR / "video"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"generated_video_{_safe_id(prompt)}.mp4"

        try:
            result = await self._run_model(model, {
                "prompt": prompt,
                "duration": duration,
            })

            if result:
                url = result if isinstance(result, str) else (
                    result.get("video") or result.get("output") if isinstance(result, dict) else str(result)
                )
                if url:
                    await self._download(url, output_path)
                    logger.info("Video generated: %s", output_path)
                    return str(output_path)
        except Exception as e:
            logger.error("Video generation failed: %s", e)

        return None

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    async def generate_image(
        self,
        model: str,
        prompt: str,
        aspect_ratio: str = "16:9",
        safety_filter_level: str = "block_medium_and_above",
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """Generate an image and return the local file path."""
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = ASSETS_DIR / "images"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"generated_image_{_safe_id(prompt)}.png"

        try:
            result = await self._run_model(model, {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "safety_filter_level": safety_filter_level,
                "number_of_images": 1,
                "output_format": "png",
            })

            if result:
                url = None
                if isinstance(result, str):
                    url = result
                elif isinstance(result, list) and len(result) > 0:
                    url = str(result[0])
                elif isinstance(result, dict):
                    url = result.get("image") or result.get("output")
                else:
                    url = str(result)
                if url:
                    await self._download(url, output_path)
                    logger.info("Image generated: %s", output_path)
                    return str(output_path)
        except Exception as e:
            logger.error("Image generation failed: %s", e)

        return None

    # ------------------------------------------------------------------
    # Core Replicate call
    # ------------------------------------------------------------------

    async def _run_model(self, model: str, input_params: dict) -> Any:
        if not self._replicate:
            logger.error("Replicate client not available")
            return None

        logger.info("Replicate: running %s", model)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._replicate.run(model, input=input_params),
        )
        return result

    # ------------------------------------------------------------------
    # File download
    # ------------------------------------------------------------------

    async def _download(self, url: Any, output_path: Path):
        url_str = str(url)
        if not url_str.startswith("http"):
            logger.warning("Not a URL, skipping download: %s", url_str)
            return

        logger.info("Downloading %s → %s", url_str[:80], output_path)
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url_str) as resp:
                if resp.status == 200:
                    with open(output_path, "wb") as f:
                        while True:
                            chunk = await resp.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                else:
                    logger.error("Download failed (%d): %s", resp.status, url_str)


def _replicate_result_to_audio_url(result: Any) -> Optional[str]:
    """Normalize Replicate output to an http(s) URL for _download."""
    if result is None:
        return None
    if isinstance(result, str) and result.startswith("http"):
        return result
    if isinstance(result, (list, tuple)) and result:
        u = str(result[0])
        return u if u.startswith("http") else None
    if isinstance(result, dict):
        for key in ("audio", "output", "waveform", "url"):
            v = result.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v
        for v in result.values():
            if isinstance(v, str) and v.startswith("http"):
                return v
    u = str(result)
    return u if u.startswith("http") else None


def _safe_id(text: str) -> str:
    import re
    clean = re.sub(r"[^\w]", "_", text.lower())[:40]
    import hashlib
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"{clean}_{h}"
