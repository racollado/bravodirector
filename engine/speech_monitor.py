"""
Speech Monitor — manages real-time AssemblyAI streaming transcription.

Wraps the mic stream in a pausable generator that yields silence bytes when paused,
keeping the WebSocket alive without triggering transcription.
"""

import logging
import math
import struct
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_LEVEL_CB_INTERVAL_S = 0.08


def _pcm16_mono_rms_level(chunk: bytes) -> float:
    """Map RMS of int16 mono PCM to ~0..1 for UI metering."""
    if not chunk or len(chunk) < 2:
        return 0.0
    n = len(chunk) // 2
    if n == 0:
        return 0.0
    try:
        samples = struct.unpack(f"{n}h", chunk[: n * 2])
    except struct.error:
        return 0.0
    acc = sum(s * s for s in samples)
    rms = math.sqrt(acc / n)
    return min(1.0, rms / 6000.0)


class SpeechMonitor:
    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None
        self._stream_thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._transcript_callback: Optional[Callable] = None
        self._level_callback: Optional[Callable[[float], None]] = None
        self._level_lock = threading.Lock()
        self._mic_level = 0.0

    def set_transcript_callback(self, callback: Callable):
        """Set callback: fn(text: str, is_final: bool)"""
        self._transcript_callback = callback

    def set_level_callback(self, callback: Optional[Callable[[float], None]]):
        """Optional callback invoked ~10Hz with mic level 0..1 (same audio sent to AssemblyAI)."""
        self._level_callback = callback

    def get_mic_level(self) -> float:
        with self._level_lock:
            return self._mic_level

    def is_streaming(self) -> bool:
        return self._running

    def _set_mic_level(self, level: float):
        with self._level_lock:
            self._mic_level = level

    def start(self):
        if self._running:
            return
        self._running = True
        self._paused = False
        self._stream_thread = threading.Thread(target=self._run_stream, daemon=True)
        self._stream_thread.start()
        logger.info("Speech monitoring started")

    def stop(self):
        self._running = False
        if self._client:
            try:
                self._client.disconnect(terminate=True)
            except Exception:
                pass
        self._client = None
        self._set_mic_level(0.0)
        if self._level_callback:
            try:
                self._level_callback(0.0)
            except Exception:
                pass
        logger.info("Speech monitoring stopped")

    def pause(self):
        self._paused = True
        logger.info("Speech monitoring paused (sending silence)")

    def resume(self):
        self._paused = False
        logger.info("Speech monitoring resumed")

    def _run_stream(self):
        try:
            import assemblyai as aai
            from assemblyai.streaming.v3 import (
                StreamingClient,
                StreamingClientOptions,
                StreamingEvents,
                StreamingParameters,
                TurnEvent,
                BeginEvent,
                TerminationEvent,
                StreamingError,
            )

            import os
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

            self._client = StreamingClient(
                StreamingClientOptions(
                    api_key=self._api_key,
                    api_host="streaming.assemblyai.com",
                )
            )

            def on_begin(client, event: BeginEvent):
                logger.info("AssemblyAI session started: %s", event.id)

            def on_turn(client, event: TurnEvent):
                if self._transcript_callback:
                    self._transcript_callback(event.transcript, event.end_of_turn)

            def on_terminated(client, event: TerminationEvent):
                logger.info("AssemblyAI session terminated: %.1fs processed", event.audio_duration_seconds)

            def on_error(client, error: StreamingError):
                logger.error("AssemblyAI error: %s", error)

            self._client.on(StreamingEvents.Begin, on_begin)
            self._client.on(StreamingEvents.Turn, on_turn)
            self._client.on(StreamingEvents.Termination, on_terminated)
            self._client.on(StreamingEvents.Error, on_error)

            self._client.connect(
                StreamingParameters(
                    sample_rate=16000,
                    format_turns=True,
                    speech_model="universal-streaming-english",
                )
            )

            mic_stream = aai.extras.MicrophoneStream(sample_rate=16000)
            self._client.stream(self._pausable_stream(mic_stream))

        except Exception as e:
            logger.error("Speech monitor stream error: %s", e)
        finally:
            self._running = False
            self._set_mic_level(0.0)
            if self._level_callback:
                try:
                    self._level_callback(0.0)
                except Exception:
                    pass

    def _pausable_stream(self, mic_stream):
        """Wrap mic stream to yield silence when paused; meter raw (pre-pause) input level."""
        last_level_cb = 0.0
        for chunk in mic_stream:
            if not self._running:
                break
            raw = chunk
            if self._paused:
                out = b"\x00" * len(chunk)
            else:
                out = chunk
            level = _pcm16_mono_rms_level(raw)
            self._set_mic_level(level)
            if self._level_callback:
                now = time.monotonic()
                if now - last_level_cb >= _LEVEL_CB_INTERVAL_S:
                    last_level_cb = now
                    try:
                        self._level_callback(level)
                    except Exception:
                        pass
            yield out
