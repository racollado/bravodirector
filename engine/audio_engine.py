"""
Audio Engine — multi-layer audio playback using pygame.mixer.

Supports three named layers (main, music, sfx) with independent:
  - Play / Stop / Pause / Resume
  - Looping (indefinite until stopped)
  - Volume (linear gain, including >1 via sample boost or pydub)
  - Speed and pitch via numpy/scipy resampling (no librosa/numba — avoids LLVM build issues), then pygame
  - Smooth volume fading (0–1 linear gain range on the mixer channel)

Video/media audio in TouchDesigner is separate (OSC /media); this engine owns Python-played clips only.
"""

import logging
import math
import os
import threading
import time
from io import BytesIO
from typing import Any, Callable, Optional, Tuple

import pygame

logger = logging.getLogger(__name__)

# Pygame/SDL output buffer in sample frames. Small buffers (~1024) keep latency low but
# increase dropouts when Python's GIL/event loop stalls (async generation, etc.) — common
# as clicks/pops on USB interfaces. Override with BRAVO_AUDIO_BUFFER (e.g. 2048, 4096).
_DEFAULT_MIXER_BUFFER = 4096
_MIXER_BUFFER = int(os.environ.get("BRAVO_AUDIO_BUFFER", str(_DEFAULT_MIXER_BUFFER)))

LAYER_CHANNELS = {"main": 0, "music": 1, "sfx": 2}
MAX_CHANNELS = 8

# Linear amplitude gain: 1 = unity, 10 ≈ +20 dB (20*log10(10)). Used by play() and set_volume().
LINEAR_GAIN_MAX = 10.0

# Reasonable bounds for effect multipliers (avoid extreme CPU / NaNs)
SPEED_MULT_MIN = 0.05
SPEED_MULT_MAX = 20.0
PITCH_MULT_MIN = 0.25
PITCH_MULT_MAX = 4.0


