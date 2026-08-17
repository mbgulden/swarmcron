"""examples/02_fastapi_microservice.py

Demonstrates how to embed SwarmCron into a production FastAPI microservice:
  - Mounts the SwarmCron router with custom store path and API key security
  - Programmatically registers cron jobs on startup
  - Exposes REST endpoints to query machine execution receipts
"""

from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
import uvicorn
from swarmcron import SwarmCronRegistry, SwarmCronTask
from swarmcron.fastapi_router import create_cron_router

app = FastAPI(
    title="Agent Swarm Orchestration Hub",
    description="Microservice scheduler with machine execution receipts powered by SwarmCron.",
    version="1.0.0",
)

# 1. Initialize SwarmCron Registry
store_path = Path.home() / ".swarmcron" / "fastapi_tasks.json"
registry = SwarmCronRegistry(path=store_path)


# 2. Security Dependency (Optional API Key Header)
def verify_agent_token(x_swarm_token: str = Header(None)) -> str:
    # In production, replace with your secret or OAuth validation
    if x_swarm_token != "swarm-secret-123":
        raise HTTPException(status_code=401, detail="Invalid or missing X-Swarm-Token header")
    return x_swarm_token


# 3. Mount SwarmCron Router
cron_router = create_cron_router(
    registry=registry,
    auth_dependency=verify_agent_token,
)
app.include_router(cron_router, prefix="/api")


# 4. Bootstrap Default Tasks on Startup
@app.on_event("startup")
def bootstrap_tasks():
    registry.register(
        SwarmCronTask(
            id="system-telemetry",
            name="Host Health & Resource Telemetry",
            schedule="*/5 * * * *",
            command=["python3", "-c", "import psutil; print(f'CPU: {psutil.cpu_percent()}%')"],
            group="monitoring",
            tags=["health", "telemetry"],
        )
    )
    registry.register(
        SwarmCronTask(
            id="cache-eviction",
            name="Stale Cache Sweeper",
            schedule="0 * * * *",
            command=["python3", "-c", "print('Stale cache entries purged')"],
            group="maintenance",
            tags=["cache"],
        )
    )


@app.get("/")
def health_root():
    return {
        "status": "online",
        "endpoints": {
            "list_crons": "GET /api/crons",
            "execute_cron": "POST /api/crons/{task_id}/action",
            "register_cron": "POST /api/crons/{task_id}/register",
        },
        "docs": "/docs",
    }


if __name__ == "__main__":
    print("Starting FastAPI SwarmCron Hub on http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
