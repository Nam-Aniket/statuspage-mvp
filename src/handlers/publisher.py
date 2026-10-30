"""Runs every few minutes in the primary region: combines regions, sends alerts, renders pages to S3."""
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

from statuspage.alerts import build_alert, send_alert
from statuspage.checks import CheckResult, combine_regions, should_alert
from statuspage.render import render_status_page
from statuspage.uptime import daily_bars, overall_uptime


def handler(event, context):
    ddb = boto3.resource("dynamodb")
    s3 = boto3.client("s3")
    mon_t = ddb.Table(os.environ["MONITORS_TABLE"])
    res_t = ddb.Table(os.environ["RESULTS_TABLE"])
    pages_t = ddb.Table(os.environ["PAGES_TABLE"])
    now = int(time.time())
    for page in pages_t.scan().get("Items", []):
        monitors = [m for m in mon_t.scan().get("Items", []) if m.get("page_id") == page["page_id"]]
        view = []
        for m in monitors:
            items = res_t.query(KeyConditionExpression=Key("pk").eq(m["monitor_id"])
                                & Key("sk").gte(str(now - 90 * 86400))).get("Items", [])
            for i in items:
                i["ts"] = int(i["ts"])
            latest = [CheckResult(m["monitor_id"], i["region"], i["ts"], i["status"], None, None)
                      for i in items if i["ts"] >= now - 600]
            current = combine_regions(latest)
            if should_alert(m.get("last_state"), current) and page.get("alert_email"):
                send_alert(page["alert_email"], *build_alert(m["name"], m["url"], m.get("last_state"), current))
            mon_t.update_item(Key={"monitor_id": m["monitor_id"]},
                              UpdateExpression="SET last_state=:s", ExpressionAttributeValues={":s": current})
            bars = daily_bars(items, now)
            view.append({"name": m["name"], "current": current, "bars": bars, "overall": overall_uptime(bars)})
        body = render_status_page(page, view, page.get("incidents", []))
        s3.put_object(Bucket=os.environ["SITE_BUCKET"], Key=f"s/{page['slug']}/index.html",
                      Body=body.encode(), ContentType="text/html", CacheControl="max-age=60")
    return {"ok": True}
