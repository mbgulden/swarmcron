# Changelog

All notable changes to SwarmCron will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-08-17

### Added
- **CLI `register` command**: Register tasks from the shell without writing Python (`swarmcron register --id X --name Y --schedule "..." --command "..."`).
- **CLI `--store` flag**: Point any CLI command at a custom `tasks.json` store file.
- **CLI `--max-retries` on `recover`**: Control retry count from the command line.
- **FastAPI `create_cron_router()` factory**: Supports pluggable `registry` and `auth_dependency` for multi-tenant setups.
- **FastAPI `POST /{task_id}/register` endpoint**: Register tasks via HTTP API.
- **`py.typed` marker**: PEP 561 compliance for `mypy` and `pyright` typed package discovery.
- **`[project.optional-dependencies] fastapi`**: Install with `pip install swarmcron[fastapi]`.
- **Comprehensive docstrings** on all `SwarmCronRegistry` public methods.
- **`max_retries` parameter** on `SwarmCronRegistry.mutate()` for the `recover` action.

### Fixed
- **README quickstart** no longer references non-existent `run_task()` method.
- **README quickstart** example is now self-contained and copy-pasteable.
- **`pyproject.toml` license format** switched to SPDX string to eliminate setuptools deprecation warnings.
- **FastAPI import guard**: Clear error message when FastAPI is not installed instead of bare `ModuleNotFoundError`.
- **Git hygiene**: Removed `__pycache__/`, `*.egg-info/`, and `dist/` from version control; added `.gitignore`.

### Changed
- `LICENSE` file now included in repository (was missing despite MIT declaration).
- `CHANGELOG.md` now included for version history tracking.

## [0.2.0] — 2026-08-17

### Added
- **Security module** (`swarmcron/security.py`): Env var sanitization (`LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`), command token validation, CWD path traversal prevention.
- **Locking module** (`swarmcron/locking.py`): Cross-platform `FileLock` for atomic `tasks.json` transactions; `TaskExecutionLock` for PID-backed overlapping run prevention.
- **Scheduler module** (`swarmcron/scheduler.py`): Zero-dependency pure-Python 5-field cron expression parser with `matches()`, `get_next_run()`, and `is_missed()`.
- **Process group isolation**: Subprocesses run in dedicated sessions; timeouts kill the entire process subtree.
- **Output capping**: Stdout/stderr capped at 100KB to prevent RAM exhaustion.
- **DAG runtime enforcement**: `check_dependencies()` verifies upstream tasks succeeded before execution.
- **Concurrency policy**: Per-task `forbid` / `allow` / `replace` policies.
- **Adversarial test suite** (`tests/test_adversarial.py`): 8 tests covering all 6 hardening domains.

## [0.1.0] — 2026-08-17

### Added
- Initial release of SwarmCron.
- `SwarmCronTask` dataclass with DAG `depends_on`, lifecycle states, and cron schedule.
- `SwarmCronRegistry` with JSON store, `register()`, `load()`, `save()`, `mutate()`.
- `CronRunReceipt` for machine execution tracking.
- CLI commands: `list`, `run`, `recover`, `export-crontab`, `mutate`.
- FastAPI router module with `GET /crons` and `POST /crons/{task_id}/action`.
- Core test suite (`tests/test_swarmcron.py`).
