import os

# Must be set before any app imports so module-level code picks them up
os.environ.setdefault("DATABASE_URL",        "sqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET",      "test-secret-key")
os.environ.setdefault("GOOGLE_API_KEY",      "test-key")
os.environ.setdefault("GROQ_API_KEY",        "test-key")
os.environ.setdefault("LLM_PROVIDER",        "groq")
os.environ.setdefault("EMBEDDING_PROVIDER",  "google")

import sys
import base64
import json

import pytest
from itsdangerous import TimestampSigner
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base, get_db
import models
import app.rag.models  # registers RAG tables with Base
from app.main import app
from security import create_access_token
from tests.helpers import make_session_cookie


### ENGINE ###

@pytest.fixture(scope="session")
def engine():
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)


### PER-TEST DB SESSION ###

@pytest.fixture
def db(engine):
    # Each test runs in a transaction that is rolled back on teardown
    connection = engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


### TEST CLIENT ###

@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with patch("socket_manager.sio.emit", new_callable=AsyncMock):
        with TestClient(app, base_url="http://test") as c:
            yield c

    app.dependency_overrides.clear()


### SEED DATA ###

@pytest.fixture
def users(db):
    alice = models.User(school_email="alice@test.edu", display_name="Alice Smith", initials="AS")
    bob   = models.User(school_email="bob@test.edu",   display_name="Bob Jones",   initials="BJ")
    db.add_all([alice, bob])
    db.flush()
    return {"alice": alice, "bob": bob}


@pytest.fixture
def course(db, users):
    c = models.Course(
        school_course_id="CS101",
        name="Intro to CS",
        course_code="CS101",
        teacher_name="Dr. Test",
        term="Spring 2026",
    )
    db.add(c)
    db.flush()

    for user in users.values():
        db.add(models.CourseEnrollment(course_id=c.id, user_id=user.id, role="student"))

    general = models.Channel(course_id=c.id, name="general",      channel_type="general",      position=0)
    annc    = models.Channel(course_id=c.id, name="announcements", channel_type="announcements", position=1)
    db.add_all([general, annc])
    db.flush()

    return {"course": c, "general": general, "announcements": annc}


### AUTH HELPERS ###

@pytest.fixture
def alice_headers(users):
    token = create_access_token(users["alice"].id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bob_headers(users):
    token = create_access_token(users["bob"].id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice_cookies(users):
    return {"session": make_session_cookie({"nexus_user_id": users["alice"].id})}
