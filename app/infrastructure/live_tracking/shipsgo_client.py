"""
shipsgo_client.py — talks to the real ShipsGo v2 REST API
(https://api.shipsgo.com/v2), built directly from the OpenAPI spec ShipsGo
publishes. Ocean and air shipments use an IDENTICAL endpoint shape:

    POST   /{mode}/shipments                       register (COSTS 1 CREDIT)
    GET    /{mode}/shipments/{shipment_id}          status/details
    GET    /{mode}/shipments/{shipment_id}/geojson  route + live position
    DELETE /{mode}/shipments/{shipment_id}          stop tracking

where {mode} is "ocean" or "air". This tracks the SHIPMENT itself (by BL
number for ocean, by AWB number for air) — not an aircraft's raw flight
position — which is the point: the geojson endpoint's "CURRENT" feature
happens to include live coordinates as part of the shipment's route, but
what you're querying is "where is BL/AWB X", not "where is plane Y".

AUTH: every request needs header `X-Shipsgo-User-Token: <your token>`.
Read from the SHIPSGO_API_TOKEN environment variable — never hardcoded.
The value baked in as a default below (a base64-encoded joke — decode it
yourself) is the placeholder ShipsGo's own docs page shows in its
interactive credentials field. It is NOT a real, working token. Replace it
with the real token from your ShipsGo dashboard's "ShipsGo API" section.

CREDIT SAFETY: registering (POST) is the ONLY call that costs a credit.
ShipsGo's own docs state that if you try to create a shipment with a
reference+identifier that already exists, they return 409 with the
EXISTING shipment's data AND "there is no cost" — so register_shipment()
treats 409 as a success (idempotent), not an error, and never double-charges
a credit for the same shipment.
"""

import os
import time
from typing import Optional

import requests

BASE_URL = "https://api.shipsgo.com/v2"

# NOT a real credential — see module docstring. Replace via env var.
_PLACEHOLDER_TOKEN = "QUxMIFlPVVIgQkFTRSBBUkUgQkVMT05HIFRPIFVT"
API_TOKEN = os.environ.get("SHIPSGO_API_TOKEN", _PLACEHOLDER_TOKEN)

_CACHE_TTL_SECONDS = 15
_cache: dict = {}


class ShipsGoNotConfigured(Exception):
    """Raised when no real API token has been set (still on the placeholder)."""


class ShipsGoUnavailable(Exception):
    """Raised on network failure or a 5xx from ShipsGo."""


class ShipsGoOutOfCredits(Exception):
    """Raised on HTTP 402 — the account doesn't have enough credits."""


class ShipsGoForbidden(Exception):
    """Raised on HTTP 403 — this user/token isn't permitted for this action."""


class ShipsGoRequestError(Exception):
    """Raised on other 4xx errors (422 bad payload, etc.)."""


def _headers() -> dict:
    return {"X-Shipsgo-User-Token": API_TOKEN, "Content-Type": "application/json"}


def _require_configured():
    if API_TOKEN == _PLACEHOLDER_TOKEN:
        raise ShipsGoNotConfigured(
            "SHIPSGO_API_TOKEN is not set (still using ShipsGo's own placeholder "
            "value from their docs, which is not a real credential). Sign up at "
            "shipsgo.com, generate a token from the 'ShipsGo API' section of "
            "your dashboard, and set it as an environment variable."
        )


def _raise_for_status(resp: requests.Response):
    """Translate ShipsGo's documented HTTP codes into specific exceptions."""
    if resp.status_code == 402:
        raise ShipsGoOutOfCredits(
            "ShipsGo returned 402: not enough credits to register this shipment."
        )
    if resp.status_code == 403:
        raise ShipsGoForbidden("ShipsGo returned 403: not permitted for this action.")
    if resp.status_code == 401:
        raise ShipsGoNotConfigured("ShipsGo returned 401: missing or invalid API token.")
    if resp.status_code >= 500:
        raise ShipsGoUnavailable(f"ShipsGo returned {resp.status_code} (server-side issue).")
    if resp.status_code >= 400 and resp.status_code != 409:
        raise ShipsGoRequestError(f"ShipsGo returned {resp.status_code}: {resp.text}")


