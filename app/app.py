"""
Energy Compliance Intelligence Hub — FastAPI entry point.
Serves the React frontend and API endpoints.
"""

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the in-memory data store in the background so first requests are fast
    def _warm():
        try:
            from server.in_memory_data import _ensure_loaded
            _ensure_loaded()
        except Exception as e:
            logger.warning(f"Data pre-warm failed: {e}")
    threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(
    title="Energy Compliance Intelligence Hub",
    description="Real-data compliance intelligence for Australian energy & utilities",
    version="1.0.0",
    lifespan=lifespan,
)

from server.routes import router
app.include_router(router)

# Serve React frontend from built assets
# Try multiple possible paths for the frontend dist directory
_candidates = [
    Path(__file__).parent / "frontend" / "dist",
    Path(os.getcwd()) / "frontend" / "dist",
    Path("/app/frontend/dist"),
]
frontend_dist = None
for _c in _candidates:
    if (_c / "index.html").exists():
        frontend_dist = _c
        logging.getLogger(__name__).info(f"Frontend found at {_c}")
        break

if frontend_dist:
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))
else:
    logging.getLogger(__name__).warning("Frontend dist not found — serving API only")

    @app.get("/health")
    async def health():
        return {"status": "ok", "frontend": False}

    @app.get("/")
    async def root():
        return {"message": "Energy Compliance Intelligence Hub API", "docs": "/docs"}
