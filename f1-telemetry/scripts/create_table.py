import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.client(
    "dynamodb",
    endpoint_url="http://localhost:8000",
    region_name="us-east-1",
    aws_access_key_id="local",
    aws_secret_access_key="local",
)

TABLE_NAME = "F1Telemetry"

try:
    dynamodb.create_table(
        TableName=TABLE_NAME,
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"Tabla '{TABLE_NAME}' creada.")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print(f"La tabla '{TABLE_NAME}' ya existe.")
    else:
        raise

tables = dynamodb.list_tables()["TableNames"]
print(f"Tablas en DynamoDB Local: {tables}")
