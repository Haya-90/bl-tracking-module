"""
Tests for shipsgo_client.py, rebuilt against ShipsGo's real, pasted v2
OpenAPI spec. No real network access to api.shipsgo.com is available here
(no real account token exists to test with, and the domain isn't reachable
from this sandbox), so requests.get/post are mocked using response shapes
taken directly from ShipsGo's own documented examples.
"""
from unittest.mock import patch, MagicMock

import pytest

import app.infrastructure.live_tracking.shipsgo_client as shipsgo_client
from app.infrastructure.live_tracking.shipsgo_client import (
    create_shipment,
    get_shipment,
    get_shipment_route,
    extract_current_position,
    ShipsGoNotConfigured,
    ShipsGoOutOfCredits,
    ShipsGoForbidden,
    ShipsGoRequestError,
)

# Real example shapes, transcribed from the pasted ShipsGo v2 spec.
AIR_CREATE_SUCCESS = {
    "message": "SUCCESS",
    "shipment": {"id": 123456, "reference": "INTERNAL_UNIQUE_IDENTIFIER", "awb_number": "333-88888888"},
}
AIR_GEOJSON_EXAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [136.8, 34.9]},
         "properties": {"status": "PAST", "location": {"iata": "NGO"}}},
        {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[136.8, 34.9], [139.0, 37.7]]},
         "properties": {"status": "CURRENT", "flight": "KJ65",
                        "current": {"index": 1, "coordinates": [138.988092, 37.692851]}}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-84.7, 39.0]},
         "properties": {"status": "FUTURE", "location": {"iata": "CVG"}}},
    ],
}


def _fresh(token="TESTTOKEN"):
    shipsgo_client._cache.clear()
    shipsgo_client.API_TOKEN = token


def test_raises_not_configured_while_still_on_placeholder():
    _fresh(token=shipsgo_client._PLACEHOLDER_TOKEN)
    with pytest.raises(ShipsGoNotConfigured):
        create_shipment("air", reference="X", identifier="333-88888888")


def test_create_air_shipment_sends_correct_field_name():
    """ShipsGo's spec confirms the air field is literally `awb_number`."""
    _fresh()
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = AIR_CREATE_SUCCESS
    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = create_shipment("air", reference="REF1", identifier="333-88888888")
    assert result["id"] == 123456
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"reference": "REF1", "awb_number": "333-88888888"}
    assert kwargs["headers"]["X-Shipsgo-User-Token"] == "TESTTOKEN"


def test_create_ocean_shipment_sends_bl_number_field():
    _fresh()
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"shipment": {"id": 7, "reference": "REF2"}}
    with patch("requests.post", return_value=mock_resp) as mock_post:
        create_shipment("ocean", reference="REF2", identifier="MSCU7741205")
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"reference": "REF2", "bl_number": "MSCU7741205"}


def test_duplicate_409_is_treated_as_success_not_error():
    """Per ShipsGo's own docs: a 409 on create returns the EXISTING
    shipment's data at no cost - this must not raise, and must not be
    treated as a failed registration."""
    _fresh()
    mock_resp = MagicMock(status_code=409)
    mock_resp.json.return_value = {"shipment": {"id": 999, "reference": "REF1"}}
    with patch("requests.post", return_value=mock_resp):
        result = create_shipment("air", reference="REF1", identifier="333-88888888")
    assert result["id"] == 999


def test_402_raises_out_of_credits():
    _fresh()
    mock_resp = MagicMock(status_code=402)
    mock_resp.text = "Not enough credits"
    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(ShipsGoOutOfCredits):
            create_shipment("air", reference="REF1", identifier="333-88888888")


def test_403_raises_forbidden():
    _fresh()
    mock_resp = MagicMock(status_code=403)
    mock_resp.text = "Forbidden"
    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(ShipsGoForbidden):
            create_shipment("air", reference="REF1", identifier="333-88888888")


def test_422_raises_request_error():
    _fresh()
    mock_resp = MagicMock(status_code=422)
    mock_resp.text = "Malformed payload"
    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(ShipsGoRequestError):
            create_shipment("air", reference="REF1", identifier="bad-format")


def test_get_shipment_returns_none_on_404():
    _fresh()
    mock_resp = MagicMock(status_code=404)
    with patch("requests.get", return_value=mock_resp):
        result = get_shipment("air", 999999)
    assert result is None


def test_get_shipment_caches_within_ttl():
    _fresh()
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {"shipment": {"id": 1, "status": "EN_ROUTE"}}
    with patch("requests.get", return_value=mock_resp) as mock_get:
        get_shipment("air", 123456)
        get_shipment("air", 123456)
        get_shipment("air", 123456)
    assert mock_get.call_count == 1


def test_extract_current_position_finds_the_current_feature():
    position = extract_current_position(AIR_GEOJSON_EXAMPLE)
    assert position["latitude"] == 37.692851
    assert position["longitude"] == 138.988092
    assert position["flight_or_voyage"] == "KJ65"


def test_extract_current_position_returns_none_without_current_feature():
    geojson_no_current = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]},
         "properties": {"status": "PAST"}},
    ]}
    assert extract_current_position(geojson_no_current) is None


def test_extract_current_position_handles_missing_geojson():
    assert extract_current_position(None) is None
