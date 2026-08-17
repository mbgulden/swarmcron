# ⚡ SwarmCron

**Zero-dependency DAG cron scheduler, machine execution receipt engine, and FastAPI router for AI agent swarms & Python microservices.**

[![PyPI](https://img.shields.io/pypi/v/swarmcron.svg)](https://pypi.org/project/swarmcron/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Typing: Typed](https://img.shields.io/badge/Typing-Typed-blue.svg)](https://peps.python.org/pep-0561/)

---

## 🌟 What Sets SwarmCron Apart

SwarmCron is designed from the ground up for modern autonomous AI agent swarms, distributed microservices, and reliable DevOps workflows.

```
       ┌─────────────────────────────────────────────────────────┐
       │                SwarmCron Orchestrator                   │
       └────────────────────────────┬────────────────────────────┘
                                    │
      ┌─────────────────────────────┼────────────────────────────┐
      ▼                             ▼                            ▼
┌──────────────┐             ┌──────────────┐             ┌──────────────┐
│  Python API  │             │   FastAPI    │             │   CLI Tool   │
│  `mutate()`  │             │ `/api/crons` │             │ `swarmcron`  │
└──────┬───────┘             └──────┬───────┘             └──────┬───────┘
       │                            │                            │
       └────────────────────────────┼────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │                  Security & Process Gate                │
       │  • Env Var Sanitization (Blocks Loader Hijacking)       │
       │  • Process Group Isolation (Kills Zombie Subtrees)      │
       │  • Output Capping (100KB RAM Protection)                │
       │  • Atomic FileLock on tasks.json                        │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │               DAG Engine (`depends_on`)                 │
       │  • Cycle Detection via Depth-First Search               │
       │  • Fail-Closed Runtime Upstream State Verification      │
       └────────────────────────────┬────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────┐
       │           Machine Execution Receipts Engine             │
       │  `CronRunReceipt`: status, exit_code, duration_ms, logs │
       └─────────────────────────────────────────────────────────┘
```

### 1. 🚀 Zero External Dependencies
Runs everywhere on pure Python 3.10+ standard library. No background databases, no messaging brokers, and no compiled extensions required.

### 2. 🔗 Native DAG Dependency Graphs (`depends_on`)
Jobs declare dependencies on other tasks. The engine checks the entire dependency graph before launching, preventing downstream execution if any prerequisite task fails.

### 3. 🧾 Machine Execution Receipts (`CronRunReceipt`)
Every execution produces an immutable, structured machine receipt with exact ISO timestamps, exit codes, execution duration in milliseconds, stdout, and stderr. Perfect for AI agents, monitoring pipelines, and automated audits.

### 4. 🔄 Self-Healing Replay Recovery (`recover`)
When transient network glitches or service outages occur, SwarmCron provides self-healing recovery actions that can replay tasks up to $N$ times automatically.

### 5. 🛡️ Enterprise Security & Process Isolation
- **Environment Sanitization**: Strips dangerous dynamic loader variables (`LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`).
- **Zombie Containment**: Runs subprocesses inside dedicated process groups (`start_new_session=True`). On timeout, terminates the entire process tree (`killpg`).
- **Memory Protection**: Caps stdout and stderr capture streams at 100KB to eliminate out-of-memory crashes.
- **Atomic File Locking**: Protects state against race conditions across multiple processes.

### 6. 🌐 Unified Interfaces: Python, CLI & FastAPI
Use SwarmCron programmatically in Python, manage tasks from shell scripts with the CLI, or drop the FastAPI router into your web services in seconds.

---

## 💻 Installation

```bash
# Core package (zero dependencies)
pip install swarmcron

# With optional FastAPI router support
pip install swarmcron[fastapi]
```

---

## ⚡ Quickstart

```python
from swarmcron import SwarmCronRegistry, SwarmCronTask

# 1. Initialize registry (defaults to ~/.swarmcron/tasks.json)
registry = SwarmCronRegistry()

# 2. Register upstream data ingestion task
registry.register(SwarmCronTask(
    id="fetch-signals",
    name="Market Signal Ingestion",
    schedule="*/10 * * * *",  # Every 10 minutes
    command=["python3", "-m", "my_app.ingest_signals"],
    tags=["ingestion", "agent:scraper"],
))

# 3. Register downstream LLM synthesis task (depends on fetch-signals)
registry.register(SwarmCronTask(
    id="synthesize-report",
    name="LLM Market Summary Synthesis",
    schedule="0 9 * * *",    # Daily at 9:00 AM
    command=["python3", "-m", "my_app.llm_analyst"],
    depends_on=["fetch-signals"],  # Fails closed if fetch-signals hasn't succeeded
    tags=["analysis", "agent:analyst"],
))

# 4. Execute a task and inspect the machine receipt
result = registry.mutate("fetch-signals", "run")
receipt = result["receipt"]
print(f"Status: {receipt['status']} | Exit: {receipt['exit_code']} | Time: {receipt['duration_ms']:.2f}ms")

# 5. Replay recovery with custom retry count
recovery = registry.mutate("synthesize-report", "recover", max_retries=3)
print(f"Recovery Success: {recovery['success']} | Replays: {recovery['replays_count']}")
```

---

## 🤖 Real-World Use Cases

### 1. Autonomous AI Agent Swarm Pipelines
Coordinate multi-agent workflows where agents depend on each other's outputs. If the research agent fails, the writer agent is automatically paused.

```python
from swarmcron import SwarmCronRegistry, SwarmCronTask

registry = SwarmCronRegistry()

# Agent 1: Web Scraper
registry.register(SwarmCronTask(
    id="agent-crawler",
    name="Web Crawler Agent",
    schedule="0 */2 * * *",
    command=["python3", "agents/crawler.py"],
))

# Agent 2: Vector Embedding (Depends on Agent 1)
registry.register(SwarmCronTask(
    id="agent-vectorizer",
    name="Vector Embedding Agent",
    schedule="0 */2 * * *",
    command=["python3", "agents/vectorizer.py"],
    depends_on=["agent-crawler"],
))

# Agent 3: Executive Report Synthesizer (Depends on Agent 2)
registry.register(SwarmCronTask(
    id="agent-synthesizer",
    name="Report Synthesizer Agent",
    schedule="0 */2 * * *",
    command=["python3", "agents/synthesizer.py"],
    depends_on=["agent-vectorizer"],
))
```

### 2. DevOps & Infrastructure Automation
Automate nightly database backups with offsite cloud replication and crontab export:

```bash
# Register backup task
swarmcron register --id db-backup --name "Nightly DB Backup" \
    --schedule "0 2 * * *" --command "pg_dump -Fc mydb > /backups/db.dump"

# Register offsite upload task (depends on db-backup)
swarmcron register --id s3-sync --name "Offsite S3 Replication" \
    --schedule "30 2 * * *" --command "aws s3 cp /backups/db.dump s3://my-backups/" \
    --depends-on "db-backup"

# Export directly to system crontab
swarmcron export-crontab --include-header | sudo tee /etc/cron.d/swarmcron-jobs
```

### 3. FastAPI Microservice Embedding
Expose your cron workflows through a secured REST API:

```python
from fastapi import FastAPI, Header, HTTPException
from swarmcron import SwarmCronRegistry
from swarmcron.fastapi_router import create_cron_router

app = FastAPI(title="Swarm Task Hub")

def verify_token(x_api_key: str = Header(...)):
    if x_api_key != "secret-key":
        raise HTTPException(status_code=401, detail="Unauthorized")

# Mount SwarmCron router with authentication
app.include_router(
    create_cron_router(auth_dependency=verify_token),
    prefix="/api",
)
```

---

## 🛠️ CLI Reference

SwarmCron includes a full-featured CLI:

```bash
# List all registered tasks
swarmcron list

# Point at a custom tasks store
swarmcron --store /data/tasks.json list

# Register a new task from the terminal
swarmcron register \
  --id "health-check" \
  --name "API Health Check" \
  --schedule "*/5 * * * *" \
  --command "curl -sf https://api.example.com/health" \
  --group "monitoring" \
  --tags "health,api" \
  --timeout 30

# Manually trigger a task
swarmcron run health-check

# Replay missed executions with custom retries
swarmcron recover health-check --max-retries 5

# Manage task state
swarmcron mutate health-check pause
swarmcron mutate health-check resume
swarmcron mutate health-check deactivate
swarmcron mutate health-check activate
swarmcron mutate health-check delete

# Export active tasks as system crontab lines
swarmcron export-crontab --include-header
```

---

## 📁 Repository Examples

Explore complete runnable examples in the [`examples/`](file:///c:/Users/Michael%20Gulden/Github/swarmcron/examples) directory:

- [`01_ai_agent_swarm_pipeline.py`](file:///c:/Users/Michael%20Gulden/Github/swarmcron/examples/01_ai_agent_swarm_pipeline.py) — 4-stage AI agent pipeline with DAG dependencies and machine receipts.
- [`02_fastapi_microservice.py`](file:///c:/Users/Michael%20Gulden/Github/swarmcron/examples/02_fastapi_microservice.py) — Turnkey FastAPI microservice with authentication.
- [`03_devops_backup_pipeline.sh`](file:///c:/Users/Michael%20Gulden/Github/swarmcron/examples/03_devops_backup_pipeline.sh) — Shell script automation, crontab export, and recovery replays.

---

## 📄 License

MIT License © 2026 Michael Gulden
