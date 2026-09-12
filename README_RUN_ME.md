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



## Live shipment tracking add-on (ShipsGo v2 API)

Shipments that are not `booked` or `cancelled` show a **"Live tracking —
ShipsGo"** section in the detail panel — for BOTH sea (tracked by BL
number) and air (tracked by AWB number). This tracks the actual shipment,
not an aircraft's raw flight position.

This was built directly against ShipsGo's real, published v2 OpenAPI spec
(`https://api.shipsgo.com/v2`) — ocean and air use an identical endpoint
shape: `POST /{mode}/shipments` to register, `GET /{mode}/shipments/{id}`
for status, `GET /{mode}/shipments/{id}/geojson` for the live route/position.

### You need a real ShipsGo account and API token — I can't create one for you

Set it before starting the server:

```cmd
set SHIPSGO_API_TOKEN=your_real_token_here
python main.py
```

Get your token from the "ShipsGo API" section of your dashboard after
signing up at shipsgo.com. **Important:** the code currently defaults to
a placeholder value if this env var isn't set — that placeholder is
literally the base64-encoded joke `"ALL YOUR BASE ARE BELONG TO US"`,
which is what ShipsGo's own docs page shows in its example credentials
field. It is not a real, working credential. Without a real token set,
tracking calls return a clean `503` explaining exactly that — the rest of
the module (create/update/status/delete) works completely normally either
way.

### Your 3 trial credits are protected by design

Registering a shipment (`POST /{mode}/shipments`) is the only call that
costs a credit — ShipsGo's docs confirm 1 credit covers all lookups for
that shipment afterward, and that trying to register the same shipment
twice returns their existing data **at no extra cost** (this app treats
that case as a normal success, not an error, so you can safely click
"Register" again without fear of double-charging). Because credits are so
limited, registration is a separate, deliberate button — opening a
shipment's detail panel or refreshing the page never spends one.

### What's genuinely new vs. the last version

- **A new database column**, `shipsgo_shipment_id`, stores the numeric id
  ShipsGo assigns when you register a shipment — their v2 API requires
  that id for every later lookup, not the BL/AWB number itself. This is a
  real schema change; if you're merging this into the real Fregix repo,
  add the equivalent migration.
- **Ocean's exact request field name is a reasonable inference, not 100%
  confirmed.** The pasted spec fully details air's create body
  (`awb_number`), but ocean's section was collapsed to endpoint names only.
  This code sends `bl_number` for ocean creates, matching the pattern's
  symmetry with air — check your dashboard/the full spec once you have
  access, and adjust `create_shipment()` in `shipsgo_client.py` if
  ShipsGo's real field name differs.
- **Specific HTTP codes are mapped to specific errors**: `402` → out of
  credits, `403` → forbidden, `401`/no real token → not configured, `409`
  on create → treated as a free, successful duplicate registration per
  ShipsGo's own documented behavior.

### What I verified vs. what needs your real token to confirm

- 52 automated tests pass, using mocked HTTP responses copied directly
  from ShipsGo's own documented examples (the exact JSON shapes in their
  spec) — this proves the field-parsing, credit-safety, and error-code
  logic is correct.
- I ran the real server end-to-end and confirmed: registration attempts
  cleanly refuse with a clear message while the placeholder token is still
  in place (rather than silently pretending to succeed), and reading
  tracking data for a shipment that hasn't been registered yet correctly
  reports that without ever calling ShipsGo.
- I could not get a real successful ShipsGo response, because no real
  account/token exists in this environment and `api.shipsgo.com` isn't
  reachable from my sandbox's network anyway. Once you set your real
  token, try registering a real shipment and tell me what comes back —
  especially whether ocean's `bl_number` field name was correct.
