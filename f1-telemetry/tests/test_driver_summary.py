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
    "_driver_summary_handler",
    os.path.join(os.path.dirname(__file__), "..", "functions", "driver-summary", "handler.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
handler = _mod.handler


@pytest.fixture(autouse=True)
def reset_mocks():
    _mock_table.reset_mock()


def _event(session_key, driver_id):
    return {"pathParameters": {"session_key": str(session_key), "driver_id": str(driver_id)}}


def test_returns_summary_with_computed_stats():
    _mock_table.get_item.return_value = {
        "Item": {
            "PK": "SESSION#1",
            "SK": "DRIVER#1",
            "driver_number": 44,
            "full_name": "Lewis Hamilton",
            "name_acronym": "HAM",
            "team_name": "Mercedes",
        }
    }
    _mock_table.query.return_value = {
        "Items": [
            {"lap_duration": Decimal("88.5"), "st_speed": Decimal("310"), "is_pit_out_lap": False},
            {"lap_duration": Decimal("89.1"), "st_speed": Decimal("315"), "is_pit_out_lap": False},
            {"lap_duration": Decimal("91.0"), "st_speed": Decimal("305"), "is_pit_out_lap": True},
        ]
    }

    result = handler(_event(1, 1), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["full_name"] == "Lewis Hamilton"
    assert body["best_lap_duration_sec"] == 88.5
    assert body["max_speed_kmh"] == 315.0
    assert body["lap_count"] == 3


def test_driver_not_found_returns_404():
    _mock_table.get_item.return_value = {}

    result = handler(_event(1, 99), None)

    assert result["statusCode"] == 404


def test_no_laps_returns_422():
    _mock_table.get_item.return_value = {
        "Item": {
            "driver_number": 44,
            "full_name": "Lewis Hamilton",
            "name_acronym": "HAM",
            "team_name": "Mercedes",
        }
    }
    _mock_table.query.return_value = {"Items": []}

    result = handler(_event(1, 1), None)

    assert result["statusCode"] == 422


def test_missing_session_key_returns_400():
    result = handler({"pathParameters": {"driver_id": "1"}}, None)

    assert result["statusCode"] == 400


def test_missing_driver_id_returns_400():
    result = handler({"pathParameters": {"session_key": "1"}}, None)

    assert result["statusCode"] == 400


def test_non_integer_params_return_400():
    result = handler({"pathParameters": {"session_key": "abc", "driver_id": "1"}}, None)

    assert result["statusCode"] == 400


def test_pit_out_laps_excluded_from_best_lap():
    _mock_table.get_item.return_value = {
        "Item": {
            "driver_number": 1,
            "full_name": "Max Verstappen",
            "name_acronym": "VER",
            "team_name": "Red Bull",
        }
    }
    _mock_table.query.return_value = {
        "Items": [
            {"lap_duration": Decimal("85.0"), "st_speed": Decimal("320"), "is_pit_out_lap": True},
            {"lap_duration": Decimal("90.0"), "st_speed": Decimal("310"), "is_pit_out_lap": False},
        ]
    }

    result = handler(_event(1, 1), None)

    body = json.loads(result["body"])
    assert body["best_lap_duration_sec"] == 90.0
