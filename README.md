# Bravo, Director v2.0

A real-time AI-powered performance orchestration system for experimental theater. A single Python process runs the show engine and serves a web-based performer view and script editor.

## Quick Start

### 1. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Build the web frontend

```bash
cd web
npm install
npm run build
cd ..
```

### 4. Run the show

```bash
python main.py
# Open http://127.0.0.1:9000 for the performer view
# Open http://127.0.0.1:9000/editor for the script editor
```

### CLI options

```
python main.py --script ./scripts/my_show.json   # Custom script
python main.py --port 3000                        # Custom port
python main.py --debug                            # Verbose logging
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                             │
│   FastAPI + uvicorn (single process)                     │
└──────────┬──────────────────────────────────┬────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────┐            ┌────────────────────┐
│   ShowController     │◄─── WS ──►│  Web UI (React)    │
│   - state machine    │           │  - Performer View  │
│   - step execution   │           │  - Script Editor   │
│   - action dispatch  │           └────────────────────┘
└──┬────┬────┬────┬────┘
   │    │    │    │
   ▼    ▼    ▼    ▼
 Speech  Cue   Audio  OSC → TouchDesigner
 Monitor Det.  Engine  Client  (visuals)
   │    │
   ▼    ▼
┌──────────────────────────────────────────┐
│           Action Handlers                 │
│  Gemini  │ Replicate │ Caption │ Timer   │
│  (text)  │ (music,   │ (OSC)  │ (count) │
│          │ TTS, video)│       │         │
│          │            │ DynamoDB (submissions)│
└──────────────────────────────────────────┘
```

## Project Structure

```
BravoDirectorFinal/
├── main.py                 # Entry point (FastAPI server)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── scripts/
│   └── example_show.json   # Example show script
├── engine/                 # Python show engine
│   ├── show_controller.py  # Central orchestration + state machine
│   ├── script_manager.py   # JSON script loading, injection, navigation
│   ├── cue_detector.py     # Fuzzy speech cue matching
│   ├── speech_monitor.py   # AssemblyAI real-time transcription
│   ├── audio_engine.py     # Multi-layer audio (pygame)
│   ├── osc_client.py       # OSC to TouchDesigner
│   ├── task_manager.py     # Background task tracking
│   └── handlers/
│       ├── gemini_handler.py     # Text generation
│       ├── replicate_handler.py  # Music, TTS, video generation
│       ├── caption_handler.py    # Caption display logic
│       ├── timer_handler.py      # Countdown timers
│       └── dynamodb_handler.py   # Audience submissions
├── server/                 # FastAPI + WebSocket
│   ├── app.py              # Routes and endpoints
│   └── ws_manager.py       # WebSocket connection manager
├── web/                    # React frontend
│   ├── src/
│   │   ├── performer/      # Performer view components
│   │   ├── editor/         # Script editor components
│   │   └── api/            # WebSocket hook
│   └── dist/               # Built frontend (served by FastAPI)
├── assets/                 # Show assets
│   ├── audio/
│   ├── video/
│   └── images/
└── logs/                   # Performance logs
```

## Script JSON Format

Shows are defined as JSON files with this structure:

```json
{
  "title": "Show Title",
  "version": "2.0",
  "settings": { ... },
  "segments": [
    {
      "id": "segment_id",
      "name": "Segment Name",
      "steps": [ ... ]
    }
  ]
}
```

### Step structure

Each step has:
- **`trigger`** — how the step starts (`speech`, `auto`, `timer`, `manual`, `audio_end`, `await_task`)
- **`caption`** — audience-facing text with color and display mode
- **`actions`** — array of things to execute (generate text, play audio, show QR, etc.)
- **`overlays`** — persistent visual layers (images, videos)
- **`performer`** — notes and section labels for the performer view

### Trigger types

| Type | Description |
|------|-------------|
| `speech` | Advance when cue phrase detected |
| `auto` | Advance immediately after previous step |
| `timer` | Advance after N seconds |
| `manual` | Only via keyboard shortcut |
| `audio_end` | When current audio finishes |
| `await_task` | When a background task completes |

### Action types

| Type | Description |
|------|-------------|
| `play_audio` | Play audio on a named layer (main/music/sfx) |
| `play_video` | Play video via OSC to TouchDesigner |
| `generate_text` | Generate text with Gemini, optionally inject into script |
| `generate_music` | Generate music via Replicate |
| `generate_tts` | Generate TTS voice with word timestamps |
| `generate_video` | Generate video via Replicate |
| `fetch_submissions` | Fetch audience words from DynamoDB |
| `show_qr` / `hide_qr` | Toggle QR code display |
| `start_timer` | Start countdown timer |
| `audio_control` | Volume, speed, pitch, fade control |
| `send_osc` | Send custom OSC message |

### Caption modes

| Mode | Behavior |
|------|----------|
| `advance_on_cue` | Caption stays until next step replaces it |
| `clear_then_voice` | Clear after delay, show next on voice onset |

## Performer Keyboard Shortcuts

| Key | Action |
|-----|--------|
| S | Start show |
| P | Pause / Resume |
| W | Skip (clean) |
| Q | Skip + increment failure counter |
| E | Go back to previous authored step |
| Shift+R | Reset show |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| WS | `/ws` | Real-time state + commands |
| GET | `/api/state` | Current show state |
| POST | `/api/command` | Send command |
| GET | `/api/script` | Get current script |
| POST | `/api/script` | Upload script |
| GET | `/api/scripts` | List available scripts |

## Development

### Frontend dev server (with hot reload)

```bash
cd web
npm run dev
# Opens on http://localhost:5173 with proxy to Python backend
```

### Backend only

```bash
python main.py --debug
```
