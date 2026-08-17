"""SwarmCron drop-in FastAPI router module."""

from typing import Any, Dict
from fastapi import APIRouter, Body, HTTPException
from .core import SwarmCronRegistry, Action

router = APIRouter(prefix="/crons", tags=["SwarmCron"])
_registry = SwarmCronRegistry()


@router.get("")
def list_crons(include_deleted: bool = False) -> Dict[str, Any]:
    """List all registered SwarmCron tasks."""
    tasks = _registry.load()
    if not include_deleted:
        tasks = [t for t in tasks if t.state != "deleted"]
    return {"ok": True, "tasks": [t.to_dict() for t in tasks]}


@router.post("/{task_id}/action")
def mutate_cron_action(task_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Execute action (run, pause, resume, deactivate, recover) on a SwarmCron task."""
    action: Action = payload.get("action", "run")
    try:
        return _registry.mutate(task_id, action)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
