# BL Tracking — standalone runnable demo

This is a real, working version of the BL Tracking module: a FastAPI
backend backed by a real SQLite file, and a frontend that talks to it over
genuine HTTP requests (open your browser's Network tab and watch it happen).

No MongoDB, no external API, no mock data — every click in the browser
sends a real request to the real backend, which runs the real business
rules from bl_tracking_service.py and reads/writes a real database file.

## How to run it (Windows cmd)

```
cd path\to\this\folder
pip install -r requirements.txt
python main.py
```

Then open your browser to:

```
http://localhost:8000
```

You'll see the BL Tracking dashboard. Click "+ New BL / AWB" to create a
real record, click a row to open its detail panel, and use the status
buttons to walk it through booked -> in_transit -> arrived -> delivered.
Refresh the page or restart the server — the data is still there, because
it's a real SQLite file (bl_tracking_demo.db) created next to main.py on
first run.

Press Ctrl+C in the terminal to stop the server.

## What's simplified vs. the real Fregix deliverable

- **Database:** SQLite file instead of Postgres, purely so this runs with
  zero extra setup. The model/repository/service code is IDENTICAL to the
  real deliverable — only `app/core/database.py`'s connection string
  differs.
- **Auth:** `app/core/security.py` always returns a fixed demo
  organization/user (no login screen), since there's no real JWT system to
  plug into standalone. Every BL you create belongs to "Demo Freight
  Forwarders" (org_id=1).
- **Organization/Inquiry/User models:** minimal stand-ins (just an `id`
  column) so BLTracking's foreign keys resolve. The real Fregix repo
  already has richer versions of these.

Everything else — the model, the business rules, the calculations, the
routes — is the exact code from the Iteration 1-10 deliverable, actually
running.

## If port 8000 is already taken

Edit the last line of `main.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8001)   # or any free port
```
and open `http://localhost:8001` instead.

# BL Tracking — Technical Reference

This covers everything running in `bl_tracking_standalone`: where each API came from, the full request flow, every endpoint's contract, and what's simplified for the demo compared to the real deliverable.

---

## 1. Where the APIs Come From

**Nothing was fetched from any external service.**

Every endpoint is code written in this project, located in:

```text
app/api/routes/bl_tracking_routes.py
```

The API is this application's own HTTP interface built with FastAPI. It supports:

- Create
- View
- List/Search
- Update
- Status transition
- Delete

There is no third-party freight tracking API or carrier API involved.

---

## 2. Request Flow

Every request follows this flow:

```text
Browser (fetch)
   ↓
FastAPI Route
   ↓
Domain Service
   ↓
Repository
   ↓
SQLite Database
```

More specifically:

```text
Browser (fetch)
   → FastAPI route      (HTTP parsing, calls the service)
      → Domain service  (validation + business rules)
         → Repository   (database queries and updates)
            → SQLite    (bl_tracking_demo.db)
```

The response or error travels back through the same chain.

- The route does not directly communicate with the database.
- The service does not import FastAPI.
- The repository handles database operations.

---

## 3. Status Lifecycle

Status transitions are enforced in:

```text
bl_tracking_service.py
```

| From | Allowed To | Extra Requirement |
|---|---|---|
| `booked` | `in_transit`, `cancelled` | `in_transit` requires an `atd` |
| `in_transit` | `arrived`, `cancelled` | `arrived` requires an `ata` |
| `arrived` | `delivered` | None |
| `delivered` | None — terminal status | — |
| `cancelled` | None — terminal status | — |

Invalid transitions such as:

```text
booked → delivered
```

are rejected with:

```text
HTTP 409 Conflict
```

---

## 4. Calculations

Calculations are located in:

```text
app/domain/calculations/bl_transit.py
```

These are pure functions and do not access the database.

### `compute_transit_days(atd, ata)`

Calculates the number of whole days between actual departure and arrival.

Returns `None` until both dates exist.

### `compute_transit_label(status, etd, eta, atd, ata)`

Creates a transit status label such as:

```text
In transit — ETA in 4 day(s)
```

or:

```text
In transit — overdue against ETA
```

This value populates `transit_label` in API responses.

### `is_overdue(status, eta)`

Returns:

```python
True
```

when a shipment is still `in_transit` after its ETA.

---

## 5. API Specification

### Base URL

```text
http://localhost:8000
```

All request bodies use JSON.

---

### `POST /bl`

Creates a new BL/AWB record.

#### Request Body

| Field | Type | Required | Notes |
|---|---|---|---|
| `bl_number` | string | Yes | Maximum 64 characters |
| `mode` | `"sea"` or `"air"` | Yes | — |
| `direction` | `"import"` or `"export"` | Yes | — |
| `carrier_name` | string | Yes | — |
| `shipper_name` | string | Yes | — |
| `consignee_name` | string | Yes | — |
| `origin_location` | string | Yes | — |
| `destination_location` | string | Yes | — |
| `vessel_name` | string | No | Sea shipments only |
| `voyage_number` | string | No | Sea shipments only |
| `container_numbers` | string | No | Sea shipments only |
| `flight_number` | string | No | Air shipments only |
| `package_count` | number | No | — |
| `gross_weight_kg` | number | No | — |
| `volume_cbm` | number | No | — |
| `etd` | ISO datetime | No | — |
| `eta` | ISO datetime | No | — |
| `notes` | string | No | — |

#### Responses

- `201` — Record created successfully
- `422` — Validation error, missing required field, invalid mode-specific field, or duplicate `bl_number`

---

### `GET /bl/{id}`

Fetches one BL record.

#### Responses

- `200` — Record found
- `404` — Record not found

---

### `GET /bl`

Lists or searches BL records.

#### Optional Query Parameters

- `mode`
- `direction`
- `status`
- `carrier_name`
- `bl_number`
- `date_from`
- `date_to`
- `page` — Default: `1`
- `page_size` — Default: `50`, Maximum: `200`

#### Example Response

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 6
}
```

---

### `PATCH /bl/{id}`

Updates shipment details.

All fields are optional. Only send the fields you want to change.

#### Responses

- `200` — Record updated
- `404` — Record not found
- `422` — Validation error

---

### `PATCH /bl/{id}/status`

Changes the status of a BL.

#### Example Request

```json
{
  "status": "in_transit",
  "atd": "2026-01-01T00:00:00Z"
}
```

`atd` and `ata` are required only for the appropriate status transition.

#### Responses

- `200` — Status updated
- `404` — Record not found
- `409` — Invalid status transition
- `422` — Required date missing

---

### `DELETE /bl/{id}`

Deletes a BL record.

#### Responses

- `204` — Record deleted
- `404` — Record not found
- `409` — Cannot delete a shipment after it has departed

---

## Response Format

Endpoints that return a BL record use a response similar to:

```json
{
  "id": 1,
  "org_id": 1,
  "inquiry_id": null,
  "bl_number": "MSCU7741205",
  "mode": "sea",
  "direction": "import",
  "status": "booked",
  "carrier_name": "MSC",
  "shipper_name": "...",
  "consignee_name": "...",
  "origin_location": "...",
  "destination_location": "...",
  "vessel_name": "...",
  "voyage_number": "...",
  "container_numbers": null,
  "flight_number": null,
  "package_count": null,
  "gross_weight_kg": null,
  "volume_cbm": null,
  "etd": null,
  "eta": null,
  "atd": null,
  "ata": null,
  "notes": null,
  "created_at": "...",
  "updated_at": "...",
  "transit_days": null,
  "transit_label": "Booked"
}
```

---

## 6. Dependencies

### Backend

| Package | Purpose |
|---|---|
| `fastapi` | Web framework, routing, request validation and API documentation |
| `uvicorn` | Runs the FastAPI server |
| `pydantic<2` | Request and response schema validation |
| `sqlalchemy` | ORM and database queries |
| `python-multipart` | Supports form-encoded data |

### Frontend

The frontend is located in:

```text
static/index.html
```

It uses:

- HTML
- CSS
- JavaScript

There is no build step and no npm setup required.

### Runtime Requirements

- Python `3.9+`
- A writable folder for the SQLite database file

### Not Used

This project does not use:

- MongoDB
- Redis
- Celery
- Message queues
- External freight-tracking APIs
- LLMs

---

## 7. Limitations

### Database

- SQLite is used instead of PostgreSQL.
- SQLite is suitable for this standalone demo but not for high concurrent multi-user production traffic.
- There is no complete migration history.
- `main.py` uses `Base.metadata.create_all()` to create missing tables.

### Authentication

There is no real login system.

```text
app/core/security.py
```

always returns a fixed demo organization and user:

```text
org_id = 1
user_id = 1
```

Anyone who can access the application can read and modify the demo data.

Do not expose this version publicly beyond `localhost` without adding proper authentication.

### Data Model

`Organization`, `Inquiry`, and `User` are minimal stand-in models containing only an `id`.

Also:

- `container_numbers` is stored as a comma-separated string.
- Containers cannot be searched individually through a separate child table.

### Scale and Performance

This standalone version does not include:

- Advanced caching
- Performance tuning
- Rate limiting
- Request throttling

Pagination uses:

```text
page
page_size
```

which is suitable for the demo but may become slower with very large datasets.

### Features Deliberately Not Included

The following are outside the scope of this standalone demo:

- Email notifications for status changes
- Celery or Redis background jobs
- Automatic carrier-status polling
- LLM functionality
- A real mobile application
- A full multi-page frontend

The current frontend is a single-page application located at:

```text
static/index.html
```

---

