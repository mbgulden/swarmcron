"""SwarmCron core task dataclass, registry store, and DAG cycle validator."""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Sequence

from .locking import FileLock, TaskExecutionLock
from .receipt import CronRunReceipt
from .scheduler import CronScheduleEvaluator
from .security import sanitize_env, validate_cwd, validate_task_command, SecurityValidationError

CRON_STATE_ACTIVE = "active"
CRON_STATE_PAUSED = "paused"
CRON_STATE_DEACTIVATED = "deactivated"
CRON_STATE_DELETED = "deleted"
QUEUE_STATES = {CRON_STATE_ACTIVE, CRON_STATE_PAUSED}

Action = Literal["pause", "resume", "deactivate", "activate", "delete", "run", "recover"]
ConcurrencyPolicy = Literal["forbid", "allow", "replace"]

MAX_OUTPUT_BYTES = 100 * 1024  # 100 KB max captured per stream to prevent RAM exhaustion


class DependencyNotSatisfiedError(RuntimeError):
    """Raised when an upstream dependency has not completed successfully."""
    pass


class TaskAlreadyRunningError(RuntimeError):
    """Raised when a task is already running and concurrency_policy is 'forbid'."""
    pass


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
            if dep == node:
                cycles.append(f"{node} -> {node} (self-reference)")
            elif dep not in visited:
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
    concurrency_policy: ConcurrencyPolicy = "forbid"
    timeout_seconds: int = 600
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
        self.command = validate_task_command(self.command)
        self.env = sanitize_env(self.env)
        self.sync_queue_state()

    def sync_queue_state(self) -> None:
        self.queue_state = "queued" if self.state in QUEUE_STATES else "out_of_queue"

    @property
    def enabled(self) -> bool:
        return self.state == CRON_STATE_ACTIVE

    def next_run_time(self, from_dt: datetime | None = None) -> str | None:
        try:
            evaluator = CronScheduleEvaluator(self.schedule)
            next_dt = evaluator.get_next_run(from_dt)
            return next_dt.isoformat() if next_dt else None
        except Exception:
            return None

    def is_missed(self, now: datetime | None = None) -> bool:
        try:
            evaluator = CronScheduleEvaluator(self.schedule)
            return evaluator.is_missed(self.last_run_at, now)
        except Exception:
            return False

    def to_dict(self) -> dict[str, Any]:
        self.sync_queue_state()
        data = asdict(self)
        data["enabled"] = self.enabled
        data["display_command"] = " ".join(shlex.quote(part) for part in self.command)
        data["next_run_at"] = self.next_run_time()
        data["is_missed"] = self.is_missed()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmCronTask:
        valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


class SwarmCronRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.environ.get("SWARMCRON_STORE", "~/.swarmcron/tasks.json")).expanduser()
        self.lock_path = self.path.with_suffix(".lock")
        self.lock_dir = self.path.parent / ".locks"

    def _file_lock(self) -> FileLock:
        return FileLock(self.lock_path)

    def load(self) -> list[SwarmCronTask]:
        if not self.path.exists():
            return []
        try:
            with self._file_lock():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                return [SwarmCronTask.from_dict(item) for item in raw.get("tasks", [])]
        except Exception:
            return []

    def _save_unlocked(self, tasks: list[SwarmCronTask]) -> None:
        payload = {"tasks": [t.to_dict() for t in tasks], "updated_at": _now()}
        _atomic_write_json(self.path, payload)

    def save(self, tasks: list[SwarmCronTask]) -> None:
        with self._file_lock():
            self._save_unlocked(tasks)

    def register(self, task: SwarmCronTask) -> SwarmCronTask:
        with self._file_lock():
            tasks = []
            if self.path.exists():
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                    tasks = [SwarmCronTask.from_dict(item) for item in raw.get("tasks", [])]
                except Exception:
                    tasks = []
            
            existing = [i for i, t in enumerate(tasks) if t.id == task.id]
            if existing:
                tasks[existing[0]] = task
            else:
                tasks.append(task)
            cycles = validate_dag_cycles(tasks)
            if cycles:
                raise ValueError(f"DAG dependency cycle detected: {cycles[0]}")
            payload = {"tasks": [t.to_dict() for t in tasks], "updated_at": _now()}
            _atomic_write_json(self.path, payload)
        return task

    def check_dependencies(self, task_id: str, tasks: list[SwarmCronTask] | None = None) -> None:
        """Verify that all upstream DAG dependencies have succeeded."""
        all_tasks = tasks or self.load()
        task_map = {t.id: t for t in all_tasks}
        target = task_map.get(task_id)
        if not target:
            raise KeyError(f"Task not found: {task_id}")

        for dep_id in target.depends_on:
            dep_task = task_map.get(dep_id)
            if not dep_task:
                raise DependencyNotSatisfiedError(f"Upstream dependency '{dep_id}' is not registered.")
            if dep_task.last_status != "success":
                raise DependencyNotSatisfiedError(
                    f"Upstream dependency '{dep_id}' has status '{dep_task.last_status}' (expected 'success')."
                )

    def mutate(self, task_id: str, action: Action, enforce_dependencies: bool = True) -> dict[str, Any]:
        with self._file_lock():
            tasks = []
            if self.path.exists():
                try:
                    raw = json.loads(self.path.read_text(encoding="utf-8"))
                    tasks = [SwarmCronTask.from_dict(item) for item in raw.get("tasks", [])]
                except Exception:
                    tasks = []

            for index, task in enumerate(tasks):
                if task.id != task_id:
                    continue
                if action == "pause":
                    if task.state == CRON_STATE_ACTIVE:
                        task.state = CRON_STATE_PAUSED
                        task.paused_at = _now()
                elif action == "resume":
                    if task.state == CRON_STATE_PAUSED:
                        task.state = CRON_STATE_ACTIVE
                        task.paused_at = None
                elif action == "deactivate":
                    if task.state != CRON_STATE_DELETED:
                        task.state = CRON_STATE_DEACTIVATED
                        task.deactivated_at = _now()
                elif action == "activate":
                    if task.state == CRON_STATE_DEACTIVATED:
                        task.state = CRON_STATE_ACTIVE
                        task.deactivated_at = None
                elif action == "delete":
                    task.state = CRON_STATE_DELETED
                    task.deleted_at = _now()
                elif action == "run":
                    if enforce_dependencies:
                        self.check_dependencies(task_id, tasks)
                    receipt = self.execute_task(task)
                    task.last_run_at = receipt.ran_at
                    task.last_status = receipt.status
                    task.last_exit_code = receipt.exit_code
                    task.last_stdout = receipt.stdout[-4000:]
                    task.last_stderr = receipt.stderr[-4000:]
                    tasks[index] = task
                    self._save_unlocked(tasks)
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
                    self._save_unlocked(tasks)
                    return {"success": last_rc["status"] == "success", "task": task.to_dict(), "replays_count": len(replays), "replays": replays}
                else:
                    raise ValueError(f"Unsupported action: {action}")
                task.updated_at = _now()
                task.sync_queue_state()
                tasks[index] = task
                self._save_unlocked(tasks)
                return {"success": True, "task": task.to_dict(), "action": action}
            raise KeyError(task_id)

    def execute_task(self, task: SwarmCronTask) -> CronRunReceipt:
        """Execute a task with concurrency locking, path validation, process group isolation, and timeout handling."""
        # 1. Concurrency Check
        exec_lock = TaskExecutionLock(self.lock_dir, task.id)
        if task.concurrency_policy == "forbid" and not exec_lock.acquire():
            return CronRunReceipt(
                task_id=task.id,
                ran_at=_now(),
                status="failed",
                exit_code=-2,
                stdout="",
                stderr=f"Task '{task.id}' is already executing (concurrency_policy='forbid')",
                duration_ms=0.0,
            )

        try:
            # 2. Path & Environment Validation
            env = os.environ.copy()
            env.update(task.env)
            cwd = validate_cwd(task.cwd)

            ran_at = _now()
            start = time.monotonic()
            
            # 3. Subprocess execution with process group session
            use_pgroup = sys.platform != "win32"
            proc = subprocess.Popen(
                task.command,
                cwd=cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=use_pgroup,
            )

            try:
                stdout_str, stderr_str = proc.communicate(timeout=task.timeout_seconds)
                exit_code = proc.returncode
                status = "success" if exit_code == 0 else "failed"
            except subprocess.TimeoutExpired:
                # Terminate entire process group to prevent zombies
                if use_pgroup:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except OSError:
                        pass
                else:
                    proc.kill()
                stdout_str, stderr_str = proc.communicate()
                exit_code = -1
                status = "failed"
                stderr_str = (stderr_str or "") + f"\n[SwarmCron: Task timed out after {task.timeout_seconds}s]"

            duration_ms = (time.monotonic() - start) * 1000

            # 4. Cap output bytes to prevent RAM exhaustion
            if len(stdout_str) > MAX_OUTPUT_BYTES:
                stdout_str = stdout_str[:MAX_OUTPUT_BYTES] + "\n[SwarmCron: stdout truncated...]"
            if len(stderr_str) > MAX_OUTPUT_BYTES:
                stderr_str = stderr_str[:MAX_OUTPUT_BYTES] + "\n[SwarmCron: stderr truncated...]"

            return CronRunReceipt(
                task_id=task.id,
                ran_at=ran_at,
                status=status,
                exit_code=exit_code,
                stdout=stdout_str,
                stderr=stderr_str,
                duration_ms=duration_ms,
            )
        except SecurityValidationError as sec_err:
            return CronRunReceipt(
                task_id=task.id,
                ran_at=_now(),
                status="failed",
                exit_code=-3,
                stdout="",
                stderr=f"Security validation error: {sec_err}",
                duration_ms=0.0,
            )
        except Exception as exc:
            return CronRunReceipt(
                task_id=task.id,
                ran_at=_now(),
                status="failed",
                exit_code=-4,
                stdout="",
                stderr=f"Unhandled execution exception: {exc}",
                duration_ms=0.0,
            )
        finally:
            exec_lock.release()
