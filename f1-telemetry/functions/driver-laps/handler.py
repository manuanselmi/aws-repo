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
    driver_id = path_params.get("driver_id") or event.get("driver_id")

    if not session_key or not driver_id:
        return _resp(400, {"error": "session_key y driver_id son requeridos en el path"})

    try:
        session_key = int(session_key)
        driver_id = int(driver_id)
    except (ValueError, TypeError):
        return _resp(400, {"error": "session_key y driver_id deben ser numeros enteros"})

    table = get_table()

    driver_item = table.get_item(
        Key={"PK": f"SESSION#{session_key}", "SK": f"DRIVER#{driver_id}"}
    ).get("Item")
    if not driver_item:
        return _resp(404, {
            "error": f"Piloto con driver_id {driver_id} no encontrado en sesion {session_key}.",
        })

    driver_number = int(driver_item["driver_number"])

    result = table.query(
        KeyConditionExpression=Key("PK").eq(f"SESSION#{session_key}#DRIVER#{driver_number}")
    )
    laps = result.get("Items", [])

    if not laps:
        return _resp(404, {
            "error": f"No hay vueltas registradas para el piloto {driver_id} en la sesion {session_key}.",
        })

    laps.sort(key=lambda l: l.get("lap_number", 0))

    laps_response = [
        {
            "lap_number": lap.get("lap_number"),
            "lap_duration_sec": float(lap["lap_duration"]) if lap.get("lap_duration") else None,
            "position": lap.get("position"),
            "is_pit_out_lap": lap.get("is_pit_out_lap", False),
        }
        for lap in laps
    ]

    return _resp(200, {
        "session_key": session_key,
        "driver_id": driver_id,
        "full_name": driver_item.get("full_name"),
        "laps_count": len(laps_response),
        "laps": laps_response,
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
