from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class TipoPessoa(str, Enum):
    fisica = "fisica"
    juridica = "juridica"


class DoadorBase(BaseModel):
    nome: str
    tipo_pessoa: TipoPessoa
    documento: str
    telefone: str | None = None
    email: str | None = None
    cidade: str
    estado: str
    latitude: float | None = None
    longitude: float | None = None


class DoadorCreate(DoadorBase):
    pass


class DoadorUpdate(BaseModel):
    nome: str | None = None
    telefone: str | None = None
    email: str | None = None
    cidade: str | None = None
    estado: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class Doador(DoadorBase):
    id: int
    criado_em: datetime
