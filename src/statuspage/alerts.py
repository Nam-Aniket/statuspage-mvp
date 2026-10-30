"""Email alerts via SES."""
from __future__ import annotations

import os


def build_alert(monitor_name: str, url: str, previous: str | None, current: str) -> tuple[str, str]:
    if current == "down":
        subj = f"[DOWN] {monitor_name} is not responding"
    else:
        subj = f"[RECOVERED] {monitor_name} is {current} again"
    body = f"Monitor: {monitor_name}\nURL: {url}\nPrevious state: {previous or 'unknown'}\nCurrent state: {current}\n"
    return subj, body


def send_alert(to: str, subject: str, body: str, ses_client=None) -> None:
    sender = os.environ.get("ALERT_FROM_EMAIL", "")
    if not sender or os.environ.get("DRY_RUN") == "1":
        print(f"[dry-run alert] to={to} subject={subject}")
        return
    import boto3
    ses = ses_client or boto3.client("ses")
    ses.send_email(Source=sender, Destination={"ToAddresses": [to]},
                   Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}})
