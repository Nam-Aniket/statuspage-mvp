# Status page MVP

Hosted, zero setup, $5. A cheap hosted alternative to Atlassian Statuspage (paid plans from US$29/mo per https://www.atlassian.com/software/statuspage/pricing; Instatus Pro US$20/mo per https://instatus.com/pricing).

## Architecture

- **Checker Lambda** (`src/handlers/checker.py`), deployed in 2 regions (default `us-east-1`, `eu-west-1`), runs every minute via EventBridge. It does an HTTP GET on each monitor and writes results to DynamoDB `sp-results` in the primary region (TTL 95 days).
- **Publisher Lambda** (`src/handlers/publisher.py`), primary region, every 5 minutes. Combines regions (down only if all regions agree, otherwise degraded), sends SES email alerts on transitions into or out of down, builds 90-day uptime bars and renders static HTML to S3 at `s/<slug>/index.html`.
- **S3 + CloudFront** (OAC, HTTPS) serve the landing page (`site/index.html`) and status pages. Optional custom domain: pass `-c domain=status.example.com -c hosted_zone=example.com` to create an ACM cert (DNS validated, us-east-1) and a Route 53 alias.
- **API Lambda** (Function URL, `src/handlers/api.py`): `/login` and `/verify` (HMAC-signed magic links, 15 min expiry, sent via SES), `/checkout` (Stripe Checkout, test mode only; refuses anything but an `sk_test_` key), `/stripe/webhook`.
- **Plans** (`src/statuspage/plans.py`): Lifetime US$29 once, Hosted US$5/mo. Both: 1 page, 10 monitors.
- DynamoDB tables: `sp-monitors`, `sp-results`, `sp-pages` (on-demand).

Out of scope: SMS, SSO, teams.

## Local dev

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
npm install -g aws-cdk   # or use npx cdk
pytest -q
npx cdk synth -q
python -c "import sys; sys.path.insert(0,'src'); from statuspage.render import render_status_page as r; open('/tmp/p.html','w').write(r({'name':'Demo'},[],[]))"
```

## Deploy (not done yet)

1. AWS account + credentials; `npx cdk bootstrap aws://ACCOUNT/us-east-1 aws://ACCOUNT/eu-west-1`.
2. Verify a sender in SES and request production access (SES sandbox only mails verified addresses).
3. Create Stripe test products/prices (US$29 one-time, US$5 recurring monthly).
4. Put secrets in SSM/Secrets Manager and wire them in (currently placeholder env values in `infra/stacks.py`): `STRIPE_SECRET_KEY`, `STRIPE_PRICE_LIFETIME`, `STRIPE_PRICE_MONTHLY`, `STRIPE_WEBHOOK_SECRET`, `MAGIC_LINK_SECRET`.
5. `npx cdk deploy --all -c alert_from=alerts@yourdomain [-c domain=... -c hosted_zone=...]`
6. Set `window.API_URL` in `site/index.html` to the `ApiUrl` output; register the webhook URL in Stripe.
7. Seed a page in `sp-pages` and monitors in `sp-monitors`; first live page should be the product's own status.

## Cost estimate (estimate only, not measured)

Rough guess for a small number of customers (around 100 monitors): Lambda checks every minute from 2 regions (~8.6M short invocations/mo if one invocation per monitor; this MVP batches all monitors into one invocation per region, so ~86k invocations/mo), DynamoDB on-demand writes for ~8.6M results/mo (a few US$ at on-demand write pricing), S3/CloudFront pennies at low traffic, SES US$0.10 per 1,000 emails. Ballpark US$5 to US$15/mo. Check https://aws.amazon.com/lambda/pricing/ and https://aws.amazon.com/dynamodb/pricing/ before relying on it. DynamoDB writes are the main cost driver; aggregate to daily rollups if it grows.

## Stubbed / TODO

- Stripe webhook signature verification and marking the account's plan.
- Dashboard UI for adding monitors and writing incidents (data model supports `incidents` on a page item).
- Per-customer custom domains (current ACM setup covers one domain plus wildcard).
- Plan limits enforced only in `can_add_monitor`, not yet at an API endpoint.
- Checker runs monitors sequentially; parallelise for scale.
