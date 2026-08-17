"""SwarmCron — Zero-dependency DAG cron scheduler & machine receipt engine."""

from .core import (
    SwarmCronTask,
    SwarmCronRegistry,
    validate_dag_cycles,
    DependencyNotSatisfiedError,
    TaskAlreadyRunningError,
    CRON_STATE_ACTIVE,
    CRON_STATE_PAUSED,
    CRON_STATE_DEACTIVATED,
    CRON_STATE_DELETED,
)
from .receipt import CronRunReceipt
from .scheduler import CronScheduleEvaluator
from .security import SecurityValidationError, sanitize_env, validate_cwd, validate_task_command
from .locking import FileLock, TaskExecutionLock

__version__ = "0.2.0"
__all__ = [
    "SwarmCronTask",
    "SwarmCronRegistry",
    "CronRunReceipt",
    "CronScheduleEvaluator",
    "FileLock",
    "TaskExecutionLock",
    "validate_dag_cycles",
    "DependencyNotSatisfiedError",
    "TaskAlreadyRunningError",
    "SecurityValidationError",
    "sanitize_env",
    "validate_cwd",
    "validate_task_command",
    "CRON_STATE_ACTIVE",
    "CRON_STATE_PAUSED",
    "CRON_STATE_DEACTIVATED",
    "CRON_STATE_DELETED",
]
