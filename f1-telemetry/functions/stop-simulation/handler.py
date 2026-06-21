import json
from datetime import datetime, timezone

from dynamo_client import get_table

_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": _CORS, "body": ""}

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except Exception:
            return _resp(400, {"error": "Body JSON invalido"})

    session_key = body.get("session_key")
    if session_key is None:
        return _resp(400, {"error": "session_key es requerido en el body"})

    try:
        session_key = int(session_key)
        if session_key <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return _resp(400, {"error": "session_key debe ser un entero positivo"})

    table = get_table()

    session_item = table.get_item(
        Key={"PK": f"SESSION#{session_key}", "SK": "#METADATA"}
    ).get("Item")
    if not session_item:
        return _resp(404, {"error": f"La sesion {session_key} no fue ingestada."})

    now = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"PK": f"SESSION#{session_key}", "SK": "SIMULATION#STATE"},
        UpdateExpression="SET #st = :s, stopped_at = :now, updated_at = :now",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":s": "STOPPED", ":now": now},
    )

    return _resp(200, {
        "session_key": session_key,
        "status": "STOPPED",
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **_CORS},
        "body": json.dumps(body),
    }
