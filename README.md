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
