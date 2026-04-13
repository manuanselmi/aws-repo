import json
import requests

OPENF1_BASE = "https://api.openf1.org/v1"

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _response(status_code: int, body: dict | list) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def list_sessions(event, context):
    """GET /sessions — List all race sessions from the 2024 season."""
    try:
        params = event.get("queryStringParameters") or {}
        year = params.get("year", "2024")

        resp = requests.get(
            f"{OPENF1_BASE}/sessions",
            params={"session_type": "Race", "year": year},
            timeout=10,
        )
        resp.raise_for_status()
        sessions = resp.json()

        result = [
            {
                "session_key": s.get("session_key"),
                "session_name": s.get("session_name"),
                "session_type": s.get("session_type"),
                "circuit_short_name": s.get("circuit_short_name"),
                "date_start": s.get("date_start"),
            }
            for s in sessions
        ]
        return _response(200, result)

    except requests.RequestException as e:
        return _response(500, {"error": str(e)})


def get_session(event, context):
    """GET /sessions/{session_key} — Get details for a single session."""
    try:
        session_key = event["pathParameters"]["session_key"]

        resp = requests.get(
            f"{OPENF1_BASE}/sessions",
            params={"session_key": session_key},
            timeout=10,
        )
        resp.raise_for_status()
        sessions = resp.json()

        if not sessions:
            return _response(404, {"error": "Session not found"})

        session = sessions[0]
        return _response(200, {
            "session_key": session.get("session_key"),
            "session_name": session.get("session_name"),
            "session_type": session.get("session_type"),
            "circuit_short_name": session.get("circuit_short_name"),
            "circuit_key": session.get("circuit_key"),
            "country_name": session.get("country_name"),
            "date_start": session.get("date_start"),
            "date_end": session.get("date_end"),
            "year": session.get("year"),
        })

    except requests.RequestException as e:
        return _response(500, {"error": str(e)})


def ingest_session(event, context):
    """POST /sessions/{session_key}/ingest — Fetch session + drivers from OpenF1."""
    try:
        session_key = event["pathParameters"]["session_key"]

        session_resp = requests.get(
            f"{OPENF1_BASE}/sessions",
            params={"session_key": session_key},
            timeout=15,
        )
        session_resp.raise_for_status()
        sessions = session_resp.json()

        if not sessions:
            return _response(404, {"error": "Session not found"})

        session = sessions[0]

        drivers_resp = requests.get(
            f"{OPENF1_BASE}/drivers",
            params={"session_key": session_key},
            timeout=30,
        )
        drivers_resp.raise_for_status()
        drivers = drivers_resp.json()

        driver_list = [
            {
                "driver_number": d.get("driver_number"),
                "full_name": d.get("full_name"),
                "team_name": d.get("team_name"),
                "name_acronym": d.get("name_acronym"),
            }
            for d in drivers
        ]

        return _response(200, {
            "session_name": session.get("session_name"),
            "session_key": session.get("session_key"),
            "drivers_count": len(driver_list),
            "drivers": driver_list,
        })

    except requests.RequestException as e:
        return _response(500, {"error": str(e)})
