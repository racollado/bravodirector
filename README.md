# Bravo, Director

**Bravo, Director v2.0** — a real-time AI-assisted performance orchestration system for experimental theater. One Python process runs the show engine (FastAPI + uvicorn) and serves the built React app for the performer view and script editor.

## Requirements

- **Python** 3.10+ (recommended: current 3.12.x)
- **Node.js** 18+ and npm (to build the web UI)

## Quick start

### 1. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env: API keys and ports (see Environment variables below)
```

### 3. Build the web frontend

The server serves static files from `web/dist`. Build before running (or use `npm run dev` during UI work — see Development).

```bash
cd web
npm install
npm run build
cd ..
```

### 4. Run the show

```bash
python main.py
```

Open the app at **`http://127.0.0.1:8000`** (or whatever you set in `SERVER_PORT`). Default OSC to TouchDesigner is on **port 9000** (`TD_OSC_PORT`) — it is independent of the HTTP port.

- **Performer view:** `http://127.0.0.1:8000/`
- **Script editor:** `http://127.0.0.1:8000/editor`

### CLI options

| Option | Description |
|--------|-------------|
| `--script PATH` | Show script JSON (default: `./scripts/uploaded_show.json`) |
| `--port N` | HTTP server port (overrides `SERVER_PORT` in `.env`) |
| `--debug` | Verbose logging to console and `logs/performance.log` |

Example:

```bash
python main.py --script ./scripts/my_show.json --port 3000 --debug
```

## Environment variables

Defined in `.env` (see `.env.example`). If optional keys are missing, related features are disabled with a startup warning.

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Text generation (Gemini) |
| `REPLICATE_API_TOKEN` | Music, TTS, image, video via Replicate |
| `ASSEMBLYAI_API_KEY` | Live speech transcription and cue matching |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `DYNAMODB_TABLE_NAME` | Audience submissions in DynamoDB |
| `TD_OSC_HOST`, `TD_OSC_PORT` | OSC destination for TouchDesigner (default host `127.0.0.1`, port `9000`) |
| `SERVER_HOST`, `SERVER_PORT` | HTTP bind address (default `127.0.0.1`:`8000`) |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                             │
│   FastAPI + uvicorn (single process)                     │
└──────────┬──────────────────────────────────┬────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────┐            ┌────────────────────┐
│   ShowController    │◄─── WS ──►│  Web UI (React)   │
│   · state machine    │           │  · Performer view │
│   · step execution   │           │  · Script editor  │
│   · action dispatch  │           └────────────────────┘
└──┬────┬────┬────┬────┘
   │    │    │    │
   ▼    ▼    ▼    ▼
Speech  Cue   Audio  OSC → TouchDesigner
Monitor Det.  Engine  Client  (visuals)
   │    │
   ▼    ▼
