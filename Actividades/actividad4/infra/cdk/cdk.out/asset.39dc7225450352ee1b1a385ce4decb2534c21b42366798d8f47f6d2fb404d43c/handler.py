"""
Lambda de ingesta F1 — Actividad 4

Flujo:
  1. Recibe evento de EventBridge (o invocación directa)
  2. Llama a la API OpenF1 para obtener sesiones recientes del año actual
  3. Para cada sesión nueva (no existe en DynamoDB):
     a. Guarda JSON crudo en S3       → s3_repo
     b. Parsea y guarda en DynamoDB   → session_repo + driver_repo

Variables de entorno requeridas:
  SESSIONS_TABLE     nombre de la tabla DynamoDB de sesiones
  DRIVER_STATS_TABLE nombre de la tabla DynamoDB de pilotos
  RAW_BUCKET         nombre del bucket S3
  AWS_ENDPOINT_URL   (opcional) para LocalStack: http://localhost:4566
"""

import json
import logging
import os
import sys
from datetime import datetime

import requests

# Agrega el directorio raíz al path para poder importar repositories/
# cuando la Lambda se ejecuta localmente (fuera de un paquete instalado)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from repositories.session_repo import SessionRepository
from repositories.driver_repo import DriverRepository
from repositories.s3_repo import S3Repository

logger = logging.getLogger()
logger.setLevel(logging.INFO)

OPENF1_BASE = "https://api.openf1.org/v1"


def _fetch_sessions(year: int) -> list[dict]:
    resp = requests.get(
        f"{OPENF1_BASE}/sessions",
        params={"session_type": "Race", "year": year},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_drivers(session_key: int) -> list[dict]:
    resp = requests.get(
        f"{OPENF1_BASE}/drivers",
        params={"session_key": session_key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def lambda_handler(event, context):
    """
    Punto de entrada de la Lambda.
    Puede ser invocada por EventBridge o directamente con:
      {"year": 2024}  ← para ingestar un año específico
    """
    year = event.get("year", datetime.utcnow().year)
    logger.info(f"Iniciando ingesta para el año {year}")

    session_repo = SessionRepository()
    driver_repo = DriverRepository()
    s3_repo = S3Repository()

    try:
        sessions = _fetch_sessions(year)
    except requests.RequestException as e:
        logger.error(f"Error al obtener sesiones: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

    logger.info(f"Sesiones encontradas en OpenF1: {len(sessions)}")

    ingested = []
    skipped = []

    for session in sessions:
        session_key = session.get("session_key")
        if not session_key:
            continue

        # Evitar re-ingestar sesiones ya guardadas
        if session_repo.exists(session_key):
            skipped.append(session_key)
            logger.info(f"Sesión {session_key} ya existe — saltando")
            continue

        # ----------------------------------------------------------------
        # 1. Guardar datos crudos en S3
        # ----------------------------------------------------------------
        s3_session_key = s3_repo.save_session_raw(session_key, session)
        logger.info(f"Sesión {session_key} → S3:{s3_session_key}")

        # ----------------------------------------------------------------
        # 2. Obtener y guardar pilotos
        # ----------------------------------------------------------------
        try:
            drivers_raw = _fetch_drivers(session_key)
        except requests.RequestException as e:
            logger.warning(f"No se pudieron obtener pilotos para {session_key}: {e}")
            drivers_raw = []

        if drivers_raw:
            s3_drivers_key = s3_repo.save_drivers_raw(session_key, drivers_raw)
            logger.info(f"Pilotos {session_key} → S3:{s3_drivers_key}")

        # ----------------------------------------------------------------
        # 3. Parsear y guardar en DynamoDB
        # ----------------------------------------------------------------
        session_item = {
            "session_key": session_key,
            "session_name": session.get("session_name"),
            "session_type": session.get("session_type"),
            "circuit_short_name": session.get("circuit_short_name"),
            "circuit_key": session.get("circuit_key"),
            "country_name": session.get("country_name"),
            "date_start": session.get("date_start"),
            "date_end": session.get("date_end"),
            "year": session.get("year"),
            "drivers_count": len(drivers_raw),
        }
        session_repo.save(session_item)

        if drivers_raw:
            driver_items = [
                {
                    "session_key": session_key,
                    "driver_number": d.get("driver_number"),
                    "full_name": d.get("full_name"),
                    "team_name": d.get("team_name"),
                    "name_acronym": d.get("name_acronym"),
                    "country_code": d.get("country_code"),
                }
                for d in drivers_raw
                if d.get("driver_number") is not None
            ]
            driver_repo.save_batch(driver_items)
            logger.info(f"Guardados {len(driver_items)} pilotos para sesión {session_key}")

        ingested.append(session_key)

    result = {
        "year": year,
        "sessions_found": len(sessions),
        "ingested": ingested,
        "skipped": skipped,
    }
    logger.info(f"Ingesta completada: {result}")
    return {"statusCode": 200, "body": json.dumps(result)}
