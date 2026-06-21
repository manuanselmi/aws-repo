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

    if not session_key:
        return _resp(400, {"error": "session_key es requerido en el path"})

    try:
        session_key = int(session_key)
    except (ValueError, TypeError):
        return _resp(400, {"error": "session_key debe ser un numero entero"})

    table = get_table()

    state_item = table.get_item(
        Key={"PK": f"SESSION#{session_key}", "SK": "SIMULATION#STATE"}
    ).get("Item")

    if not state_item:
        return _resp(404, {
            "error": f"No hay simulacion iniciada para la sesion {session_key}.",
        })

    return _resp(200, {
        "session_key": session_key,
        "status": state_item.get("status"),
        "events_published": state_item.get("events_published"),
        "events_processed": int(state_item.get("events_processed", 0)),
        "duration_seconds": state_item.get("duration_seconds"),
        "started_at": state_item.get("started_at"),
        "stopped_at": state_item.get("stopped_at"),
        "updated_at": state_item.get("updated_at"),
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **_CORS},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
