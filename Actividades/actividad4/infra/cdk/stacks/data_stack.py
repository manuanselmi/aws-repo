from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
)
from constructs import Construct


class DataStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.sessions_table = dynamodb.Table(
            self,
            "F1SessionsTable",
            table_name="f1_sessions",
            partition_key=dynamodb.Attribute(
                name="session_key",
                type=dynamodb.AttributeType.NUMBER,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.driver_stats_table = dynamodb.Table(
            self,
            "F1DriverStatsTable",
            table_name="f1_driver_stats",
            partition_key=dynamodb.Attribute(
                name="session_key",
                type=dynamodb.AttributeType.NUMBER,
            ),
            sort_key=dynamodb.Attribute(
                name="driver_number",
                type=dynamodb.AttributeType.NUMBER,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.raw_bucket = s3.Bucket(
            self,
            "F1RawDataBucket",
            bucket_name="f1-raw-data",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