┌──────────────────────────────────────────┐
│           Action handlers                 │
│  Gemini │ Replicate │ Caption │ Timer    │
│  (text) │ (media)     │ (OSC)   │ (OSC)    │
│         │             │ DynamoDB (submissions) │
└──────────────────────────────────────────┘
```

## Project structure

```
./
├── main.py                 # Entry point: wires engine + FastAPI + uvicorn
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── scripts/                # Show scripts (JSON)
│   └── uploaded_show.json  # Default script path for main.py
├── engine/                 # Show engine
│   ├── show_controller.py # Orchestration and state machine
│   ├── script_manager.py   # Script load, steps, cue phrases
│   ├── cue_detector.py     # Fuzzy speech cue matching
│   ├── speech_monitor.py   # AssemblyAI streaming transcription
│   ├── audio_engine.py     # Layered audio playback (pygame)
│   ├── osc_client.py       # OSC client for TouchDesigner
│   ├── task_manager.py     # Async task references ($task id)
│   └── handlers/
│       ├── gemini_handler.py
│       ├── replicate_handler.py
│       ├── caption_handler.py
│       ├── timer_handler.py
│       └── dynamodb_handler.py
├── server/
│   ├── app.py              # Routes, WebSocket, static SPA
│   └── ws_manager.py       # WebSocket broadcast + connections
├── web/                    # React (Vite) frontend
│   ├── src/
│   │   ├── performer/      # Performer view
│   │   ├── editor/         # Script editor
│   │   └── api/            # `websocket.js` — live state + commands
│   └── dist/               # Production build (gitignored; created by npm run build)
├── assets/                 # Audio, video, images, text (see .gitignore for tracked paths)
└── logs/                   # e.g. performance.log (created at runtime)
```

## Script JSON format

Shows are JSON documents shaped like:

```json
{
  "title": "Show Title",
  "version": "2.0",
  "settings": { },
  "segments": [
    {
      "id": "segment_id",
      "name": "Segment Name",
      "steps": [ ]
    }
  ]
}
```

### Step fields

- **`trigger`** — How the step is entered and whether it chains (see below).
- **`caption`** — Audience-facing text, colors, display modes (`advance_on_cue`, `clear_then_voice`, etc.).
- **`actions`** — Ordered list of action objects (`type` + parameters).
- **`overlays`** — Images/videos layered with the step.
- **`performer`** — Notes and labels for the performer UI.
- **`mode`** — e.g. `timed_sequence` for synchronized multi-line playback (handled in `ShowController`).

### Trigger behavior (runtime)

| `trigger.type` | Role |
|----------------|------|
| `speech` | Step advances when the cue phrase matches the live transcript (`phrase`, `confidence`). |
| `auto` | Runs when the show advances to this step. Can chain immediately to the next step unless gated (`wait_for_voice`, timed delays, etc.). |
| `timer` | Waits `duration` seconds (silent, no on-screen countdown) before running the step’s actions. |

Additional trigger fields include `delay`, `wait_for_voice`, and `phrase`/`confidence` for speech steps — see `engine/show_controller.py` and example steps in `scripts/uploaded_show.json`.

### Action types

Implemented in `ShowController` (`engine/show_controller.py`):

| Type | Description |
|------|-------------|
| `play_audio` | Play audio on a named layer (`main` / `music` / `sfx`, etc.) |
| `play_video` | Video via OSC to TouchDesigner |
| `generate_text` | Gemini generation; can inject lines into the script |
| `generate_music` | Music via Replicate |
| `generate_sfx` | Sound effect generation via Replicate |
| `generate_tts` | TTS with word-level timing |
| `generate_video` | Video via Replicate |
| `generate_image` | Image via Replicate |
| `fetch_submissions` | Audience words from DynamoDB |
| `show_qr` / `hide_qr` | QR display over OSC |
| `start_timer` | Visible countdown synchronized with OSC |
| `audio_control` | Volume, speed, pitch, fade |
| `send_osc` | Custom OSC message |

### Caption modes (caption handler)

| Mode | Behavior |
|------|----------|
| `advance_on_cue` | Caption stays until the next step replaces it |
| `clear_then_voice` | After a delay, clear; show next caption on voice onset |

## Performer keyboard shortcuts

Ignored while focus is in an `INPUT` or `TEXTAREA`.

| Key | Action |
|-----|--------|
| S | Start show **from idle** (from step index 0) |
| P | Pause / resume |
| W | Skip step (clean) |
| Q | Skip step and count a failure |
| F | Add failure only (increment counter, optional SFX/OSC — no skip) |
| E | Go back |
| Shift+R | Reset show |

## HTTP API

| Method | Path | Description |
|--------|------|-------------|
| WS | `/ws` | Live `state_update` frames + JSON commands (`command`, `args`) |
| GET | `/api/state` | Current show state snapshot |
| POST | `/api/command` | Same commands as WebSocket (body: `command`, optional `args`) |
| GET | `/api/script` | Current script JSON |
| POST | `/api/script` | Upload script body; writes `scripts/uploaded_show.json` |
| GET | `/api/scripts` | List `scripts/*.json` |

## Development

### Frontend with hot reload (Vite)

```bash
cd web
npm run dev
```

Dev server defaults to **http://localhost:5173**. `vite.config.js` proxies `/ws` and `/api` to **http://127.0.0.1:8000**, so run the Python app in another terminal:

```bash
python main.py --debug
```

### Backend only

```bash
python main.py --debug
```

Without a `web/dist` build, the root URL may show an API-only message; build the frontend or use `npm run dev` for the UI.
