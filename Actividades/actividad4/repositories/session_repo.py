from __future__ import annotations

import os
import boto3
from boto3.dynamodb.conditions import Key
from typing import Optional


TABLE_NAME = os.environ.get("SESSIONS_TABLE", "f1_sessions")


def _get_table():
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    kwargs = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1", **kwargs)
    return dynamodb.Table(TABLE_NAME)


class SessionRepository:

    def __init__(self):
        self._table = _get_table()

    def save(self, session: dict) -> None:
        item = {**session, "session_key": int(session["session_key"])}
        self._table.put_item(Item=item)

    def get(self, session_key: int) -> Optional[dict]:
        response = self._table.get_item(
            Key={"session_key": int(session_key)}
        )
        return response.get("Item")

    def list_all(self) -> list[dict]:
        response = self._table.scan()
        items = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = self._table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))

        return items

    def exists(self, session_key: int) -> bool:
        return self.get(session_key) is not None
