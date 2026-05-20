from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ALLOWED_EXTENSIONS, JOB_DIR, MAX_FRAMES, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, UPLOAD_DIR
from .jobs import manager
from .processor import CropRect, ProcessOptions

app = FastAPI(title="Motion Sprite Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_filename(name: str) -> str:
    name = Path(name or "video.mp4").name
    name = re.sub(r"[^a-zA-Z0-9._\-\u4e00-\u9fff]", "_", name)
    return name[:120] or "video.mp4"


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "motion-sprite-studio"}


@app.get("/api/config")
def get_config() -> dict:
    return {
        "max_upload_mb": MAX_UPLOAD_MB,
        "max_frames": MAX_FRAMES,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
    }


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    start_time: float = Form(0.0),
    end_time: float = Form(0.0),
    fps: float = Form(12.0),
    max_frames: int = Form(MAX_FRAMES),
    remove_background: bool = Form(True),
    key_color: str = Form("#00ff00"),
    tolerance: float = Form(45.0),
    softness: float = Form(18.0),
    despill: float = Form(0.75),
    denoise: int = Form(1),
    fill_holes: int = Form(1),
    crop_x: int = Form(0),
    crop_y: int = Form(0),
    crop_w: int = Form(0),
    crop_h: int = Form(0),
    resize_width: int = Form(0),
    resize_height: int = Form(0),
    sheet_columns: int = Form(6),
    sheet_gap: int = Form(0),
    spine_animation: str = Form("idle"),
):
    original_name = _safe_filename(file.filename or "video.mp4")
    ext = Path(original_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的视频格式：{ext}，支持：{', '.join(sorted(ALLOWED_EXTENSIONS))}")

    temp_id = os.urandom(8).hex()
    upload_path = UPLOAD_DIR / f"{temp_id}_{original_name}"
    total = 0
    try:
        with upload_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"文件超过限制：{MAX_UPLOAD_MB}MB")
                out.write(chunk)
    except Exception:
        if upload_path.exists():
            upload_path.unlink(missing_ok=True)
        raise

    options = ProcessOptions(
        start_time=start_time,
        end_time=end_time,
        fps=fps,
        max_frames=max_frames,
        remove_background=remove_background,
        key_color=key_color,
        tolerance=tolerance,
        softness=softness,
        despill=despill,
        denoise=denoise,
        fill_holes=fill_holes,
        crop=CropRect(crop_x, crop_y, crop_w, crop_h),
        resize_width=resize_width,
        resize_height=resize_height,
        sheet_columns=sheet_columns,
        sheet_gap=sheet_gap,
        spine_animation=spine_animation,
    )
    state = manager.create_job(upload_path, original_name, options)
    return state.to_dict()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    state = manager.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="任务不存在")
    return state.to_dict()


@app.get("/api/jobs/{job_id}/download/{filename}")
def download(job_id: str, filename: str):
    filename = Path(filename).name
    allowed = {"frames.zip", "sprite_sheet.png", "animation.gif", "spine.zip", "report.json"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="文件不存在")
    path = JOB_DIR / job_id / "outputs" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path, filename=filename)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    job_dir = JOB_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="任务不存在")
    shutil.rmtree(job_dir, ignore_errors=True)
    return {"ok": True}


# Serve built Vite frontend from Docker/production image.
DIST_DIR = Path(__file__).resolve().parents[2] / "frontend_dist"
if DIST_DIR.exists():
    assets = DIST_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = DIST_DIR / full_path
        if target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST_DIR / "index.html")
