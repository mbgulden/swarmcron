"""SwarmCron core task dataclass, registry store, and DAG cycle validator."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Sequence

from .receipt import CronRunReceipt

CRON_STATE_ACTIVE = "active"
CRON_STATE_PAUSED = "paused"
CRON_STATE_DEACTIVATED = "deactivated"
CRON_STATE_DELETED = "deleted"
QUEUE_STATES = {CRON_STATE_ACTIVE, CRON_STATE_PAUSED}

Action = Literal["pause", "resume", "deactivate", "activate", "delete", "run", "recover"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def validate_dag_cycles(tasks: Sequence[SwarmCronTask]) -> list[str]:
    """Detect circular dependencies in depends_on DAG using Depth-First Search."""
    graph = {t.id: set(t.depends_on) for t in tasks}
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles: list[str] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        for dep in graph.get(node, []):
            if dep not in visited:
                dfs(dep, path + [dep])
            elif dep in rec_stack:
                cycle_str = " -> ".join(path + [dep])
                cycles.append(cycle_str)
        rec_stack.remove(node)

    for task_id in graph:
        if task_id not in visited:
            dfs(task_id, [task_id])

    return cycles


@dataclass
class SwarmCronTask:
    id: str
    name: str
    schedule: str
    command: list[str]
    cwd: str = "."
    group: str = "general"
    description: str = ""
    state: str = CRON_STATE_ACTIVE
    queue_state: str = "queued"
    output_policy: str = "silent_on_success"
    env: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    last_run_at: str | None = None
    last_status: str | None = None
    last_exit_code: int | None = None
    last_stdout: str | None = None
    last_stderr: str | None = None
    deactivated_at: str | None = None
    deleted_at: str | None = None
    paused_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        self.sync_queue_state()

    def sync_queue_state(self) -> None:
        self.queue_state = "queued" if self.state in QUEUE_STATES else "out_of_queue"

    @property
    def enabled(self) -> bool:
        return self.state == CRON_STATE_ACTIVE

    def to_dict(self) -> dict[str, Any]:
        self.sync_queue_state()
        data = asdict(self)
        data["enabled"] = self.enabled
        data["display_command"] = " ".join(shlex.quote(part) for part in self.command)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmCronTask:
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


class SwarmCronRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.environ.get("SWARMCRON_STORE", "~/.swarmcron/tasks.json")).expanduser()

    def load(self) -> list[SwarmCronTask]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return [SwarmCronTask.from_dict(item) for item in raw.get("tasks", [])]
        except Exception:
            return []

    def save(self, tasks: list[SwarmCronTask]) -> None:
        payload = {"tasks": [t.to_dict() for t in tasks], "updated_at": _now()}
        _atomic_write_json(self.path, payload)

    def register(self, task: SwarmCronTask) -> SwarmCronTask:
        tasks = self.load()
        existing = [i for i, t in enumerate(tasks) if t.id == task.id]
        if existing:
            tasks[existing[0]] = task
        else:
            tasks.append(task)
        cycles = validate_dag_cycles(tasks)
        if cycles:
            raise ValueError(f"DAG dependency cycle detected: {cycles[0]}")
        self.save(tasks)
        return task

    def mutate(self, task_id: str, action: Action) -> dict[str, Any]:
        tasks = self.load()
        for index, task in enumerate(tasks):
            if task.id != task_id:
                continue
            if action == "pause":
                if task.state == CRON_STATE_ACTIVE:
                    task.state = CRON_STATE_PAUSED
                    task.paused_at = _now()
            elif action == "resume":
                if task.state == CRON_STATE_PAUSED:
                    task.state = CRON_STATE_ACTIVE; task.paused_at = None
            elif action == "deactivate":
                if task.state != CRON_STATE_DELETED:
                    task.state = CRON_STATE_DEACTIVATED; task.deactivated_at = _now()
            elif action == "activate":
                if task.state == CRON_STATE_DEACTIVATED:
                    task.state = CRON_STATE_ACTIVE; task.deactivated_at = None
            elif action == "delete":
                task.state = CRON_STATE_DELETED; task.deleted_at = _now()
            elif action == "run":
                receipt = self.execute_task(task)
                task.last_run_at = receipt.ran_at
                task.last_status = receipt.status
                task.last_exit_code = receipt.exit_code
                task.last_stdout = receipt.stdout[-4000:]
                task.last_stderr = receipt.stderr[-4000:]
                tasks[index] = task
                self.save(tasks)
                return {"success": receipt.status == "success", "task": task.to_dict(), "receipt": receipt.to_dict()}
            elif action == "recover":
                replays = []
                for _ in range(3):
                    rc = self.execute_task(task)
                    replays.append(rc.to_dict())
                    if rc.status != "success":
                        break
                last_rc = replays[-1]
                task.last_run_at = last_rc["ran_at"]
                task.last_status = last_rc["status"]
                task.last_exit_code = last_rc["exit_code"]
                task.last_stdout = last_rc["stdout"][-4000:]
                task.last_stderr = last_rc["stderr"][-4000:]
                tasks[index] = task
                self.save(tasks)
                return {"success": last_rc["status"] == "success", "task": task.to_dict(), "replays_count": len(replays), "replays": replays}
            else:
                raise ValueError(f"Unsupported action: {action}")
            task.updated_at = _now()
            task.sync_queue_state()
            tasks[index] = task
            self.save(tasks)
            return {"success": True, "task": task.to_dict(), "action": action}
        raise KeyError(task_id)

    def execute_task(self, task: SwarmCronTask, timeout: int = 600) -> CronRunReceipt:
        env = os.environ.copy()
        env.update(task.env)
        cwd = Path(task.cwd).expanduser().resolve() if Path(task.cwd).is_absolute() else Path.cwd() / task.cwd
        ran_at = _now()
        start = time.monotonic()
        completed = subprocess.run(
            task.command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        duration_ms = (time.monotonic() - start) * 1000
        return CronRunReceipt(
            task_id=task.id,
            ran_at=ran_at,
            status="success" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=duration_ms,
        )
