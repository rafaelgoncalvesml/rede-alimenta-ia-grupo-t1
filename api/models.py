from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


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


class OngBase(BaseModel):
    nome: str
    cnpj: str
    endereco: str
    cidade: str
    estado: str
    latitude: float | None = None
    longitude: float | None = None
    capacidade_kg: float
    necessidades: list[str] = []  # tipos de alimento que a ONG aceita receber


class OngCreate(OngBase):
    pass


class OngUpdate(BaseModel):
    nome: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    capacidade_kg: float | None = None
    necessidades: list[str] | None = None


class Ong(OngBase):
    id: int
    criado_em: datetime


class Armazenamento(str, Enum):
    ambiente = "ambiente"
    refrigerado = "refrigerado"
    congelado = "congelado"


class StatusLote(str, Enum):
    disponivel = "disponivel"
    reservado = "reservado"
    doado = "doado"
    descartado = "descartado"


class LoteBase(BaseModel):
    doador_id: int
    descricao: str = Field(min_length=1)
    quantidade_kg: float = Field(gt=0)  # mesmo check do schema.sql
    validade: date
    armazenamento: Armazenamento
    tipo: str | None = None  # a IA preenche no POST /lotes (dia 15+), por enquanto manual


class LoteCreate(LoteBase):
    pass


class LoteUpdate(BaseModel):
    descricao: str | None = Field(default=None, min_length=1)
    quantidade_kg: float | None = Field(default=None, gt=0)
    validade: date | None = None
    armazenamento: Armazenamento | None = None
    tipo: str | None = None
    status: StatusLote | None = None


class Lote(LoteBase):
    id: int
    status: StatusLote = StatusLote.disponivel
    prioridade: str | None = None  # so o modelo escreve, nao entra no Create/Update
    criado_em: datetime
