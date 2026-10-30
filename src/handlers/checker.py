"""EventBridge-scheduled Lambda. Deployed in 2 regions; writes to the primary-region table."""
import os
import time

import boto3

from statuspage.checks import run_check

REGION = os.environ.get("AWS_REGION", "local")


def handler(event, context):
    ddb = boto3.resource("dynamodb", region_name=os.environ["TABLE_REGION"])
    monitors = ddb.Table(os.environ["MONITORS_TABLE"]).scan().get("Items", [])
    results = ddb.Table(os.environ["RESULTS_TABLE"])
    ttl = int(time.time()) + 95 * 86400
    with results.batch_writer() as bw:
        for m in monitors:
            r = run_check(m, REGION)
            item = r.to_item()
            item["pk"] = m["monitor_id"]
            item["sk"] = f"{r.ts}#{REGION}"
            item["expires"] = ttl
            bw.put_item(Item=item)
    return {"checked": len(monitors), "region": REGION}
