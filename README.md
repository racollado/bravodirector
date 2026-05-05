# Bravo, Director

## IMPORTANT HUMAN DISCLAIMER:

A lot of this code is AI-generated. And by a lot, I mean pretty much all of it. Am I proud of this fact? Not particularly. However, does it work? For the most part, I think.

I like to consider this repository a supplementary digital artifact of the show that further showcases the bittersweet irony of instant AI gratification. Not all of this code makes sense for its intended goal. In fact, in producing this show, I found myself finding ways to work around the janky AI output instead of making it right.

However, the fact of the matter is, this show - which ultimately made people pretty happy - wouldn't have existed by its performance date had it not been for Claude. And, to me, there's something deeply horrifying about that fact. Thanks, Claude... I guess?

The rest of this README is also AI-generated. I highly doubt anyone really cares to deeply understand this project's architecture, let alone clone and run the code, but if you do, some of it is definitely wrong and I'm sorry. But actually I'm not sorry because I didn't write it! Enjoy.

P.S. Watch the show recording here: https://www.youtube.com/watch?v=qoAK9d_af1E

-------------------------------

**Bravo, Director v2.0** — a real-time, AI-assisted performance orchestration system for experimental theater. A single Python process runs the show engine (FastAPI + uvicorn) and serves the built React app for the performer view and script editor. Audience-facing visuals (captions, video, QR codes, timer) are rendered by a companion TouchDesigner project that listens for OSC messages.

## Requirements

- **Python** 3.10+ (recommended: current 3.12.x)
- **Node.js** 18+ and npm (to build the web UI)
- **TouchDesigner** (optional, for audience visuals via OSC) — a project file is provided: `BravoDirector.15.toe`
- A working microphone (for live speech / cue detection)
- **ffmpeg** on `PATH` (recommended; pydub uses it for `.mp3` decoding and >1.0× volume boost rendering)

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

Or use the convenience script, which rebuilds the frontend and then starts the server:

```bash
./run.sh                 # rebuilds web/dist then runs main.py
./run.sh --debug         # forwards extra args to main.py
```

Open the app at **`http://127.0.0.1:8000`** (or whatever you set in `SERVER_PORT`). Default OSC to TouchDesigner is on **port 9000** (`TD_OSC_PORT`) — independent of the HTTP port.

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

Defined in `.env` (see `.env.example`). If optional keys are missing, the related feature is disabled with a startup warning rather than a hard failure.

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Text generation (Google Gemini, default model `gemini-2.5-flash`) |
| `REPLICATE_API_TOKEN` | Music, TTS, image, and video generation via Replicate |
| `ASSEMBLYAI_API_KEY` | Live streaming transcription + cue matching |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `DYNAMODB_TABLE_NAME` | Audience submissions stored in DynamoDB |
| `TD_OSC_HOST`, `TD_OSC_PORT` | OSC destination for TouchDesigner (defaults: `127.0.0.1`, `9000`) |
| `SERVER_HOST`, `SERVER_PORT` | HTTP bind address (defaults: `127.0.0.1`, `8000`) |
| `BRAVO_AUDIO_BUFFER` | Pygame/SDL audio buffer in sample frames (default `4096`). Larger values reduce dropouts on USB interfaces; smaller values reduce latency. |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       main.py                            │
│   FastAPI + uvicorn (single process, single port)        │
└──────────┬──────────────────────────────────┬────────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────┐            ┌────────────────────┐
│   ShowController    │◄─── WS ──►│  Web UI (React)    │
│   · state machine   │            │  · Performer view  │
│   · step execution  │            │  · Script editor   │
│   · action dispatch │            └────────────────────┘
└──┬────┬────┬────┬───┘
   │    │    │    │
   ▼    ▼    ▼    ▼
Speech  Cue   Audio  OSC ──► TouchDesigner
Monitor Det.  Engine Client   (audience visuals)
   │     │
   ▼     ▼
