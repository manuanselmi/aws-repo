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
        return _resp(422, {
            "error": f"No hay vueltas registradas para el piloto {driver_id} en la sesion {session_key}.",
        })

    valid_laps = [
        lap for lap in laps
        if lap.get("lap_duration") and not lap.get("is_pit_out_lap", False)
    ]

    best_lap = None
    if valid_laps:
        best_lap_item = min(valid_laps, key=lambda l: l["lap_duration"])
        best_lap = float(best_lap_item["lap_duration"])

    speeds = [float(lap["st_speed"]) for lap in laps if lap.get("st_speed")]
    max_speed = max(speeds) if speeds else None
    avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else None

    return _resp(200, {
        "session_key": session_key,
        "driver_id": driver_id,
        "full_name": driver_item.get("full_name"),
        "name_acronym": driver_item.get("name_acronym"),
        "team_name": driver_item.get("team_name"),
        "lap_count": len(laps),
        "best_lap_duration_sec": best_lap,
        "avg_speed_kmh": avg_speed,
        "max_speed_kmh": max_speed,
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
