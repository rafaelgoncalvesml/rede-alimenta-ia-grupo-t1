import os

# tem que vir antes de importar a app: os testes nunca falam com o banco em nuvem
os.environ["STORAGE"] = "memory"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from api.storage import get_storage  # noqa: E402


@pytest.fixture
def client():
    get_storage().reset()
    return TestClient(app)
