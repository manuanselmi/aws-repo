"""
Crea la tabla F1Telemetry en DynamoDB Local.
Correr UNA SOLA VEZ luego de levantar el contenedor de Docker.

Uso:
    python3 scripts/create_table.py
"""
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.client(
    "dynamodb",
    endpoint_url="http://localhost:4566",
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
    print(f"Tabla '{TABLE_NAME}' creada exitosamente.")
except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print(f"La tabla '{TABLE_NAME}' ya existe. OK.")
    else:
        raise

# Verificar
tables = dynamodb.list_tables()["TableNames"]
print(f"Tablas en DynamoDB Local: {tables}")
