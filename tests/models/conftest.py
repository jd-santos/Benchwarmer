from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from benchwarmer.models.source import Source


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    event.listen(
        engine,
        "connect",
        lambda connection, record: connection.execute("PRAGMA foreign_keys=ON"),
    )
    Source.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        with factory() as database_session:
            yield database_session
    finally:
        engine.dispose()