def create_shipment(mode: str, reference: str, identifier: str) -> dict:
    """
    Registers a shipment for tracking. COSTS 1 CREDIT — call only from an
    explicit, user-initiated action, never automatically.

    mode: "ocean" or "air"
    reference: your own internal reference (this app uses the bl_number)
    identifier: the AWB number (air) or BL number (ocean) — ShipsGo's air
        schema names this field `awb_number` exactly (confirmed in their
        spec). Ocean's equivalent field name is inferred by symmetry with
        air (the spec lists the same endpoint shape but collapsed ocean's
        body detail) — if ShipsGo's dashboard shows a different field name
        for ocean, adjust the payload dict below.

    Returns the shipment dict, e.g. {"id": 123456, "reference": ..., ...}.
    On a 409 (already exists), ShipsGo returns the EXISTING shipment's data
    at no cost — this function treats that as a normal success, not an
    error, so registering the same shipment twice never double-charges.
    """
    _require_configured()
    if mode == "air":
        payload = {"reference": reference, "awb_number": identifier}
    else:
        payload = {"reference": reference, "bl_number": identifier}

    try:
        resp = requests.post(
            f"{BASE_URL}/{mode}/shipments", json=payload, headers=_headers(), timeout=10
        )
    except requests.RequestException as exc:
        raise ShipsGoUnavailable(str(exc)) from exc

    if resp.status_code != 409:
        _raise_for_status(resp)

    body = resp.json()
    return body.get("shipment", body)


def get_shipment(mode: str, shipment_id: int) -> Optional[dict]:
    """Details of an already-registered shipment. Free to call repeatedly."""
    _require_configured()

    def _fetch():
        resp = requests.get(
            f"{BASE_URL}/{mode}/shipments/{shipment_id}", headers=_headers(), timeout=10
        )
        if resp.status_code == 404:
            return None
        _raise_for_status(resp)
        return resp.json().get("shipment")

    return _cached_get(f"detail:{mode}:{shipment_id}", _fetch)


def get_shipment_route(mode: str, shipment_id: int) -> Optional[dict]:
    """
    The GeoJSON route (includes live position in the 'CURRENT' feature, per
    ShipsGo's documented shape). Free to call repeatedly.
    """
    _require_configured()

    def _fetch():
        resp = requests.get(
            f"{BASE_URL}/{mode}/shipments/{shipment_id}/geojson",
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        _raise_for_status(resp)
        return resp.json().get("geojson")

    return _cached_get(f"geojson:{mode}:{shipment_id}", _fetch)


def _cached_get(cache_key: str, fetch_fn):
    now = time.monotonic()
    entry = _cache.get(cache_key)
    if entry is not None and (now - entry["fetched_at"]) < _CACHE_TTL_SECONDS:
        return entry["data"]
    try:
        data = fetch_fn()
    except requests.RequestException as exc:
        if entry is not None:
            return entry["data"]
        raise ShipsGoUnavailable(str(exc)) from exc
    _cache[cache_key] = {"fetched_at": now, "data": data}
    return data


def extract_current_position(geojson: Optional[dict]) -> Optional[dict]:
    """
    Pulls the live lat/lon out of the 'CURRENT' LineString feature, per
    ShipsGo's documented geojson shape (see the AIR - Route example: a
    LineString feature with properties.status == "CURRENT" and a
    properties.current.coordinates [lon, lat] pair).
    """
    if not geojson:
        return None
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        if props.get("status") == "CURRENT":
            current = props.get("current", {})
            coords = current.get("coordinates")
            if coords and len(coords) == 2:
                return {
                    "longitude": coords[0],
                    "latitude": coords[1],
                    "flight_or_voyage": props.get("flight") or props.get("voyage"),
                }
    return None
