import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock

import pytest

_mock_table = MagicMock()
sys.modules["dynamo_client"] = MagicMock(get_table=MagicMock(return_value=_mock_table))

_spec = importlib.util.spec_from_file_location(
    "_list_drivers_handler",
    os.path.join(os.path.dirname(__file__), "..", "functions", "list-drivers", "handler.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
handler = _mod.handler


@pytest.fixture(autouse=True)
def reset_mocks():
    _mock_table.reset_mock()


def _event(session_key):
    return {"pathParameters": {"session_key": str(session_key)}}


def test_returns_drivers_for_existing_session():
    _mock_table.get_item.return_value = {"Item": {"PK": "SESSION#1", "SK": "#METADATA"}}
    _mock_table.query.return_value = {
        "Items": [
            {"SK": "DRIVER#1", "driver_number": 44, "full_name": "Lewis Hamilton", "team_name": "Mercedes"},
            {"SK": "DRIVER#2", "driver_number": 1, "full_name": "Max Verstappen", "team_name": "Red Bull"},
        ]
    }

    result = handler(_event(1), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["drivers_count"] == 2
    assert body["drivers"][0]["driver_id"] == 1
    assert body["drivers"][1]["full_name"] == "Max Verstappen"


def test_session_not_found_returns_404():
    _mock_table.get_item.return_value = {}

    result = handler(_event(999), None)

    assert result["statusCode"] == 404
    body = json.loads(result["body"])
    assert "error" in body


def test_missing_session_key_returns_400():
    result = handler({"pathParameters": {}}, None)

    assert result["statusCode"] == 400


def test_non_integer_session_key_returns_400():
    result = handler({"pathParameters": {"session_key": "abc"}}, None)

    assert result["statusCode"] == 400


def test_empty_drivers_list_still_returns_200():
    _mock_table.get_item.return_value = {"Item": {"PK": "SESSION#1", "SK": "#METADATA"}}
    _mock_table.query.return_value = {"Items": []}

    result = handler(_event(1), None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["drivers_count"] == 0
