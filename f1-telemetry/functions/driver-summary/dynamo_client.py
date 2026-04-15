import os
import boto3

def get_table():
    endpoint = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
    table_name = os.environ.get("TABLE_NAME", "F1Telemetry")
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "local"),
    )
    return dynamodb.Table(table_name)
