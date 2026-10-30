from statuspage.auth import make_token, verify_token
from statuspage.plans import PLANS, can_add_monitor
from statuspage.render import render_status_page


def test_magic_link():
    t = make_token("A@b.com", "s", ttl=60, now=1000)
    assert verify_token(t, "s", now=1030) == "a@b.com"
    assert verify_token(t, "s", now=2000) is None
    assert verify_token(t, "other", now=1030) is None
    assert verify_token("garbage", "s") is None


def test_plans():
    assert PLANS["lifetime"]["price_usd"] == 29 and PLANS["hosted"]["price_usd"] == 5
    assert can_add_monitor("lifetime", 9) and not can_add_monitor("lifetime", 10)


def test_render_escapes_and_banner():
    html = render_status_page({"name": "<Acme>"}, [{"name": "API", "current": "down", "bars": [], "overall": None}], [])
    assert "&lt;Acme&gt;" in html and "Major outage" in html and "\u2014" not in html
