#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.data_stack import DataStack
from stacks.lambda_stack import LambdaStack
from stacks.messaging_stack import MessagingStack

app = cdk.App()

env = cdk.Environment(account="000000000000", region="us-east-1")

data_stack = DataStack(app, "F1DataStack", env=env)

lambda_stack = LambdaStack(
    app,
    "F1LambdaStack",
    raw_bucket=data_stack.raw_bucket,
    sessions_table=data_stack.sessions_table,
    driver_stats_table=data_stack.driver_stats_table,
    env=env,
)
lambda_stack.add_dependency(data_stack)

messaging_stack = MessagingStack(
    app,
    "F1MessagingStack",
    ingest_function=lambda_stack.ingest_function,
    env=env,
)
messaging_stack.add_dependency(lambda_stack)

app.synth()
