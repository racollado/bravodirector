"""
FastAPI Application — serves the web UI and provides WebSocket + REST endpoints.

Routes:
  GET  /                     → Performer view (served from web/dist)
  GET  /editor               → Script editor
  WS   /ws                   → Real-time state stream + command channel
  GET  /api/state            → Current show state snapshot
  POST /api/command           → Send a command (pause, skip, etc.)
  GET  /api/script            → Get current script JSON
  POST /api/script            → Upload / replace script JSON
  GET  /api/scripts           → List available script files
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from server.ws_manager import WSManager

logger = logging.getLogger(__name__)


class CommandRequest(BaseModel):
    command: str
    args: Optional[dict] = None


class ScriptUpload(BaseModel):
    script: dict


def create_app(show_controller=None, ws_manager: Optional[WSManager] = None) -> FastAPI:
    app = FastAPI(title="Bravo, Director", version="2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    ws_mgr = ws_manager or WSManager()

    # ------------------------------------------------------------------
    # WebSocket
    # ------------------------------------------------------------------

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_mgr.connect(ws)
        try:
            # Send initial state
            if show_controller:
                state = show_controller.get_state_snapshot()
                await ws.send_text(json.dumps({"type": "state_update", "data": state}))

            while True:
                msg = await ws.receive_text()
                try:
                    data = json.loads(msg)
                    cmd = data.get("command")
                    if cmd and show_controller:
                        _handle_command(show_controller, cmd, data.get("args", {}))
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            await ws_mgr.disconnect(ws)
        except Exception as e:
            logger.error("WebSocket error: %s", e)
            await ws_mgr.disconnect(ws)

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------

    @app.get("/api/state")
    async def get_state():
        if not show_controller:
            raise HTTPException(status_code=503, detail="Show controller not initialized")
        return JSONResponse(show_controller.get_state_snapshot())

    @app.post("/api/command")
    async def post_command(req: CommandRequest):
        if not show_controller:
            raise HTTPException(status_code=503, detail="Show controller not initialized")
        _handle_command(show_controller, req.command, req.args or {})
        return {"status": "ok", "command": req.command}

    @app.get("/api/script")
    async def get_script():
        if not show_controller:
            raise HTTPException(status_code=503, detail="Show controller not initialized")
        return JSONResponse(show_controller.script._raw)

    @app.post("/api/script")
    async def upload_script(req: ScriptUpload):
        scripts_dir = Path("./scripts")
        scripts_dir.mkdir(parents=True, exist_ok=True)
        path = scripts_dir / "uploaded_show.json"
        with open(path, "w") as f:
            json.dump(req.script, f, indent=2)
        return {"status": "ok", "path": str(path)}

    @app.get("/api/scripts")
    async def list_scripts():
        scripts_dir = Path("./scripts")
        if not scripts_dir.exists():
            return {"scripts": []}
        files = sorted(scripts_dir.glob("*.json"))
        return {"scripts": [{"name": f.name, "path": str(f)} for f in files]}

    # ------------------------------------------------------------------
    # Static files (built web frontend)
    # ------------------------------------------------------------------

    dist_dir = Path(__file__).parent.parent / "web" / "dist"
    if dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="static-assets")

        @app.get("/editor")
        async def editor_page():
            return FileResponse(str(dist_dir / "index.html"))

        @app.get("/{full_path:path}")
        async def catch_all(full_path: str):
            file_path = dist_dir / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(dist_dir / "index.html"))
    else:
        @app.get("/")
        async def root():
            return {"message": "Bravo, Director API running. Build the web frontend with: cd web && npm run build"}

    return app


def _handle_command(controller, command: str, args: dict):
    cmd_map = {
        "start": lambda: controller.start_show(args.get("start_index", 0)),
        "stop": controller.stop_show,
        "pause": controller.pause_show,
        "add_failure": controller.add_failure,
        "skip_with_failure": controller.skip_with_failure,
        "skip_clean": controller.skip_clean,
        "go_back": controller.go_back,
        "reset": controller.reset_show,
    }

    fn = cmd_map.get(command)
    if fn:
        fn()
        logger.info("Command executed: %s", command)
    else:
        logger.warning("Unknown command: %s", command)
