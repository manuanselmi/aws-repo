"""
Lambda: driver_laps
Descripcion: Lista todas las vueltas de un piloto en una sesion,
             incluyendo la posicion en la que termino cada vuelta.
             NO llama a OpenF1.

GET /sessions/{session_key}/drivers/{driver_number}/laps
"""
import json
import decimal
from boto3.dynamodb.conditions import Key

from dynamo_client import get_table


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    session_key = path_params.get("session_key") or event.get("session_key")
    driver_number = path_params.get("driver_number") or event.get("driver_number")

    if not session_key or not driver_number:
        return _resp(400, {"error": "session_key y driver_number son requeridos en el path"})

    try:
        session_key = int(session_key)
        driver_number = int(driver_number)
    except (ValueError, TypeError):
        return _resp(400, {"error": "session_key y driver_number deben ser numeros enteros"})

    table = get_table()

    # Verificar que el piloto existe en la sesion
    driver_item = table.get_item(
        Key={"PK": f"SESSION#{session_key}", "SK": f"DRIVER#{driver_number}"}
    ).get("Item")
    if not driver_item:
        return _resp(404, {
            "error": f"Piloto {driver_number} no encontrado en sesion {session_key}.",
            "hint": f"Verificar que la sesion fue ingestada con POST /sessions/{session_key}/ingest",
        })

    # Consultar todas las vueltas: PK = SESSION#sk#DRIVER#dn
    result = table.query(
        KeyConditionExpression=Key("PK").eq(f"SESSION#{session_key}#DRIVER#{driver_number}")
    )
    laps = result.get("Items", [])

    if not laps:
        return _resp(404, {
            "error": f"No hay vueltas registradas para el piloto {driver_number} en la sesion {session_key}.",
        })

    # Ordenar por numero de vuelta
    laps.sort(key=lambda l: l.get("lap_number", 0))

    laps_response = [
        {
            "lap_number": lap.get("lap_number"),
            "lap_duration_sec": float(lap["lap_duration"]) if lap.get("lap_duration") else None,
            "st_speed_kmh": float(lap["st_speed"]) if lap.get("st_speed") else None,
            "i1_speed_kmh": float(lap["i1_speed"]) if lap.get("i1_speed") else None,
            "i2_speed_kmh": float(lap["i2_speed"]) if lap.get("i2_speed") else None,
            "position": lap.get("position"),
            "is_pit_out_lap": lap.get("is_pit_out_lap", False),
            "date_start": lap.get("date_start"),
        }
        for lap in laps
    ]

    return _resp(200, {
        "session_key": session_key,
        "driver_number": driver_number,
        "full_name": driver_item.get("full_name"),
        "laps_count": len(laps_response),
        "laps": laps_response,
    })


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=DecimalEncoder),
    }
