from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
)
from constructs import Construct


class DataStack(Stack):
    """
    Crea el almacenamiento principal de la aplicación F1:
      - Tabla DynamoDB f1_sessions          (PK: session_key  Number)
      - Tabla DynamoDB f1_driver_stats      (PK: session_key  Number, SK: driver_number Number)
      - Bucket S3      f1-raw-data          (guarda las respuestas crudas de la API)
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ------------------------------------------------------------------
        # DynamoDB: sesiones F1
        # Guarda metadata de cada sesión (circuito, fecha, tipo, etc.)
        # ------------------------------------------------------------------
        self.sessions_table = dynamodb.Table(
            self,
            "F1SessionsTable",
            table_name="f1_sessions",
            partition_key=dynamodb.Attribute(
                name="session_key",
                type=dynamodb.AttributeType.NUMBER,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # OK para dev/localstack
        )

        # ------------------------------------------------------------------
        # DynamoDB: stats de pilotos por sesión
        # Permite consultar todos los pilotos de una sesión, o un piloto
        # específico (session_key + driver_number).
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # S3: datos crudos
        # Guarda los JSON originales de la API OpenF1 antes de parsearlos.
        # Estructura de claves: sessions/{session_key}/raw.json
        #                       sessions/{session_key}/drivers.json
        # ------------------------------------------------------------------
        self.raw_bucket = s3.Bucket(
            self,
            "F1RawDataBucket",
            bucket_name="f1-raw-data",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
