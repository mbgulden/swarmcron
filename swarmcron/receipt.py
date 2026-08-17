"""SwarmCron machine execution receipt dataclass and recorder."""

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class CronRunReceipt:
    task_id: str
    ran_at: str
    status: str  # "success" | "failed"
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
