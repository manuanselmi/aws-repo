"""
Lambda: list_drivers
Descripcion: Dado un session_key, consulta la API de OpenF1
             y retorna la lista de pilotos de esa sesion.

Soporta invocacion directa y API Gateway (query string).

GET /drivers?session_key=9158
"""
import json
import urllib.error
import urllib.request

OPENF1_BASE_URL = "https://api.openf1.org/v1"


def handler(event, context):
    params = event.get("queryStringParameters") or event
    session_key = params.get("session_key")

    if not session_key:
        return _response(400, {"error": "session_key is required"})

    url = f"{OPENF1_BASE_URL}/drivers?session_key={session_key}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return _response(502, {"error": f"OpenF1 API returned HTTP {e.code}"})
    except Exception as e:
        return _response(500, {"error": f"Internal error: {str(e)}"})

    if not raw_data:
        return _response(404, {"error": f"No drivers found for session_key {session_key}"})

    drivers = [
        {
            "driver_number": d.get("driver_number"),
            "full_name": d.get("full_name"),
            "team_name": d.get("team_name"),
            "country_code": d.get("country_code"),
        }
        for d in raw_data
    ]

    return _response(200, {
        "session_key": int(session_key),
        "drivers_count": len(drivers),
        "drivers": drivers,
    })


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
