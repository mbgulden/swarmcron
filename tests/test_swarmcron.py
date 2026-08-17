"""Unit tests for SwarmCron package."""

import pytest
from swarmcron import (
    SwarmCronTask,
    SwarmCronRegistry,
    validate_dag_cycles,
    CronRunReceipt,
)


def test_swarmcron_task_instantiation() -> None:
    task = SwarmCronTask(
        id="task-1",
        name="Test Swarm Task",
        schedule="*/5 * * * *",
        command=["python3", "app.py"],
    )
    assert task.id == "task-1"
    assert task.enabled is True
    d = task.to_dict()
    assert d["display_command"] == "python3 app.py"


def test_validate_dag_cycles() -> None:
    t1 = SwarmCronTask(id="task-a", name="A", schedule="manual", command=["true"], depends_on=["task-b"])
    t2 = SwarmCronTask(id="task-b", name="B", schedule="manual", command=["true"], depends_on=["task-a"])
    cycles = validate_dag_cycles([t1, t2])
    assert len(cycles) >= 1
    assert "task-a" in cycles[0] and "task-b" in cycles[0]


def test_swarmcron_registry_and_recover(tmp_path) -> None:
    store_file = tmp_path / "tasks.json"
    registry = SwarmCronRegistry(path=store_file)
    task = SwarmCronTask(
        id="task-rec-1",
        name="Recoverable Task",
        schedule="manual",
        command=["python3", "-c", "print('swarmcron ok')"],
    )
    registry.register(task)

    res = registry.mutate("task-rec-1", "recover")
    assert res["success"] is True
    assert res["replays_count"] == 3
    assert res["task"]["last_status"] == "success"
