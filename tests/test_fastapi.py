"""tests/test_fastapi.py — Unit and integration tests for SwarmCron FastAPI router."""

import pytest
from pathlib import Path
from swarmcron.core import SwarmCronRegistry, SwarmCronTask

try:
    from fastapi import FastAPI, Depends, Header, HTTPException
    from fastapi.testclient import TestClient
    from swarmcron.fastapi_router import create_cron_router
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_fastapi_router_endpoints(tmp_path: Path) -> None:
    store_file = tmp_path / "tasks.json"
    registry = SwarmCronRegistry(path=store_file)

    task = SwarmCronTask(
        id="api-task-1",
        name="API Task",
        schedule="manual",
        command=["python3", "-c", "print('api-ok')"],
    )
    registry.register(task)

    app = FastAPI()
    router = create_cron_router(registry=registry)
    app.include_router(router)

    client = TestClient(app)

    # 1. GET /crons
    res_list = client.get("/crons")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["ok"] is True
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == "api-task-1"

    # 2. POST /crons/{task_id}/register
    res_reg = client.post("/crons/api-task-2/register", json={
        "name": "Second API Task",
        "schedule": "*/10 * * * *",
        "command": ["python3", "-c", "print('second')"],
        "tags": ["fastapi", "agent"],
    })
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert reg_data["ok"] is True
    assert reg_data["task"]["id"] == "api-task-2"

    # 3. POST /crons/{task_id}/action (run)
    res_run = client.post("/crons/api-task-1/action", json={"action": "run"})
    assert res_run.status_code == 200
    run_data = res_run.json()
    assert run_data["success"] is True
    assert run_data["receipt"]["status"] == "success"

    # 4. POST /crons/{task_id}/action (pause)
    res_pause = client.post("/crons/api-task-1/action", json={"action": "pause"})
    assert res_pause.status_code == 200
    pause_data = res_run = res_pause.json()
    assert pause_data["task"]["state"] == "paused"

    # 5. Non-existent task 404
    res_404 = client.post("/crons/unknown-task-999/action", json={"action": "run"})
    assert res_404.status_code == 404


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_fastapi_router_auth_dependency(tmp_path: Path) -> None:
    store_file = tmp_path / "tasks.json"
    registry = SwarmCronRegistry(path=store_file)

    def verify_api_key(x_api_key: str = Header(...)):
        if x_api_key != "secret-swarm-token":
            raise HTTPException(status_code=401, detail="Unauthorized")

    app = FastAPI()
    router = create_cron_router(registry=registry, auth_dependency=verify_api_key)
    app.include_router(router)

    client = TestClient(app)

    # Missing auth header -> 422 or 401
    res_unauth = client.get("/crons")
    assert res_unauth.status_code in [401, 422]

    # Valid auth header -> 200
    res_auth = client.get("/crons", headers={"x-api-key": "secret-swarm-token"})
    assert res_auth.status_code == 200
    assert res_auth.json()["ok"] is True
