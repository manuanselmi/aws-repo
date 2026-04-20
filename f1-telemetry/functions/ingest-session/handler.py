import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from dynamo_client import get_table

OPENF1_BASE = "https://api.openf1.org/v1"


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    session_key = path_params.get("session_key") or event.get("session_key")

    if not session_key:
        return _resp(400, {"error": "session_key es requerido en el path"})

    try:
        session_key = int(session_key)
    except (ValueError, TypeError):
        return _resp(400, {"error": "session_key debe ser un numero entero"})

    force = False
    if event.get("body"):
        try:
            force = json.loads(event["body"]).get("force", False)
        except Exception:
            pass

    table = get_table()

    if not force:
        existing = table.get_item(
            Key={"PK": f"SESSION#{session_key}", "SK": "#METADATA"}
        ).get("Item")
        if existing:
            return _resp(409, {
                "error": f"La sesion {session_key} ya fue ingestada.",
                "hint": "Enviar {\"force\": true} en el body para re-ingestar.",
            })

    session_data = _openf1_get(f"/sessions?session_key={session_key}")
    if not session_data:
        return _resp(404, {"error": f"Sesion {session_key} no encontrada en OpenF1"})
    session = session_data[0]

    drivers_data = _openf1_get(f"/drivers?session_key={session_key}")
    laps_data = _openf1_get(f"/laps?session_key={session_key}")
    positions_data = _openf1_get(f"/position?session_key={session_key}")

    positions_by_driver = {}
    for p in positions_data:
        dn = p.get("driver_number")
        if dn is None:
            continue
        if dn not in positions_by_driver:
            positions_by_driver[dn] = []
        positions_by_driver[dn].append(p)
    for dn in positions_by_driver:
        positions_by_driver[dn].sort(key=lambda x: x.get("date", ""))

    with table.batch_writer() as batch:
        batch.put_item(Item={
            "PK": f"SESSION#{session_key}",
            "SK": "#METADATA",
            "session_key": session_key,
            "session_name": session.get("session_name") or "",
            "session_type": session.get("session_type") or "",
            "date_start": session.get("date_start") or "",
            "year": session.get("year") or 0,
            "country_name": session.get("country_name") or "",
            "circuit_short_name": session.get("circuit_short_name") or "",
        })

        driver_id = 0
        for d in drivers_data:
            dn = d.get("driver_number")
            if dn is None:
                continue
            driver_id += 1
            batch.put_item(Item={
                "PK": f"SESSION#{session_key}",
                "SK": f"DRIVER#{driver_id}",
                "driver_number": dn,
                "full_name": d.get("full_name") or "",
                "name_acronym": d.get("name_acronym") or "",
                "team_name": d.get("team_name") or "",
            })

        for lap in laps_data:
            dn = lap.get("driver_number")
            lap_number = lap.get("lap_number")
            if dn is None or lap_number is None:
                continue

            position = _get_position_at_lap_end(
                positions_by_driver.get(dn, []),
                lap.get("date_start"),
                lap.get("lap_duration"),
            )

            item = {
                "PK": f"SESSION#{session_key}#DRIVER#{dn}",
                "SK": f"LAP#{lap_number:03d}",
                "lap_number": lap_number,
                "driver_number": dn,
                "date_start": lap.get("date_start") or "",
                "is_pit_out_lap": bool(lap.get("is_pit_out_lap", False)),
            }

            for field in ["lap_duration", "i1_speed", "i2_speed", "st_speed",
                          "duration_sector_1", "duration_sector_2", "duration_sector_3"]:
                val = lap.get(field)
                if val is not None:
                    item[field] = Decimal(str(val))

            if position is not None:
                item["position"] = position

            batch.put_item(Item=item)

    return _resp(200, {
        "session_key": session_key,
        "status": "ingested",
        "drivers_count": len(drivers_data),
        "laps_count": len(laps_data),
    })


def _get_position_at_lap_end(driver_positions, lap_start_date, lap_duration_sec):
    if not driver_positions or not lap_start_date:
        return None
    try:
        start = datetime.fromisoformat(lap_start_date.replace("Z", "+00:00"))
        duration = float(lap_duration_sec) if lap_duration_sec else 0
        lap_end = start + timedelta(seconds=duration)
        lap_end_iso = lap_end.isoformat()
    except Exception:
        return None

    last_pos = None
    for p in driver_positions:
        p_date = p.get("date", "")
        if p_date and p_date <= lap_end_iso:
            last_pos = p.get("position")
    return last_pos


def _openf1_get(path):
    url = f"{OPENF1_BASE}{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise Exception(f"OpenF1 error HTTP {e.code} en: {path}")
    except Exception as e:
        raise Exception(f"Error consultando OpenF1 ({path}): {str(e)}")


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
