import decimal
import json

from dynamo_client import get_table

_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": _CORS, "body": ""}

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

    live_item = table.get_item(
        Key={
            "PK": f"SESSION#{session_key}#DRIVER#{driver_number}",
            "SK": "LIVE#STATE",
        }
    ).get("Item")

    if not live_item:
        return _resp(404, {
            "error": (
                f"No hay estado live para el piloto {driver_id} en la sesion {session_key}. "
                "Inicia la simulacion primero."
            ),
        })

    return _resp(200, {
        "session_key": session_key,
        "driver_id": driver_id,
        "driver_number": driver_number,
        "current_lap": live_item.get("current_lap"),
        "position": live_item.get("position"),
        "speed": live_item.get("speed"),
        "gap_ms": live_item.get("gap_ms"),
        "x": live_item.get("x"),
        "y": live_item.get("y"),
        "status": live_item.get("status", "RUNNING"),
        "updated_at": live_item.get("updated_at"),
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **_CORS},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
