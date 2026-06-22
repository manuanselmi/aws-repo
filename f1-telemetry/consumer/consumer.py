import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3

TABLE_NAME = os.environ.get("TABLE_NAME", "F1Telemetry")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localstack:4566")
SQS_ENDPOINT = os.environ.get("SQS_ENDPOINT", "http://localstack:4566")
QUEUE_URL = os.environ.get("SIMULATION_QUEUE_URL", "http://localstack:4566/000000000000/SimulationQueue")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
AWS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET = os.environ.get("AWS_SECRET_ACCESS_KEY", "test")


def to_decimal(value):
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def get_table():
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET,
    )
    return dynamodb.Table(TABLE_NAME)


def get_sqs():
    return boto3.client(
        "sqs",
        endpoint_url=SQS_ENDPOINT,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET,
    )


def get_sim_state(table, session_key):
    return table.get_item(
        Key={"PK": f"SESSION#{session_key}", "SK": "SIMULATION#STATE"}
    ).get("Item")


def is_simulation_stopped(table, session_key):
    item = get_sim_state(table, session_key)
    return item is not None and item.get("status") == "STOPPED"


def is_stale_or_stopped(table, session_key, msg_epoch):
    """Returns True if the simulation is STOPPED or the message belongs to a different run."""
    item = get_sim_state(table, session_key)
    if item is None:
        return True
    if item.get("status") == "STOPPED":
        return True
    current_epoch = round(float(item.get("sim_epoch") or 0), 2)
    if current_epoch > 0 and round(float(msg_epoch), 2) != current_epoch:
        return True
    return False


def update_live_state(table, session_key, driver_number, event):
    now = datetime.now(timezone.utc).isoformat()

    # Use update_item instead of put_item so fields not present in this event
    # (e.g. st_speed=None on certain laps) are preserved from the previous state.
    update_parts = [
        "current_lap = :lap",
        "#pos = :pos",
        "#st = :run",
        "updated_at = :now",
        "session_key = :sk",
        "driver_number = :dn",
    ]
    expr_values = {
        ":lap": to_decimal(event.get("lap_number")),
        ":pos": to_decimal(event.get("position")),
        ":run": "RUNNING",
        ":now": now,
        ":sk":  session_key,
        ":dn":  driver_number,
    }
    # position and status are DynamoDB reserved words — must alias them
    expr_names = {"#pos": "position", "#st": "status"}

    if event.get("st_speed") is not None:
        update_parts.append("speed = :spd")
        expr_values[":spd"] = to_decimal(event["st_speed"])

    if event.get("gap_ms") is not None:
        update_parts.append("gap_ms = :gap")
        expr_values[":gap"] = to_decimal(event["gap_ms"])

    if event.get("lap_duration_sec") is not None:
        update_parts.append("lap_duration_sec = :dur")
        expr_values[":dur"] = to_decimal(event["lap_duration_sec"])

    try:
        table.update_item(
            Key={"PK": f"SESSION#{session_key}#DRIVER#{driver_number}", "SK": "LIVE#STATE"},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )
    except Exception as e:
        print(f"[WARN] No se pudo actualizar LIVE#STATE driver={driver_number}: {e}")

    # Always increment events_processed — even if the live state update failed.
    try:
        table.update_item(
            Key={"PK": f"SESSION#{session_key}", "SK": "SIMULATION#STATE"},
            UpdateExpression=(
                "SET events_processed = if_not_exists(events_processed, :zero) + :one,"
                " updated_at = :now"
            ),
            ExpressionAttributeValues={":zero": 0, ":one": 1, ":now": now},
        )
    except Exception as e:
        print(f"[WARN] No se pudo incrementar events_processed: {e}")


