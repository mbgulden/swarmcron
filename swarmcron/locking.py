"""SwarmCron cross-platform inter-process file locking and execution concurrency guards."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import TracebackType


class FileLock:
    """Zero-dependency inter-process file lock using flock on POSIX with cross-platform fallback."""

    def __init__(self, lock_path: Path | str, timeout: float = 10.0, retry_interval: float = 0.05) -> None:
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self.retry_interval = retry_interval
        self._fd: int | None = None

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.monotonic()

        while True:
            try:
                # Open or create lockfile
                self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except (OSError, IOError):
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except OSError:
                        pass
                    self._fd = None
                if (time.monotonic() - start_time) >= self.timeout:
                    raise TimeoutError(f"Could not acquire file lock on {self.lock_path} within {self.timeout}s")
                time.sleep(self.retry_interval)

    def release(self) -> None:
        if self._fd is not None:
            try:
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            finally:
                self._fd = None

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()


class TaskExecutionLock:
    """PID-backed per-task execution lock to prevent overlapping task runs."""

    def __init__(self, lock_dir: Path, task_id: str) -> None:
        self.lock_file = lock_dir / f"{task_id}.pid"
        self._locked = False

    def is_running(self) -> bool:
        if not self.lock_file.exists():
            return False
        try:
            pid = int(self.lock_file.read_text().strip())
            # Check if process is still alive
            if sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if process != 0:
                    kernel32.CloseHandle(process)
                    return True
                return False
            else:
                os.kill(pid, 0)
                return True
        except (ValueError, OSError):
            # Process died or lock is stale
            try:
                self.lock_file.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def acquire(self) -> bool:
        if self.is_running():
            return False
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.lock_file.write_text(str(os.getpid()))
            self._locked = True
            return True
        except OSError:
            return False

    def release(self) -> None:
        if self._locked:
            try:
                self.lock_file.unlink(missing_ok=True)
            except OSError:
                pass
            self._locked = False

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()
