import importlib.util
import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

_mock_table = MagicMock()
sys.modules["dynamo_client"] = MagicMock(get_table=MagicMock(return_value=_mock_table))

_spec = importlib.util.spec_from_file_location(
    "_start_simulation_handler",
    os.path.join(os.path.dirname(__file__), "..", "functions", "start-simulation", "handler.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
handler = _mod.handler


@pytest.fixture(autouse=True)
def reset_mocks():
    _mock_table.reset_mock()


def _event(session_key, duration_seconds):
    return {"body": json.dumps({"session_key": session_key, "duration_seconds": duration_seconds})}


_DRIVER_ITEM = {
    "PK": "SESSION#1",
    "SK": "DRIVER#1",
    "driver_number": 44,
    "full_name": "Lewis Hamilton",
}
_LAP_ITEMS = [
    {
        "PK": "SESSION#1#DRIVER#44",
        "SK": "LAP#001",
        "lap_number": 1,
        "lap_duration": Decimal("88.5"),
        "position": 2,
        "is_pit_out_lap": False,
    },
    {
        "PK": "SESSION#1#DRIVER#44",
        "SK": "LAP#002",
        "lap_number": 2,
        "lap_duration": Decimal("89.0"),
        "position": 1,
        "is_pit_out_lap": False,
    },
]

_ENV = {"SIMULATION_QUEUE_URL": "http://localhost:4566/000000000000/SimulationQueue", "SQS_ENDPOINT": "http://localhost:4566"}


def test_starts_simulation_and_publishes_events():
    _mock_table.get_item.return_value = {"Item": {"PK": "SESSION#1", "SK": "#METADATA"}}
    _mock_table.query.side_effect = [
        {"Items": [_DRIVER_ITEM]},
        {"Items": _LAP_ITEMS},
    ]

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {}

    with patch("boto3.client", return_value=mock_sqs):
        with patch.dict(os.environ, _ENV):
            result = handler(_event(1, 60), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["events_published"] == 2
    assert body["status"] == "simulation_started"
    assert body["session_key"] == 1
    assert mock_sqs.send_message.call_count == 2


def test_session_not_found_returns_404():
    _mock_table.get_item.return_value = {}

    result = handler(_event(999, 60), None)

    assert result["statusCode"] == 404


def test_no_laps_returns_422():
    _mock_table.get_item.return_value = {"Item": {"PK": "SESSION#1", "SK": "#METADATA"}}
    _mock_table.query.side_effect = [
        {"Items": [_DRIVER_ITEM]},
        {"Items": []},
    ]

    mock_sqs = MagicMock()
    with patch("boto3.client", return_value=mock_sqs):
        with patch.dict(os.environ, {"SIMULATION_QUEUE_URL": "http://test/q", "SQS_ENDPOINT": ""}):
            result = handler(_event(1, 60), None)

    assert result["statusCode"] == 422


def test_missing_session_key_returns_400():
    result = handler({"body": json.dumps({"duration_seconds": 60})}, None)

    assert result["statusCode"] == 400


def test_missing_duration_returns_400():
    result = handler({"body": json.dumps({"session_key": 1})}, None)

    assert result["statusCode"] == 400


def test_negative_session_key_returns_400():
    result = handler(_event(-1, 60), None)

    assert result["statusCode"] == 400


def test_zero_duration_returns_400():
    result = handler(_event(1, 0), None)

    assert result["statusCode"] == 400


def test_invalid_json_body_returns_400():
    result = handler({"body": "not-json"}, None)

    assert result["statusCode"] == 400


def test_compression_ratio_is_computed():
    _mock_table.get_item.return_value = {"Item": {"PK": "SESSION#1", "SK": "#METADATA"}}
    _mock_table.query.side_effect = [
        {"Items": [_DRIVER_ITEM]},
        {"Items": _LAP_ITEMS},
    ]

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {}

    with patch("boto3.client", return_value=mock_sqs):
        with patch.dict(os.environ, {"SIMULATION_QUEUE_URL": "http://test/q", "SQS_ENDPOINT": ""}):
            result = handler(_event(1, 30), None)

    body = json.loads(result["body"])
    assert body["compression_ratio"] == round(177.5 / 30, 4)
    assert body["total_session_duration_sec"] == 177.5
