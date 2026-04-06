"""
Lambda: driver_summary
Descripcion: Dado un driver_number, retorna informacion general del piloto
             agregando datos de sus ultimas sesiones (nombre, equipo, pais,
             y las sesiones en las que participo).

GET /drivers/summary?driver_number=1
"""
import json
import urllib.error
import urllib.request

OPENF1_BASE_URL = "https://api.openf1.org/v1"


def handler(event, context):
    params = event.get("queryStringParameters") or event
    driver_number = params.get("driver_number")

    if not driver_number:
        return _response(400, {"error": "driver_number is required"})

    url = f"{OPENF1_BASE_URL}/drivers?driver_number={driver_number}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return _response(502, {"error": f"OpenF1 API returned HTTP {e.code}"})
    except Exception as e:
        return _response(500, {"error": f"Internal error: {str(e)}"})

    if not raw_data:
        return _response(404, {"error": f"No data found for driver_number {driver_number}"})

    latest = raw_data[-1]
    seen_sessions = set()
    sessions = []
    for entry in raw_data:
        sk = entry.get("session_key")
        if sk and sk not in seen_sessions:
            seen_sessions.add(sk)
            sessions.append(sk)

    summary = {
        "driver_number": latest.get("driver_number"),
        "full_name": latest.get("full_name"),
        "first_name": latest.get("first_name"),
        "last_name": latest.get("last_name"),
        "name_acronym": latest.get("name_acronym"),
        "team_name": latest.get("team_name"),
        "team_colour": latest.get("team_colour"),
        "country_code": latest.get("country_code"),
        "headshot_url": latest.get("headshot_url"),
        "broadcast_name": latest.get("broadcast_name"),
        "sessions_count": len(sessions),
        "session_keys": sessions,
    }

    return _response(200, summary)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
