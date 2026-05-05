"""
Timer Handler — manages countdown timers displayed in TouchDesigner.
"""

import asyncio
import logging
from typing import Optional

from engine.osc_client import OSCClient

logger = logging.getLogger(__name__)


class TimerHandler:
    def __init__(self, osc: OSCClient):
        self._osc = osc
        self.active_timer: Optional[asyncio.Task] = None
        self.remaining: float = 0
        self.total: float = 0

    async def start_countdown(self, duration: int, display: bool = True):
        """Blocking countdown that sends updates every second."""
        self.total = duration
        self.remaining = duration

        if display:
            self._osc.start_timer(duration)

        while self.remaining > 0:
            if display:
                self._osc.update_timer(int(self.remaining))
            await asyncio.sleep(1)
            self.remaining -= 1

        self.remaining = 0
        if display:
            self._osc.stop_timer()
        logger.info("Timer completed (%ds)", duration)

    def start_background(self, duration: int, loop: asyncio.AbstractEventLoop, display: bool = True):
        """Non-blocking: run the countdown as a background task."""
        self.active_timer = asyncio.run_coroutine_threadsafe(
            self.start_countdown(duration, display), loop
        )

    def cancel(self):
        if self.active_timer and not self.active_timer.done():
            self.active_timer.cancel()
            self.remaining = 0
