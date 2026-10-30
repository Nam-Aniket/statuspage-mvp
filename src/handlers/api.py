"""HTTP API (Lambda Function URL): magic-link login, Stripe Checkout, Stripe webhook.
Stripe is called over its REST API with urllib, using STRIPE_SECRET_KEY (test mode key, sk_test_...)."""
import json
import os
import urllib.parse
import urllib.request

from statuspage.alerts import send_alert
from statuspage.auth import make_token, verify_token
from statuspage.plans import PLANS


def _resp(code, body):
    return {"statusCode": code, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def create_checkout(plan: str, email: str) -> dict:
    p = PLANS[plan]
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        return {"stub": True, "reason": "STRIPE_SECRET_KEY not set to a test key", "plan": plan}
    base = os.environ.get("APP_URL", "http://localhost:8000")
    data = urllib.parse.urlencode({
        "mode": p["mode"], "customer_email": email,
        "line_items[0][price]": os.environ[p["price_env"]], "line_items[0][quantity]": 1,
        "success_url": f"{base}/?paid=1", "cancel_url": f"{base}/?cancelled=1",
        "metadata[plan]": plan}).encode()
    req = urllib.request.Request("https://api.stripe.com/v1/checkout/sessions", data=data,
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        s = json.loads(r.read())
    return {"url": s["url"]}


def handler(event, context):
    path = event.get("rawPath", "/")
    body = json.loads(event.get("body") or "{}")
    secret = os.environ.get("MAGIC_LINK_SECRET", "dev-only-secret")
    if path == "/login":
        token = make_token(body["email"], secret)
        link = f"{os.environ.get('APP_URL', 'http://localhost:8000')}/verify?token={token}"
        send_alert(body["email"], "Your sign-in link", f"Sign in: {link}\nThis link expires in 15 minutes.")
        return _resp(200, {"sent": True})
    if path == "/verify":
        email = verify_token((event.get("queryStringParameters") or {}).get("token", ""), secret)
        return _resp(200, {"email": email}) if email else _resp(401, {"error": "invalid or expired link"})
    if path == "/checkout":
        if body.get("plan") not in PLANS:
            return _resp(400, {"error": "unknown plan"})
        return _resp(200, create_checkout(body["plan"], body.get("email", "")))
    if path == "/stripe/webhook":
        # TODO: verify Stripe-Signature with STRIPE_WEBHOOK_SECRET, then mark account plan in DynamoDB.
        return _resp(200, {"received": True})
    return _resp(404, {"error": "not found"})
