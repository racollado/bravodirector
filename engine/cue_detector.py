"""
Cue Detector — fuzzy-matches transcript text against expected cue phrases.

Strategy:
  - Only checks the NEXT untriggered cue (linear progression)
  - Normalizes text: strips punctuation, collapses whitespace, lowercases
  - Length ratio guard: transcript must be ≥75% as long as the cue phrase
  - Tail anchor: for phrases of 5+ words, requires the ending words to be present
  - Multi-strategy scoring: partial_ratio, token_set_ratio, token_sort_ratio
  - 1.5-second cooldown between triggers
  - Transcript buffer accumulates text but only keeps the last 150 words
"""

import re
import time
import logging
from typing import Callable, Optional

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class CueDetector:
    def __init__(self):
        self._cues: list[dict] = []  # {phrase, step_index, confidence_threshold, triggered}
        self._transcript_buffer: str = ""
        self._last_trigger_time: float = 0
        self._cooldown: float = 1.5
        self._callback: Optional[Callable] = None
        self._next_cue_idx: int = 0

    def set_cue_callback(self, callback: Callable):
        """Set callback: fn(step_index, phrase, confidence)"""
        self._callback = callback

    def add_cue(self, phrase: str, step_index: int, confidence_threshold: float = 0.85):
        self._cues.append({
            "phrase": self._normalize(phrase),
            "raw_phrase": phrase,
            "step_index": step_index,
            "confidence_threshold": confidence_threshold,
            "triggered": False,
        })

    def clear_all_cues(self):
        self._cues.clear()
        self._next_cue_idx = 0
        self._transcript_buffer = ""

    def mark_step_triggered(self, step_index: int):
        for cue in self._cues:
            if cue["step_index"] == step_index:
                cue["triggered"] = True
        self._advance_next_cue()

    def reset_transcript(self):
        self._transcript_buffer = ""

    def process_transcript(self, text: str, is_final: bool):
        if not text.strip():
            return

        self._transcript_buffer += " " + text.strip()
        words = self._transcript_buffer.split()
        if len(words) > 150:
            self._transcript_buffer = " ".join(words[-150:])

        self._check_next_cue()

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _check_next_cue(self):
        if self._next_cue_idx >= len(self._cues):
            return

        now = time.time()
        if now - self._last_trigger_time < self._cooldown:
            return

        cue = self._cues[self._next_cue_idx]
        if cue["triggered"]:
            self._advance_next_cue()
            return

        phrase = cue["phrase"]
        threshold = cue["confidence_threshold"]
        transcript = self._normalize(self._transcript_buffer)

        if not transcript or not phrase:
            return

        # Length guard
        if len(transcript) < len(phrase) * 0.75:
            return

        # Tail anchor for longer phrases
        phrase_words = phrase.split()
        if len(phrase_words) >= 5:
            tail = " ".join(phrase_words[-2:])
            if tail not in transcript:
                return

        score = self._multi_score(transcript, phrase)
        conf = score / 100.0

        if conf >= threshold:
            cue["triggered"] = True
            self._last_trigger_time = now
            self._transcript_buffer = ""
            self._advance_next_cue()

            logger.info(
                "Cue matched: '%s' → step_index=%d conf=%.2f",
                cue["raw_phrase"], cue["step_index"], conf,
            )
            if self._callback:
                self._callback(cue["step_index"], cue["raw_phrase"], conf)

    def _advance_next_cue(self):
        while self._next_cue_idx < len(self._cues) and self._cues[self._next_cue_idx]["triggered"]:
            self._next_cue_idx += 1

    @staticmethod
    def _multi_score(transcript: str, phrase: str) -> float:
        return max(
            fuzz.partial_ratio(phrase, transcript),
            fuzz.token_set_ratio(phrase, transcript),
            fuzz.token_sort_ratio(phrase, transcript),
        )

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
