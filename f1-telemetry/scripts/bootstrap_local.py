"""
Bootstrap local: crea tabla DynamoDB, colas SQS (SimulationQueue + SimulationDLQ).
Idempotente: si ya existen, no falla.
"""
import os
import time

import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:4566")
SQS_ENDPOINT = os.environ.get("SQS_ENDPOINT", "http://localhost:4566")
TABLE_NAME = os.environ.get("TABLE_NAME", "F1Telemetry")
REGION = "us-east-1"
KEY_ID = "test"
SECRET = "test"


def wait_for_localstack(max_attempts=30):
    import urllib.request
    url = ENDPOINT.replace("4566", "4566") + "/_localstack/health"
    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(
                url.replace(":4566/_localstack", ":4566/_localstack"), timeout=3
            ):
                print("LocalStack disponible.")
                return
        except Exception:
            print(f"Esperando LocalStack... intento {attempt + 1}/{max_attempts}")
            time.sleep(2)
    raise RuntimeError("LocalStack no disponible.")


def create_table():
    dynamo = boto3.client(
        "dynamodb",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=KEY_ID,
        aws_secret_access_key=SECRET,
    )
    try:
        dynamo.create_table(
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
            print(f"Tabla '{TABLE_NAME}' ya existe.")
        else:
            raise


def create_queues():
    sqs = boto3.client(
        "sqs",
        endpoint_url=SQS_ENDPOINT,
        region_name=REGION,
        aws_access_key_id=KEY_ID,
        aws_secret_access_key=SECRET,
    )

    # DLQ
    try:
        dlq = sqs.create_queue(QueueName="SimulationDLQ")
        print(f"Cola SimulationDLQ creada: {dlq['QueueUrl']}")
    except ClientError as e:
        if "QueueAlreadyExists" in str(e):
            print("Cola SimulationDLQ ya existe.")
        else:
            raise

    # Obtener ARN de DLQ
    dlq_url = sqs.get_queue_url(QueueName="SimulationDLQ")["QueueUrl"]
    dlq_attrs = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"]
    )
    dlq_arn = dlq_attrs["Attributes"]["QueueArn"]

    # Main queue con redrive
    try:
        main_q = sqs.create_queue(
            QueueName="SimulationQueue",
            Attributes={
                "RedrivePolicy": f'{{"maxReceiveCount":"3","deadLetterTargetArn":"{dlq_arn}"}}',
                "VisibilityTimeout": "3600",
            },
        )
        print(f"Cola SimulationQueue creada: {main_q['QueueUrl']}")
    except ClientError as e:
        if "QueueAlreadyExists" in str(e):
            print("Cola SimulationQueue ya existe.")
        else:
            raise

    # Siempre actualizar VisibilityTimeout (idempotente, cubre colas pre-existentes)
    main_url = sqs.get_queue_url(QueueName="SimulationQueue")["QueueUrl"]
    sqs.set_queue_attributes(
        QueueUrl=main_url,
        Attributes={"VisibilityTimeout": "3600"},
    )
    print("SimulationQueue VisibilityTimeout=3600 actualizado.")


def main():
    print("=== Bootstrap local F1 Telemetry ===")
    wait_for_localstack()
    create_table()
    create_queues()
    print("\n=== Bootstrap completado ===")
    print(f"  DynamoDB tabla: {TABLE_NAME}")
    print("  SQS colas: SimulationQueue, SimulationDLQ")
    print(f"  Endpoint: {ENDPOINT}")


if __name__ == "__main__":
    main()
