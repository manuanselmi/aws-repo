import importlib.util
import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

_mock_table = MagicMock()
sys.modules["dynamo_client"] = MagicMock(get_table=MagicMock(return_value=_mock_table))

_spec = importlib.util.spec_from_file_location(
    "_driver_laps_handler",
    os.path.join(os.path.dirname(__file__), "..", "functions", "driver-laps", "handler.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
handler = _mod.handler


@pytest.fixture(autouse=True)
def reset_mocks():
    _mock_table.reset_mock()


def _event(session_key, driver_id):
    return {"pathParameters": {"session_key": str(session_key), "driver_id": str(driver_id)}}


def test_returns_laps_sorted_by_lap_number():
    _mock_table.get_item.return_value = {
        "Item": {
            "PK": "SESSION#1",
            "SK": "DRIVER#1",
            "driver_number": 44,
            "full_name": "Lewis Hamilton",
        }
    }
    _mock_table.query.return_value = {
        "Items": [
            {"lap_number": 2, "lap_duration": Decimal("89.1"), "position": 1, "is_pit_out_lap": False},
            {"lap_number": 1, "lap_duration": Decimal("88.5"), "position": 2, "is_pit_out_lap": False},
        ]
    }

    result = handler(_event(1, 1), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["laps_count"] == 2
    assert body["laps"][0]["lap_number"] == 1
    assert body["laps"][1]["lap_number"] == 2
    assert body["full_name"] == "Lewis Hamilton"


def test_driver_not_found_returns_404():
    _mock_table.get_item.return_value = {}

    result = handler(_event(1, 99), None)

    assert result["statusCode"] == 404


def test_no_laps_returns_404():
    _mock_table.get_item.return_value = {
        "Item": {"driver_number": 44, "full_name": "Lewis Hamilton"}
    }
    _mock_table.query.return_value = {"Items": []}

    result = handler(_event(1, 1), None)

    assert result["statusCode"] == 404


def test_missing_params_returns_400():
    result = handler({"pathParameters": {"session_key": "1"}}, None)

    assert result["statusCode"] == 400


def test_non_integer_params_return_400():
    result = handler({"pathParameters": {"session_key": "x", "driver_id": "1"}}, None)

    assert result["statusCode"] == 400


def test_lap_duration_none_is_handled():
    _mock_table.get_item.return_value = {
        "Item": {"driver_number": 44, "full_name": "Lewis Hamilton"}
    }
    _mock_table.query.return_value = {
        "Items": [
            {"lap_number": 1, "lap_duration": None, "position": 3, "is_pit_out_lap": False},
        ]
    }

    result = handler(_event(1, 1), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["laps"][0]["lap_duration_sec"] is None
