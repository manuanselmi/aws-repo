import decimal
import json
import os
import time as time_module
from datetime import datetime, timezone

import boto3
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


def _get_sqs_client():
    endpoint = os.environ.get("SQS_ENDPOINT")
    return boto3.client(
        "sqs",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "local"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "local"),
    )


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": _CORS, "body": ""}

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except Exception:
            return _resp(400, {"error": "Body JSON invalido"})

    session_key = body.get("session_key")
    duration_seconds = body.get("duration_seconds")

    if session_key is None or duration_seconds is None:
        return _resp(400, {"error": "session_key y duration_seconds son requeridos en el body"})

    try:
        session_key = int(session_key)
        if session_key <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return _resp(400, {"error": "session_key debe ser un entero positivo"})

    try:
        duration_seconds = int(duration_seconds)
        if duration_seconds <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return _resp(400, {"error": "duration_seconds debe ser un entero positivo"})

    table = get_table()

    session_item = table.get_item(
        Key={"PK": f"SESSION#{session_key}", "SK": "#METADATA"}
    ).get("Item")
    if not session_item:
        return _resp(404, {"error": f"La sesion {session_key} no fue ingestada."})

    drivers_result = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"SESSION#{session_key}") &
            Key("SK").begins_with("DRIVER#")
        )
    )
    drivers = drivers_result.get("Items", [])

    # Recolectar todas las vueltas por piloto, guardando el driver_number
    all_laps = []
    for driver in drivers:
        driver_number = int(driver["driver_number"])
        # begins_with("LAP#") is REQUIRED: this partition also holds the LIVE#STATE
        # item from a previous run. Without the filter it would be picked up as a
        # bogus "lap" (lap_number=None) and published as a junk SQS event.
        laps_result = table.query(
            KeyConditionExpression=(
                Key("PK").eq(f"SESSION#{session_key}#DRIVER#{driver_number}") &
                Key("SK").begins_with("LAP#")
            )
        )
        for lap in laps_result.get("Items", []):
            all_laps.append({
                "driver_number": driver_number,
                "lap_number": lap.get("lap_number"),
                "lap_duration": lap.get("lap_duration"),
                "position": lap.get("position"),
                "is_pit_out_lap": lap.get("is_pit_out_lap", False),
                "st_speed": float(lap["st_speed"]) if lap.get("st_speed") else None,
            })

    if not all_laps:
        return _resp(422, {"error": f"La sesion {session_key} no tiene vueltas registradas."})

    # total_duration_sec = la duracion de carrera del piloto mas lento (el que
    # define el largo total de la carrera). Antes se sumaba lap_duration de TODOS
    # los pilotos, haciendo el denominador ~N veces mas grande y colapsando toda
    # la simulacion en duration_seconds / N segundos.
    total_by_driver = {}
    for lap in all_laps:
        if lap["lap_duration"] is not None and not lap["is_pit_out_lap"]:
            dn = lap["driver_number"]
            total_by_driver[dn] = total_by_driver.get(dn, 0.0) + float(lap["lap_duration"])
    total_duration_sec = max(total_by_driver.values()) if total_by_driver else 0.0

    # Ordenar globalmente por lap_number para publicar en orden
    all_laps.sort(key=lambda lap: (lap["lap_number"] or 0, lap["driver_number"]))

    # Calcular el tiempo acumulado por piloto para obtener el delay proporcional
    sim_started_at = time_module.time()  # epoch float, unique per simulation run
    elapsed_by_driver = {}
    events = []
    for lap in all_laps:
        dn = lap["driver_number"]
        if dn not in elapsed_by_driver:
            elapsed_by_driver[dn] = 0.0

        lap_elapsed_time = elapsed_by_driver[dn]

        if total_duration_sec > 0:
            delay_seconds = (lap_elapsed_time / total_duration_sec) * duration_seconds
        else:
            delay_seconds = 0.0

        lap_duration_sec = float(lap["lap_duration"]) if lap["lap_duration"] is not None else None

        events.append({
            "session_key": session_key,
            "driver_number": dn,
            "lap_number": lap["lap_number"],
            "lap_duration_sec": lap_duration_sec,
            "position": lap.get("position"),
            "is_pit_out_lap": lap["is_pit_out_lap"],
            "st_speed": lap.get("st_speed"),
            "scheduled_delay_seconds": round(delay_seconds, 3),
            "sim_started_at": sim_started_at,
            "compression_ratio": (
                round(total_duration_sec / duration_seconds, 4) if duration_seconds else None
            ),
        })

        # Acumular solo vueltas con duración válida y no pit-out
        if lap_duration_sec is not None and not lap["is_pit_out_lap"]:
            elapsed_by_driver[dn] += lap_duration_sec

    now = datetime.now(timezone.utc).isoformat()

    # Reset LIVE#STATE for every driver before publishing events.
    # This clears stale data from the previous simulation so the frontend never
    # shows old lap/position data while the new race is starting.
    for driver in drivers:
        driver_number = int(driver["driver_number"])
        table.put_item(Item={
            "PK": f"SESSION#{session_key}#DRIVER#{driver_number}",
            "SK": "LIVE#STATE",
            "session_key": session_key,
            "driver_number": driver_number,
            "current_lap": 0,
            "status": "STARTING",
            "updated_at": now,
        })

    compression_ratio = (
        round(total_duration_sec / duration_seconds, 4) if duration_seconds else None
    )

    # Write SIMULATION#STATE BEFORE publishing to SQS. The consumer discards any
    # message whose session has no SIMULATION#STATE yet (treated as stale), so if
    # we published first the early laps (including lap 1) could be dropped while
    # this loop is still running — making a later lap appear first.
    table.put_item(Item={
        "PK": f"SESSION#{session_key}",
        "SK": "SIMULATION#STATE",
        "session_key": session_key,
        "status": "RUNNING",
        "duration_seconds": duration_seconds,
        "events_published": len(events),
        "events_processed": 0,
        "started_at": now,
        "updated_at": now,
        # epoch stored so the consumer can discard messages from previous runs
        "sim_epoch": decimal.Decimal(str(round(sim_started_at, 2))),
    })

    sqs = _get_sqs_client()
    queue_url = os.environ.get("SIMULATION_QUEUE_URL")

    # Purge any leftover messages from previous runs BEFORE publishing this run's
    # events. Without this, stale messages (a stopped/restarted run) linger in the
    # queue; the consumer drops them by epoch but in-flight messages from an
    # interrupted run could leave events_processed short of events_published, so
    # the race never reaches 100% / FINISHED. A clean queue per run guarantees the
    # consumer processes exactly the events we just published.
    try:
        sqs.purge_queue(QueueUrl=queue_url)
    except Exception as e:
        print(f"[WARN] purge_queue fallo (continuando): {e}")

    for evt in events:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(evt, cls=DecimalEncoder),
        )

    return _resp(200, {
        "session_key": session_key,
        "duration_seconds": duration_seconds,
        "total_session_duration_sec": round(total_duration_sec, 3),
        "compression_ratio": compression_ratio,
        "events_published": len(events),
        "status": "simulation_started",
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **_CORS},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
