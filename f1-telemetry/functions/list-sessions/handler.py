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

    result = table.scan(
        FilterExpression="SK = :sk",
        ExpressionAttributeValues={":sk": "#METADATA"},
    )
    items = result.get("Items", [])

    if not items:
        return _resp(404, {"error": "No hay sesiones ingestadas."})

    sessions = [
        {
            "session_key": item.get("session_key"),
            "session_name": item.get("session_name"),
            "country_name": item.get("country_name"),
            "date_start": item.get("date_start"),
            "year": item.get("year"),
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
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
