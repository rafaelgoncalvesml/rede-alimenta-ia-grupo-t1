import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routers import doadores, lotes, ongs


@pytest.fixture
def client():
    # storage em memoria e global: limpa os dicts e volta os contadores de id
    for mod, store in ((doadores, "_doadores"), (ongs, "_ongs"), (lotes, "_lotes")):
        getattr(mod, store).clear()
        mod._proximo_id = 1
    return TestClient(app)
