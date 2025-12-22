# controllers/ui_scheduler.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Dict


@dataclass
class _Job:
    delay_ms: int
    fn: Callable[[], None]
    after_id: Optional[str] = None
    running: bool = False


class Repeater:
    """
    Tkinter scheduler that can run multiple repeating tasks.
    Usage:
        ui = Repeater(root)
        ui.every(1000, tick_fn)
        ui.every(60_000, recolor_fn)
        ui.start_all()
    """
    def __init__(self, root: any):
        self.root = root
        self._jobs: Dict[int, _Job] = {}  # key by delay_ms+fn id? we'll use incremental keys
        self._next_id = 1

    def every(self, delay_ms: int, fn: Callable[[], None]) -> int:
        job_id = self._next_id
        self._next_id += 1
        self._jobs[job_id] = _Job(delay_ms=delay_ms, fn=fn, running=True)
        self._tick(job_id)  # schedule first tick immediately
        return job_id

    def cancel(self, job_id: int) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        job.running = False
        if job.after_id is not None:
            try:
                self.root.after_cancel(job.after_id)
            except Exception:
                pass
            job.after_id = None
        self._jobs.pop(job_id, None)

    def stop_all(self) -> None:
        for job_id in list(self._jobs.keys()):
            self.cancel(job_id)

    def _tick(self, job_id: int) -> None:
        job = self._jobs.get(job_id)
        if not job or not job.running:
            return

        try:
            job.fn()
        finally:
            # schedule next tick no matter what; exceptions should not kill the loop
            job.after_id = self.root.after(job.delay_ms, lambda: self._tick(job_id))
