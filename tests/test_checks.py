from statuspage.checks import CheckResult, classify, combine_regions, run_check, should_alert


def test_classify():
    assert classify(200, 100) == "up"
    assert classify(301, 100) == "up"
    assert classify(500, 100) == "down"
    assert classify(404, 100) == "down"
    assert classify(200, 6000) == "degraded"
    assert classify(None, None, error="URLError") == "down"
    assert classify(404, 50, expected=(404,)) == "up"
    assert classify(200, 50, expected=(204,)) == "down"


def test_run_check_ok():
    r = run_check({"monitor_id": "m1", "url": "https://x.test"}, "us-east-1", fetch=lambda u, t: 200, clock=lambda: 1000)
    assert (r.status, r.http_status, r.ts, r.region) == ("up", 200, 1000, "us-east-1")
    assert r.latency_ms is not None and "error" not in r.to_item()


def test_run_check_exception_and_invalid():
    def boom(u, t):
        raise TimeoutError()
    r = run_check({"monitor_id": "m1", "url": "https://x.test"}, "eu-west-1", fetch=boom)
    assert r.status == "down" and r.error == "TimeoutError" and r.latency_ms is None
    assert run_check({"monitor_id": "m", "url": "ftp://x"}, "r").error == "invalid url"


def _r(s):
    return CheckResult("m", "r", 0, s, None, None)


def test_combine_regions():
    assert combine_regions([_r("up"), _r("up")]) == "up"
    assert combine_regions([_r("up"), _r("down")]) == "degraded"
    assert combine_regions([_r("down"), _r("down")]) == "down"
    assert combine_regions([]) == "unknown"


def test_should_alert():
    assert should_alert("up", "down")
    assert should_alert("down", "up")
    assert not should_alert("up", "degraded")
    assert not should_alert("down", "down")
    assert should_alert(None, "down") and not should_alert(None, "up")
