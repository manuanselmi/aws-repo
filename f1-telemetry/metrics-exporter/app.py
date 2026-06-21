import os
import time

import boto3
from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

TABLE_NAME = os.environ.get("TABLE_NAME", "F1Telemetry")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localstack:4566")
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
AWS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET = os.environ.get("AWS_SECRET_ACCESS_KEY", "test")

events_processed_gauge = Gauge(
    "f1_simulation_events_processed_total",
    "Total events processed by consumer",
    ["session_key"],
)
events_published_gauge = Gauge(
    "f1_simulation_events_published_total",
    "Total events published by start-simulation",
    ["session_key"],
)
simulation_status_gauge = Gauge(
    "f1_simulation_status",
    "Simulation status (1=active for this status, 0=inactive)",
    ["session_key", "status"],
)
driver_speed_gauge = Gauge(
    "f1_driver_speed_kmh",
    "Driver current speed in km/h",
    ["session_key", "driver_number"],
)
driver_position_gauge = Gauge(
    "f1_driver_position",
    "Driver current race position",
    ["session_key", "driver_number"],
)
driver_gap_gauge = Gauge(
    "f1_driver_gap_seconds",
    "Driver gap in seconds",
    ["session_key", "driver_number"],
)
driver_lap_gauge = Gauge(
    "f1_driver_current_lap",
    "Driver current lap number",
    ["session_key", "driver_number"],
)


def get_table():
    dynamodb = boto3.resource(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET,
    )
    return dynamodb.Table(TABLE_NAME)


def collect_metrics():
    table = get_table()

    sim_result = table.scan(
        FilterExpression="SK = :sk",
        ExpressionAttributeValues={":sk": "SIMULATION#STATE"},
    )
    for item in sim_result.get("Items", []):
        sk = str(item.get("session_key", ""))
        status = item.get("status", "UNKNOWN")
        ep = item.get("events_processed", 0)
        epub = item.get("events_published", 0)

        events_processed_gauge.labels(session_key=sk).set(float(ep))
        events_published_gauge.labels(session_key=sk).set(float(epub))

        for s in ["RUNNING", "STOPPED", "FINISHED"]:
            simulation_status_gauge.labels(session_key=sk, status=s).set(
                1 if status == s else 0
            )

    live_result = table.scan(
        FilterExpression="SK = :sk",
        ExpressionAttributeValues={":sk": "LIVE#STATE"},
    )
    for item in live_result.get("Items", []):
        pk = item.get("PK", "")
        parts = pk.split("#")
        if len(parts) < 4:
            continue
        sk = parts[1]
        dn = parts[3]

        speed = item.get("speed")
        pos = item.get("position")
        gap = item.get("gap_ms")
        lap = item.get("current_lap")

        if speed is not None:
            driver_speed_gauge.labels(session_key=sk, driver_number=dn).set(float(speed))
        if pos is not None:
            driver_position_gauge.labels(session_key=sk, driver_number=dn).set(float(pos))
        if gap is not None:
            driver_gap_gauge.labels(session_key=sk, driver_number=dn).set(float(gap) / 1000.0)
        if lap is not None:
            driver_lap_gauge.labels(session_key=sk, driver_number=dn).set(float(lap))


@app.route("/metrics")
def metrics():
    try:
        collect_metrics()
    except Exception as e:
        print(f"[ERROR] collecting metrics: {e}")
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/health")
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9100)
