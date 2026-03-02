"""Pytest fixtures: test client with shared in-memory DB."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Create a shared in-memory engine (StaticPool makes all connections share same :memory: db)
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Patch BEFORE importing anything that uses app.db
import app.db as _db_mod
_db_mod.engine = _test_engine
_db_mod.SessionLocal = sessionmaker(bind=_test_engine)

# Now import everything
import app.models  # noqa: F401 — register all models on Base
from app.db import Base, get_db
from app.main import app
from app.seed import seed_database

# Create tables
Base.metadata.create_all(bind=_test_engine)

# Seed once at module level
_init_session = _db_mod.SessionLocal()
seed_database(_init_session)
_init_session.close()


@pytest.fixture()
def db():
    session = _db_mod.SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_header(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}
