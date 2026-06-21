import decimal
import json
import os

from boto3.dynamodb.conditions import Key
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

    drivers_result = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"SESSION#{session_key}") &
            Key("SK").begins_with("DRIVER#")
        )
    )
    drivers = drivers_result.get("Items", [])

    if not drivers:
        return _resp(404, {"error": f"La sesion {session_key} no fue ingestada o no tiene pilotos."})

    # Single batch call instead of 20 individual get_item calls.
    # Uses table.meta.client so the same client is used in tests.
    table_name = os.environ.get("TABLE_NAME", "F1Telemetry")
    driver_numbers = [int(d["driver_number"]) for d in drivers]
    keys = [
        {"PK": f"SESSION#{session_key}#DRIVER#{dn}", "SK": "LIVE#STATE"}
        for dn in driver_numbers
    ]

    batch_resp = table.meta.client.batch_get_item(RequestItems={table_name: {"Keys": keys}})
    live_by_pk = {
        item["PK"]: item
        for item in batch_resp.get("Responses", {}).get(table_name, [])
    }

    live_states = []
    for driver in drivers:
        driver_id = int(driver["SK"].split("#")[1])
        driver_number = int(driver["driver_number"])
        pk = f"SESSION#{session_key}#DRIVER#{driver_number}"
        live = live_by_pk.get(pk)

        live_states.append({
            "driver_id": driver_id,
            "driver_number": driver_number,
            "full_name": driver.get("full_name"),
            "name_acronym": driver.get("name_acronym"),
            "team_name": driver.get("team_name"),
            "current_lap": live.get("current_lap") if live else None,
            "position": live.get("position") if live else None,
            "speed": live.get("speed") if live else None,
            "lap_duration_sec": live.get("lap_duration_sec") if live else None,
            "status": live.get("status") if live else "NO_DATA",
            "updated_at": live.get("updated_at") if live else None,
        })

    live_states.sort(key=lambda x: (x.get("position") is None, x.get("position") or 99))

    return _resp(200, {
        "session_key": session_key,
        "live_count": len([s for s in live_states if s["position"] is not None]),
        "live_states": live_states,
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **_CORS},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
