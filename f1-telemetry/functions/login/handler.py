import json
import os

VALID_USERNAME = os.environ.get("LOGIN_USERNAME", "admin")
VALID_PASSWORD = os.environ.get("LOGIN_PASSWORD", "admin")

_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": _CORS, "body": ""}

    body = {}
    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except Exception:
            return _resp(400, {"error": "Body JSON invalido"})

    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        return _resp(400, {"error": "username y password son requeridos"})

    if username == VALID_USERNAME and password == VALID_PASSWORD:
        return _resp(200, {
            "access_token": "local-dev-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        })

    return _resp(401, {"error": "Credenciales invalidas"})


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **_CORS},
        "body": json.dumps(body),
    }
