import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock

import pytest

_mock_table = MagicMock()
sys.modules["dynamo_client"] = MagicMock(get_table=MagicMock(return_value=_mock_table))

_spec = importlib.util.spec_from_file_location(
    "_list_sessions_handler",
    os.path.join(os.path.dirname(__file__), "..", "functions", "list-sessions", "handler.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
handler = _mod.handler


@pytest.fixture(autouse=True)
def reset_mocks():
    _mock_table.reset_mock()


def test_returns_sessions_list():
    _mock_table.scan.return_value = {
        "Items": [
            {
                "PK": "SESSION#1",
                "SK": "#METADATA",
                "session_key": 1,
                "session_name": "Race",
                "country_name": "Bahrain",
                "date_start": "2024-03-02T00:00:00",
                "year": 2024,
                "circuit_short_name": "BAH",
            },
            {
                "PK": "SESSION#2",
                "SK": "#METADATA",
                "session_key": 2,
                "session_name": "Qualifying",
                "country_name": "Monaco",
                "date_start": "2024-05-25T00:00:00",
                "year": 2024,
                "circuit_short_name": "MON",
            },
        ]
    }

    result = handler({}, None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["sessions_count"] == 2
    assert body["sessions"][0]["session_key"] == 1
    assert body["sessions"][1]["country_name"] == "Monaco"


def test_no_sessions_returns_404():
    _mock_table.scan.return_value = {"Items": []}

    result = handler({}, None)

    assert result["statusCode"] == 404
    body = json.loads(result["body"])
    assert "error" in body


def test_response_has_correct_fields():
    _mock_table.scan.return_value = {
        "Items": [
            {
                "session_key": 9149,
                "session_name": "Race",
                "country_name": "Australia",
                "date_start": "2023-04-02",
                "year": 2023,
                "circuit_short_name": "Melbourne",
            }
        ]
    }

    result = handler({}, None)

    body = json.loads(result["body"])
    session = body["sessions"][0]
    for field in ["session_key", "session_name", "country_name", "date_start", "year", "circuit_short_name"]:
        assert field in session
