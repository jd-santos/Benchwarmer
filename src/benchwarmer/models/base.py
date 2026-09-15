"""Shared SQLAlchemy declarative base for durable Benchwarmer records."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy persistence mappings."""
