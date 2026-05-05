"""
Bravo, Director — Main Entry Point

Starts the FastAPI server which runs the show engine and serves the performer
view + script editor web UI.

Usage:
    python main.py                          # defaults: script=scripts/example_show.json, port=8000
    python main.py --script my_show.json    # custom script
    python main.py --port 3000              # custom port
    python main.py --debug                  # verbose logging
"""

import os
import sys
import argparse
import asyncio
import logging
from pathlib import Path

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from dotenv import load_dotenv
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))

from engine.script_manager import ScriptManager
from engine.cue_detector import CueDetector
from engine.speech_monitor import SpeechMonitor
from engine.audio_engine import AudioEngine
from engine.osc_client import OSCClient
from engine.show_controller import ShowController
from engine.handlers import (
    GeminiHandler,
    ReplicateHandler,
    CaptionHandler,
    TimerHandler,
    DynamoDBHandler,
)
from server.ws_manager import WSManager
from server.app import create_app


def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    Path("./logs").mkdir(exist_ok=True)
    fh = logging.FileHandler("./logs/performance.log")
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(fh)


def load_env() -> dict:
    load_dotenv()
    return {
        "gemini_key": os.getenv("GEMINI_API_KEY", ""),
        "replicate_token": os.getenv("REPLICATE_API_TOKEN", ""),
        "assemblyai_key": os.getenv("ASSEMBLYAI_API_KEY", ""),
        "aws_access_key": os.getenv("AWS_ACCESS_KEY_ID", ""),
        "aws_secret_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "aws_region": os.getenv("AWS_REGION", "us-east-1"),
        "dynamodb_table": os.getenv("DYNAMODB_TABLE_NAME", ""),
        "td_host": os.getenv("TD_OSC_HOST", "127.0.0.1"),
        "td_port": int(os.getenv("TD_OSC_PORT", "9000")),
        "server_host": os.getenv("SERVER_HOST", "127.0.0.1"),
        "server_port": int(os.getenv("SERVER_PORT", "8000")),
    }


def main():
    parser = argparse.ArgumentParser(description="Bravo, Director — Performance Orchestration System")
    parser.add_argument("--script", default="./scripts/uploaded_show.json", help="Path to show script JSON")
    parser.add_argument("--port", type=int, help="Server port (overrides .env)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    setup_logging(args.debug)
    logger = logging.getLogger("main")
    logger.info("=== Bravo, Director v2.0 ===")

    Path("./assets/audio").mkdir(parents=True, exist_ok=True)
    Path("./assets/video").mkdir(parents=True, exist_ok=True)
    Path("./assets/images").mkdir(parents=True, exist_ok=True)

    env = load_env()
    port = args.port or env["server_port"]

    # --- Script ---
    if not os.path.exists(args.script):
        logger.error("Script not found: %s", args.script)
        return 1
    script_manager = ScriptManager(args.script)

    # --- Core components ---
    osc = OSCClient(host=env["td_host"], port=env["td_port"])
    cue_detector = CueDetector()
    audio = AudioEngine()

    # Register cues from script
    for cue in script_manager.get_all_cue_phrases():
        cue_detector.add_cue(
            phrase=cue["phrase"],
            step_index=cue["step_index"],
            confidence_threshold=cue["confidence"],
        )

    # --- Speech monitor ---
    speech = None
    if env["assemblyai_key"]:
        speech = SpeechMonitor(api_key=env["assemblyai_key"])
    else:
        logger.warning("ASSEMBLYAI_API_KEY not set — speech recognition disabled")

    # --- Handlers ---
    handlers: dict = {}

    if env["gemini_key"]:
        text_model = script_manager.settings.get("models", {}).get("text", "gemini-2.5-flash")
        handlers["gemini"] = GeminiHandler(api_key=env["gemini_key"], model=text_model)
    else:
        logger.warning("GEMINI_API_KEY not set — text generation disabled")

    if env["replicate_token"]:
        handlers["replicate"] = ReplicateHandler(api_token=env["replicate_token"])
    else:
        logger.warning("REPLICATE_API_TOKEN not set — media generation disabled")

    handlers["caption"] = CaptionHandler(osc)
    handlers["timer"] = TimerHandler(osc)

    if env["dynamodb_table"]:
        handlers["dynamodb"] = DynamoDBHandler(
            region=env["aws_region"],
            access_key=env["aws_access_key"],
            secret_key=env["aws_secret_key"],
        )
    else:
        logger.warning("DYNAMODB_TABLE_NAME not set — audience submissions disabled")

    # --- WebSocket manager ---
    ws_manager = WSManager()

    def on_state_change(state_snapshot: dict):
        ws_manager.broadcast_sync(state_snapshot)

    # --- Show Controller ---
    controller = ShowController(
        script_manager=script_manager,
        cue_detector=cue_detector,
        speech_monitor=speech,
        audio_engine=audio,
        osc_client=osc,
        handlers=handlers,
        on_state_change=on_state_change,
    )

    # --- FastAPI ---
    app = create_app(show_controller=controller, ws_manager=ws_manager)

    logger.info("Server starting at http://%s:%d", env["server_host"], port)
    logger.info("Open the performer view in your browser")

    uvicorn.run(app, host=env["server_host"], port=port, log_level="info")

    controller.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
