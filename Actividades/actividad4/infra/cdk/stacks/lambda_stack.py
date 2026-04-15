import os
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class LambdaStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        raw_bucket: s3.Bucket,
        sessions_table: dynamodb.Table,
        driver_stats_table: dynamodb.Table,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.ingest_function = lambda_.Function(
            self,
            "F1IngestFunction",
            function_name="f1-ingest",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "../../../lambdas/ingest")
            ),
            handler="handler.lambda_handler",
            timeout=Duration.seconds(120),
            memory_size=512,
            environment={
                "SESSIONS_TABLE": sessions_table.table_name,
                "DRIVER_STATS_TABLE": driver_stats_table.table_name,
                "RAW_BUCKET": raw_bucket.bucket_name,
            },
        )

        raw_bucket.grant_read_write(self.ingest_function)
        sessions_table.grant_read_write_data(self.ingest_function)
        driver_stats_table.grant_read_write_data(self.ingest_function)
