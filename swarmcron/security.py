"""SwarmCron security, path validation, and environment isolation utilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Dangerous environment variables that could hijack dynamic linking or execution
HAZARDOUS_ENV_VARS = {
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES",
    "DYLD_LIBRARY_PATH",
    "PYTHONINSPECT",
    "BASH_ENV",
    "ENV",
}


class SecurityValidationError(ValueError):
    """Raised when task configuration fails security validation."""
    pass


def sanitize_env(env: dict[str, str] | None, allow_hazardous: bool = False) -> dict[str, str]:
    """Sanitize environment variables, removing dangerous loader hijack keys."""
    if not env:
        return {}
    clean: dict[str, str] = {}
    for k, v in env.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        if not allow_hazardous and k.upper() in HAZARDOUS_ENV_VARS:
            continue
        clean[k] = v
    return clean


def validate_task_command(command: Any) -> list[str]:
    """Validate task command is a non-empty list of string arguments."""
    if isinstance(command, str):
        if not command.strip():
            raise SecurityValidationError("Command cannot be empty")
        # Split safely into tokens
        import shlex
        return shlex.split(command)
    if not isinstance(command, (list, tuple)) or not command:
        raise SecurityValidationError(f"Command must be a non-empty list of strings, got {type(command)}")
    for part in command:
        if not isinstance(part, str):
            raise SecurityValidationError(f"Command tokens must be strings, got {type(part)}")
    return list(command)


def validate_cwd(cwd: str | Path | None, repo_root: Path | None = None) -> Path:
    """Validate working directory exists and is accessible."""
    if not cwd or cwd == ".":
        return repo_root or Path.cwd()
    target = Path(cwd).expanduser()
    if not target.is_absolute() and repo_root:
        target = repo_root / target
    resolved = target.resolve()
    if not resolved.exists():
        raise SecurityValidationError(f"Working directory does not exist: {resolved}")
    if not resolved.is_dir():
        raise SecurityValidationError(f"Working directory is not a directory: {resolved}")
    return resolved
