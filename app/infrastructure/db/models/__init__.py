"""
Model registry for the standalone demo.

Includes minimal stand-in Organization / Inquiry / User models (just an
`id` column each) purely so BLTracking's foreign keys have something real
to point at. In the real Fregix repo these already exist with much richer
schemas — delete these stubs and import the real ones when this merges in.
"""

from sqlalchemy import Column, Integer, String

from app.core.database import Base
from app.infrastructure.db.models.bl_tracking import (  # noqa: F401
    BLTracking,
    BLMode,
    BLDirection,
    BLStatus,
)


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)


class Inquiry(Base):
    __tablename__ = "inquiries"
    id = Column(Integer, primary_key=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
