import pytest

from app.config import SNAPSHOTS_DIR
from app.data.repository import load_repository


@pytest.fixture
def repo():
    return load_repository(SNAPSHOTS_DIR)


@pytest.fixture
def calpers(repo):
    return repo.get("CALPERS")
