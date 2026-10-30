"""Render the public status page as static HTML (uploaded to S3, served by CloudFront)."""
from __future__ import annotations

import html


def render_status_page(page: dict, monitors: list[dict], incidents: list[dict]) -> str:
    """monitors: [{name, current, bars, overall}], incidents: [{title, status, body, started}]"""
    worst = "up"
    for m in monitors:
        if m["current"] == "down":
            worst = "down"
        elif m["current"] == "degraded" and worst != "down":
            worst = "degraded"
    banner = {"up": "All systems operational", "degraded": "Some systems degraded",
              "down": "Major outage"}[worst]
    rows = []
    for m in monitors:
        bars = "".join(
            f'<span class="bar {b["color"]}" title="{b["date"]}: '
            f'{"no data" if b["uptime"] is None else str(b["uptime"]) + "%"}"></span>'
            for b in m["bars"])
        ov = "no data" if m.get("overall") is None else f'{m["overall"]}% uptime'
        rows.append(f'<div class="mon"><div class="row"><b>{html.escape(m["name"])}</b>'
                    f'<span class="st {m["current"]}">{m["current"]}</span></div>'
                    f'<div class="bars">{bars}</div><small>90 days ago, {ov}, today</small></div>')
    inc = "".join(
        f'<li><b>{html.escape(i["title"])}</b> ({html.escape(i["status"])}, {html.escape(i["started"])})'
        f'<p>{html.escape(i.get("body", ""))}</p></li>' for i in incidents) or "<li>No recent incidents.</li>"
    title = html.escape(page["name"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} status</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#222}}
.banner{{padding:1rem;border-radius:8px;color:#fff;font-weight:600}}.banner.up{{background:#2e9d5b}}
.banner.degraded{{background:#d9a400}}.banner.down{{background:#c8372d}}.mon{{margin:1.5rem 0}}
.row{{display:flex;justify-content:space-between}}.bars{{display:flex;gap:2px;margin:.4rem 0}}
.bar{{flex:1;height:28px;border-radius:2px}}.green{{background:#2e9d5b}}.yellow{{background:#d9a400}}
.red{{background:#c8372d}}.nodata{{background:#ddd}}.st.up{{color:#2e9d5b}}.st.degraded{{color:#b38700}}
.st.down{{color:#c8372d}}</style></head><body><h1>{title}</h1>
<div class="banner {worst}">{banner}</div>{"".join(rows)}<h2>Incidents</h2><ul>{inc}</ul>
</body></html>"""
