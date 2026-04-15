"""
Lambda: list_drivers
Descripcion: Lista los pilotos de una sesion ya ingestada en DynamoDB.
             NO llama a OpenF1.

GET /sessions/{session_key}/drivers
"""
import json
import decimal
from boto3.dynamodb.conditions import Key

from dynamo_client import get_table


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    session_key = path_params.get("session_key") or event.get("session_key")

    if not session_key:
        return _resp(400, {"error": "session_key es requerido en el path"})

    try:
        session_key = int(session_key)
    except (ValueError, TypeError):
        return _resp(400, {"error": "session_key debe ser un numero entero"})

    table = get_table()

    # Verificar que la sesion existe
    session_item = table.get_item(
        Key={"PK": f"SESSION#{session_key}", "SK": "#METADATA"}
    ).get("Item")
    if not session_item:
        return _resp(404, {
            "error": f"La sesion {session_key} no fue ingestada.",
            "hint": f"Usar POST /sessions/{session_key}/ingest primero.",
        })

    # Consultar pilotos: PK = SESSION#sk, SK begins_with DRIVER#
    result = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"SESSION#{session_key}") &
            Key("SK").begins_with("DRIVER#")
        )
    )
    items = result.get("Items", [])

    drivers = [
        {
            "driver_number": item.get("driver_number"),
            "full_name": item.get("full_name"),
            "name_acronym": item.get("name_acronym"),
            "team_name": item.get("team_name"),
            "country_code": item.get("country_code"),
        }
        for item in items
    ]

    return _resp(200, {
        "session_key": session_key,
        "drivers_count": len(drivers),
        "drivers": drivers,
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
