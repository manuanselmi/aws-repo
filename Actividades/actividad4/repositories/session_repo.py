"""
SessionRepository — abstracción sobre la tabla DynamoDB f1_sessions.

Uso:
    repo = SessionRepository()
    repo.save({"session_key": 9158, "session_name": "Race", ...})
    session = repo.get(9158)
    sessions = repo.list_all()

Para LocalStack:
    export AWS_ENDPOINT_URL=http://localhost:4566
    python -c "from repositories.session_repo import SessionRepository; print('OK')"
"""

from __future__ import annotations

import os
import boto3
from boto3.dynamodb.conditions import Key
from typing import Optional


TABLE_NAME = os.environ.get("SESSIONS_TABLE", "f1_sessions")


def _get_table():
    """
    Crea el recurso de DynamoDB apuntando a LocalStack si AWS_ENDPOINT_URL
    está definido, o a AWS real si no lo está.
    """
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    kwargs = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1", **kwargs)
    return dynamodb.Table(TABLE_NAME)


class SessionRepository:
    """Repository para la tabla f1_sessions (PK: session_key Number)."""

    def __init__(self):
        self._table = _get_table()

    def save(self, session: dict) -> None:
        """
        Guarda o actualiza una sesión completa.
        session debe contener al menos {"session_key": <int>, ...}
        """
        # Asegurar que session_key sea int (DynamoDB Number)
        item = {**session, "session_key": int(session["session_key"])}
        self._table.put_item(Item=item)

    def get(self, session_key: int) -> Optional[dict]:
        """Devuelve la sesión con ese session_key, o None si no existe."""
        response = self._table.get_item(
            Key={"session_key": int(session_key)}
        )
        return response.get("Item")

    def list_all(self) -> list[dict]:
        """
        Escanea y devuelve todas las sesiones.
        En producción con tablas grandes usar paginación.
        """
        response = self._table.scan()
        items = response.get("Items", [])

        # Paginar si hay más items
        while "LastEvaluatedKey" in response:
            response = self._table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response.get("Items", []))

        return items

    def exists(self, session_key: int) -> bool:
        """Comprueba si ya existe la sesión (evita re-ingestas)."""
        return self.get(session_key) is not None
