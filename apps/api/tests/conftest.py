import os

os.environ.setdefault("INGESTION_SCHEDULE_ENABLED", "false")
os.environ.setdefault("NEWS_POLL_ENABLED", "false")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from atlas_api.db import Base  # noqa: E402
from atlas_api.deps import db_session  # noqa: E402
from atlas_api.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from testcontainers.postgres import PostgresContainer  # noqa: E402


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    with PostgresContainer(
        "pgvector/pgvector:pg15", username="atlas", password="atlas", dbname="atlas"
    ) as pg:
        url = pg.get_connection_url()
        # testcontainers may return psycopg2 dialect; coerce to psycopg v3.
        url = url.replace("postgresql+psycopg2", "postgresql+psycopg")
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        yield url


@pytest.fixture(scope="session")
def engine(pg_url):
    eng = create_engine(pg_url, future=True)
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture(autouse=True)
def _clean_db(engine):
    """Truncate all tables before each test to prevent cross-test data leaks."""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture()
def session(engine):
    # Wrap each test in an outer transaction; use a nested savepoint so that
    # session.commit() inside the test flushes but doesn't durably commit.
    # Rolling back the outer transaction after the test cleans up all rows.
    conn = engine.connect()
    trans = conn.begin()
    test_session_factory = sessionmaker(
        bind=conn,
        autoflush=False,
        autocommit=False,
        future=True,
        join_transaction_mode="create_savepoint",
    )
    s = test_session_factory()
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        conn.close()


@pytest.fixture()
def client(session) -> Iterator[TestClient]:
    def _override():
        yield session

    app.dependency_overrides[db_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
