"""
Lambda: list_sessions
Descripcion: Lista todas las sesiones que fueron ingestadas en DynamoDB.
             NO llama a OpenF1. Lee solo de la base local.

GET /sessions
"""
import json
import decimal

from dynamo_client import get_table


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    table = get_table()

    # Buscar todos los items con SK = "#METADATA" (uno por sesion ingestada)
    result = table.scan(
        FilterExpression="SK = :sk",
        ExpressionAttributeValues={":sk": "#METADATA"},
    )
    items = result.get("Items", [])

    if not items:
        return _resp(404, {"error": "No hay sesiones ingestadas todavia. Usar POST /sessions/{session_key}/ingest primero."})

    sessions = [
        {
            "session_key": item.get("session_key"),
            "session_name": item.get("session_name"),
            "session_type": item.get("session_type"),
            "date_start": item.get("date_start"),
            "year": item.get("year"),
            "country_name": item.get("country_name"),
            "circuit_short_name": item.get("circuit_short_name"),
            "status": item.get("status"),
            "ingested_at": item.get("ingested_at"),
        }
        for item in items
    ]

    return _resp(200, {
        "sessions_count": len(sessions),
        "sessions": sessions,
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