┌───────────────────────────────────────────────────────┐
│                   Action handlers                      │
│  Gemini │ Replicate │ Caption │ Timer │ DynamoDB      │
│  (text) │ (media)   │ (OSC)   │ (OSC) │ (submissions) │
└───────────────────────────────────────────────────────┘
```

The `ShowController` runs on a dedicated background asyncio loop in its own thread. Step execution, generation calls, and timers are all coroutines on that loop; the FastAPI / uvicorn loop is reserved for HTTP and WebSocket I/O.

## Project structure

```
./
├── main.py                  # Entry point: wires engine + FastAPI + uvicorn
├── run.sh                   # Convenience: rebuild web + start main.py
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── BravoDirector.15.toe     # TouchDesigner project (audience visuals via OSC)
├── scripts/                 # Show scripts (JSON)
│   └── uploaded_show.json   # Default script path for main.py
├── engine/                  # Show engine (Python)
│   ├── show_controller.py   # Orchestration + state machine + action dispatch
│   ├── script_manager.py    # Script load, step model, AI injection, cue phrases
│   ├── cue_detector.py      # Linear-progression fuzzy cue matching (rapidfuzz)
│   ├── speech_monitor.py    # AssemblyAI streaming v3 transcription + RMS metering
│   ├── audio_engine.py      # Multi-layer audio playback (pygame + scipy DSP)
│   ├── osc_client.py        # OSC client for TouchDesigner
│   ├── task_manager.py      # Async task references ($task_id)
│   └── handlers/
│       ├── gemini_handler.py
│       ├── replicate_handler.py
│       ├── caption_handler.py
│       ├── timer_handler.py
│       └── dynamodb_handler.py
├── server/
│   ├── app.py               # FastAPI: routes, WebSocket, static SPA
│   └── ws_manager.py        # WebSocket broadcast + connection registry
├── web/                     # React 19 + Vite + Tailwind CSS 4
│   ├── package.json
│   ├── vite.config.js       # Dev proxy: /ws + /api → 127.0.0.1:8000
│   ├── index.html
│   ├── src/
│   │   ├── App.jsx          # React Router (/, /editor)
│   │   ├── main.jsx
│   │   ├── api/
│   │   │   └── websocket.js # useShowState() — live state + sendCommand
│   │   ├── performer/       # Performer view + components
│   │   ├── editor/          # Script editor + components
│   │   └── styles/
│   └── dist/                # Production build (gitignored; created by npm run build)
├── assets/                  # Audio, video, images, text (mostly gitignored)
└── logs/                    # performance.log (created at runtime)
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

`ScriptManager` flattens segments into an ordered list of steps. The current step index is what the performer view, cue detector, and OSC visuals all track.

### Top-level `settings`

Common keys consumed by the engine (see `scripts/uploaded_show.json` for a full example):

| Path | Purpose |
|------|---------|
| `settings.osc.host` / `settings.osc.port` | Override OSC target at script level (env vars usually win) |
| `settings.speech.default_confidence` | Default fuzzy-match threshold for AI-injected speech cues |
| `settings.speech.default_cue_words` | Tail-word count used to derive cue phrases for injected sentences |
| `settings.models.text` | Gemini text model (e.g. `gemini-2.5-flash`) |
| `settings.models.music` / `tts` / `video` / `sfx` | Replicate model slugs used as defaults for `generate_*` actions |
| `settings.failure.sfx` | Optional audio file played on failure |
| `settings.generation.loading_sfx` / `complete_sfx` | Played while waiting on AI generation and on completion |

### Step fields

- **`trigger`** — How the step is entered and whether it chains (see below).
- **`caption`** — Audience-facing text, color, and display mode (`advance_on_cue`, `clear_then_voice`).
- **`actions`** — Ordered list of action objects (`type` + parameters).
- **`overlays`** — Images/videos layered with the step (`show_image`, `hide_image`, `play_video`, `hide_video`).
- **`performer`** — Notes/labels for the performer UI (not sent to the audience).
- **`mode`** — Set to `timed_sequence` for synchronized multi-line playback (driven by an audio track + a `sequence` array of `{time, caption, video}` events).

### Trigger behavior (runtime)

| `trigger.type` | Role |
|----------------|------|
| `speech` | Step advances when the cue phrase fuzzy-matches the live transcript (`phrase`, `confidence`). |
| `auto` | Runs as soon as the show advances to this step. Can chain immediately to the next step unless gated (`wait_for_voice`, `delay`, etc.). |
| `timer` | Silently waits `duration` seconds (no OSC, no on-screen countdown) before running the step's actions. Speech cue matching is suppressed during the wait. |

