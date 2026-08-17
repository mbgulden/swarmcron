"""SwarmCron pure-Python 5-field cron parser and schedule evaluator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence


def _parse_field(field_str: str, min_val: int, max_val: int) -> set[int]:
    """Parse a single cron field (minute, hour, dom, month, dow) into valid integers."""
    result: set[int] = set()
    for part in field_str.split(","):
        part = part.strip()
        if not part:
            continue
        if part == "*":
            result.update(range(min_val, max_val + 1))
        elif part.startswith("*/"):
            step = int(part[2:])
            result.update(range(min_val, max_val + 1, step))
        elif "-" in part:
            start_s, end_s = part.split("-", 1)
            result.update(range(int(start_s), int(end_s) + 1))
        else:
            val = int(part)
            if min_val <= val <= max_val:
                result.add(val)
    return result


class CronScheduleEvaluator:
    """Zero-dependency 5-field cron expression evaluator (minute, hour, dom, month, dow)."""

    def __init__(self, expression: str) -> None:
        self.expression = expression.strip()
        self.is_manual = self.expression == "manual"
        if not self.is_manual:
            parts = self.expression.split()
            if len(parts) != 5:
                raise ValueError(f"Invalid cron expression: expected 5 fields, got {len(parts)} ({expression})")
            self.minutes = _parse_field(parts[0], 0, 59)
            self.hours = _parse_field(parts[1], 0, 23)
            self.doms = _parse_field(parts[2], 1, 31)
            self.months = _parse_field(parts[3], 1, 12)
            # Sunday is 0 or 7
            dows = _parse_field(parts[4], 0, 7)
            if 7 in dows:
                dows.add(0)
            self.dows = dows

    def matches(self, dt: datetime) -> bool:
        """Check if datetime matches the cron schedule."""
        if self.is_manual:
            return False
        # In Python weekday: Monday is 0, Sunday is 6. Cron: Sunday is 0.
        cron_dow = (dt.weekday() + 1) % 7
        return (
            dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.day in self.doms
            and dt.month in self.months
            and cron_dow in self.dows
        )

    def get_next_run(self, from_dt: datetime | None = None, max_iterations: int = 525600) -> datetime | None:
        """Compute the next scheduled run datetime from given starting point (default: now in UTC)."""
        if self.is_manual:
            return None
        current = (from_dt or datetime.now(timezone.utc)).replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(max_iterations):
            if self.matches(current):
                return current
            current += timedelta(minutes=1)
        return None

    def is_missed(self, last_run_at: str | None, now: datetime | None = None, grace_minutes: int = 15) -> bool:
        """Check if a scheduled cron execution window was missed."""
        if self.is_manual:
            return False
        current_time = now or datetime.now(timezone.utc)
        if not last_run_at:
            return False  # Never ran yet
        try:
            last_dt = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
            next_after_last = self.get_next_run(from_dt=last_dt)
            if next_after_last and (current_time - next_after_last) > timedelta(minutes=grace_minutes):
                return True
        except Exception:
            return False
        return False
