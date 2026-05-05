"""
Caption Handler — manages caption display logic and modes.

Two modes:
  - advance_on_cue: Caption stays visible, replaced when next step triggers
  - clear_then_voice: After end-of-line detected, wait clear_delay seconds,
    clear caption, then show next caption on voice onset
"""

import logging
from typing import Optional

from engine.osc_client import OSCClient

logger = logging.getLogger(__name__)


class CaptionHandler:
    def __init__(self, osc: OSCClient):
        self._osc = osc
        self._current_text: str = ""
        self._current_color: str = "#ffffff"

    def display(self, step, caption_override: Optional[dict] = None) -> None:
        """Display caption from a StepData object.

        If caption_override is set (e.g. task-resolved text), it is used instead of step.caption.
        """
        cap = caption_override if caption_override is not None else step.caption
        if not cap:
            return
        if not cap.get("display", True):
            return

        text = cap.get("text", "")
        color = cap.get("color", "#ffffff")

        if step.is_ai_generated:
            color = cap.get("color", "#ff4444")

        self._current_text = text
        self._current_color = color
        self._osc.send_caption(text, color)
        logger.debug("Caption displayed: '%s' [%s]", text[:60], color)

    def display_raw(self, text: str, color: str = "#ffffff"):
        self._current_text = text
        self._current_color = color
        self._osc.send_caption(text, color)

    def clear(self):
        self._current_text = ""
        self._osc.clear_caption()
        logger.debug("Caption cleared")

    @property
    def current_text(self) -> str:
        return self._current_text

    @property
    def current_color(self) -> str:
        return self._current_color
