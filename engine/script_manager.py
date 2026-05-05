"""
Script Manager — loads the show JSON, tracks position, handles AI injection and navigation.

Responsibilities:
  - Parse and validate the show JSON
  - Flatten segments into an ordered step list
  - Track current step position
  - Inject AI-generated content (per_sentence, per_line, tts_driven, timed_sequence)
  - Navigate backward to the last authored step, wiping injected content
  - Provide step data for the performer view
"""

import json
import re
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class StepData:
    """Unified representation of a single show step."""
    id: str
    segment_id: str
    segment_name: str
    index: int  # position in the flattened list

    trigger: dict = field(default_factory=dict)
    caption: Optional[dict] = None
    actions: list = field(default_factory=list)
    overlays: list = field(default_factory=list)
    performer: Optional[dict] = None
    mode: Optional[str] = None  # "timed_sequence" or None for normal steps
    audio: Optional[dict] = None  # for timed_sequence mode
    sequence: Optional[list] = None  # for timed_sequence mode

    is_authored: bool = True
    is_ai_generated: bool = False
    parent_step_id: Optional[str] = None  # authored step that spawned this injection


class ScriptManager:
    def __init__(self, script_path: str):
        self._script_path = script_path
        self._raw: dict = {}
        self._settings: dict = {}
        self._steps: list[StepData] = []
        self._current_index: int = 0

        self._load_script()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_script(self):
        with open(self._script_path, "r") as f:
            self._raw = json.load(f)

        self._settings = self._raw.get("settings", {})
        self._steps = self._flatten_segments(self._raw.get("segments", []))
        self._current_index = 0
        logger.info(
            "Script loaded: '%s' — %d steps across %d segments",
            self._raw.get("title", "Untitled"),
            len(self._steps),
            len(self._raw.get("segments", [])),
        )

    def _flatten_segments(self, segments: list[dict]) -> list[StepData]:
        steps: list[StepData] = []
        for seg in segments:
            seg_id = seg.get("id", "unknown")
            seg_name = seg.get("name", "")
            for raw_step in seg.get("steps", []):
                sd = StepData(
                    id=raw_step.get("id", f"step_{len(steps)}"),
                    segment_id=seg_id,
                    segment_name=seg_name,
                    index=len(steps),
                    trigger=raw_step.get("trigger", {"type": "auto"}),
                    caption=raw_step.get("caption"),
                    actions=raw_step.get("actions", []),
                    overlays=raw_step.get("overlays", []),
                    performer=raw_step.get("performer"),
                    mode=raw_step.get("mode"),
                    audio=raw_step.get("audio"),
                    sequence=raw_step.get("sequence"),
                    is_authored=True,
                    is_ai_generated=False,
                )
                steps.append(sd)
        return steps

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @property
    def current_step(self) -> Optional[StepData]:
        if 0 <= self._current_index < len(self._steps):
            return self._steps[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total_steps(self) -> int:
        return len(self._steps)

    def get_step(self, index: int) -> Optional[StepData]:
        if 0 <= index < len(self._steps):
            return self._steps[index]
        return None

    def get_step_by_id(self, step_id: str) -> Optional[StepData]:
        for s in self._steps:
            if s.id == step_id:
                return s
        return None

    def advance(self) -> Optional[StepData]:
        """Move to the next step. Returns the new current step or None."""
        if self._current_index + 1 < len(self._steps):
            self._current_index += 1
            return self.current_step
        return None

    def set_index(self, index: int):
        if 0 <= index < len(self._steps):
            self._current_index = index

    def go_back(self) -> Optional[StepData]:
        """Go back to the previous authored step, wiping injected content in between."""
        target = self._current_index - 1
        while target >= 0:
            if self._steps[target].is_authored:
                break
            target -= 1
        if target < 0:
            return self.current_step

        self._wipe_injected_after(target)
        self._current_index = target
        logger.info("Navigated back to authored step '%s' (index %d)", self._steps[target].id, target)
        return self.current_step

    def _wipe_injected_after(self, authored_index: int):
        """Remove all AI-injected steps that follow `authored_index` up to the
        next authored step (or end of list)."""
        remove_start = authored_index + 1
        remove_end = remove_start
        while remove_end < len(self._steps) and not self._steps[remove_end].is_authored:
            remove_end += 1
        if remove_end > remove_start:
            count = remove_end - remove_start
            del self._steps[remove_start:remove_end]
            self._reindex()
            logger.info("Wiped %d injected steps after index %d", count, authored_index)

    def _reindex(self):
        for i, step in enumerate(self._steps):
            step.index = i

    # ------------------------------------------------------------------
    # Upcoming steps for performer view
    # ------------------------------------------------------------------

    def get_upcoming(self, count: int = 8) -> list[StepData]:
        start = self._current_index + 1
        return self._steps[start : start + count]

    # ------------------------------------------------------------------
    # AI Content Injection
    # ------------------------------------------------------------------

    def inject_sentences(
        self,
        after_index: int,
        sentences: list[str],
        caption_color: str = "#ff4444",
        trigger_mode: str = "speech",
        overlay: Optional[dict] = None,
        parent_step_id: Optional[str] = None,
    ) -> list[StepData]:
        """Insert AI-generated sentences as individual speech-triggered steps."""
        new_steps: list[StepData] = []
        cue_words = self._settings.get("speech", {}).get("default_cue_words", 4)
        confidence = self._settings.get("speech", {}).get("default_confidence", 0.85)

        for i, sentence in enumerate(sentences):
            cue_phrase = self._extract_tail_cue(sentence, cue_words)
            step_id = f"{parent_step_id or 'ai'}__injected_{i}"
            sd = StepData(
                id=step_id,
                segment_id=self._steps[after_index].segment_id if after_index < len(self._steps) else "injected",
                segment_name=self._steps[after_index].segment_name if after_index < len(self._steps) else "",
                index=0,
                trigger={
                    "type": trigger_mode,
                    "phrase": cue_phrase,
                    "confidence": confidence,
                } if trigger_mode == "speech" else {"type": "auto"},
                caption={
                    "text": sentence,
                    "color": caption_color,
                    "mode": "advance_on_cue",
                    "display": True,
                },
                actions=[],
                overlays=[{"type": "show_image", **overlay}] if overlay and i == 0 else [],
                is_authored=False,
                is_ai_generated=True,
                parent_step_id=parent_step_id,
            )
            new_steps.append(sd)

        insert_at = after_index + 1
        self._steps[insert_at:insert_at] = new_steps
        self._reindex()
        logger.info("Injected %d sentence steps after index %d", len(new_steps), after_index)
        return new_steps

    def inject_lines(
        self,
        after_index: int,
        lines: list[str],
        caption_color: str = "#00ffcc",
        trigger_mode: str = "speech",
        parent_step_id: Optional[str] = None,
    ) -> list[StepData]:
        """Insert AI-generated lines (e.g. rap lyrics) as individual steps."""
        return self.inject_sentences(
            after_index=after_index,
            sentences=lines,
            caption_color=caption_color,
            trigger_mode=trigger_mode,
            parent_step_id=parent_step_id,
        )

    def inject_tts_driven(
        self,
        after_index: int,
        words_with_timestamps: list[dict],
        caption_color: str = "#88ccff",
        parent_step_id: Optional[str] = None,
    ) -> list[StepData]:
        """Insert steps driven by TTS word-level timestamps.
        Each entry: {"text": "sentence...", "start": 0.0, "end": 2.5}
        The runtime will use timer-based triggers synchronized to TTS playback."""
        new_steps: list[StepData] = []
        for i, chunk in enumerate(words_with_timestamps):
            step_id = f"{parent_step_id or 'tts'}__tts_{i}"
            sd = StepData(
                id=step_id,
                segment_id=self._steps[after_index].segment_id if after_index < len(self._steps) else "injected",
                segment_name=self._steps[after_index].segment_name if after_index < len(self._steps) else "",
                index=0,
                trigger={
                    "type": "timer",
                    "duration": chunk["start"],
                    "_tts_driven": True,
                },
                caption={
                    "text": chunk["text"],
                    "color": caption_color,
                    "mode": "advance_on_cue",
                    "display": True,
                },
                actions=[],
                is_authored=False,
                is_ai_generated=True,
                parent_step_id=parent_step_id,
            )
            new_steps.append(sd)

        insert_at = after_index + 1
        self._steps[insert_at:insert_at] = new_steps
        self._reindex()
        logger.info("Injected %d TTS-driven steps after index %d", len(new_steps), after_index)
        return new_steps

    # ------------------------------------------------------------------
    # Cue extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tail_cue(text: str, num_words: int = 4) -> str:
        words = re.sub(r"[^\w\s]", "", text).strip().split()
        return " ".join(words[-num_words:]).lower() if len(words) >= num_words else " ".join(words).lower()

    # ------------------------------------------------------------------
    # Cue list (for CueDetector registration)
    # ------------------------------------------------------------------

    def get_all_cue_phrases(self) -> list[dict]:
        cues = []
        for step in self._steps:
            if step.trigger.get("type") == "speech" and step.trigger.get("phrase"):
                cues.append({
                    "phrase": step.trigger["phrase"],
                    "step_index": step.index,
                    "confidence": step.trigger.get("confidence", 0.85),
                })
        return cues

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self):
        """Reload the script from disk, wiping all injected content."""
        self._load_script()
        logger.info("Script reset from disk")

    # ------------------------------------------------------------------
    # Settings access
    # ------------------------------------------------------------------

    @property
    def settings(self) -> dict:
        return self._settings

    @property
    def title(self) -> str:
        return self._raw.get("title", "Untitled Show")

    # ------------------------------------------------------------------
    # Serialization (for WebSocket state)
    # ------------------------------------------------------------------

    @staticmethod
    def step_to_dict(step: Optional[StepData]) -> Optional[dict]:
        if step is None:
            return None
        return {
            "id": step.id,
            "index": step.index,
            "segment_id": step.segment_id,
            "segment_name": step.segment_name,
            "trigger": step.trigger,
            "caption": step.caption,
            "mode": step.mode,
            "is_authored": step.is_authored,
            "is_ai_generated": step.is_ai_generated,
            "performer": step.performer,
            "has_actions": len(step.actions) > 0,
        }

    @staticmethod
    def step_outline_dict(step: StepData) -> dict:
        """Compact step info for idle script picker (performer UI)."""
        cap = step.caption or {}
        text = (cap.get("text") or "").strip().replace("\n", " ")
        if len(text) > 180:
            text = text[:177] + "…"
        trig = step.trigger or {}
        phrase = (trig.get("phrase") or "").strip()
        return {
            "index": step.index,
            "id": step.id,
            "segment_name": step.segment_name or step.segment_id,
            "caption_preview": text,
            "trigger_type": trig.get("type", "auto"),
            "trigger_phrase": phrase or None,
        }

    def get_steps_outline(self) -> list[dict]:
        return [self.step_outline_dict(s) for s in self._steps]
