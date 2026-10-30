from statuspage.uptime import DAY, bar_color, daily_bars, overall_uptime, uptime_pct

NOW = 1_800_000_000


def test_uptime_pct():
    assert uptime_pct([]) is None
    assert uptime_pct(["up"] * 99 + ["down"]) == 99.0
    assert uptime_pct(["degraded", "up"]) == 100.0


def test_bar_color():
    assert bar_color(None) == "nodata"
    assert bar_color(100) == "green"
    assert bar_color(99.5) == "yellow"
    assert bar_color(90) == "red"


def test_daily_bars():
    checks = [{"ts": NOW, "status": "up"}, {"ts": NOW - 10, "status": "down"},
              {"ts": NOW - DAY, "status": "up"}, {"ts": NOW - 200 * DAY, "status": "down"}]
    bars = daily_bars(checks, NOW)
    assert len(bars) == 90
    assert bars[-1]["uptime"] == 50.0 and bars[-1]["color"] == "red"
    assert bars[-2]["uptime"] == 100.0
    assert bars[0]["uptime"] is None
    assert overall_uptime(bars) == 75.0
    assert overall_uptime(daily_bars([], NOW)) is None
