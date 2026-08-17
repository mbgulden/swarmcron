# ⚡ SwarmCron

**Zero-dependency DAG cron scheduler, machine execution receipt engine, and FastAPI router for AI agent swarms & Python microservices.**

[![PyPI](https://img.shields.io/pypi/v/swarmcron.svg)](https://pypi.org/project/swarmcron/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## 🔥 Why SwarmCron?

Traditional Python schedulers (Celery/Celery Beat, Airflow, Prefect) carry heavy infrastructure requirements (Redis, RabbitMQ, PostgreSQL, Docker). Light in-memory schedulers (APScheduler) lack persistent execution receipts, DAG dependencies, and systemd export capabilities.

**SwarmCron** solves this by delivering a **pure Python standard library engine** designed specifically for AI agent swarms and microservices:

- 🚀 **Zero External Dependencies**: Standard Python 3.10+ stdlib only (`subprocess`, `dataclasses`, `json`).
- 🔗 **DAG Dependency Graph (`depends_on`)**: Jobs won't fire until their upstream task dependencies succeed.
- 🔄 **Self-Healing Recovery (`recover`)**: Automatically replays missed execution windows with configurable retries.
- 🧾 **Machine Execution Receipts (`CronRunReceipt`)**: Logs full ISO timestamps, exit codes, stdout, stderr, and execution duration.
- 🔒 **Security Hardened**: Env var sanitization, command token validation, path traversal prevention, process group isolation, output capping.
- 🐧 **Systemd & Crontab Exporter**: One command `swarmcron export-crontab` generates production crontab lines.
- 🌐 **Instant FastAPI Router**: Drop-in FastAPI endpoints with pluggable auth (`pip install swarmcron[fastapi]`).

---

## 💻 Installation

```bash
pip install swarmcron
```

With optional FastAPI support:

```bash
pip install swarmcron[fastapi]
```

---

## ⚡ Quickstart

```python
from swarmcron import SwarmCronRegistry, SwarmCronTask

# 1. Initialize registry (defaults to ~/.swarmcron/tasks.json)
registry = SwarmCronRegistry()

# 2. Register tasks
registry.register(SwarmCronTask(
    id="fetch-analytics",
    name="Fetch Analytics Data",
    schedule="*/10 * * * *",  # Every 10 minutes
    command=["python3", "-m", "my_app.fetch_analytics"],
    tags=["analytics"],
))

registry.register(SwarmCronTask(
    id="daily-seo-audit",
    name="Multi-Site SEO Rank & Vital Auditor",
    schedule="0 9 * * *",  # Daily at 9am
    command=["python3", "-m", "my_app.seo_auditor"],
    depends_on=["fetch-analytics"],  # Won't run until fetch-analytics succeeds
    tags=["seo", "agent:ned"],
))

# 3. Execute a task (returns receipt with exit code, stdout, stderr, duration)
result = registry.mutate("fetch-analytics", "run")
print(f"Status: {result['receipt']['status']}, Exit Code: {result['receipt']['exit_code']}")

# 4. Recover missed executions (retries up to 3 times by default)
recovery = registry.mutate("daily-seo-audit", "recover")
print(f"Replays: {recovery['replays_count']}, Success: {recovery['success']}")
```

---

## 🌐 FastAPI Integration

Mount SwarmCron endpoints to any FastAPI gateway in 3 lines:

```python
from fastapi import FastAPI
from swarmcron.fastapi_router import create_cron_router

app = FastAPI()
app.include_router(create_cron_router(), prefix="/api")
```

Or with custom registry and authentication:

```python
from swarmcron import SwarmCronRegistry
from swarmcron.fastapi_router import create_cron_router

registry = SwarmCronRegistry(path=Path("/data/my_tasks.json"))
app.include_router(
    create_cron_router(registry=registry, auth_dependency=my_auth_dep),
    prefix="/api",
)
```

Exposes:
- `GET /api/crons` — List all registered tasks and queue states.
- `POST /api/crons/{task_id}/action` — Actions: `run`, `pause`, `resume`, `deactivate`, `activate`, `recover`.

---

## 🛠️ CLI Usage

```bash
# List all registered tasks
swarmcron list

# Point at a specific store file
swarmcron --store /path/to/tasks.json list

# Register a task from the command line
swarmcron register --id my-backup --name "Nightly Backup" \
    --schedule "0 2 * * *" --command "pg_dump mydb > /backups/db.sql"

# Manually trigger a task
swarmcron run daily-seo-audit

# Replay missed executions
swarmcron recover daily-seo-audit

# Pause / resume / deactivate / activate / delete
swarmcron mutate daily-seo-audit pause

# Export systemd / crontab lines
swarmcron export-crontab --include-header
```

---

## 🔒 Security Features

SwarmCron is hardened against common subprocess and scheduling attack vectors:

- **Env var sanitization**: Blocks `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, and other dynamic loader injection keys.
- **Command token validation**: Rejects empty or non-string command arguments.
- **Path validation**: Prevents non-existent or non-directory working directories.
- **Process group isolation**: Tasks run in dedicated process sessions; timeouts kill the entire subtree.
- **Output capping**: Stdout/stderr capped at 100KB to prevent RAM exhaustion.
- **File locking**: Atomic read-modify-write on the task store prevents data corruption under concurrent access.
- **Concurrency policy**: Per-task `forbid` / `allow` / `replace` policies prevent stampedes.

---

## 📄 License

MIT License © 2026 Michael Gulden
