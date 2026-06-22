import importlib.util
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_mock_table = MagicMock()
sys.modules["dynamo_client"] = MagicMock(get_table=MagicMock(return_value=_mock_table))

_spec = importlib.util.spec_from_file_location(
    "_ingest_session_handler",
    os.path.join(os.path.dirname(__file__), "..", "functions", "ingest-session", "handler.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
handler = _mod.handler


@pytest.fixture(autouse=True)
def reset_mocks():
    _mock_table.reset_mock()


def _make_url_response(data):
    inner = MagicMock()
    inner.read.return_value = json.dumps(data).encode()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=inner)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


_SESSION_DATA = [
    {
        "session_key": 9149,
        "session_name": "Race",
        "session_type": "Race",
        "date_start": "2023-04-02T06:00:00",
        "year": 2023,
        "country_name": "Australia",
        "circuit_short_name": "Melbourne",
    }
]
_DRIVERS_DATA = [
    {
        "driver_number": 44,
        "full_name": "Lewis Hamilton",
        "name_acronym": "HAM",
        "team_name": "Mercedes",
    }
]
_LAPS_DATA = [
    {
        "driver_number": 44,
        "lap_number": 1,
        "lap_duration": 88.5,
        "date_start": "2023-04-02T06:05:00",
        "i1_speed": 290,
        "i2_speed": 300,
        "st_speed": 310,
        "duration_sector_1": 30.1,
        "duration_sector_2": 28.5,
        "duration_sector_3": 29.9,
        "is_pit_out_lap": False,
    }
]
_POSITIONS_DATA = [
    {"driver_number": 44, "position": 1, "date": "2023-04-02T06:06:30"},
]


def test_ingest_new_session():
    _mock_table.get_item.return_value = {}
    batch_mock = MagicMock()
    _mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=batch_mock)
    _mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            _make_url_response(_SESSION_DATA),
            _make_url_response(_DRIVERS_DATA),
            _make_url_response(_LAPS_DATA),
            _make_url_response(_POSITIONS_DATA),
        ]

        result = handler({"pathParameters": {"session_key": "9149"}}, None)

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["status"] == "ingested"
    assert body["session_key"] == 9149
    assert body["drivers_count"] == 1
    assert body["laps_count"] == 1


def test_already_ingested_returns_409():
    _mock_table.get_item.return_value = {"Item": {"PK": "SESSION#9149", "SK": "#METADATA"}}

    result = handler({"pathParameters": {"session_key": "9149"}}, None)

    assert result["statusCode"] == 409
    body = json.loads(result["body"])
    assert "hint" in body


def test_force_reingest_overwrites_existing():
    _mock_table.get_item.return_value = {"Item": {"PK": "SESSION#9149", "SK": "#METADATA"}}
    batch_mock = MagicMock()
    _mock_table.batch_writer.return_value.__enter__ = MagicMock(return_value=batch_mock)
    _mock_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = [
            _make_url_response(_SESSION_DATA),
            _make_url_response(_DRIVERS_DATA),
            _make_url_response(_LAPS_DATA),
            _make_url_response(_POSITIONS_DATA),
        ]

        result = handler(
            {
                "pathParameters": {"session_key": "9149"},
                "body": json.dumps({"force": True}),
            },
            None,
        )

    assert result["statusCode"] == 200


def test_session_not_found_in_openf1_returns_404():
    _mock_table.get_item.return_value = {}

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_url_response([])

        result = handler({"pathParameters": {"session_key": "0000"}}, None)

    assert result["statusCode"] == 404


def test_missing_session_key_returns_400():
    result = handler({"pathParameters": {}}, None)

    assert result["statusCode"] == 400


def test_non_integer_session_key_returns_400():
    result = handler({"pathParameters": {"session_key": "xyz"}}, None)

    assert result["statusCode"] == 400
