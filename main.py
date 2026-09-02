"""
Standalone runnable entry point for the BL Tracking module demo.

Run with:
    python main.py

Then open:
    http://localhost:8000

This starts a real FastAPI server, backed by a real SQLite file
(bl_tracking_demo.db, created next to this file on first run), and serves
the frontend from the same origin so the browser's fetch() calls just work
with no CORS setup needed. The frontend in static/index.html is NOT a mock
— every button click makes a real HTTP request to the routes in
app/api/routes/bl_tracking_routes.py, which call the real service, which
calls the real repository, which reads/writes the real database.
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.database import Base, engine, SessionLocal
from app.infrastructure.db import models as _models  # noqa: F401  (registers all tables)
from app.infrastructure.db.models import Organization, User
from app.api.routes.bl_tracking_routes import router as bl_tracking_router

app = FastAPI(title="Fregix — BL Tracking (standalone demo)")


@app.on_event("startup")
def on_startup():
    # Create all tables if they don't exist yet (idempotent, like the real
    # migration script — safe to restart the server any number of times).
    Base.metadata.create_all(bind=engine)

    # Seed the one demo organization/user that core/security.py's stand-in
    # auth always returns, so BLTracking's org_id foreign key resolves.
    db = SessionLocal()
    try:
        if db.get(Organization, 1) is None:
            db.add(Organization(id=1, name="Demo Freight Forwarders"))
        if db.get(User, 1) is None:
            db.add(User(id=1, name="Demo User"))
        db.commit()
    finally:
        db.close()


app.include_router(bl_tracking_router)


@app.get("/")
def serve_frontend():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
