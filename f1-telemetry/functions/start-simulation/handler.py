import json
import os
import decimal
import boto3
from boto3.dynamodb.conditions import Key

from dynamo_client import get_table


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
        laps_result = table.query(
            KeyConditionExpression=Key("PK").eq(
                f"SESSION#{session_key}#DRIVER#{driver_number}"
            )
        )
        for lap in laps_result.get("Items", []):
            all_laps.append({
                "driver_number": driver_number,
                "lap_number": lap.get("lap_number"),
                "lap_duration": lap.get("lap_duration"),
                "position": lap.get("position"),
                "is_pit_out_lap": lap.get("is_pit_out_lap", False),
            })

    if not all_laps:
        return _resp(422, {"error": f"La sesion {session_key} no tiene vueltas registradas."})

    # Calcular total_duration_sec: suma de lap_duration excluyendo nulos y pit-out laps
    total_duration_sec = sum(
        float(lap["lap_duration"])
        for lap in all_laps
        if lap["lap_duration"] is not None and not lap["is_pit_out_lap"]
    )

    # Ordenar globalmente por lap_number para publicar en orden
    all_laps.sort(key=lambda l: (l["lap_number"] or 0, l["driver_number"]))

    # Calcular el tiempo acumulado por piloto para obtener el delay proporcional
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
            "scheduled_delay_seconds": round(delay_seconds, 3),
            "compression_ratio": round(total_duration_sec / duration_seconds, 4) if duration_seconds else None,
        })

        # Acumular solo vueltas con duración válida y no pit-out
        if lap_duration_sec is not None and not lap["is_pit_out_lap"]:
            elapsed_by_driver[dn] += lap_duration_sec

    sqs = _get_sqs_client()
    queue_url = os.environ.get("SIMULATION_QUEUE_URL")

    for evt in events:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(evt, cls=DecimalEncoder),
        )

    compression_ratio = round(total_duration_sec / duration_seconds, 4) if duration_seconds else None

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
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
