from __future__ import annotations

import json
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from .config import JOB_DIR, TASK_WORKERS
from .processor import ProcessOptions, process_video


@dataclass
class JobState:
    id: str
    status: str = "queued"  # queued, running, completed, failed
    progress: float = 0.0
    message: str = "等待处理"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    input_name: str = ""
    error: Optional[str] = None
    outputs: List[dict] = field(default_factory=list)
    report: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "input_name": self.input_name,
            "error": self.error,
            "outputs": self.outputs,
            "report": self.report,
        }


class JobManager:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=max(1, TASK_WORKERS))
        self.jobs: Dict[str, JobState] = {}
        self.futures: Dict[str, Future] = {}
        self.lock = Lock()

    def create_job(self, input_path: Path, input_name: str, options: ProcessOptions) -> JobState:
        job_id = uuid.uuid4().hex[:16]
        job_dir = JOB_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        state = JobState(id=job_id, input_name=input_name)
        with self.lock:
            self.jobs[job_id] = state
        self._persist(state)
        future = self.executor.submit(self._run_job, job_id, input_path, job_dir, options)
        self.futures[job_id] = future
        return state

    def get(self, job_id: str) -> Optional[JobState]:
        with self.lock:
            state = self.jobs.get(job_id)
        if state:
            return state
        state_file = JOB_DIR / job_id / "job.json"
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            state = JobState(id=data["id"])
            for k, v in data.items():
                setattr(state, k, v)
            with self.lock:
                self.jobs[job_id] = state
            return state
        return None

    def _update(self, job_id: str, **kwargs) -> None:
        with self.lock:
            state = self.jobs[job_id]
            for k, v in kwargs.items():
                setattr(state, k, v)
            state.updated_at = datetime.now().isoformat(timespec="seconds")
        self._persist(state)

    def _progress_cb(self, job_id: str):
        def cb(progress: float, message: str) -> None:
            self._update(job_id, progress=round(float(progress), 4), message=message)
        return cb

    def _run_job(self, job_id: str, input_path: Path, job_dir: Path, options: ProcessOptions) -> None:
        try:
            self._update(job_id, status="running", progress=0.01, message="任务开始")
            report = process_video(input_path, job_dir, options, self._progress_cb(job_id))
            outputs_dir = job_dir / "outputs"
            outputs = []
            for name in ["frames.zip", "sprite_sheet.png", "animation.gif", "spine.zip", "report.json"]:
                path = outputs_dir / name
                if path.exists():
                    outputs.append({
                        "name": name,
                        "size_bytes": path.stat().st_size,
                        "url": f"/api/jobs/{job_id}/download/{name}",
                    })
            self._update(job_id, status="completed", progress=1.0, message="处理完成", outputs=outputs, report=report)
        except Exception as exc:
            tb = traceback.format_exc()
            (job_dir / "error.log").write_text(tb, encoding="utf-8")
            self._update(job_id, status="failed", error=str(exc), message="处理失败")

    def _persist(self, state: JobState) -> None:
        job_dir = JOB_DIR / state.id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "job.json").write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


manager = JobManager()
