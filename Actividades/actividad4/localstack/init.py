import boto3
import os
import sys

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = "us-east-1"

AWS_KWARGS = dict(
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)


def create_dynamodb_tables():
    client = boto3.client("dynamodb", **AWS_KWARGS)
    existing = {t for t in client.list_tables()["TableNames"]}

    if "f1_sessions" not in existing:
        client.create_table(
            TableName="f1_sessions",
            AttributeDefinitions=[
                {"AttributeName": "session_key", "AttributeType": "N"},
            ],
            KeySchema=[
                {"AttributeName": "session_key", "KeyType": "HASH"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("✓ Tabla f1_sessions creada")
    else:
        print("- Tabla f1_sessions ya existe")

    if "f1_driver_stats" not in existing:
        client.create_table(
            TableName="f1_driver_stats",
            AttributeDefinitions=[
                {"AttributeName": "session_key", "AttributeType": "N"},
                {"AttributeName": "driver_number", "AttributeType": "N"},
            ],
            KeySchema=[
                {"AttributeName": "session_key", "KeyType": "HASH"},
                {"AttributeName": "driver_number", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        print("✓ Tabla f1_driver_stats creada")
    else:
        print("- Tabla f1_driver_stats ya existe")


def create_s3_bucket():
    client = boto3.client("s3", **AWS_KWARGS)
    existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}

    if "f1-raw-data" not in existing:
        client.create_bucket(Bucket="f1-raw-data")
        print("✓ Bucket f1-raw-data creado")
    else:
        print("- Bucket f1-raw-data ya existe")


def verify():
    ddb = boto3.client("dynamodb", **AWS_KWARGS)
    s3 = boto3.client("s3", **AWS_KWARGS)

    tables = ddb.list_tables()["TableNames"]
    buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]

    print("\n--- Verificación ---")
    print(f"Tablas DynamoDB: {tables}")
    print(f"Buckets S3:      {buckets}")

    ok = "f1_sessions" in tables and "f1_driver_stats" in tables and "f1-raw-data" in buckets
    if ok:
        print("\n✓ Todos los recursos están listos")
    else:
        print("\n✗ Faltan recursos — revisar errores arriba")
        sys.exit(1)


if __name__ == "__main__":
    print(f"Conectando a LocalStack en {ENDPOINT}...\n")
    try:
        create_dynamodb_tables()
        create_s3_bucket()
        verify()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("  ¿Está LocalStack corriendo? Ejecutá: make start")
        sys.exit(1)