def get_sleep_needed(session_key, sim_started_at, scheduled_delay):
    """Seconds to wait before this lap event should be applied.

    Timing is anchored on the *absolute* simulation start time (``sim_started_at``,
    an epoch float written by start-simulation) — NOT on whichever message the
    consumer happens to pull first. ``SimulationQueue`` is a standard SQS queue and
    delivers out of order, so anchoring on the first-received message let a
    high-delay lap (e.g. lap 41) define t=0 and fire immediately — the
    "lap 41 shows instead of lap 1" bug. The Lambda and the consumer share the same
    Docker host clock, so the epoch is directly comparable to ``time.time()`` here.

    A negative result means the event is already "due" (the simulation started a
    few seconds ago) and should be applied immediately.
    """
    if sim_started_at is None:
        return 0.0
    return (float(sim_started_at) + float(scheduled_delay)) - time.time()


def process_message(table, sqs, queue_url, message):
    body = json.loads(message["Body"])
    session_key = body.get("session_key")
    driver_number = body.get("driver_number")

    if session_key is None or driver_number is None:
        print("[WARN] Mensaje sin session_key o driver_number, descartando.")
        return

    msg_epoch = round(float(body.get("sim_started_at") or 0), 2)

    # Discard messages that belong to a different (older) simulation run.
    # When a sim is stopped early, its unprocessed SQS messages linger.
    # The next run publishes new messages with a new sim_epoch; comparing
    # epoch ensures stale messages are silently dropped.
    if is_stale_or_stopped(table, session_key, msg_epoch):
        print(
            f"[INFO] {session_key} STOPPED o mensaje de sim diferente "
            f"(epoch={msg_epoch}) — descartado."
        )
        return

    # Wait until this event's scheduled wall-clock time
    scheduled_delay = float(body.get("scheduled_delay_seconds") or 0)
    sim_started_at = body.get("sim_started_at")
    sleep_needed = get_sleep_needed(session_key, sim_started_at, scheduled_delay)

    if sleep_needed > 0.05:
        # Extend visibility so message doesn't go back to the queue during long sleeps
        if sleep_needed > 10:
            try:
                sqs.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=message["ReceiptHandle"],
                    VisibilityTimeout=min(int(sleep_needed) + 60, 43200),
                )
            except Exception as e:
                print(f"[WARN] No se pudo extender visibility: {e}")

        # Sleep in 100ms chunks so we can detect STOP or new-sim-epoch quickly
        slept = 0.0
        while slept < sleep_needed:
            chunk = min(0.1, sleep_needed - slept)
            time.sleep(chunk)
            slept += chunk
            if is_stale_or_stopped(table, session_key, msg_epoch):
                print(f"[INFO] {session_key} STOPPED o epoch cambio durante espera — descartado.")
                return

    update_live_state(table, session_key, driver_number, body)
    print(
        f"[OK] session={session_key} driver={driver_number} "
        f"lap={body.get('lap_number')} pos={body.get('position')}"
    )


def _scheduled_delay(message):
    """Best-effort read of scheduled_delay_seconds for ordering a received batch."""
    try:
        return float(json.loads(message["Body"]).get("scheduled_delay_seconds") or 0)
    except Exception:
        return 0.0


def wait_for_sqs(sqs):
    for attempt in range(30):
        try:
            sqs.get_queue_url(QueueName="SimulationQueue")
            print("[CONSUMER] Cola SQS lista.")
            return
        except Exception:
            print(f"[CONSUMER] Esperando SQS... intento {attempt + 1}/30")
            time.sleep(3)
    raise RuntimeError("SQS no disponible despues de 90 segundos.")


def main():
    print(f"[CONSUMER] Iniciando — cola: {QUEUE_URL}")
    sqs = get_sqs()
    wait_for_sqs(sqs)
    table = get_table()

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5,
            )
            # Standard SQS delivers out of order; process the earliest lap first
            # so a high-delay event can't block lower laps queued behind it.
            messages = sorted(response.get("Messages", []), key=_scheduled_delay)
            for msg in messages:
                try:
                    process_message(table, sqs, QUEUE_URL, msg)
                    sqs.delete_message(
                        QueueUrl=QUEUE_URL,
                        ReceiptHandle=msg["ReceiptHandle"],
                    )
                except Exception as e:
                    print(f"[ERROR] procesando mensaje: {e}")
        except Exception as e:
            print(f"[ERROR] recibiendo mensajes: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
