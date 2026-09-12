import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.api.routes.bl_tracking_routes import router as bl_tracking_router
from app.core.database import Base
from app.infrastructure.db import models  # noqa: F401

TEST_ORG_ID = 1
TEST_USER_ID = 1


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(bl_tracking_router)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def override_get_current_org_id():
        return TEST_ORG_ID

    def override_get_current_user_id():
        return TEST_USER_ID

    from app.core.database import get_db
    from app.core.security import get_current_org_id, get_current_user_id

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_org_id] = override_get_current_org_id
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id

    with TestClient(app) as test_client:
        yield test_client

    engine.dispose()
