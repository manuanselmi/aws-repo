"""
Lambda: list_drivers
Descripcion: Dado un session_key recibido en el event, consulta la API de OpenF1
             y retorna la lista de pilotos de esa sesion.

Input (event):
    {
        "session_key": 9158
    }

Output:
    {
        "statusCode": 200,
        "body": {
            "session_key": 9158,
            "drivers_count": 20,
            "drivers": [
                {
                    "driver_number": 1,
                    "full_name": "Max Verstappen",
                    "team_name": "Red Bull Racing",
                    "country_code": "NED"
                },
                ...
            ]
        }
    }
"""
import json
import urllib.error
import urllib.request

OPENF1_BASE_URL = "https://api.openf1.org/v1"


def handler(event, context):
    # --- 1. Leer session_key del evento ---
    session_key = event.get("session_key")

    if not session_key:
        return _response(400, {"error": "session_key is required in the event payload"})

    # --- 2. Llamar a la API de OpenF1 ---
    url = f"{OPENF1_BASE_URL}/drivers?session_key={session_key}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))

    except urllib.error.HTTPError as e:
        return _response(502, {"error": f"OpenF1 API returned HTTP {e.code}"})

    except Exception as e:
        return _response(500, {"error": f"Internal error: {str(e)}"})

    # --- 3. Validar que la API devolvio pilotos ---
    if not raw_data:
        return _response(404, {"error": f"No drivers found for session_key {session_key}"})

    # --- 4. Construir la lista de pilotos ---
    drivers = [
        {
            "driver_number": d.get("driver_number"),
            "full_name": d.get("full_name"),
            "team_name": d.get("team_name"),
            "country_code": d.get("country_code"),
        }
        for d in raw_data
    ]

    # --- 5. Retornar respuesta exitosa ---
    return _response(200, {
        "session_key": session_key,
        "drivers_count": len(drivers),
        "drivers": drivers,
    })


def _response(status_code, body):
    """Helper para construir la respuesta Lambda estandar."""
    return {
        "statusCode": status_code,
        "body": json.dumps(body),
    }
