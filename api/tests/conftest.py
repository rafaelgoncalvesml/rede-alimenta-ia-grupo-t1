import os

# tem que vir antes de importar a app: os testes nunca falam com o banco em nuvem
os.environ["STORAGE"] = "memory"
os.environ["JWT_SECRET"] = "segredo-so-dos-testes-" + "x" * 32
os.environ["ADMIN_EMAIL"] = "admin@teste.local"
os.environ["ADMIN_PASSWORD"] = "senha-do-admin-1"

import pytest  # noqa: E402
from argon2 import PasswordHasher  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import seguranca  # noqa: E402
from api.main import app  # noqa: E402
from api.storage import get_storage  # noqa: E402

# argon2 com custo minimo: o padrao leva ~50 ms por hash e cada teste cria usuarios
seguranca.hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
seguranca._HASH_FALSO = seguranca.hasher.hash("nada")
SENHA = "senha-de-teste-123"


def entra(email: str, senha: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    return c


@pytest.fixture(autouse=True)
def _limpa():
    get_storage().reset()
    seguranca._falhas.clear()
    seguranca.garantir_admin()


@pytest.fixture
def client():
    """Admin logado: e o cliente dos testes de CRUD, que nao tratam de permissao."""
    return entra("admin@teste.local", "senha-do-admin-1")


@pytest.fixture
def anonimo():
    return TestClient(app)


@pytest.fixture
def usuario_de(client):
    """Cria um usuario (doador ou ong) pelo admin e devolve o cliente logado como ele."""
    def _cria(papel, entidade_id, email=None):
        email = email or f"{papel}{entidade_id}@teste.local"
        corpo = {"email": email, "senha": SENHA, "papel": papel,
                 ("doador_id" if papel == "doador" else "ong_id"): entidade_id}
        assert client.post("/usuarios", json=corpo).status_code == 201
        return entra(email, SENHA)
    return _cria
