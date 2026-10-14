from datetime import date, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from ml import relogio
from ml.features import CATEGORIAS

# Tetos de negocio (issue 11). PREMISSA do Rafael, o grupo ainda nao confirmou: o maior lote do
# dataset v1 tem 1176 kg e a maior validade, 325 dias. Os tetos deixam folga e barram erro de
# digitacao ou de unidade (1e308 kg, validade em 9999). So valem na entrada (Create/Update);
# uma linha ja gravada nao e rejeitada na leitura.
QUANTIDADE_MAX_KG = 5_000
CAPACIDADE_MAX_KG = 100_000
VALIDADE_MAX_DIAS = 730


class TipoPessoa(str, Enum):
    fisica = "fisica"
    juridica = "juridica"


EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
UF_RE = r"^[A-Za-z]{2}$"


class DoadorBase(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    tipo_pessoa: TipoPessoa
    documento: str  # CPF ou CNPJ, guardado sem mascara (igual ao schema.sql)
    telefone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, pattern=EMAIL_RE, max_length=200)
    cidade: str = Field(min_length=1, max_length=100)
    estado: str = Field(pattern=UF_RE)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("nome", "cidade")
    @classmethod
    def _sem_espacos_nas_pontas(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nao pode ser vazio")
        return v

    @field_validator("estado")
    @classmethod
    def _uf_maiuscula(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _documento_bate_com_o_tipo(self):
        # aceita com mascara (123.456.789-09) e guarda so os digitos
        digitos = "".join(c for c in self.documento if c.isdigit())
        esperado = 11 if self.tipo_pessoa == TipoPessoa.fisica else 14
        if len(digitos) != esperado:
            qual = "CPF" if esperado == 11 else "CNPJ"
            raise ValueError(f"{qual} precisa ter {esperado} digitos")
        self.documento = digitos
        return self


class DoadorCreate(DoadorBase):
    pass


class DoadorUpdate(BaseModel):
    """Atualizacao parcial. Documento e tipo de pessoa nao mudam depois de criado."""

    nome: str | None = Field(default=None, min_length=1, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, pattern=EMAIL_RE, max_length=200)
    cidade: str | None = Field(default=None, min_length=1, max_length=100)
    estado: str | None = Field(default=None, pattern=UF_RE)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _obrigatorios_nao_viram_null(self):
        # telefone, email e coordenadas podem ser limpos com null; o resto nao
        for campo in ("nome", "cidade", "estado"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} nao pode ser null")
        if self.estado is not None:
            self.estado = self.estado.upper()
        return self


class Doador(DoadorBase):
    id: int
    criado_em: datetime


def _limpa_necessidades(itens: list[str]) -> list[str]:
    # minuscula, sem espaco nas pontas, sem vazio e sem repetido (mantem a ordem)
    limpos = [i.strip().lower() for i in itens]
    return list(dict.fromkeys(i for i in limpos if i))


def _necessidades_validas(itens: list[str]) -> list[str]:
    # as mesmas 6 categorias que o modelo grava em Lote.tipo; texto livre nunca casaria (issue 7)
    itens = _limpa_necessidades(itens)
    fora = [i for i in itens if i not in CATEGORIAS]
    if fora:
        raise ValueError(f"necessidades fora das categorias ({', '.join(CATEGORIAS)}): {', '.join(fora)}")
    return itens


def _capacidade_no_teto(v: float | None) -> float | None:
    if v is not None and v > CAPACIDADE_MAX_KG:
        raise ValueError(f"capacidade_kg acima do teto de {CAPACIDADE_MAX_KG} kg")
    return v


class OngBase(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    cnpj: str  # sem mascara, igual ao schema.sql
    endereco: str = Field(min_length=1, max_length=300)
    cidade: str = Field(min_length=1, max_length=100)
    estado: str = Field(pattern=UF_RE)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacidade_kg: float = Field(ge=0, allow_inf_nan=False)
    necessidades: list[str] = []  # tipos de alimento que a ONG aceita receber

    @field_validator("nome", "endereco", "cidade")
    @classmethod
    def _sem_espacos_nas_pontas(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nao pode ser vazio")
        return v

    @field_validator("estado")
    @classmethod
    def _uf_maiuscula(cls, v: str) -> str:
        return v.upper()

    @field_validator("necessidades")
    @classmethod
    def _necessidades(cls, v: list[str]) -> list[str]:
        return _limpa_necessidades(v)

    @field_validator("cnpj")
    @classmethod
    def _cnpj_14_digitos(cls, v: str) -> str:
        digitos = "".join(c for c in v if c.isdigit())
        if len(digitos) != 14:
            raise ValueError("CNPJ precisa ter 14 digitos")
        return digitos


class OngCreate(OngBase):
    _checa_capacidade = field_validator("capacidade_kg")(_capacidade_no_teto)

    @field_validator("necessidades")
    @classmethod
    def _so_categorias(cls, v: list[str]) -> list[str]:
        return _necessidades_validas(v)


class OngUpdate(BaseModel):
    """Atualizacao parcial. O CNPJ nao muda depois de criada."""

    nome: str | None = Field(default=None, min_length=1, max_length=200)
    endereco: str | None = Field(default=None, min_length=1, max_length=300)
    cidade: str | None = Field(default=None, min_length=1, max_length=100)
    estado: str | None = Field(default=None, pattern=UF_RE)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacidade_kg: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    necessidades: list[str] | None = None

    _checa_capacidade = field_validator("capacidade_kg")(_capacidade_no_teto)

    @model_validator(mode="after")
    def _obrigatorios_nao_viram_null(self):
        # so as coordenadas podem ser limpas com null
        for campo in ("nome", "endereco", "cidade", "estado", "capacidade_kg", "necessidades"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} nao pode ser null")
        if self.estado is not None:
            self.estado = self.estado.upper()
        if self.necessidades is not None:
            self.necessidades = _necessidades_validas(self.necessidades)
        return self


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
    descricao: str = Field(min_length=1, max_length=500)
    quantidade_kg: float = Field(gt=0, allow_inf_nan=False)  # mesmo check do schema.sql
    validade: date
    armazenamento: Armazenamento
    tipo: str | None = Field(default=None, max_length=50)  # a IA preenche no POST /lotes (dia 15+), por enquanto manual


def _validade_nao_vencida(v: date | None) -> date | None:
    # so na entrada: um lote ja gravado pode vencer depois e continuar legivel
    if v is None:
        return v
    hoje = relogio.hoje()
    if v < hoje:
        raise ValueError("lote vencido nao pode ser cadastrado")
    if v > hoje + timedelta(days=VALIDADE_MAX_DIAS):
        raise ValueError(f"validade alem do teto de {VALIDADE_MAX_DIAS} dias")
    return v


def _quantidade_no_teto(v: float | None) -> float | None:
    if v is not None and v > QUANTIDADE_MAX_KG:
        raise ValueError(f"quantidade_kg acima do teto de {QUANTIDADE_MAX_KG} kg por lote")
    return v


class LoteCreate(LoteBase):
    _checa_validade = field_validator("validade")(_validade_nao_vencida)
    _checa_quantidade = field_validator("quantidade_kg")(_quantidade_no_teto)


class LoteUpdate(BaseModel):
    descricao: str | None = Field(default=None, min_length=1, max_length=500)
    quantidade_kg: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    validade: date | None = None
    armazenamento: Armazenamento | None = None
    tipo: str | None = Field(default=None, max_length=50)
    status: StatusLote | None = None

    _checa_validade = field_validator("validade")(_validade_nao_vencida)
    _checa_quantidade = field_validator("quantidade_kg")(_quantidade_no_teto)

    @model_validator(mode="after")
    def _obrigatorios_nao_viram_null(self):
        # so o tipo pode ser limpo com null
        for campo in ("descricao", "quantidade_kg", "validade", "armazenamento", "status"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} nao pode ser null")
        return self


class Lote(LoteBase):
    id: int
    status: StatusLote = StatusLote.disponivel
    prioridade: str | None = None  # so o modelo escreve, nao entra no Create/Update
    criado_em: datetime


class StatusDoacao(str, Enum):
    confirmada = "confirmada"
    cancelada = "cancelada"


class DoacaoCreate(BaseModel):
    """O que o cliente manda. Status e timestamps sao do servidor."""

    lote_id: int
    ong_id: int
    # ignorados: o servidor calcula os dois com ml.matching (api/routers/doacoes.py). Ficam no
    # corpo so pra nao quebrar cliente antigo que ainda os manda
    distancia_km: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    score: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class Doacao(BaseModel):
    id: int
    lote_id: int
    ong_id: int
    distancia_km: float | None = None
    score: float | None = None
    status: StatusDoacao
    criado_em: datetime
    confirmado_em: datetime
    tempo_match_s: float  # confirmado_em menos o criado_em do lote


class Papel(str, Enum):
    admin = "admin"
    doador = "doador"
    ong = "ong"


class UsuarioCreate(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=200)
    senha: str = Field(min_length=10, max_length=128)
    papel: Papel
    doador_id: int | None = None
    ong_id: int | None = None

    @field_validator("email")
    @classmethod
    def _email_minusculo(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def _entidade_bate_com_o_papel(self):
        # doador e ONG precisam apontar pra entidade deles; admin nao aponta pra nenhuma
        esperado = {Papel.doador: "doador_id", Papel.ong: "ong_id"}.get(self.papel)
        for campo in ("doador_id", "ong_id"):
            tem = getattr(self, campo) is not None
            if tem != (campo == esperado):
                raise ValueError(f"papel {self.papel.value} " + (
                    f"exige {esperado}" if campo == esperado else f"nao aceita {campo}"))
        return self


class Usuario(BaseModel):
    id: int
    email: str
    papel: Papel
    doador_id: int | None = None
    ong_id: int | None = None
    criado_em: datetime


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    senha: str = Field(max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos
