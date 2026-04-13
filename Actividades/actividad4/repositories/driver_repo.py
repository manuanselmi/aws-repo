"""
DriverRepository — abstracción sobre la tabla DynamoDB f1_driver_stats.

La tabla usa PK compuesta:
  - session_key   (Number) — qué sesión
  - driver_number (Number) — qué piloto

Esto permite:
  - Obtener todos los pilotos de una sesión: query por PK
  - Obtener un piloto específico:             get_item por PK + SK
"""

from __future__ import annotations

import os
import boto3
from boto3.dynamodb.conditions import Key
from typing import Optional


TABLE_NAME = os.environ.get("DRIVER_STATS_TABLE", "f1_driver_stats")


def _get_table():
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    kwargs = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1", **kwargs)
    return dynamodb.Table(TABLE_NAME)


class DriverRepository:
    """Repository para la tabla f1_driver_stats (PK: session_key, SK: driver_number)."""

    def __init__(self):
        self._table = _get_table()

    def save(self, driver: dict) -> None:
        """
        Guarda o actualiza un registro de piloto para una sesión.
        driver debe tener al menos:
          {"session_key": <int>, "driver_number": <int>, ...}
        """
        item = {
            **driver,
            "session_key": int(driver["session_key"]),
            "driver_number": int(driver["driver_number"]),
        }
        self._table.put_item(Item=item)

    def save_batch(self, drivers: list[dict]) -> None:
        """
        Guarda múltiples pilotos usando batch_writer (más eficiente que
        múltiples put_item individuales — DynamoDB agrupa en lotes de 25).
        """
        with self._table.batch_writer() as batch:
            for driver in drivers:
                item = {
                    **driver,
                    "session_key": int(driver["session_key"]),
                    "driver_number": int(driver["driver_number"]),
                }
                batch.put_item(Item=item)

    def get(self, session_key: int, driver_number: int) -> Optional[dict]:
        """Devuelve un piloto específico de una sesión."""
        response = self._table.get_item(
            Key={
                "session_key": int(session_key),
                "driver_number": int(driver_number),
            }
        )
        return response.get("Item")

    def list_by_session(self, session_key: int) -> list[dict]:
        """Devuelve todos los pilotos de una sesión usando Query (eficiente)."""
        response = self._table.query(
            KeyConditionExpression=Key("session_key").eq(int(session_key))
        )
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = self._table.query(
                KeyConditionExpression=Key("session_key").eq(int(session_key)),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))

        return items