def _sound_from_file_with_linear_gain(filepath: str, linear_gain: float):
    """
    Decode audio with pydub, apply linear gain (>1), return pygame.mixer.Sound.
    Falls back to loading the file without boost if pydub/ffmpeg fails.
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        logger.warning("pydub not installed — cannot apply gain > 1; install pydub (and ffmpeg for mp3)")
        return None, False

    try:
        seg = AudioSegment.from_file(filepath)
        db = 20.0 * math.log10(linear_gain)
        boosted = seg.apply_gain(db)
        buf = BytesIO()
        boosted.export(buf, format="wav")
        buf.seek(0)
        return pygame.mixer.Sound(file=buf), True
    except Exception as e:
        logger.warning("Gain boost failed (%s); playing source file without DSP boost", e)
        return None, False


def _load_mono_float(filepath: str) -> Optional[Tuple[Any, int]]:
    """Load file to mono float64 ~[-1, 1] and sample rate. soundfile first, then pydub."""
    import numpy as np

    try:
        import soundfile as sf

        y, sr = sf.read(filepath, always_2d=False)
        if y.size == 0:
            return None
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        y = np.asarray(y, dtype=np.float64)
        peak = float(np.max(np.abs(y))) if y.size else 0.0
        if peak > 1.01:
            y = y / 32768.0 if peak > 100.0 else (y / peak if peak > 0 else y)
        y = np.clip(y, -1.0, 1.0)
        return y, int(sr)
    except Exception as e:
        logger.debug("soundfile load failed (%s), trying pydub", e)

    try:
        from pydub import AudioSegment

        seg = AudioSegment.from_file(filepath)
        sr = int(seg.frame_rate)
        raw = np.array(seg.get_array_of_samples(), dtype=np.float64)
        if seg.channels > 1:
            raw = raw.reshape((-1, seg.channels)).mean(axis=1)
        y = raw / float(1 << (8 * seg.sample_width - 1))
        return np.clip(y, -1.0, 1.0), sr
    except Exception as e:
        logger.error("Could not load audio for DSP: %s", e)
        return None


def _pitch_shift_resample(y: Any, pitch_mult: float) -> Any:
    """Length-preserving pitch change via two-step scipy resample (cheap vs phase vocoder)."""
    import numpy as np
    from scipy import signal

    P = float(max(PITCH_MULT_MIN, min(PITCH_MULT_MAX, pitch_mult)))
    if abs(P - 1.0) < 1e-9:
        return y
    n = int(y.shape[0])
    if n < 2:
        return y
    mid = max(1, int(round(n / P)))
    y1 = signal.resample(y, mid)
    return signal.resample(y1, n)


def _effects_numpy_from_file(filepath: str, speed_mult: float, pitch_mult: float) -> Optional[Tuple[Any, int]]:
    """
    Load audio and apply pitch then playback speed (scipy.signal.resample).
    speed_mult: 1 = normal, 2 = half as many samples = twice as fast.
    pitch_mult: frequency multiplier (1 = normal); uses two-step resample to keep duration.
    Returns (y_mono_float64, sr) or None on failure.
    """
    try:
        import numpy as np
        from scipy import signal
    except ImportError:
        logger.warning("numpy/scipy not available for speed/pitch DSP")
        return None

    loaded = _load_mono_float(filepath)
    if loaded is None:
        return None
    y, sr = loaded
    if y.size == 0:
        return None

    sm = float(max(SPEED_MULT_MIN, min(SPEED_MULT_MAX, speed_mult)))
    pm = float(max(PITCH_MULT_MIN, min(PITCH_MULT_MAX, pitch_mult)))

    try:
        if abs(pm - 1.0) > 1e-6:
            y = _pitch_shift_resample(y, pm)
        if abs(sm - 1.0) > 1e-6:
            new_len = max(1, int(round(len(y) / sm)))
            y = signal.resample(y, new_len)
        y = np.clip(np.asarray(y, dtype=np.float64), -1.0, 1.0)
        return y, sr
    except Exception as e:
        logger.error("scipy DSP failed: %s", e)
        return None


def _numpy_to_pygame_sound(y: Any, sr: int, linear_gain: float) -> Tuple[pygame.mixer.Sound, float]:
    """Build Sound from float mono array. Bakes linear_gain > 1 into samples; else uses channel volume."""
    import numpy as np
    import soundfile as sf

    lg = float(max(0.0, min(LINEAR_GAIN_MAX, linear_gain)))
    if lg <= 1.0:
        y_out = np.clip(y.astype(np.float64, copy=False), -1.0, 1.0)
        buf = BytesIO()
        sf.write(buf, y_out, sr, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return pygame.mixer.Sound(file=buf), lg

    y_out = np.clip(y.astype(np.float64, copy=False) * lg, -1.0, 1.0)
    buf = BytesIO()
    sf.write(buf, y_out, sr, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return pygame.mixer.Sound(file=buf), 1.0


def _build_sound(
    filepath: str, linear_gain: float, speed_mult: float, pitch_mult: float
) -> Tuple[pygame.mixer.Sound, float]:
    """
    Returns (Sound, pygame_channel_volume).
    When linear_gain <= 1 and no speed/pitch, may use fast pygame load.
    """
    lg = float(max(0.0, min(LINEAR_GAIN_MAX, linear_gain)))
    sm = float(max(SPEED_MULT_MIN, min(SPEED_MULT_MAX, speed_mult)))
    pm = float(max(PITCH_MULT_MIN, min(PITCH_MULT_MAX, pitch_mult)))

    need_fx = abs(sm - 1.0) > 1e-6 or abs(pm - 1.0) > 1e-6

    if not need_fx and lg <= 1.0:
        sound = pygame.mixer.Sound(filepath)
        return sound, lg

    if not need_fx and lg > 1.0:
        sound, boosted = _sound_from_file_with_linear_gain(filepath, lg)
        if sound is not None:
            return sound, 1.0 if boosted else min(1.0, lg)
        return pygame.mixer.Sound(filepath), min(1.0, lg)

    arr = _effects_numpy_from_file(filepath, sm, pm)
    if arr is None:
        logger.warning("Falling back to unpitched playback for %s", filepath)
        return _build_sound(filepath, lg, 1.0, 1.0)

    y, sr = arr
    return _numpy_to_pygame_sound(y, sr, lg)


class AudioEngine:
    def __init__(self):
        self._initialized = False
        self._layers: dict[str, dict] = {}
        self._voice_callback: Optional[Callable] = None
        self._voice_monitor_thread: Optional[threading.Thread] = None
        self._init_pygame()

    def _init_pygame(self):
        try:
            pygame.mixer.pre_init(
                frequency=44100, size=-16, channels=2, buffer=max(512, _MIXER_BUFFER)
            )
            pygame.mixer.init()
            pygame.mixer.set_num_channels(MAX_CHANNELS)
            self._initialized = True

            for name, ch_id in LAYER_CHANNELS.items():
                self._layers[name] = {
                    "channel": pygame.mixer.Channel(ch_id),
                    "file": None,
                    "playing": False,
                    "paused": False,
                    "loop": False,
                    "volume": 1.0,
                    "linear_gain": 1.0,
                    "speed_mult": 1.0,
                    "pitch_mult": 1.0,
                }
            logger.info(
                "AudioEngine initialized with %d layers (pygame buffer=%d samples)",
                len(LAYER_CHANNELS),
                max(512, _MIXER_BUFFER),
            )
        except Exception as e:
            logger.error("Failed to initialize pygame.mixer: %s", e)
            self._initialized = False

    def play(self, layer: str, filepath: str, loop: bool = False, volume: float = 1.0):
        """Play a file. Resets speed/pitch to 1.0 for a fresh clip (new ``play_audio`` action)."""
        self._play_layer(layer, filepath, loop, volume, reset_rate_dsp=True)

    def _play_layer(self, layer: str, filepath: str, loop: bool, linear_gain: float, reset_rate_dsp: bool):
        if not self._initialized or layer not in self._layers:
            return

        info = self._layers[layer]
        try:
            if reset_rate_dsp:
                info["speed_mult"] = 1.0
                info["pitch_mult"] = 1.0

            loops = -1 if loop else 0
            lg = max(0.0, min(LINEAR_GAIN_MAX, float(linear_gain)))
            sm = float(info.get("speed_mult", 1.0))
            pm = float(info.get("pitch_mult", 1.0))

            sound, pygame_vol = _build_sound(filepath, lg, sm, pm)

            info["volume"] = pygame_vol
            info["linear_gain"] = lg
            info["channel"].play(sound, loops=loops)
            info["channel"].set_volume(pygame_vol)
            info["file"] = filepath
            info["playing"] = True
            info["paused"] = False
            info["loop"] = loop

            logger.info(
                "Audio layer '%s': playing '%s' (loop=%s) gain=%.2f speed=%.3f pitch=%.3f ch_vol=%.2f",
                layer,
                filepath,
                loop,
                lg,
                sm,
                pm,
                pygame_vol,
            )
        except Exception as e:
            logger.error("Audio play failed on layer '%s': %s", layer, e)

    def _rebuild_playback(self, layer: str):
        """Re-decode and play the current file with updated DSP / gain (restarts from beginning)."""
        info = self._layers.get(layer)
        if not info:
            return
        fp = info.get("file")
        if not fp:
            logger.warning("_rebuild_playback: no active file on layer '%s'", layer)
            return
        self._play_layer(layer, fp, bool(info.get("loop")), float(info.get("linear_gain", 1.0)), reset_rate_dsp=False)

    def stop_layer(self, layer: str):
        if layer not in self._layers:
            return
        info = self._layers[layer]
        info["channel"].stop()
        info["playing"] = False
        info["paused"] = False
        info["file"] = None
        info["volume"] = 1.0
        info["linear_gain"] = 1.0
        info["speed_mult"] = 1.0
        info["pitch_mult"] = 1.0
        logger.info("Audio layer '%s': stopped", layer)

    def stop_all(self):
        for layer in self._layers:
            self.stop_layer(layer)

    def pause_layer(self, layer: str):
        if layer not in self._layers:
            return
        info = self._layers[layer]
        if info["playing"] and not info["paused"]:
            info["channel"].pause()
            info["paused"] = True
            logger.info("Audio layer '%s': paused", layer)

    def pause_all(self):
        for layer in self._layers:
            self.pause_layer(layer)

    def resume_layer(self, layer: str):
        if layer not in self._layers:
            return
        info = self._layers[layer]
        if info["paused"]:
            info["channel"].unpause()
            info["paused"] = False
            logger.info("Audio layer '%s': resumed", layer)

    def resume_all(self):
        for layer in self._layers:
            self.resume_layer(layer)

    def set_speed(self, layer: str, speed_mult: float, duration: float = 0):
        """
        Playback rate (1 = normal, 2 = twice as fast). Processed with librosa time_stretch;
        **restarts** the current clip from the beginning. ``duration`` is reserved for future ramps.
        """
        if duration and duration > 0:
            logger.info("set_speed: duration ramp not implemented; applying immediately")
        if layer not in self._layers:
            return
        sm = float(max(SPEED_MULT_MIN, min(SPEED_MULT_MAX, speed_mult)))
        self._layers[layer]["speed_mult"] = sm
        self._rebuild_playback(layer)

    def set_pitch(self, layer: str, pitch_mult: float, duration: float = 0):
        """
        Frequency multiplier (1 = normal, 2 ≈ +1 octave). Processed with scipy two-step resample;
        **restarts** the current clip from the beginning.
        """
        if duration and duration > 0:
            logger.info("set_pitch: duration ramp not implemented; applying immediately")
        if layer not in self._layers:
            return
        pm = float(max(PITCH_MULT_MIN, min(PITCH_MULT_MAX, pitch_mult)))
        self._layers[layer]["pitch_mult"] = pm
        self._rebuild_playback(layer)

    def set_volume(self, layer: str, volume: float, duration: float = 0):
        """Set output level as **linear gain**: 0 = silent, 1 = unity, up to ~10 (+20 dB).

        Same convention as ``play(..., volume=...)``. For gains in (0, 1], only pygame channel
        level changes when the buffer was built at unity; re-render for gain > 1.
        Smooth fades only apply when both endpoints are ≤ 1.0.
        """
        if layer not in self._layers:
            return
        info = self._layers[layer]
        target = max(0.0, min(LINEAR_GAIN_MAX, float(volume)))
        start_lg = float(info.get("linear_gain", info["volume"]))

        if duration > 0 and max(start_lg, target) <= 1.0:
            threading.Thread(
                target=self._fade_volume,
                args=(layer, start_lg, target, duration),
                daemon=True,
            ).start()
            return

        if duration > 0 and max(start_lg, target) > 1.0:
            logger.warning(
                "Volume fade not supported when linear gain exceeds 1.0 (start=%.3f end=%.3f); applying instantly",
                start_lg,
                target,
            )

        self._apply_linear_gain(layer, target)

    def _apply_linear_gain(self, layer: str, linear_gain: float):
        if layer not in self._layers:
            return
        info = self._layers[layer]
        lg = max(0.0, min(LINEAR_GAIN_MAX, float(linear_gain)))

        if lg <= 1.0:
            info["linear_gain"] = lg
            info["volume"] = lg
            info["channel"].set_volume(lg)
            return

        fp = info.get("file")
        loop = bool(info.get("loop", False))
        if not fp:
            logger.warning(
                "set_volume: boost above unity (%.2f) needs an active clip on layer '%s'; clamping to 1.0",
                lg,
                layer,
            )
            info["channel"].set_volume(1.0)
            info["linear_gain"] = 1.0
            return

        self._play_layer(layer, fp, loop=loop, linear_gain=lg, reset_rate_dsp=False)

    def fade_out(self, layer: str, duration: float = 2.0):
        self.set_volume(layer, 0.0, duration)
        threading.Timer(duration + 0.1, lambda: self.stop_layer(layer)).start()

    def fade_in(self, layer: str, duration: float = 2.0):
        self.set_volume(layer, 1.0, duration)

    def _fade_volume(self, layer: str, start: float, end: float, duration: float):
        info = self._layers.get(layer)
        if not info:
            return
        steps = max(1, int(duration * 30))
        step_time = duration / steps
        for i in range(steps + 1):
            t = i / steps
            lg = start + (end - start) * t
            info["channel"].set_volume(lg)
            info["linear_gain"] = lg
            info["volume"] = lg
            time.sleep(step_time)

    def is_playing(self, layer: str) -> bool:
        if layer not in self._layers:
            return False
        info = self._layers[layer]
        if info["paused"]:
            return True
        if info["playing"]:
            busy = info["channel"].get_busy()
            if not busy:
                info["playing"] = False
            return busy
        return False

    # ------------------------------------------------------------------
    # Voice onset detection (RMS monitor)
    # ------------------------------------------------------------------

    def wait_for_voice(self, callback: Callable, threshold: float = 0.01):
        """Monitor mic for voice onset above threshold, then fire callback."""
        self._voice_callback = callback
        self._voice_monitor_thread = threading.Thread(
            target=self._monitor_voice, args=(threshold,), daemon=True
        )
        self._voice_monitor_thread.start()

    def cancel_voice_wait(self):
        self._voice_callback = None

    def _monitor_voice(self, threshold: float):
        try:
            import pyaudio
            import struct
            import math

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )

            while self._voice_callback:
                data = stream.read(1024, exception_on_overflow=False)
                samples = struct.unpack(f"<{len(data)//2}h", data)
                rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
                if rms > threshold:
                    cb = self._voice_callback
                    self._voice_callback = None
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    if cb:
                        cb()
                    return

            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            logger.error("Voice monitor error: %s", e)

    # ------------------------------------------------------------------
    # State for WebSocket
    # ------------------------------------------------------------------

    def get_layer_states(self) -> dict:
        states = {}
        for name, info in self._layers.items():
            states[name] = {
                "playing": self.is_playing(name),
                "paused": info["paused"],
                "file": info["file"],
                "loop": info["loop"],
                "volume": info["volume"],
                "linear_gain": info.get("linear_gain", info["volume"]),
                "speed_mult": info.get("speed_mult", 1.0),
                "pitch_mult": info.get("pitch_mult", 1.0),
            }
        return states
