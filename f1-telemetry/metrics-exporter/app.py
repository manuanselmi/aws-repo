import os

import boto3
from flask import Flask, Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

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
    ["session_key", "driver_number", "driver_name"],
)
driver_position_gauge = Gauge(
    "f1_driver_position",
    "Driver current race position",
    ["session_key", "driver_number", "driver_name"],
)
driver_gap_gauge = Gauge(
    "f1_driver_gap_seconds",
    "Driver gap in seconds",
    ["session_key", "driver_number", "driver_name"],
)
driver_lap_gauge = Gauge(
    "f1_driver_current_lap",
    "Driver current lap number",
    ["session_key", "driver_number", "driver_name"],
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

    # Clear every series before re-reading DynamoDB so each scrape reflects ONLY
    # the current state. Without this, gauges keep stale label sets for the life
    # of the process (e.g. old driver_name="#N" labels, or drivers from a previous
    # run), which shows up as duplicated series in Grafana.
    for g in (
        events_processed_gauge,
        events_published_gauge,
        simulation_status_gauge,
        driver_speed_gauge,
        driver_position_gauge,
        driver_gap_gauge,
        driver_lap_gauge,
    ):
        g.clear()

    # Build a (session_key, driver_number) -> name map so metrics can be labeled
    # with the driver's acronym/name instead of just the bare race number.
    name_map = {}
    drivers_result = table.scan(
        FilterExpression="begins_with(SK, :p)",
        ExpressionAttributeValues={":p": "DRIVER#"},
    )
    for item in drivers_result.get("Items", []):
        pk = str(item.get("PK", ""))
        if not pk.startswith("SESSION#"):
            continue
        sk = pk.split("#")[1]
        dn = str(item.get("driver_number", ""))
        name = item.get("name_acronym") or item.get("full_name") or f"#{dn}"
        name_map[(sk, dn)] = name

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
    # Group live states by session so we can compute a UNIQUE race ranking.
    by_session = {}
    for item in live_result.get("Items", []):
        parts = str(item.get("PK", "")).split("#")
        if len(parts) < 4:
            continue
        by_session.setdefault(parts[1], []).append((parts[3], item))

    for sk, drivers in by_session.items():
        rank_map = _rank_drivers(drivers)
        for dn, item in drivers:
            name = name_map.get((sk, dn), f"#{dn}")
            speed = item.get("speed")
            gap = item.get("gap_ms")
            lap = item.get("current_lap")

            # Position uses the computed unique rank (not the raw per-driver value)
            driver_position_gauge.labels(
                session_key=sk, driver_number=dn, driver_name=name
            ).set(float(rank_map[dn]))
            if speed is not None:
                driver_speed_gauge.labels(
                    session_key=sk, driver_number=dn, driver_name=name
                ).set(float(speed))
            if gap is not None:
                driver_gap_gauge.labels(
                    session_key=sk, driver_number=dn, driver_name=name
                ).set(float(gap) / 1000.0)
            if lap is not None:
                driver_lap_gauge.labels(
                    session_key=sk, driver_number=dn, driver_name=name
                ).set(float(lap))


def _rank_drivers(drivers):
    """Assign a unique 1..N race position to each driver in a session.

    The raw per-driver ``position`` can repeat: at a given instant drivers sit on
    different laps (the sim applies each driver's laps at slightly different times)
    and a car that fell back keeps its last position, so two drivers may report the
    same number. We rebuild a unique order: cars on more laps rank ahead; cars that
    fell >2 laps behind the leader (or lost their position) are classified at the
    back — mirroring how DNFs are ranked.
    """
    def _num(v, default):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _dn(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    laps = [_num(it.get("current_lap"), 0.0) for _, it in drivers]
    leader_lap = max(laps) if laps else 0.0

    enriched = []
    for dn, it in drivers:
        lap = _num(it.get("current_lap"), 0.0)
        has_pos = it.get("position") is not None
        pos = _num(it.get("position"), 999.0)
        retired = leader_lap > 3 and (lap < leader_lap - 2 or not has_pos)
        enriched.append((dn, lap, pos, retired))

    active = sorted((e for e in enriched if not e[3]), key=lambda e: (e[2], _dn(e[0])))
    out = sorted((e for e in enriched if e[3]), key=lambda e: (-e[1], _dn(e[0])))
    ordered = list(active) + list(out)
    return {e[0]: i + 1 for i, e in enumerate(ordered)}


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
