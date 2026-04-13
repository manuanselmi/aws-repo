"""
S3Repository — abstracción sobre el bucket f1-raw-data.

Guarda las respuestas crudas de la API OpenF1 como JSON.
Estructura de claves en S3:
  sessions/{session_key}/session.json   ← datos crudos de la sesión
  sessions/{session_key}/drivers.json   ← lista cruda de pilotos
"""
from __future__ import annotations

import json
import os
import boto3
from typing import Optional


BUCKET_NAME = os.environ.get("RAW_BUCKET", "f1-raw-data")


def _get_client():
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    kwargs = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url

    return boto3.client("s3", region_name="us-east-1", **kwargs)


class S3Repository:
    """Repository para el bucket f1-raw-data."""

    def __init__(self):
        self._client = _get_client()
        self._bucket = BUCKET_NAME

    def save_session_raw(self, session_key: int, data: dict | list) -> str:
        """
        Guarda el JSON crudo de una sesión.
        Devuelve la S3 key donde quedó guardado.
        """
        key = f"sessions/{session_key}/session.json"
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=json.dumps(data, default=str),
            ContentType="application/json",
        )
        return key

    def save_drivers_raw(self, session_key: int, data: list) -> str:
        """
        Guarda el JSON crudo de la lista de pilotos de una sesión.
        Devuelve la S3 key donde quedó guardado.
        """
        key = f"sessions/{session_key}/drivers.json"
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=json.dumps(data, default=str),
            ContentType="application/json",
        )
        return key

    def get_session_raw(self, session_key: int) -> Optional[dict | list]:
        """
        Lee y devuelve el JSON crudo de una sesión, o None si no existe.
        """
        key = f"sessions/{session_key}/session.json"
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return json.loads(response["Body"].read())
        except self._client.exceptions.NoSuchKey:
            return None

    def get_drivers_raw(self, session_key: int) -> Optional[list]:
        """
        Lee y devuelve el JSON crudo de pilotos de una sesión, o None si no existe.
        """
        key = f"sessions/{session_key}/drivers.json"
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return json.loads(response["Body"].read())
        except self._client.exceptions.NoSuchKey:
            return None

    def list_session_keys(self) -> list[int]:
        """Lista todos los session_keys que tienen datos en S3."""
        paginator = self._client.get_paginator("list_objects_v2")
        keys = set()
        for page in paginator.paginate(Bucket=self._bucket, Prefix="sessions/", Delimiter="/"):
            for prefix in page.get("CommonPrefixes", []):
                # prefix["Prefix"] = "sessions/9158/"
                part = prefix["Prefix"].strip("/").split("/")[-1]
                if part.isdigit():
                    keys.add(int(part))
        return sorted(keys)
