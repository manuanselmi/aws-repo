"""
Lambda: get_session
Descripcion: Dado un session_key, retorna los detalles de esa sesion
             (circuito, pais, fecha, tipo de sesion, etc.).

GET /sessions/{session_key}
"""
import json
import urllib.error
import urllib.request

OPENF1_BASE_URL = "https://api.openf1.org/v1"


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    session_key = path_params.get("session_key") or event.get("session_key")

    if not session_key:
        return _response(400, {"error": "session_key is required"})

    url = f"{OPENF1_BASE_URL}/sessions?session_key={session_key}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return _response(502, {"error": f"OpenF1 API returned HTTP {e.code}"})
    except Exception as e:
        return _response(500, {"error": f"Internal error: {str(e)}"})

    if not raw_data:
        return _response(404, {"error": f"No session found for session_key {session_key}"})

    s = raw_data[0]
    session = {
        "session_key": s.get("session_key"),
        "session_name": s.get("session_name"),
        "session_type": s.get("session_type"),
        "date_start": s.get("date_start"),
        "date_end": s.get("date_end"),
        "year": s.get("year"),
        "country_name": s.get("country_name"),
        "country_code": s.get("country_code"),
        "circuit_key": s.get("circuit_key"),
        "circuit_short_name": s.get("circuit_short_name"),
    }

    return _response(200, session)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
