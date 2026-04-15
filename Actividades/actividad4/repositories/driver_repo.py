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

    def __init__(self):
        self._table = _get_table()

    def save(self, driver: dict) -> None:
        item = {
            **driver,
            "session_key": int(driver["session_key"]),
            "driver_number": int(driver["driver_number"]),
        }
        self._table.put_item(Item=item)

    def save_batch(self, drivers: list[dict]) -> None:
        with self._table.batch_writer() as batch:
            for driver in drivers:
                item = {
                    **driver,
                    "session_key": int(driver["session_key"]),
                    "driver_number": int(driver["driver_number"]),
                }
                batch.put_item(Item=item)

    def get(self, session_key: int, driver_number: int) -> Optional[dict]:
        response = self._table.get_item(
            Key={
                "session_key": int(session_key),
                "driver_number": int(driver_number),
            }
        )
        return response.get("Item")

    def list_by_session(self, session_key: int) -> list[dict]:
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
