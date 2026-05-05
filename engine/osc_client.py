"""
OSC Client — sends Open Sound Control messages to TouchDesigner via UDP.

All audience-facing visuals are rendered by TouchDesigner. This module provides
typed convenience methods for common messages, plus a generic send() for custom ones.
"""

import logging
from typing import Any

from pythonosc import udp_client

logger = logging.getLogger(__name__)


class OSCClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self._host = host
        self._port = port
        self._client = udp_client.SimpleUDPClient(host, port)
        logger.info("OSC client ready → %s:%d", host, port)

    def send(self, address: str, *args: Any):
        try:
            self._client.send_message(address, list(args) if args else [])
        except Exception as e:
            logger.error("OSC send failed [%s]: %s", address, e)

    # ------------------------------------------------------------------
    # Captions
    # ------------------------------------------------------------------

    def send_caption(self, text: str, color: str = "#ffffff"):
        self.send("/caption", text, color)

    def clear_caption(self):
        self.send("/caption", "")

    # ------------------------------------------------------------------
    # QR Code
    # ------------------------------------------------------------------

    def show_qr(self, url: str = ""):
        self.send("/qr/show", url)

    def hide_qr(self):
        self.send("/qr/hide")

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    def send_timer(self, value):
        self.send("/timer", value)

    # ------------------------------------------------------------------
    # Loading / Generation feedback
    # ------------------------------------------------------------------

    def show_loading(self, message: str = ""):
        self.send("/loading/show", message)

    def hide_loading(self):
        self.send("/loading/hide")

    # ------------------------------------------------------------------
    # Failure counter
    # ------------------------------------------------------------------

    def increment_failure(self, count: int):
        self.send("/failure/increment", count)

    def reset_failure(self):
        self.send("/failure/reset", 0)

    # ------------------------------------------------------------------
    # Show state
    # ------------------------------------------------------------------

    def send_pause(self):
        self.send("/pause", 0)

    def send_resume(self, text: str = ""):
        self.send("/pause", 1)
        self.send("/caption", text)

    # ------------------------------------------------------------------
    # Media (video / image)
    # ------------------------------------------------------------------

    def play_media(self, filepath: str, volume: float = 1.0):
        self.send("/media", filepath, volume)
        self.send("/pause", 1)

    def clear_media(self):
        import os
        self.send("/media", os.path.abspath("./assets/image/black.png"), 0.0)
