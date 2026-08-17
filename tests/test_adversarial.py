"""tests/test_adversarial.py — Exhaustive multi-angle adversarial test suite for SwarmCron."""

import pytest
import time
from datetime import datetime, timezone
from pathlib import Path
from swarmcron import (
    SwarmCronTask,
    SwarmCronRegistry,
    CronScheduleEvaluator,
    DependencyNotSatisfiedError,
    SecurityValidationError,
    sanitize_env,
    validate_cwd,
    validate_task_command,
    validate_dag_cycles,
)


def test_adversarial_env_sanitization() -> None:
    malicious_env = {
        "LD_PRELOAD": "/evil/libinject.so",
        "DYLD_INSERT_LIBRARIES": "/evil/libmac.dylib",
        "MY_CUSTOM_VAR": "clean_value",
    }
    clean = sanitize_env(malicious_env)
    assert "LD_PRELOAD" not in clean
    assert "DYLD_INSERT_LIBRARIES" not in clean
    assert clean["MY_CUSTOM_VAR"] == "clean_value"


def test_adversarial_invalid_command_tokens() -> None:
    with pytest.raises(SecurityValidationError):
        validate_task_command("")
    with pytest.raises(SecurityValidationError):
        validate_task_command([])
    with pytest.raises(SecurityValidationError):
        validate_task_command([123])


def test_adversarial_invalid_cwd(tmp_path) -> None:
    non_existent = tmp_path / "does_not_exist_xyz"
    with pytest.raises(SecurityValidationError):
        validate_cwd(non_existent)


def test_adversarial_dag_cycle_and_self_reference() -> None:
    # Direct self reference
    t1 = SwarmCronTask(id="self-loop", name="Self Loop", schedule="manual", command=["true"], depends_on=["self-loop"])
    cycles = validate_dag_cycles([t1])
    assert len(cycles) >= 1
    assert "self-reference" in cycles[0]


def test_adversarial_dag_runtime_dependency_enforcement(tmp_path) -> None:
    store_file = tmp_path / "tasks.json"
    registry = SwarmCronRegistry(path=store_file)

    upstream = SwarmCronTask(
        id="upstream-job",
        name="Upstream Job",
        schedule="manual",
        command=["python3", "-c", "import sys; sys.exit(1)"], # Fails
    )
    downstream = SwarmCronTask(
        id="downstream-job",
        name="Downstream Job",
        schedule="manual",
        command=["python3", "-c", "print('should not run')"],
        depends_on=["upstream-job"],
    )

    registry.register(upstream)
    registry.register(downstream)

    # 1. Run upstream -> fails
    res_up = registry.mutate("upstream-job", "run", enforce_dependencies=False)
    assert res_up["success"] is False

    # 2. Run downstream -> must raise DependencyNotSatisfiedError
    with pytest.raises(DependencyNotSatisfiedError):
        registry.mutate("downstream-job", "run", enforce_dependencies=True)


def test_adversarial_timeout_and_zombie_containment(tmp_path) -> None:
    store_file = tmp_path / "tasks.json"
    registry = SwarmCronRegistry(path=store_file)

    task = SwarmCronTask(
        id="slow-task",
        name="Slow Task",
        schedule="manual",
        command=["python3", "-c", "import time; time.sleep(10)"],
        timeout_seconds=1, # 1 second timeout
    )
    registry.register(task)

    res = registry.mutate("slow-task", "run")
    assert res["success"] is False
    assert res["receipt"]["status"] == "failed"
    assert res["receipt"]["exit_code"] == -1
    assert "timed out after 1s" in res["receipt"]["stderr"]


def test_adversarial_stdout_capping(tmp_path) -> None:
    store_file = tmp_path / "tasks.json"
    registry = SwarmCronRegistry(path=store_file)

    # Emit 200KB of text
    task = SwarmCronTask(
        id="heavy-logger",
        name="Heavy Logger",
        schedule="manual",
        command=["python3", "-c", "print('A' * 200000)"],
    )
    registry.register(task)

    res = registry.mutate("heavy-logger", "run")
    assert res["success"] is True
    # Captured output should be capped and marked
    assert len(res["receipt"]["stdout"]) < 120000
    assert "[SwarmCron: stdout truncated...]" in res["receipt"]["stdout"]


def test_pure_python_cron_schedule_evaluator() -> None:
    evaluator = CronScheduleEvaluator("*/15 9-17 * * 1-5")
    
    # Matches 9:15 on Wednesday
    wed_915 = datetime(2026, 8, 19, 9, 15, tzinfo=timezone.utc) # Wed
    assert evaluator.matches(wed_915) is True

    # Does not match 9:16
    wed_916 = datetime(2026, 8, 19, 9, 16, tzinfo=timezone.utc)
    assert evaluator.matches(wed_916) is False

    # Does not match on Sunday (dow 0)
    sun_915 = datetime(2026, 8, 23, 9, 15, tzinfo=timezone.utc)
    assert evaluator.matches(sun_915) is False

    # Next run calculation
    next_run = evaluator.get_next_run(from_dt=wed_915)
    assert next_run is not None
    assert next_run.minute == 30 and next_run.hour == 9
