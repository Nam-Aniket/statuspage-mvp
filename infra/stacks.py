from aws_cdk import (Duration, RemovalPolicy, Stack, CfnOutput,
                     aws_certificatemanager as acm, aws_cloudfront as cf,
                     aws_cloudfront_origins as origins, aws_dynamodb as ddb,
                     aws_events as events, aws_events_targets as targets, aws_iam as iam,
                     aws_lambda as lambda_, aws_route53 as r53, aws_route53_targets as r53t,
                     aws_s3 as s3, aws_s3_deployment as s3d)
from constructs import Construct

MONITORS_TABLE = "sp-monitors"
RESULTS_TABLE = "sp-results"
PAGES_TABLE = "sp-pages"
def code():
    return lambda_.Code.from_asset("src", exclude=["**/__pycache__"])
RUNTIME = lambda_.Runtime.PYTHON_3_12


class CoreStack(Stack):
    """Primary region (us-east-1, required for CloudFront ACM certs)."""

    def __init__(self, scope: Construct, id: str, *, domain: str | None = None,
                 hosted_zone: str | None = None, alert_from: str = "", **kw):
        super().__init__(scope, id, **kw)
        pk = ddb.Attribute(name="pk", type=ddb.AttributeType.STRING)
        monitors = ddb.Table(self, "Monitors", table_name=MONITORS_TABLE,
                             partition_key=ddb.Attribute(name="monitor_id", type=ddb.AttributeType.STRING),
                             billing_mode=ddb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.RETAIN)
        results = ddb.Table(self, "Results", table_name=RESULTS_TABLE, partition_key=pk,
                            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
                            time_to_live_attribute="expires",
                            billing_mode=ddb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.RETAIN)
        pages = ddb.Table(self, "Pages", table_name=PAGES_TABLE,
                          partition_key=ddb.Attribute(name="page_id", type=ddb.AttributeType.STRING),
                          billing_mode=ddb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.RETAIN)

        bucket = s3.Bucket(self, "Site", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                           enforce_ssl=True, removal_policy=RemovalPolicy.RETAIN)

        cert, names, zone = None, None, None
        if domain and hosted_zone:
            zone = r53.HostedZone.from_lookup(self, "Zone", domain_name=hosted_zone)
            cert = acm.Certificate(self, "Cert", domain_name=domain,
                                   subject_alternative_names=[f"*.{domain}"],
                                   validation=acm.CertificateValidation.from_dns(zone))
            names = [domain, f"*.{domain}"]
        dist = cf.Distribution(self, "Cdn",
                               default_behavior=cf.BehaviorOptions(
                                   origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                                   viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS),
                               default_root_object="index.html", certificate=cert, domain_names=names)
        if zone:
            r53.ARecord(self, "Alias", zone=zone, record_name=domain,
                        target=r53.RecordTarget.from_alias(r53t.CloudFrontTarget(dist)))
        s3d.BucketDeployment(self, "Landing", sources=[s3d.Source.asset("site")],
                             destination_bucket=bucket, distribution=dist, prune=False)

        env = {"MONITORS_TABLE": MONITORS_TABLE, "RESULTS_TABLE": RESULTS_TABLE, "PAGES_TABLE": PAGES_TABLE,
               "SITE_BUCKET": bucket.bucket_name, "ALERT_FROM_EMAIL": alert_from}
        publisher = lambda_.Function(self, "Publisher", runtime=RUNTIME, code=code(),
                                     handler="handlers.publisher.handler", timeout=Duration.minutes(2),
                                     memory_size=256, environment=env)
        for t in (monitors, results, pages):
            t.grant_read_write_data(publisher)
        bucket.grant_put(publisher)
        publisher.add_to_role_policy(iam.PolicyStatement(actions=["ses:SendEmail"], resources=["*"]))
        events.Rule(self, "PublishEvery5", schedule=events.Schedule.rate(Duration.minutes(5)),
                    targets=[targets.LambdaFunction(publisher)])

        # Secrets are injected at deploy time via env/SSM; placeholders only here.
        api = lambda_.Function(self, "Api", runtime=RUNTIME, code=code(), handler="handlers.api.handler",
                               timeout=Duration.seconds(15), environment={
                                   **env, "STRIPE_SECRET_KEY": "set-me-sk_test",
                                   "STRIPE_PRICE_LIFETIME": "price_set_me", "STRIPE_PRICE_MONTHLY": "price_set_me",
                                   "MAGIC_LINK_SECRET": "set-me", "APP_URL": f"https://{domain or dist.distribution_domain_name}"})
        api.add_to_role_policy(iam.PolicyStatement(actions=["ses:SendEmail"], resources=["*"]))
        monitors.grant_read_write_data(api)
        url = api.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        CfnOutput(self, "CdnDomain", value=dist.distribution_domain_name)
        CfnOutput(self, "ApiUrl", value=url.url)


class CheckerStack(Stack):
    """Deployed once per check region. Writes to the primary-region tables by name."""

    def __init__(self, scope: Construct, id: str, *, table_region: str, account: str | None, **kw):
        super().__init__(scope, id, **kw)
        fn = lambda_.Function(self, "Checker", runtime=RUNTIME, code=code(), handler="handlers.checker.handler",
                              timeout=Duration.seconds(55), memory_size=256,
                              environment={"MONITORS_TABLE": MONITORS_TABLE, "RESULTS_TABLE": RESULTS_TABLE,
                                           "TABLE_REGION": table_region})
        acct = account or self.account
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["dynamodb:Scan", "dynamodb:BatchWriteItem", "dynamodb:PutItem"],
            resources=[f"arn:aws:dynamodb:{table_region}:{acct}:table/{MONITORS_TABLE}",
                       f"arn:aws:dynamodb:{table_region}:{acct}:table/{RESULTS_TABLE}"]))
        events.Rule(self, "Every1Min", schedule=events.Schedule.rate(Duration.minutes(1)),
                    targets=[targets.LambdaFunction(fn)])
