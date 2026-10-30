"""HTTP check logic. Pure functions plus a thin urllib runner (no extra deps)."""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Callable

DEFAULT_TIMEOUT = 10.0
SLOW_MS = 5000


@dataclass
class CheckResult:
    monitor_id: str
    region: str
    ts: int  # epoch seconds
    status: str  # "up" | "degraded" | "down"
    http_status: int | None
    latency_ms: int | None
    error: str | None = None

    def to_item(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


def classify(http_status: int | None, latency_ms: int | None, expected: tuple[int, ...] | None = None,
             error: str | None = None, slow_ms: int = SLOW_MS) -> str:
    if error is not None or http_status is None:
        return "down"
    ok = (http_status in expected) if expected else 200 <= http_status < 400
    if not ok:
        return "down"
    if latency_ms is not None and latency_ms > slow_ms:
        return "degraded"
    return "up"


def _fetch(url: str, timeout: float) -> int:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "statuspage-mvp-checker/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def run_check(monitor: dict, region: str, fetch: Callable[[str, float], int] = _fetch,
              clock: Callable[[], float] = time.time) -> CheckResult:
    url = monitor["url"]
    if not url.startswith(("http://", "https://")):
        return CheckResult(monitor["monitor_id"], region, int(clock()), "down", None, None, "invalid url")
    expected = tuple(monitor["expected_status"]) if monitor.get("expected_status") else None
    start = time.perf_counter()
    try:
        code = fetch(url, float(monitor.get("timeout", DEFAULT_TIMEOUT)))
        err = None
    except Exception as e:  # network errors, timeouts, DNS
        code, err = None, type(e).__name__
    latency = int((time.perf_counter() - start) * 1000)
    status = classify(code, latency if err is None else None, expected, err)
    return CheckResult(monitor["monitor_id"], region, int(clock()), status, code,
                       latency if err is None else None, err)


def combine_regions(results: list[CheckResult]) -> str:
    """A monitor is only 'down' if every region says down. One region failing = degraded
    (protects against a single network blip causing a false alarm)."""
    if not results:
        return "unknown"
    states = {r.status for r in results}
    if states == {"down"}:
        return "down"
    if "down" in states or "degraded" in states:
        return "degraded"
    return "up"


def should_alert(previous: str | None, current: str) -> bool:
    """Alert on transitions into or out of 'down' only."""
    if previous is None:
        return current == "down"
    return previous != current and "down" in (previous, current)
