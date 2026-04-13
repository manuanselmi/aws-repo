#!/usr/bin/env python3
"""
CDK App — Actividad 4: S3, DynamoDB y EventBridge

Stacks:
  F1DataStack      → DynamoDB tables + S3 bucket
  F1LambdaStack    → Lambda de ingesta (depende de DataStack)
  F1MessagingStack → EventBridge rule (depende de LambdaStack)

Para LocalStack usar cdklocal en lugar de cdk:
  cdklocal bootstrap
  cdklocal deploy --all
"""
import aws_cdk as cdk

from stacks.data_stack import DataStack
from stacks.lambda_stack import LambdaStack
from stacks.messaging_stack import MessagingStack

app = cdk.App()

# Cuenta/región para LocalStack (cdklocal usa 000000000000 / us-east-1)
env = cdk.Environment(account="000000000000", region="us-east-1")

# 1. Recursos de almacenamiento
data_stack = DataStack(app, "F1DataStack", env=env)

# 2. Lambda de ingesta — recibe referencias del DataStack
lambda_stack = LambdaStack(
    app,
    "F1LambdaStack",
    raw_bucket=data_stack.raw_bucket,
    sessions_table=data_stack.sessions_table,
    driver_stats_table=data_stack.driver_stats_table,
    env=env,
)
lambda_stack.add_dependency(data_stack)

# 3. EventBridge rule — apunta a la Lambda del LambdaStack
messaging_stack = MessagingStack(
    app,
    "F1MessagingStack",
    ingest_function=lambda_stack.ingest_function,
    env=env,
)
messaging_stack.add_dependency(lambda_stack)

app.synth()
