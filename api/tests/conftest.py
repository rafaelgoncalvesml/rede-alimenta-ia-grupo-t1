import os

# tem que vir antes de importar a app: os testes nunca falam com o banco em nuvem
os.environ["STORAGE"] = "memory"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import ia  # noqa: E402
from api.main import app  # noqa: E402
from api.storage import get_storage  # noqa: E402


@pytest.fixture(autouse=True)
def sem_modelo(monkeypatch):
    # os testes de CRUD nao dependem do ml/predict.py; quem quer modelo troca ia._predict
    monkeypatch.setattr(ia, "_predict", None)
    monkeypatch.setattr(ia, "_ja_tentou", True)


@pytest.fixture
def client():
    get_storage().reset()
    return TestClient(app)
