"""
Integration tests: full API → Service → Repository → Database path.

ASSUMPTION: `get_current_org_id` / `get_current_user_id` are overridden in
conftest.py rather than exercising real JWT auth, since the real
core/security.py implementation isn't available yet. Once it is, add a
companion test hitting these routes WITHOUT auth overrides to confirm a 401
is returned, per the blueprint's testing checklist ("Unauthorized request").
"""


def _create_payload(bl_number="MSCU1234567"):
    return {
        "bl_number": bl_number,
        "mode": "sea",
        "direction": "import",
        "carrier_name": "MSC",
        "shipper_name": "Acme Exports",
        "consignee_name": "Acme Imports",
        "origin_location": "CNSHA",
        "destination_location": "PKKHI",
        "vessel_name": "MSC Anna",
        "voyage_number": "V123",
    }


def test_create_bl_returns_201(client):
    resp = client.post("/bl", json=_create_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["bl_number"] == "MSCU1234567"
    assert body["status"] == "booked"


def test_create_bl_invalid_mode_field_combo_returns_422(client):
    payload = _create_payload(bl_number="BAD1")
    payload["flight_number"] = "EK601"  # illegal for mode=sea
    resp = client.post("/bl", json=payload)
    assert resp.status_code == 422


def test_get_bl_returns_200(client):
    created = client.post("/bl", json=_create_payload()).json()
    resp = client.get(f"/bl/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_bl_not_found_returns_404(client):
    resp = client.get("/bl/999999")
    assert resp.status_code == 404


def test_list_bl_returns_200_with_pagination_shape(client):
    client.post("/bl", json=_create_payload())
    resp = client.get("/bl")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body and "page" in body


def test_update_bl_returns_200(client):
    created = client.post("/bl", json=_create_payload()).json()
    resp = client.patch(f"/bl/{created['id']}", json={"carrier_name": "CMA CGM"})
    assert resp.status_code == 200
    assert resp.json()["carrier_name"] == "CMA CGM"


def test_status_transition_requires_atd_returns_422(client):
    created = client.post("/bl", json=_create_payload()).json()
    resp = client.patch(f"/bl/{created['id']}/status", json={"status": "in_transit"})
    assert resp.status_code == 422


def test_status_transition_success_returns_200(client):
    created = client.post("/bl", json=_create_payload()).json()
    resp = client.patch(
        f"/bl/{created['id']}/status",
        json={"status": "in_transit", "atd": "2026-01-01T00:00:00Z"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_transit"


def test_illegal_status_transition_returns_409(client):
    created = client.post("/bl", json=_create_payload()).json()
    resp = client.patch(f"/bl/{created['id']}/status", json={"status": "delivered"})
    assert resp.status_code == 409


def test_delete_while_booked_returns_204(client):
    created = client.post("/bl", json=_create_payload()).json()
    resp = client.delete(f"/bl/{created['id']}")
    assert resp.status_code == 204


def test_delete_after_in_transit_returns_409(client):
    created = client.post("/bl", json=_create_payload()).json()
    client.patch(
        f"/bl/{created['id']}/status",
        json={"status": "in_transit", "atd": "2026-01-01T00:00:00Z"},
    )
    resp = client.delete(f"/bl/{created['id']}")
    assert resp.status_code == 409
