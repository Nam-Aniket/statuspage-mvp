#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.stacks import CheckerStack, CoreStack

app = cdk.App()
account = os.environ.get("CDK_DEFAULT_ACCOUNT")
primary = "us-east-1"
check_regions = app.node.try_get_context("check_regions") or ["us-east-1", "eu-west-1"]

core = CoreStack(app, "StatusPageCore", env=cdk.Environment(account=account, region=primary),
                 domain=app.node.try_get_context("domain"), hosted_zone=app.node.try_get_context("hosted_zone"),
                 alert_from=app.node.try_get_context("alert_from") or "")
for r in check_regions:
    s = CheckerStack(app, f"StatusPageChecker-{r}", table_region=primary, account=account,
                     env=cdk.Environment(account=account, region=r))
    s.add_dependency(core)
app.synth()
