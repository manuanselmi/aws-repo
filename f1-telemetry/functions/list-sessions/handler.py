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

    table = get_table()

    result = table.scan(
        FilterExpression="SK = :sk",
        ExpressionAttributeValues={":sk": "#METADATA"},
    )
    items = result.get("Items", [])

    if not items:
        return _resp(404, {"error": "No hay sesiones ingestadas."})

    sessions = [
        {
            "session_key": (
                int(item["session_key"]) if item.get("session_key") is not None else None
            ),
            "session_name": item.get("session_name"),
            "country_name": item.get("country_name"),
            "date_start": item.get("date_start"),
            "year": int(item["year"]) if item.get("year") is not None else None,
            "circuit_short_name": item.get("circuit_short_name"),
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
        "headers": {"Content-Type": "application/json", **_CORS},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
