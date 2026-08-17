"""SwarmCron drop-in FastAPI router module.

Requires the ``fastapi`` optional dependency::

    pip install swarmcron[fastapi]
"""

from __future__ import annotations

from typing import Any, Dict

from .core import SwarmCronRegistry, Action

try:
    from fastapi import APIRouter, Body, Depends, HTTPException
except ImportError:
    raise ImportError(
        "FastAPI is required for swarmcron.fastapi_router. "
        "Install it with: pip install swarmcron[fastapi]"
    )


def create_cron_router(
    registry: SwarmCronRegistry | None = None,
    auth_dependency: Any = None,
) -> APIRouter:
    """Create a FastAPI router for SwarmCron task management.

    Args:
        registry: Optional custom SwarmCronRegistry instance. If None,
            a default registry is created using the standard store path.
        auth_dependency: Optional FastAPI dependency for authentication.
            When provided, all endpoints will require this dependency.

    Returns:
        A configured FastAPI APIRouter with ``/crons`` endpoints.
    """
    reg = registry or SwarmCronRegistry()

    dependencies = []
    if auth_dependency is not None:
        dependencies.append(Depends(auth_dependency))

    router = APIRouter(prefix="/crons", tags=["SwarmCron"], dependencies=dependencies)

    @router.get("")
    def list_crons(include_deleted: bool = False) -> Dict[str, Any]:
        """List all registered SwarmCron tasks."""
        tasks = reg.load()
        if not include_deleted:
            tasks = [t for t in tasks if t.state != "deleted"]
        return {"ok": True, "tasks": [t.to_dict() for t in tasks]}

    @router.post("/{task_id}/action")
    def mutate_cron_action(task_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        """Execute action (run, pause, resume, deactivate, activate, recover) on a SwarmCron task."""
        action: Action = payload.get("action", "run")
        try:
            return reg.mutate(task_id, action)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/{task_id}/register")
    def register_task(task_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        """Register a new task or update an existing one."""
        from .core import SwarmCronTask
        payload["id"] = task_id
        try:
            task = SwarmCronTask.from_dict(payload)
            reg.register(task)
            return {"ok": True, "task": task.to_dict()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    return router


# Backwards-compatible module-level router for simple usage:
#   from swarmcron.fastapi_router import router
router = create_cron_router()
