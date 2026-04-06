"""
Lambda: list_sessions
Descripcion: Lista sesiones de F1 con filtros opcionales
             (year, country_name, session_type, circuit_short_name).

GET /sessions?year=2024&country_name=Belgium&session_type=Race
"""
import json
import urllib.error
import urllib.request
import urllib.parse

OPENF1_BASE_URL = "https://api.openf1.org/v1"

ALLOWED_FILTERS = ["year", "country_name", "session_type", "circuit_short_name"]


def handler(event, context):
    params = event.get("queryStringParameters") or event

    query_parts = []
    for key in ALLOWED_FILTERS:
        value = params.get(key)
        if value:
            query_parts.append(f"{key}={urllib.parse.quote(str(value))}")

    if not query_parts:
        return _response(400, {
            "error": "At least one filter is required",
            "allowed_filters": ALLOWED_FILTERS,
        })

    url = f"{OPENF1_BASE_URL}/sessions?{'&'.join(query_parts)}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return _response(502, {"error": f"OpenF1 API returned HTTP {e.code}"})
    except Exception as e:
        return _response(500, {"error": f"Internal error: {str(e)}"})

    if not raw_data:
        return _response(404, {"error": "No sessions found with the given filters"})

    sessions = [
        {
            "session_key": s.get("session_key"),
            "session_name": s.get("session_name"),
            "session_type": s.get("session_type"),
            "date_start": s.get("date_start"),
            "year": s.get("year"),
            "country_name": s.get("country_name"),
            "circuit_short_name": s.get("circuit_short_name"),
        }
        for s in raw_data
    ]

    return _response(200, {
        "sessions_count": len(sessions),
        "sessions": sessions,
    })


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
