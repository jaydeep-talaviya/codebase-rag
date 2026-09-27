import pytest
from sqlmodel import Session

from app.db.db import engine


@pytest.fixture
def db():
    with Session(engine) as session:
        yield session
