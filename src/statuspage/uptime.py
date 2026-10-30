"""Uptime aggregation for the 90-day bars."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

DAY = 86400


def day_key(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def uptime_pct(statuses: list[str]) -> float | None:
    """'up' and 'degraded' count as available. None when there is no data."""
    if not statuses:
        return None
    ok = sum(1 for s in statuses if s in ("up", "degraded"))
    return round(100.0 * ok / len(statuses), 2)


def daily_bars(checks: list[dict], now_ts: int, days: int = 90) -> list[dict]:
    """Return `days` entries oldest-first: {date, uptime, color}."""
    by_day: dict[str, list[str]] = defaultdict(list)
    cutoff = now_ts - days * DAY
    for c in checks:
        if c["ts"] > cutoff - DAY:
            by_day[day_key(c["ts"])].append(c["status"])
    today = datetime.fromtimestamp(now_ts, tz=timezone.utc).date()
    out = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        pct = uptime_pct(by_day.get(d, []))
        out.append({"date": d, "uptime": pct, "color": bar_color(pct)})
    return out


def bar_color(pct: float | None) -> str:
    if pct is None:
        return "nodata"
    if pct >= 99.9:
        return "green"
    if pct >= 99.0:
        return "yellow"
    return "red"


def overall_uptime(bars: list[dict]) -> float | None:
    vals = [b["uptime"] for b in bars if b["uptime"] is not None]
    return round(sum(vals) / len(vals), 2) if vals else None