Additional trigger fields: `delay` (extra wait before actions), `wait_for_voice` (hold previous caption, clear after `delay` seconds, then arm a mic-RMS voice-onset detector before showing this step's caption), `phrase` and `confidence` for `speech` triggers.

### Action types

Implemented in `ShowController` (`engine/show_controller.py`):

| Type | Description |
|------|-------------|
| `play_audio` | Play audio on a named layer (`main`, `music`, `sfx`); supports `loop`, `blocking`, `volume` (linear gain up to ~10×) |
| `play_video` | Play video file in TouchDesigner via `/media` OSC |
| `generate_text` | Gemini generation; can `inject` lines/sentences as new steps |
| `generate_music` | Music via Replicate (Stable Audio, Lyria, etc.) |
| `generate_sfx` | Text-to-SFX via Replicate (e.g. AudioGen); plays the result on a layer |
| `generate_tts` | TTS with word-level timing; can drive a synchronized run of injected caption steps |
| `generate_video` | Video via Replicate (e.g. Veo) |
| `generate_image` | Image via Replicate (e.g. Imagen) |
| `fetch_submissions` | Pull audience words/phrases from DynamoDB and stash them as a task output |
| `show_qr` / `hide_qr` | QR display via OSC |
| `start_timer` | Visible/blocking countdown synchronized with OSC `/timer` |
| `audio_control` | `fade_out`, `fade_in`, `set_volume`, `set_speed`, `set_pitch`, `stop` per layer |
| `send_osc` | Custom OSC message (`address`, `args`) |

Most actions accept `blocking: true|false` and `task_id`. Outputs (file paths, generated text) can be referenced from later steps via `$task_id`, including in `prompt_source`, `prompt_append_task`, `text_source`, `text_append_task`, and `inject` chains.

### Caption modes

| Mode | Behavior |
|------|----------|
| `advance_on_cue` | Caption stays until the next step replaces it. |
| `clear_then_voice` | After `clear_delay` seconds, the caption is cleared; the next caption is held until mic RMS crosses the voice-onset threshold. |

### Audio layers

`AudioEngine` exposes three independently-controlled pygame mixer channels: `main`, `music`, `sfx`. Each layer supports linear-gain volume up to ~10× (boosts above 1.0 are baked into the buffer via pydub), playback-speed change, and pitch shift (length-preserving two-step `scipy.signal.resample`). Speed/pitch changes restart the active clip from the beginning.

### AI content injection

`generate_text` and `generate_tts` can dynamically grow the script at runtime:

- **`inject.mode = "per_sentence"`** — Splits Gemini output on sentence boundaries; each sentence becomes a new speech-triggered step inserted after the current one. Cue phrases are derived from each sentence's tail (`settings.speech.default_cue_words`).
- **`inject.mode = "per_line"`** — Like `per_sentence`, but splits on newlines (useful for rap/lyric output).
- **TTS-driven** — When `generate_tts` returns word-level timestamps, the script is grown with timer-triggered steps and captions are advanced in lock-step with TTS playback (with a real-vs-estimated duration scale factor).

## Performer keyboard shortcuts

Ignored when focus is in an `<input>` or `<textarea>`.

| Key | Action |
|-----|--------|
| S | Start show **from idle** (step index 0) |
| P | Pause / resume |
| W | Skip step (clean) |
| Q | Skip step and count a failure |
| F | Add failure only (increment counter, plays `settings.failure.sfx`, sends `/failure` OSC — no skip) |
| E | Go back to the previous **authored** step (wipes injected AI steps in between) |
| Shift+R | Reset show |

The performer view also exposes click controls for these commands and a script start picker (idle screen) that lets you start at an arbitrary step index instead of 0.

## HTTP / WebSocket API

| Method | Path | Description |
|--------|------|-------------|
| WS | `/ws` | On connect, receives a `state_update` snapshot, then ongoing `state_update` frames. Send `{"command": ..., "args": {...}}` to control the show. |
| GET | `/api/state` | Current show state snapshot (same shape as the `data` field of `state_update`). |
| POST | `/api/command` | Same commands as WebSocket. Body: `{"command": "...", "args": {...}}`. |
| GET | `/api/script` | Current script JSON. |
| POST | `/api/script` | Upload a script. Body: `{"script": {...}}`. Writes `scripts/uploaded_show.json`. |
| GET | `/api/scripts` | List `scripts/*.json` files. |

Recognized commands: `start` (`args.start_index`), `stop`, `pause`, `add_failure`, `skip_with_failure`, `skip_clean`, `go_back`, `reset`.

### State snapshot fields (high-level)

`show_state`, `show_title`, `failure_count`, `current_step`, `current_index`, `total_steps`, `upcoming_steps`, `displayed_caption`, `loading_message`, `transcript` (`lines`, `partial`), `mic` (`level`, `streaming`), `tasks`, `timer` (`remaining`, `total`), `audio_layers`, `steps_outline`.

### OSC messages sent to TouchDesigner

The performer process is the OSC sender; TouchDesigner is expected to listen on `TD_OSC_HOST:TD_OSC_PORT`. Common addresses:

| Address | Args | Purpose |
|---------|------|---------|
| `/caption` | `text`, `color` | Show caption (empty `text` clears) |
| `/caption/clear` | — | Explicit clear |
| `/media` | `abs_path`, `volume` | Play a video/image asset (uses absolute path) |
| `/pause` | `0` / `1` | Show pause state hint |
| `/timer` | `seconds` (or `""`) | Visible countdown updates |
| `/qr/show` / `/qr/hide` | `url` | Audience QR overlay |
| `/failure` | `text` | Failure-counter feedback (cleared after ~2s) |

Custom OSC can be sent with the `send_osc` action.

## Development

### Frontend with hot reload (Vite)

The web app uses **React 19 + Vite 6 + Tailwind CSS 4** (`@tailwindcss/vite`).

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

Without a `web/dist` build, the root URL returns an API-only JSON message; build the frontend or use `npm run dev` for the UI.

### Logs

Console logging is mirrored to `./logs/performance.log` whenever the server is running. `--debug` raises the log level to `DEBUG` for both sinks. Detailed per-action info (Gemini prompts/outputs, Replicate model + result, cue matches, audio layer changes) is logged at `INFO` and above.
