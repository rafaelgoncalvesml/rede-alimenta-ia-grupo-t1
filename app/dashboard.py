
import base64
import html
from datetime import date
from pathlib import Path

import streamlit as st
from services import paineis
from services.api_client import TRANSICOES, ClienteAPI, ErroAPI

# ==================================================
# CONFIGURAÇÃO
# ==================================================

st.set_page_config(
    page_title="Rede Alimenta IA",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

PAGINAS = [
    "🏠 Início",
    "📦 Doações",
    "🤝 ONGs",
    "🔗 Matchings",
    "📊 Relatórios",
]

STATUS = {
    "disponivel": "Disponível",
    "reservado": "Reservado",
    "doado": "Doado",
    "descartado": "Descartado",
}

CORES_STATUS = {
    "disponivel": "#21C58E",
    "reservado": "#FF9F43",
    "doado": "#579BFF",
    "descartado": "#F17887",
}

ARMAZENAMENTOS = {
    "Ambiente": "ambiente",
    "Refrigerado": "refrigerado",
    "Congelado": "congelado",
}

if "pagina_atual" not in st.session_state:
    st.session_state.pagina_atual = "🏠 Início"

if "mensagem_sistema" not in st.session_state:
    st.session_state.mensagem_sistema = None

cliente = ClienteAPI()

# ==================================================
# FUNÇÕES AUXILIARES
# ==================================================

def carregar_imagem(nome):
    caminho = ASSETS_DIR / nome
    if not caminho.is_file():
        return ""
    return base64.b64encode(caminho.read_bytes()).decode("ascii")


def imagem_uri(nome):
    conteudo = carregar_imagem(nome)
    if not conteudo:
        return ""
    extensao = Path(nome).suffix.lower()
    tipo = "image/jpeg" if extensao in (".jpg", ".jpeg") else "image/png"
    return f"data:{tipo};base64,{conteudo}"


def seguro(valor):
    # Não usar "valor or ''": isso apagaria o número zero!
    return html.escape("" if valor is None else str(valor))


def renderizar_html(conteudo):
    st.markdown(
        " ".join(linha.strip() for linha in conteudo.splitlines()),
        unsafe_allow_html=True,
    )


def data_br(valor):
    if not valor:
        return "Não informada"
    try:
        return date.fromisoformat(str(valor)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return seguro(valor)


def nome_doador(doador_id, doadores):
    for doador in doadores:
        if doador["id"] == doador_id:
            return doador["nome"]
    return f"Doador #{doador_id}"


def ir_para(pagina):
    st.session_state.destino_pagina = pagina
    st.session_state.rolagem_pendente = True
    st.rerun()


def concluir(mensagem):
    st.session_state.mensagem_sistema = mensagem
    st.rerun()


def carregar_dados():
    """Carrega apenas recursos permitidos, sem mascarar erros da API."""
    perfil = st.session_state.get("api_usuario") or {}
    papel = perfil.get("papel")
    if papel not in ("admin", "doador", "ong"):
        return [], [], [], "Perfil de acesso inválido ou ausente. Faça login novamente."

    try:
        if papel == "admin":
            doadores = cliente.listar_doadores()
        elif papel == "doador":
            identificador = perfil.get("doador_id")
            if identificador is None:
                return [], [], [], "Conta de doador sem cadastro vinculado."
            doadores = [cliente.buscar_doador(identificador)]
        else:
            doadores = []  # ONGs não podem listar doadores.

        # 403 significa que a coleção não é autorizada para este perfil.
        # Não confundir 403 com falha de rede, 401 ou erro do servidor.
        try:
            lotes = cliente.listar_lotes()
        except ErroAPI as erro:
            if papel != "admin" and "403" in str(erro):
                lotes = []
            else:
                raise

        try:
            ongs = cliente.listar_ongs()
        except ErroAPI as erro:
            if papel == "ong" and "403" in str(erro):
                identificador = perfil.get("ong_id")
                if identificador is None:
                    return [], [], [], "Conta de ONG sem cadastro vinculado."
                ongs = [cliente.buscar_ong(identificador)]
            elif papel == "doador" and "403" in str(erro):
                ongs = []
            else:
                raise
        return doadores, lotes, ongs, None
    except ErroAPI as erro:
        return [], [], [], str(erro)


def classificar_alimento(descricao):
    import re
    import unicodedata

    texto = unicodedata.normalize("NFKD", descricao.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)

    categorias = {
        "Grãos / Cereais": [
            "arroz", "aveia", "milho", "trigo", "farinha"
        ],
        "Frutas": [
            "banana", "laranja", "maca", "uva", "mamao",
            "manga", "pera", "melancia", "abacaxi", "morango"
        ],
        "Leguminosas": [
            "feijao", "lentilha", "grao de bico", "ervilha"
        ],
        "Legumes / Verduras": [
            "cenoura", "batata", "alface", "couve",
            "brocolis", "abobrinha", "tomate", "pepino"
        ],
        "Laticínios": [
            "leite", "queijo", "iogurte", "manteiga"
        ],
        "Carnes / Aves / Peixes": [
            "frango", "carne bovina", "carne suina",
            "peixe", "tilapia"
        ],
        "Massas": [
            "macarrao", "espaguete", "lasanha"
        ],
    }

    for categoria, alimentos in categorias.items():
        for alimento in alimentos:
            if re.search(r"\b" + re.escape(alimento) + r"\b", texto):
                return categoria

    return None

def classificar_tipo_api(descricao):
    categoria = classificar_alimento(descricao)

    mapa = {
        "Grãos / Cereais": "nao_pereciveis",
        "Frutas": "hortifruti",
        "Leguminosas": "nao_pereciveis",
        "Legumes / Verduras": "hortifruti",
        "Laticínios": "laticinios",
        "Carnes / Aves / Peixes": "carnes_peixes",
        "Massas": "nao_pereciveis",
    }

    return mapa.get(categoria)


# ==================================================
# FRUTAS DECORATIVAS
# ==================================================

FRUTAS = {
    "maca": '<path d="M31 23C23 17 12 21 12 35c0 13 9 23 17 20 3-1 5-1 8 0 8 3 17-9 17-21 0-13-11-18-19-11"/><path d="M32 23c0-8 2-13 7-17 M34 16c7-8 14-6 17-8-1 9-7 13-17 12"/>',
    "cenoura": '<path d="M21 25c-5 3-6 9-2 15l10 16c1 2 3 2 4 0 l16-30c3-7-5-13-12-8-5-5-12-2-16 7Z"/><path d="M35 19c-5-8-3-13-1-16 M38 18c5-9 10-9 14-9 M40 21c8-4 12-2 16 1"/>',
    "laranja": '<circle cx="32" cy="35" r="22"/><path d="M32 13c-1-5 1-9 5-11 M32 15c5-8 12-7 17-5-4 6-10 8-17 5"/>',
    "pera": '<path d="M25 24c2-5 1-12 7-13 7-1 8 8 8 13 0 4 4 8 8 13 7 10 1 23-16 23S9 47 16 37 c4-5 8-9 9-13Z"/><path d="M32 12c0-6 2-9 6-11"/>',
    "abacaxi": '<path d="M21 25h22l3 9-4 22H22l-4-22 3-9Z"/><path d="M32 25V5 M32 18 19 7 M32 18 45 7 M32 13 26 3 M32 13 38 3 M20 34l24 20 M44 34 20 54 M19 43h26"/>',
    "melancia": '<path d="M9 20h46A23 23 0 0 1 9 20Z"/><path d="M13 20a19 19 0 0 0 38 0 M24 29l2 4 M39 29l-2 4 M32 39v4"/>',
    "tomate": '<path d="M20 22C10 27 9 43 18 51c8 8 21 8 29 0 9-8 8-24-3-29"/><path d="M32 20c-6-9-10-9-13-8l5 9-11 3 13 2 6-7 6 7 13-2-11-3 5-9c-4-1-8-1-13 8Z"/><path d="M32 19v-9"/>',
    "morango": '<path d="M32 22c-12-7-23 1-20 15 3 11 15 22 20 24 5-2 17-13 20-24 3-14-8-22-20-15Z"/><path d="M32 22c-5-7-10-10-15-9 M32 22c5-7 10-10 15-9 M32 22v-13 M24 34h1 M39 34h1 M32 45h1"/>',
    "cereja": '<path d="M30 27C29 16 34 8 42 5 M42 5C39 16 42 23 47 30"/><path d="M42 5c-8-5-15-3-19 3 8 3 14 2 19-3Z"/><circle cx="23" cy="41" r="12"/><circle cx="45" cy="43" r="12"/>',
}

FRUTAS_ESQUERDA = [
    ("maca", 8, 20, .78, -19, .52),
    ("cenoura", 94, 108, .67, 26, .42),
    ("cereja", 18, 207, .75, 17, .48),
    ("abacaxi", 95, 311, .70, -22, .44),
    ("laranja", 10, 416, .82, 14, .50),
    ("pera", 95, 522, .72, -28, .46),
    ("melancia", 16, 628, .78, 27, .45),
    ("tomate", 98, 732, .70, -18, .49),
    ("morango", 20, 841, .76, 17, .46),
    ("cenoura", 96, 946, .68, -13, .43),
]

FRUTAS_DIREITA = [
    ("melancia", 94, 18, .76, -22, .48),
    ("tomate", 12, 120, .70, 23, .44),
    ("morango", 96, 222, .76, -16, .49),
    ("cereja", 12, 327, .72, 32, .44),
    ("maca", 94, 431, .74, 15, .50),
    ("abacaxi", 10, 538, .71, -20, .43),
    ("cenoura", 96, 645, .70, 18, .47),
    ("laranja", 15, 750, .76, -27, .44),
    ("pera", 96, 852, .75, 28, .48),
    ("tomate", 14, 953, .69, -13, .43),
]


def gerar_estampa(frutas):
    desenhos = []
    for nome, x, y, escala, angulo, opacidade in frutas:
        desenhos.append(
            f'<g transform="translate({x} {y}) '
            f'rotate({angulo} 32 32) scale({escala})" '
            f'opacity="{opacidade}">{FRUTAS[nome]}</g>'
        )

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="180" height="1050" viewBox="0 0 180 1050">'
        '<g fill="none" stroke="#21C58E" stroke-width="2.3" '
        'stroke-linecap="round" stroke-linejoin="round">'
        + "".join(desenhos)
        + "</g></svg>"
    )
    return base64.b64encode(svg.encode()).decode()


# ==================================================
# ESTILO GLOBAL
# ==================================================

CSS = """
<style>
.stApp {
    background-color: #091525;
    color: #FFFFFF;
    background-image:
        url("data:image/svg+xml;base64,FRUTAS_ESQ"),
        url("data:image/svg+xml;base64,FRUTAS_DIR");
    background-position: left top 10px, right top 64px;
    background-size: clamp(100px,10vw,170px) auto;
    background-repeat: repeat-y, repeat-y;
}

.block-container {
    max-width: 1500px;
    padding-top: 3rem;
    padding-bottom: 3rem;
}

h1,h2,h3 { letter-spacing: -.5px; }

.st-key-botao_logo button {
    width: 96px !important;
    height: 96px !important;
    min-height: 96px !important;
    padding: 0 !important;
    border: 0 !important;
    background-color: transparent !important;
    background-image: url("LOGO_URI") !important;
    background-position: center !important;
    background-size: 85px 85px !important;
    background-repeat: no-repeat !important;
    box-shadow: none !important;
    transition: transform .25s ease !important;
}

.st-key-botao_logo button:hover {
    transform: scale(1.06);
}

.st-key-botao_logo button p {
    font-size: 0 !important;
}

div[data-testid="stRadio"] [role="radiogroup"] {
    flex-wrap: wrap;
    gap: 15px;
}

div[data-testid="stRadio"] [role="radiogroup"] label {
    border-radius: 12px;
    padding: 11px 15px;
    transition: background .25s ease;
}

div[data-testid="stRadio"] [role="radiogroup"] label:hover {
    background: rgba(33,197,142,.1);
}

div[data-testid="stRadio"]
[role="radiogroup"] label:has(input:checked) {
    background: rgba(33,197,142,.14);
    outline: 1px solid rgba(33,197,142,.5);
}

div[data-testid="stRadio"] [role="radiogroup"] label p {
    font-size: 17px;
    font-weight: 650;
}

.metric-card {
    --cor: #21C58E;
    position: relative;
    background: #14283D;
    border: 1px solid #29425B;
    border-top: 2px solid var(--cor);
    border-radius: 16px;
    padding: 23px;
    min-height: 155px;
    box-sizing: border-box;
    overflow: hidden;
    transition: transform .3s ease, box-shadow .3s ease,
                border-color .3s ease;
}

.metric-card.green { --cor: #21C58E; }
.metric-card.cyan { --cor: #66E9EC; }
.metric-card.orange { --cor: #FF9F43; }
.metric-card.blue { --cor: #579BFF; }
.metric-card.red { --cor: #F17887; }

.metric-card:hover {
    transform: translateY(-6px);
    border-color: var(--cor);
    box-shadow: 0 12px 28px rgba(0,0,0,.22);
}

.metric-card::after {
    content: "";
    position: absolute;
    bottom: 0;
    left: 23px;
    width: 42px;
    height: 3px;
    background: var(--cor);
    transition: width .3s;
}

.metric-card:hover::after { width: 90px; }

.metric-header {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 22px;
}

.metric-icon {
    font-size: 27px;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(33,197,142,.08);
    border-radius: 12px;
}

.metric-label {
    color: #D8E7F2 !important;
    font-size: 16px;
    font-weight: 500;
}

.metric-value {
    color: var(--cor) !important;
    font-size: 38px;
    font-weight: 750;
    line-height: 1.2;
    display: block;
    min-height: 46px;
    opacity: 1 !important;
    visibility: visible !important;
}

.quick-action-card {
    background: #14283D;
    border: 1px solid #29425B;
    border-radius: 16px;
    padding: 24px;
    min-height: 165px;
    transition: transform .3s ease, border-color .3s ease;
}

.quick-action-card:hover {
    transform: translateY(-4px);
    border-color: #21C58E;
}

.quick-icon { font-size: 32px; margin-bottom: 10px; }
.quick-title {
    font-size: 20px;
    font-weight: 750;
    color: #FFFFFF;
    margin-bottom: 8px;
}
.quick-description {
    font-size: 14px;
    line-height: 1.7;
    color: #B9CDDC;
}

.empty-panel {
    background: #14283D;
    border: 1px solid #29425B;
    border-radius: 16px;
    padding: 48px 24px;
    text-align: center;
    color: #B9CDDC;
}

.empty-panel h3 { color: #FFFFFF; }
.empty-panel .empty-icon { font-size: 40px; }

div[data-testid="stDialog"] [role="dialog"] {
    background: #091525 !important;
    color: white !important;
    border: 1px solid #27576A !important;
    border-radius: 20px !important;
}

div.stButton > button[kind="primary"],
div.stFormSubmitButton > button[kind="primary"] {
    background: #21C58E;
    color: #091525;
    border-color: #21C58E;
    font-weight: 750;
}

div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button[kind="primary"]:hover {
    background: #32DBA0;
    color: #091525;
    border-color: #32DBA0;
}

.cinema-banner {
    position: relative;
    isolation: isolate;
    display: flex;
    align-items: center;
    min-height: 420px;
    border: 1px solid #27576A;
    border-radius: 22px;
    overflow: hidden;
    margin-bottom: 28px;
    background: #102A3D;
    animation: entrada .9s ease-out both;
}


.cinema-image {
    position: absolute;
    inset: -9px;
    z-index: 0;
    background-image: url("IMAGEM_BANNER");
    background-position: center;
    background-size: cover;
    background-repeat: no-repeat;
    animation: flutuar 6s ease-in-out infinite;
}

.cinema-overlay {
    position: absolute;
    inset: 0;
    z-index: 1;
    background: linear-gradient(
        90deg,
        rgba(7,20,37,.93) 0%,
        rgba(7,20,37,.68) 33%,
        rgba(7,20,37,.18) 70%,
        transparent 100%
    );
}

.cinema-content {
    position: relative;
    z-index: 3;
    max-width: 630px;
    padding: 44px;
    animation: entrada 1s ease-out both;
}

.cinema-tag {
    color: #66E9EC;
    font-size: 13px;
    letter-spacing: 2px;
    font-weight: 800;
    margin-bottom: 17px;
}

.cinema-title {
    color: white;
    font-size: clamp(30px,3.5vw,48px);
    font-weight: 850;
    line-height: 1.16;
    margin-bottom: 16px;
}

.cinema-title span { color: #66E9EC; }

.cinema-description {
    color: #E0EDF3;
    font-size: 16px;
    line-height: 1.8;
    max-width: 440px;
}

.cinema-shine {
    position: absolute;
    inset: 0;
    z-index: 2;
    pointer-events: none;
    background: linear-gradient(
        110deg, transparent 30%,
        rgba(102,233,236,.045) 50%, transparent 70%
    );
    background-size: 200% 100%;
    animation: brilho 10s linear infinite;
}

.doacao-item {
    background: #14283D;
    border: 1px solid #29425B;
    border-left: 3px solid #21C58E;
    border-radius: 15px;
    padding: 21px 24px;
    margin-bottom: 10px;
    transition: border-color .3s ease;
}

.doacao-item:hover { border-color: #21C58E; }

.doacao-topo {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    flex-wrap: wrap;
}

.doacao-nome {
    color: white;
    font-size: 20px;
    font-weight: 750;
}

.doacao-codigo {
    color: #849CB1;
    font-size: 12px;
    margin-top: 5px;
}

.doacao-status {
    border-radius: 20px;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 750;
}

.doacao-detalhes {
    color: #C6D9E5;
    font-size: 14px;
    line-height: 2;
    margin-top: 13px;
}

.sobre-painel {
    border: 1px solid #27576A;
    border-radius: 18px;
    overflow: hidden;
    background: #0A1B2C;
}

.sobre-hero {
    position: relative;
    min-height: 360px;
    padding: 34px;
    background-color: #0A1B2C;
    background-image:
        linear-gradient(
            90deg,
            #091525 0%,
            rgba(9,21,37,.97) 29%,
            rgba(9,21,37,.82) 49%,
            rgba(9,21,37,.12) 100%
        ),
        url("FACHADA_URI");
    background-size: auto, 50% auto;
    background-position: center, right center;
    background-repeat: no-repeat;
    display: flex;
    align-items: center;
}

.sobre-hero-texto {
    max-width: 550px;
    position: relative;
    z-index: 1;
}

.sobre-tag {
    color: #66E9EC;
    font-size: 12px;
    font-weight: 750;
    letter-spacing: 2px;
}

.sobre-titulo {
    font-size: clamp(46px,7vw,86px);
    font-weight: 850;
    line-height: .98;
    letter-spacing: -2px;
    margin: 18px 0;
}

.sobre-titulo .branco { color: #FFFFFF; display: block; }
.sobre-titulo .ciano { color: #34E5EF; display: block; }

.sobre-chamada {
    font-size: 18px;
    font-weight: 650;
    color: #FFFFFF;
    margin-bottom: 14px;
}

.sobre-descricao {
    font-size: 14px;
    line-height: 1.8;
    color: #D3E6E9;
}

.sobre-conteudo { padding: 18px 24px 24px; }

.sobre-valores {
    display: grid;
    grid-template-columns: repeat(4,minmax(0,1fr));
    gap: 12px;
}

.sobre-valor {
    background: #14283D;
    border: 1px solid #27576A;
    border-radius: 14px;
    padding: 18px 14px;
}

.sobre-valor .icone {
    font-size: 27px;
    display: block;
    margin-bottom: 10px;
}

.sobre-valor strong {
    color: #FFFFFF;
    font-size: 15px;
    display: block;
    margin-bottom: 8px;
}

.sobre-valor p {
    color: #C6D9E5;
    font-size: 12px;
    line-height: 1.65;
    margin: 0;
}

.sobre-impacto {
    margin-top: 14px;
    background: #14283D;
    border: 1px solid #27576A;
    border-radius: 14px;
    padding: 20px;
}

.sobre-impacto h3 {
    color: #FFFFFF;
    font-size: 18px;
    margin: 0 0 16px;
}

.sobre-impacto h3 span { color: #34E5EF; }

.sobre-numeros {
    display: grid;
    grid-template-columns: repeat(3,1fr);
    gap: 10px;
    text-align: center;
}

.sobre-numero {
    border-right: 1px solid #29425B;
}

.sobre-numero:last-child { border-right: 0; }

.sobre-numero b {
    color: #34E5EF;
    font-size: 30px;
    display: block;
}

.sobre-numero small {
    color: #D3E6E9;
    font-size: 12px;
}

.sobre-citacao {
    margin-top: 14px;
    border: 1px solid #27576A;
    border-radius: 12px;
    padding: 18px;
    color: #D8E7F2;
    font-size: 14px;
    font-style: italic;
}

@keyframes entrada {
    from { opacity: 0; transform: translateY(18px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes flutuar {
    0%,100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
}

@keyframes brilho {
    from { background-position: 200% center; }
    to { background-position: -200% center; }
}

@media(max-width:1000px) {
    .stApp { background-image: none; }
}

@media(max-width:768px) {
    .cinema-banner { min-height: 370px; }
    .cinema-content { padding: 25px; }
    .cinema-overlay { background: rgba(7,20,37,.68); }
    .sobre-valores { grid-template-columns: repeat(2,1fr); }
    .sobre-conteudo { padding: 12px; }
    .metric-value { font-size: 33px; }
}

@media(prefers-reduced-motion:reduce) {
    .cinema-banner,.cinema-image,.cinema-content,.cinema-shine {
        animation: none !important;
    }
}
</style>
"""

CSS = (
    CSS.replace("FRUTAS_ESQ", gerar_estampa(FRUTAS_ESQUERDA))
    .replace("FRUTAS_DIR", gerar_estampa(FRUTAS_DIREITA))
    .replace("LOGO_URI", imagem_uri("logo.png"))
    .replace("FACHADA_URI", imagem_uri("fachada_rede_alimenta.png"))
)

st.markdown(CSS, unsafe_allow_html=True)


# ==================================================
# COMPONENTES VISUAIS
# ==================================================

def criar_card(icone, valor, titulo, cor="green"):
    renderizar_html(f"""
    <div class="metric-card {cor}">
        <div class="metric-header">
            <span class="metric-icon">{seguro(icone)}</span>
            <span class="metric-label">{seguro(titulo)}</span>
        </div>
        <div class="metric-value">{seguro(valor)}</div>
    </div>
    """)


def mostrar_banner(imagem, tag, titulo, descricao):
    fundo = imagem_uri(imagem)
    estilo = (
        f"background-image:url('{fundo}');"
        if fundo else
        "background:linear-gradient(115deg,#14283D,#103B47,#075E57);"
    )

    conteudo = f"""
    <style>
    .cinema-image {{ {estilo} }}
    </style>
    <div class="cinema-banner">
        <div class="cinema-image"></div>
        <div class="cinema-overlay"></div>
        <div class="cinema-shine"></div>
        <div class="cinema-content">
            <div class="cinema-tag">{tag}</div>
            <div class="cinema-title">{titulo}</div>
            <div class="cinema-description">{descricao}</div>
        </div>
    </div>
    """
    st.html(
        " ".join(linha.strip() for linha in conteudo.splitlines())
    )


def painel_vazio(icone, titulo, descricao):
    renderizar_html(f"""
    <div class="empty-panel">
        <div class="empty-icon">{seguro(icone)}</div>
        <h3>{seguro(titulo)}</h3>
        <p>{seguro(descricao)}</p>
    </div>
    """)


def acao_card(icone, titulo, descricao):
    renderizar_html(f"""
    <div class="quick-action-card">
        <div class="quick-icon">{seguro(icone)}</div>
        <div class="quick-title">{seguro(titulo)}</div>
        <div class="quick-description">{seguro(descricao)}</div>
    </div>
    """)


# ==================================================
# QUEM SOMOS
# ==================================================

@st.dialog("🌱 Rede Alimenta IA", width="large")
def mostrar_sobre_nos():

    _, lotes, ongs, erro = carregar_dados()

    if erro:
        st.warning("Não foi possível consultar os indicadores.")
        total_lotes = "—"
        total_ongs = "—"
    else:
        total_lotes = str(len(lotes))
        total_ongs = str(len(ongs))

    renderizar_html(f"""
    <div class="sobre-painel">
        <div class="sobre-hero">
            <div class="sobre-hero-texto">
                <div class="sobre-tag">
                    TECNOLOGIA QUE ALIMENTA O FUTURO
                </div>
                <div class="sobre-titulo">
                    <span class="branco">Quem</span>
                    <span class="ciano">somos?</span>
                </div>
                <div class="sobre-chamada">
                    Tecnologia que conecta alimentos
                    a um futuro melhor.
                </div>
                <div class="sobre-descricao">
                    A Rede Alimenta IA é um projeto de
                    tecnologia e impacto social que busca
                    combater o desperdício de alimentos
                    e facilitar a conexão entre doadores
                    e organizações sociais.
                    <p>
                    Com inteligência artificial, queremos
                    tornar o processo de doação mais
                    inteligente, eficiente e acessível.
                    </p>
                </div>
            </div>
        </div>

        <div class="sobre-conteudo">
            <div class="sobre-valores">
                <div class="sobre-valor">
                    <span class="icone">🌱</span>
                    <strong>Nosso propósito</strong>
                    <p>Reduzir o desperdício e combater a fome.</p>
                </div>
                <div class="sobre-valor">
                    <span class="icone">🤝</span>
                    <strong>Nossa missão</strong>
                    <p>Conectar doadores e ONGs com tecnologia.</p>
                </div>
                <div class="sobre-valor">
                    <span class="icone">💡</span>
                    <strong>Nossos valores</strong>
                    <p>Solidariedade, inovação e transparência.</p>
                </div>
                <div class="sobre-valor">
                    <span class="icone">👥</span>
                    <strong>Nossa equipe</strong>
                    <p>Estudantes unidos pelo impacto social.</p>
                </div>
            </div>

            <div class="sobre-impacto">
                <h3>Nossa visão <span>em números</span></h3>
                <div class="sobre-numeros">
                    <div class="sobre-numero">
                        <b>{total_lotes}</b>
                        <small>📦 Lotes cadastrados</small>
                    </div>
                    <div class="sobre-numero">
                        <b>{total_ongs}</b>
                        <small>🤝 ONGs cadastradas</small>
                    </div>
                    <div class="sobre-numero">
                        <b>—</b>
                        <small>🔗 Matchings realizados</small>
                    </div>
                </div>
            </div>

            <div class="sobre-citacao">
                ❝ Acreditamos que a tecnologia pode ser
                uma grande aliada na construção de uma
                sociedade mais justa e solidária. ❞
            </div>
        </div>
    </div>
    """)

    if st.button("Fechar", use_container_width=True):
        st.rerun()



# ==================================================
# NOVA DOAÇÃO - DOADOR + LOTE NA MESMA JANELA
# ==================================================

@st.dialog("📦 Nova doação", width="large")
def nova_doacao():

    # Carrega somente os dados permitidos ao perfil
    if eh_admin:
        try:
            doadores = cliente.listar_doadores()
        except ErroAPI as erro:
            st.error(str(erro))
            return

    elif eh_doador:
        if doador_usuario_id is None:
            st.error("Sua conta não está vinculada a um doador.")
            return

        try:
            doador = cliente.buscar_doador(doador_usuario_id)
            doadores = [doador]
        except ErroAPI as erro:
            st.error(str(erro))
            return

    else:
        st.error("Seu perfil não possui permissão para cadastrar doações.")
        return

    st.caption(
        "Cadastre seu alimento em um único processo. "
        + ("Você pode usar um doador existente ou cadastrar um novo."
           if eh_admin else "Sua doação será vinculada ao seu cadastro.")
    )

    # A seleção fica FORA do formulário para atualizar
    # os campos imediatamente quando o doador mudar.
    st.markdown("#### 1. Quem está doando?")

    opcoes = []

    if eh_admin:
        opcoes.append("Cadastrar novo doador")

    opcoes += [
        f"#{d['id']} • {d['nome']}" for d in doadores
    ]

    if not opcoes:
        st.error("Nenhum doador disponível para esta conta.")
        return

    escolha = st.selectbox(
        "Selecione o doador",
        opcoes,
        key="selecao_doador_nova_doacao",
    )

    novo_doador = escolha == "Cadastrar novo doador"

    # Edição opcional do doador existente, sem abrir outro diálogo.
    if not novo_doador:
        doador_id_selecionado = int(escolha.split(" • ", 1)[0].lstrip("#"))
        doador_selecionado = next(
            (d for d in doadores if d["id"] == doador_id_selecionado), None
        )
        if doador_selecionado is not None:
            with st.expander("✏️ Editar dados deste doador"):
                st.caption(
                    "CPF/CNPJ e tipo de pessoa são identificadores e não podem ser alterados."
                )
                with st.form(f"form_editar_doador_{doador_id_selecionado}"):
                    nome_editado = st.text_input(
                        "Nome *", value=doador_selecionado.get("nome") or ""
                    )
                    col_ed1, col_ed2 = st.columns(2)
                    with col_ed1:
                        cidade_editada = st.text_input(
                            "Cidade *", value=doador_selecionado.get("cidade") or ""
                        )
                        telefone_editado = st.text_input(
                            "Telefone", value=doador_selecionado.get("telefone") or ""
                        )
                    with col_ed2:
                        estado_editado = st.text_input(
                            "UF *", value=doador_selecionado.get("estado") or "",
                            max_chars=2
                        )
                        email_editado = st.text_input(
                            "E-mail", value=doador_selecionado.get("email") or ""
                        )
                    salvar_doador = st.form_submit_button(
                        "Salvar dados do doador", type="primary",
                        use_container_width=True
                    )
                if salvar_doador:
                    if not all((nome_editado.strip(), cidade_editada.strip(), estado_editado.strip())):
                        st.error("Preencha nome, cidade e UF.")
                    elif len(estado_editado.strip()) != 2 or not estado_editado.strip().isalpha():
                        st.error("Informe uma UF válida, como SP.")
                    elif email_editado.strip() and (
                        "@" not in email_editado or "." not in email_editado.split("@")[-1]
                    ):
                        st.error("Informe um e-mail válido.")
                    else:
                        dados_edicao = {
                            "nome": nome_editado.strip(),
                            "cidade": cidade_editada.strip(),
                            "estado": estado_editado.strip().upper(),
                            "telefone": telefone_editado.strip() or None,
                            "email": email_editado.strip() or None,
                        }
                        try:
                            cliente.atualizar_doador(doador_id_selecionado, dados_edicao)
                            concluir("Dados do doador atualizados com sucesso!")
                        except ErroAPI as erro:
                            st.error(str(erro))

    with st.form("form_nova_doacao"):

        if novo_doador:
            nome = st.text_input(
                "Nome do doador ou estabelecimento *"
            )

            col1, col2 = st.columns(2)

            with col1:
                tipo_pessoa = st.selectbox(
                    "Tipo de pessoa",
                    ["Pessoa física", "Pessoa jurídica"],
                )
                cidade = st.text_input("Cidade *")
                telefone = st.text_input("Telefone")

            with col2:
                documento = st.text_input("CPF ou CNPJ *")
                estado = st.text_input(
                    "Estado (UF) *",
                    max_chars=2,
                    placeholder="SP",
                )
                email = st.text_input("E-mail")

        else:
            st.caption(
                "✓ Doador já cadastrado. "
                "Os dados cadastrais serão reutilizados automaticamente."
            )

        st.divider()
        st.markdown("#### 2. O que você deseja doar?")

        descricao = st.text_input(
            "Descrição do alimento *",
            placeholder="Ex.: Arroz branco",
        )

        col1, col2 = st.columns(2)

        with col1:
            quantidade = st.number_input(
                "Quantidade em kg *",
                min_value=0.01,
                value=1.0,
                step=0.5,
            )
            armazenamento = st.selectbox(
                "Armazenamento *",
                list(ARMAZENAMENTOS.keys()),
            )

        with col2:
            validade = st.date_input(
                "Data de validade *",
                value=date.today(),
                min_value=date.today(),
                format="DD/MM/YYYY",
            )
            st.caption(
                "🏷️ A categoria será identificada "
                "automaticamente ao cadastrar."
            )

        st.caption(
            "Os alimentos são registrados em kg porque "
            "essa é a unidade utilizada pelo backend."
        )

        salvar = st.form_submit_button(
            "✓ Cadastrar doação",
            type="primary",
            use_container_width=True,
        )

        if salvar:
            if not descricao.strip():
                st.error("Informe a descrição do alimento.")
                return

            if novo_doador:
                if not all([
                    nome.strip(),
                    documento.strip(),
                    cidade.strip(),
                    estado.strip(),
                ]):
                    st.error(
                        "Preencha os dados obrigatórios do doador."
                    )
                    return

                if len(estado.strip()) != 2 or not estado.isalpha():
                    st.error("Informe uma UF válida, como SP.")
                    return

                digitos = "".join(
                    c for c in documento if c.isdigit()
                )

                pessoa = (
                    "fisica"
                    if tipo_pessoa == "Pessoa física"
                    else "juridica"
                )
                esperado = 11 if pessoa == "fisica" else 14

                if len(digitos) != esperado:
                    st.error(
                        f"O documento precisa ter {esperado} dígitos."
                    )
                    return

                if email.strip() and (
                    "@" not in email or "." not in email.split("@")[-1]
                ):
                    st.error("Informe um e-mail válido.")
                    return

                dados_doador = {
                    "nome": nome.strip(),
                    "tipo_pessoa": pessoa,
                    "documento": digitos,
                    "telefone": telefone.strip() or None,
                    "email": email.strip() or None,
                    "cidade": cidade.strip(),
                    "estado": estado.strip().upper(),
                    "latitude": None,
                    "longitude": None,
                }

            try:
                if novo_doador:
                    doador = cliente.cadastrar_doador(
                        dados_doador
                    )
                    doador_id = doador["id"]
                else:
                    doador_id = int(
                        escolha.split(" • ", 1)[0].lstrip("#")
                    )

                if eh_doador and str(doador_id) != str(doador_usuario_id):
                    st.error("Você só pode cadastrar doações em seu próprio nome.")
                    return

                if not (eh_admin or eh_doador):
                    st.error("Seu perfil não permite cadastrar doações.")
                    return
            


                dados_lote = {
                    "doador_id": doador_id,
                    "descricao": descricao.strip(),
                    "quantidade_kg": float(quantidade),
                    "validade": validade.isoformat(),
                    "armazenamento": ARMAZENAMENTOS[armazenamento],
                    "tipo": classificar_tipo_api(
                        descricao.strip()
                    ),
                }

                cliente.cadastrar_lote(dados_lote)

            except ErroAPI as erro:
                st.error(str(erro))
                if novo_doador and "doador_id" in locals():
                    st.warning(
                        "O doador foi cadastrado, mas o lote não. "
                        "Ao tentar novamente, selecione esse "
                        "doador existente para evitar duplicidade."
                    )
                return

            concluir("Doação cadastrada com sucesso!")


# ==================================================
# VISUALIZAR LOTE
# ==================================================

@st.dialog("📋 Detalhes da doação", width="large")
def visualizar_lote(lote, doadores):

    st.markdown(f"### 📦 {seguro(lote['descricao'])}")
    st.caption(f"Lote #{lote['id']}")
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Quantidade**")
        st.write(f"{float(lote['quantidade_kg']):g} kg")

        st.markdown("**Tipo de alimento**")
        st.write(lote.get("tipo") or "Não classificado")

        st.markdown("**Validade**")
        st.write(data_br(lote["validade"]))

        st.markdown("**Armazenamento**")
        st.write(lote["armazenamento"].capitalize())

    with col2:
        st.markdown("**Status**")
        st.write(STATUS.get(lote["status"], lote["status"]))

        st.markdown("**Doador**")
        st.write(nome_doador(lote["doador_id"], doadores))

        st.markdown("**Prioridade da IA**")
        st.write(lote.get("prioridade") or "Não calculada")

        st.markdown("**Data de cadastro**")
        st.write(data_br(lote.get("criado_em")))

    if st.button("Fechar", use_container_width=True):
        st.rerun()


# ==================================================
# EDITAR LOTE
# ==================================================

@st.dialog("✏️ Editar doação", width="large")
def editar_lote(lote):
    if not (eh_admin or (eh_doador and doador_usuario_id is not None
            and str(lote.get("doador_id")) == str(doador_usuario_id))):
        st.error("Você não tem permissão para gerenciar este lote.")
        return


    if lote["status"] in ("doado", "descartado"):
        st.warning("Este lote está finalizado.")
        return

    armazenamento_atual = next(
        (
            nome for nome, valor in ARMAZENAMENTOS.items()
            if valor == lote["armazenamento"]
        ),
        "Ambiente",
    )

    with st.form(f"form_editar_{lote['id']}"):

        descricao = st.text_input(
            "Descrição *",
            value=lote["descricao"],
        )

        col1, col2 = st.columns(2)

        with col1:
            quantidade = st.number_input(
                "Quantidade (kg) *",
                min_value=0.01,
                value=float(lote["quantidade_kg"]),
                step=0.5,
            )

            armazenamento = st.selectbox(
                "Armazenamento",
                list(ARMAZENAMENTOS.keys()),
                index=list(ARMAZENAMENTOS).index(
                    armazenamento_atual
                ),
            )

        with col2:
            validade = st.date_input(
                "Validade *",
                value=date.fromisoformat(
                    str(lote["validade"])[:10]
                ),
                format="DD/MM/YYYY",
            )

            tipo = st.text_input(
                "Tipo de alimento",
                value=lote.get("tipo") or "",
            )

        if st.form_submit_button(
            "Salvar alterações",
            type="primary",
            use_container_width=True,
        ):
            if not descricao.strip():
                st.error("Informe a descrição.")
                return

            if validade < date.today():
                st.error("A validade não pode estar vencida.")
                return

            dados = {
                "descricao": descricao.strip(),
                "quantidade_kg": float(quantidade),
                "validade": validade.isoformat(),
                "armazenamento": ARMAZENAMENTOS[armazenamento],
                "tipo": tipo.strip() or None,
            }

            try:
                cliente.atualizar_lote(lote["id"], dados)
                concluir("Doação atualizada com sucesso!")
            except ErroAPI as erro:
                st.error(str(erro))


# ==================================================
# EXCLUIR LOTE
# ==================================================

@st.dialog("🗑️ Excluir doação")
def excluir_lote(lote):
    if not (eh_admin or (eh_doador and doador_usuario_id is not None
            and str(lote.get("doador_id")) == str(doador_usuario_id))):
        st.error("Você não tem permissão para gerenciar este lote.")
        return


    st.warning(
        "Tem certeza de que deseja excluir esta doação?"
    )

    st.write(f"**Lote:** #{lote['id']}")
    st.write(f"**Alimento:** {lote['descricao']}")

    if lote["status"] in ("reservado", "doado"):
        st.error(
            "A API não permite excluir lotes "
            "reservados ou doados."
        )
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()

    with col2:
        if st.button(
            "Confirmar exclusão",
            type="primary",
            use_container_width=True,
        ):
            try:
                cliente.excluir_lote(lote["id"])
                concluir("Doação excluída com sucesso!")
            except ErroAPI as erro:
                st.error(str(erro))


# ==================================================
# ALTERAR STATUS
# ==================================================

@st.dialog("🔄 Atualizar status")
def alterar_status(lote):
    if not (eh_admin or (eh_doador and doador_usuario_id is not None
            and str(lote.get("doador_id")) == str(doador_usuario_id))):
        st.error("Você não tem permissão para gerenciar este lote.")
        return


    atual = lote["status"]
    permitidos = TRANSICOES.get(atual, set())

    st.write(f"**Status atual:** {STATUS[atual]}")

    if not permitidos:
        st.info("Este lote não permite novas transições.")
        return

    opcoes = {
        STATUS[s]: s
        for s in (
            "disponivel", "reservado", "doado", "descartado"
        )
        if s in permitidos
    }

    escolhido = st.selectbox(
        "Novo status",
        list(opcoes),
    )

    if escolhido == "Doado":
        st.warning(
            "Finalizar como doado não registra "
            "automaticamente a ONG que recebeu o lote."
        )

    if escolhido == "Descartado":
        st.warning(
            "Descartar é uma operação definitiva."
        )

    if st.button(
        "Confirmar alteração",
        type="primary",
        use_container_width=True,
    ):
        try:
            cliente.atualizar_lote(
                lote["id"],
                {"status": opcoes[escolhido]},
            )
            concluir("Status atualizado com sucesso!")
        except ErroAPI as erro:
            st.error(str(erro))


# ==================================================
# ONGs — FUNÇÕES AUXILIARES E FORMULÁRIOS
# ==================================================

def formatar_cnpj(cnpj):
    numeros = "".join(c for c in str(cnpj or "") if c.isdigit())
    if len(numeros) == 14:
        return (
            f"{numeros[:2]}.{numeros[2:5]}.{numeros[5:8]}/"
            f"{numeros[8:12]}-{numeros[12:]}"
        )
    return str(cnpj or "Não informado")


def texto_necessidades(ong):
    necessidades = ong.get("necessidades_alimentares") or []
    if isinstance(necessidades, list):
        return ", ".join(map(str, necessidades)) or "Não informadas"
    return str(necessidades)


def dados_formulario_ong(nome, cnpj, endereco, cidade, estado,
                        capacidade, necessidades, latitude, longitude,
                        incluir_cnpj=True):
    dados = {
        "nome": nome.strip(),
        "endereco": endereco.strip(),
        "cidade": cidade.strip(),
        "estado": estado.strip().upper(),
        "capacidade_kg": float(capacidade),
        "necessidades_alimentares": [
            item.strip()
            for item in necessidades.split(",")
            if item.strip()
        ],
        "latitude": float(latitude) if latitude.strip() else None,
        "longitude": float(longitude) if longitude.strip() else None,
    }

    if incluir_cnpj:
        dados["cnpj"] = "".join(c for c in cnpj if c.isdigit())

    return dados


def campos_ong(ong=None, prefixo="nova"):
    ong = ong or {}

    nome = st.text_input(
        "Nome da ONG *",
        value=ong.get("nome", ""),
        max_chars=200,
        key=f"{prefixo}_nome",
    )

    cnpj = st.text_input(
        "CNPJ *",
        value=formatar_cnpj(ong.get("cnpj", "")) if ong else "",
        disabled=bool(ong),
        key=f"{prefixo}_cnpj",
    )

    endereco = st.text_input(
        "Endereço *",
        value=ong.get("endereco", ""),
        max_chars=300,
        key=f"{prefixo}_endereco",
    )

    col_cidade, col_estado = st.columns([3, 1])

    with col_cidade:
        cidade = st.text_input(
            "Cidade *",
            value=ong.get("cidade", ""),
            max_chars=100,
            key=f"{prefixo}_cidade",
        )

    with col_estado:
        estado = st.text_input(
            "UF *",
            value=ong.get("estado", ""),
            max_chars=2,
            key=f"{prefixo}_estado",
        )

    capacidade = st.number_input(
        "Capacidade de recebimento (kg) *",
        min_value=0.0,
        value=float(ong.get("capacidade_kg") or 0),
        step=1.0,
        key=f"{prefixo}_capacidade",
    )

    necessidades = ong.get("necessidades_alimentares") or []
    if isinstance(necessidades, list):
        necessidades = ", ".join(map(str, necessidades))

    necessidades_texto = st.text_input(
        "Necessidades alimentares",
        value=str(necessidades),
        placeholder="Ex.: arroz, feijão, hortifruti",
        help="Separe os alimentos por vírgulas.",
        key=f"{prefixo}_necessidades",
    )

    with st.expander("📍 Coordenadas geográficas (opcional)"):
        col_lat, col_lon = st.columns(2)

        with col_lat:
            latitude = st.text_input(
                "Latitude",
                value=str(ong.get("latitude"))
                if ong.get("latitude") is not None else "",
                key=f"{prefixo}_latitude",
            )

        with col_lon:
            longitude = st.text_input(
                "Longitude",
                value=str(ong.get("longitude"))
                if ong.get("longitude") is not None else "",
                key=f"{prefixo}_longitude",
            )

    return (
        nome, cnpj, endereco, cidade, estado,
        capacidade, necessidades_texto, latitude, longitude
    )


def validar_formulario_ong(valores, novo=True):
    nome, cnpj, endereco, cidade, estado, capacidade, necessidades, lat, lon = valores

    if not all(x.strip() for x in (nome, endereco, cidade, estado)):
        raise ErroAPI("Preencha todos os campos obrigatórios.")

    if len(estado.strip()) != 2 or not estado.strip().isalpha():
        raise ErroAPI("Informe uma UF válida com duas letras.")

    if novo:
        numeros = "".join(c for c in cnpj if c.isdigit())
        if len(numeros) != 14:
            raise ErroAPI("Informe um CNPJ com 14 dígitos.")

    try:
        if lat.strip() and not -90 <= float(lat) <= 90:
            raise ErroAPI("Latitude deve estar entre -90 e 90.")
        if lon.strip() and not -180 <= float(lon) <= 180:
            raise ErroAPI("Longitude deve estar entre -180 e 180.")
    except ValueError as exc:
        raise ErroAPI("Latitude e longitude precisam ser números.") from exc


@st.dialog("🤝 Cadastrar nova ONG", width="large")
def nova_ong():
    st.caption("Cadastre uma organização para participar da Rede Alimenta IA.")

    with st.form("form_nova_ong"):
        valores = campos_ong(prefixo="nova")
        enviar = st.form_submit_button(
            "Cadastrar ONG",
            type="primary",
            use_container_width=True,
        )

    if enviar:
        try:
            validar_formulario_ong(valores)

            dados = dados_formulario_ong(*valores)
            cliente.cadastrar_ong(dados)

            concluir("ONG cadastrada com sucesso!")
        except (ErroAPI, ValueError) as erro:
            st.error(str(erro))


@st.dialog("🏢 Detalhes da ONG", width="large")
def visualizar_ong(ong_id):
    try:
        ong = cliente.buscar_ong(ong_id)
    except ErroAPI as erro:
        st.error(str(erro))
        return

    st.subheader(ong.get("nome", "ONG"))

    st.write(f"**Código:** {ong.get('id', '—')}")
    st.write(f"**CNPJ:** {formatar_cnpj(ong.get('cnpj'))}")
    st.write(f"**Endereço:** {ong.get('endereco') or '—'}")
    st.write(f"**Cidade:** {ong.get('cidade') or '—'}")
    st.write(f"**Estado:** {ong.get('estado') or '—'}")
    st.write(f"**Capacidade:** {float(ong.get('capacidade_kg') or 0):,.2f} kg")
    st.write(f"**Necessidades alimentares:** {texto_necessidades(ong)}")

    if ong.get("latitude") is not None:
        st.write(f"**Latitude:** {ong['latitude']}")

    if ong.get("longitude") is not None:
        st.write(f"**Longitude:** {ong['longitude']}")

    if ong.get("criado_em"):
        st.write(f"**Cadastro:** {data_br(ong['criado_em'])}")


@st.dialog("✏️ Editar ONG", width="large")
def editar_ong(ong_id):
    try:
        ong = cliente.buscar_ong(ong_id)
    except ErroAPI as erro:
        st.error(str(erro))
        return

    st.info("O CNPJ é um identificador da organização e não pode ser alterado.")

    with st.form(f"form_editar_ong_{ong_id}"):
        valores = campos_ong(ong, prefixo=f"editar_{ong_id}")
        salvar = st.form_submit_button(
            "Salvar alterações",
            type="primary",
            use_container_width=True,
        )

    if salvar:
        try:
            validar_formulario_ong(valores, novo=False)

            dados = dados_formulario_ong(
                *valores,
                incluir_cnpj=False,
            )

            cliente.atualizar_ong(ong_id, dados)
            concluir("Dados da ONG atualizados com sucesso!")
        except (ErroAPI, ValueError) as erro:
            st.error(str(erro))


@st.dialog("🗑️ Excluir ONG")
def excluir_ong(ong_id):
    try:
        ong = cliente.buscar_ong(ong_id)
    except ErroAPI as erro:
        st.error(str(erro))
        return

    st.warning(
        f"Tem certeza que deseja excluir a organização "
        f"**{ong.get('nome', 'ONG')}**?"
    )

    st.caption("Essa ação não poderá ser desfeita.")

    confirmar = st.checkbox(
        "Confirmo que desejo excluir esta ONG.",
        key=f"confirmar_exclusao_ong_{ong_id}",
    )

    if st.button(
        "Excluir definitivamente",
        type="primary",
        disabled=not confirmar,
        use_container_width=True,
        key=f"excluir_ong_{ong_id}",
    ):
        try:
            cliente.excluir_ong(ong_id)
            concluir("ONG excluída com sucesso!")
        except ErroAPI as erro:
            st.error(str(erro))


# ==================================================
# LOGIN DEMONSTRATIVO
# ==================================================

if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = False

if not st.session_state.usuario_logado:

    st.markdown("""
    <style>
    .login-topo {
        text-align: center;
        padding: 35px 15px 20px;
        animation: login-entrada .8s ease-out both;
    }

    .login-icone {
        font-size: 58px;
        margin-bottom: 12px;
    }

    .login-titulo {
        color: #FFFFFF;
        font-size: clamp(32px, 5vw, 52px);
        font-weight: 850;
        margin-bottom: 8px;
    }

    .login-titulo span {
        color: #21C58E;
    }

    .login-subtitulo {
        color: #B9CDDC;
        font-size: 16px;
        line-height: 1.7;
    }

    .login-rodape {
        text-align: center;
        color: #849CB1;
        font-size: 12px;
        margin-top: 28px;
    }

    @keyframes login-entrada {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .login-topo {
            animation: none;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""

<div class="login-topo">
    <img
        src="{imagem_uri('logo.png')}"
        style="
            width: 125px;
            height: 125px;
            object-fit: contain;
            margin-bottom: 15px;
        "
    >
    <div class="login-titulo">
        Rede Alimenta <span>IA</span>
    </div>
    <div class="login-subtitulo">
        Tecnologia que conecta alimentos a quem mais precisa.
        <br>
        Bem-vindo à nossa plataforma!
    </div>
</div>
""", unsafe_allow_html=True)

    esquerda, centro, direita = st.columns([1, 1.4, 1])

    with centro:
        with st.container(border=True):

            st.markdown("### 🔐 Acesse sua conta")
            st.caption("Entre com seu e-mail e sua senha.")

            with st.form("form_login_rede_alimenta"):

                usuario = st.text_input(
                    "Usuário",
                    placeholder="Digite seu usuário"
                )

                senha = st.text_input(
                    "Senha",
                    type="password",
                    placeholder="Digite sua senha"
                )

                entrar = st.form_submit_button(
                    "Entrar na plataforma →",
                    type="primary",
                    use_container_width=True
                )

                if entrar:
                    if not usuario.strip() or not senha:
                        st.error("Informe seu e-mail e sua senha.")
                    else:
                        try:
                            cliente.fazer_login(usuario.strip(), senha)

                            perfil = st.session_state.get("api_usuario")

                            if not isinstance(perfil, dict):
                                st.session_state["api_access_token"] = None
                                st.session_state["api_usuario"] = None
                                cliente.token = None
                                st.error(
                                    "A API não retornou o perfil do usuário."
                                )
                            else:
                                st.session_state.usuario_logado = True
                                st.session_state.pagina_atual = "🏠 Início"
                                st.rerun()

                        except ErroAPI:
                            st.error("E-mail ou senha inválidos.")

        st.markdown("""
        <div class="login-rodape">
            🌍 Juntos contra o desperdício de alimentos.
            <br>
            Rede Alimenta IA • Ambiente demonstrativo
        </div>
        """, unsafe_allow_html=True)

    st.stop()

# ==========================================
# PERFIL E PERMISSÕES DO USUÁRIO
# ==========================================

perfil_usuario = st.session_state.get("api_usuario") or {}

papel_usuario = perfil_usuario.get("papel", "")
doador_usuario_id = perfil_usuario.get("doador_id")
ong_usuario_id = perfil_usuario.get("ong_id")

eh_admin = papel_usuario == "admin"
eh_doador = papel_usuario == "doador"
eh_ong = papel_usuario == "ong"

st.sidebar.caption(f"Perfil conectado: {papel_usuario or 'não identificado'}")




# ==================================================
# CABEÇALHO
# ==================================================

col_logo, col_titulo, col_sobre = st.columns(
    [1, 7, 2],
    vertical_alignment="center",
)

with col_logo:
    if st.button(
        "Voltar ao início",
        key="botao_logo",
        help="Voltar ao início",
    ):
        ir_para("🏠 Início")

with col_titulo:
    st.title("Rede Alimenta IA")
    st.caption(
        "Plataforma Inteligente de Gestão de Doações"
    )

with col_sobre:
    if st.button(
        "ⓘ Sobre nós",
        use_container_width=True,
    ):
        mostrar_sobre_nos()

    if st.button(
        "🚪 Sair",
        use_container_width=True,
        key="botao_sair"
    ):
        st.session_state.usuario_logado = False
        st.session_state["api_access_token"] = None
        st.session_state["api_usuario"] = None
        cliente.token = None
        st.session_state.pagina_atual = "🏠 Início"
        st.rerun()

st.divider()


# ==================================================
# MENU DE NAVEGAÇÃO
# ==================================================

if "destino_pagina" in st.session_state:
    st.session_state.pagina_atual = st.session_state.pop(
        "destino_pagina"
    )

pagina = st.radio(
    "Navegação principal",
    PAGINAS,
    key="pagina_atual",
    horizontal=True,
    label_visibility="collapsed",
)

st.divider()


# ==================================================
# VOLTAR AO TOPO AO MUDAR DE PÁGINA
# ==================================================

if st.session_state.get("rolagem_pendente", False):
    st.session_state.rolagem_pendente = False

    st.components.v1.html(
        """
        <script>
            const parentWindow = window.parent;

            parentWindow.scrollTo({
                top: 0,
                behavior: "instant"
            });

            const container = parentWindow.document.querySelector(
                '[data-testid="stMain"]'
            );

            if (container) {
                container.scrollTo({
                    top: 0,
                    behavior: "instant"
                });
            }
        </script>
        """,
        height=0,
    )


# ==================================================
# DADOS
# ==================================================

doadores, lotes, ongs, erro_dados = carregar_dados()

if erro_dados:
    st.error(
        "Não foi possível carregar as informações: "
        + erro_dados
    )
    st.stop()

if st.session_state.mensagem_sistema:
    st.success(st.session_state.mensagem_sistema)
    st.session_state.mensagem_sistema = None

if cliente.demonstracao:
    st.caption(
        "🧪 Ambiente demonstrativo • "
        "Os cadastros desta sessão não estão no banco real."
    )


# ==================================================
# HOME
# ==================================================

if pagina == "🏠 Início":

    mostrar_banner(
        "cesta.png",
        "OLÁ, SEJA BEM-VINDO!",
        "Sua doação pode <span>transformar vidas.</span>",
        "Cadastre alimentos, acompanhe suas contribuições "
        "e descubra o impacto da solidariedade. "
        "Juntos, podemos combater o desperdício "
        "e alimentar um futuro melhor.",
    )

    st.markdown("### Visão geral")

    kg_doados = sum(
        float(l["quantidade_kg"])
        for l in lotes
        if l["status"] == "doado"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        criar_card(
            "📦", len(lotes), "Lotes cadastrados", "green"
        )

    with col2:
        criar_card(
            "🤝", len(ongs), "ONGs cadastradas", "cyan"
        )

    try:
        doacoes_confirmadas = sum(
            1 for d in cliente.listar_doacoes() if d.get("status") == "confirmada"
        )
        total_matchings = "—" if cliente.demonstracao else str(doacoes_confirmadas)
    except ErroAPI:
        total_matchings = "—"

    with col3:
        criar_card(
            "🔗", total_matchings, "Matchings realizados", "orange"
        )

    with col4:
        criar_card(
            "🌱", f"{kg_doados:,.1f} kg",
            "Alimentos doados", "blue"
        )

    st.caption(
        "Os kg doados são calculados pelos lotes "
        "marcados como 'doado'. Matchings realizados "
        "são as doações confirmadas na API."
    )

    st.markdown("### Ações rápidas")

    col1, col2 = st.columns(2)

    with col1:
        acao_card(
            "📦",
            "Quero doar alimentos",
            "Acesse a gestão de doações e registre "
            "seus alimentos em um único processo.",
        )

        if st.button(
            "Ir para Doações →",
            type="primary",
            use_container_width=True,
        ):
            ir_para("📦 Doações")

    with col2:
        acao_card(
            "🤝",
            "Conhecer ONGs",
            "Consulte as organizações participantes "
            "e descubra como elas podem receber alimentos.",
        )

        if st.button(
            "Ir para ONGs →",
            use_container_width=True,
        ):
            ir_para("🤝 ONGs")

    st.markdown("### Atividades recentes")

    if not lotes:
        painel_vazio(
            "📋",
            "Nenhuma atividade recente",
            "Os lotes cadastrados aparecerão aqui.",
        )
    else:
        recentes = sorted(
            lotes,
            key=lambda l: l.get("criado_em", ""),
            reverse=True,
        )[:3]

        for lote in recentes:
            renderizar_html(f"""
            <div class="doacao-item">
                <div class="doacao-nome">
                    📦 {seguro(lote['descricao'])}
                </div>
                <div class="doacao-detalhes">
                    Lote #{seguro(lote['id'])}
                    • {seguro(STATUS.get(lote['status'], lote['status']))}
                    • {float(lote['quantidade_kg']):g} kg
                </div>
            </div>
            """)

    st.stop()


# ==================================================
# DOAÇÕES
# ==================================================

if pagina == "📦 Doações":

    mostrar_banner(
        "doacoes.png",
        "REDE ALIMENTA IA • DOAÇÕES",
        "Compartilhe alimentos. <span>Transforme vidas.</span>",
        "Cada alimento doado representa uma oportunidade "
        "de fazer a diferença. Cadastre, acompanhe e "
        "gerencie suas doações em um só lugar.",
    )

    st.markdown("### Visão geral das doações")

    contagens = {
        status: sum(
            1 for lote in lotes
            if lote["status"] == status
        )
        for status in STATUS
    }

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        criar_card(
            "📦", len(lotes), "Total de lotes", "green"
        )

    with col2:
        criar_card(
            "⏳", contagens["disponivel"],
            "Disponíveis", "cyan"
        )

    with col3:
        criar_card(
            "🔗", contagens["reservado"],
            "Reservados", "orange"
        )

    with col4:
        criar_card(
            "✅", contagens["doado"],
            "Doados", "blue"
        )

    st.caption(
        f"Descartados: {contagens['descartado']} "
        "• Indicadores calculados com os registros disponíveis."
    )

    st.write("")

    col_titulo, col_botao = st.columns(
        [4, 1.5],
        vertical_alignment="center",
    )

    with col_titulo:
        st.markdown("### Gerenciar doações")
        st.caption(
            "Cadastre, consulte e acompanhe "
            "os lotes de alimentos."
        )

    with col_botao:
        if (eh_admin or eh_doador) and st.button(
            "＋ Nova doação",
            type="primary",
            use_container_width=True,
        ):
            nova_doacao()

    st.write("")

    col_busca, col_status, col_tipo = st.columns(
        [2.5, 1.4, 1.6]
    )

    with col_busca:
        busca = st.text_input(
            "Buscar doações",
            placeholder="🔎 Alimento, doador ou código...",
        )

    with col_status:
        filtro_status = st.selectbox(
            "Status",
            ["Todos"] + list(STATUS.values()),
        )

    tipos = sorted({
        lote["tipo"]
        for lote in lotes
        if lote.get("tipo")
    })

    with col_tipo:
        filtro_tipo = st.selectbox(
            "Tipo de alimento",
            ["Todos"] + tipos,
        )

    filtrados = []

    for lote in lotes:
        doador = nome_doador(
            lote["doador_id"], doadores
        )

        texto = (
            f"{lote['id']} "
            f"{lote['descricao']} "
            f"{doador} "
            f"{lote.get('tipo') or ''}"
        ).lower()

        if busca.strip().lower() not in texto:
            continue

        if (
            filtro_status != "Todos"
            and STATUS[lote["status"]] != filtro_status
        ):
            continue

        if (
            filtro_tipo != "Todos"
            and lote.get("tipo") != filtro_tipo
        ):
            continue

        filtrados.append(lote)

    filtrados.sort(
        key=lambda l: l.get("criado_em", ""),
        reverse=True,
    )

    st.caption(f"{len(filtrados)} lote(s) encontrado(s)")

    if not filtrados:
        painel_vazio(
            "📦",
            "Nenhuma doação encontrada",
            "Cadastre uma nova doação ou altere os filtros.",
        )

    for lote in filtrados:
        lote_id = lote["id"]
        status_atual = lote["status"]
        cor = CORES_STATUS.get(status_atual, "#21C58E")

        doador = nome_doador(
            lote["doador_id"], doadores
        )

        renderizar_html(f"""
        <div class="doacao-item"
             style="border-left-color:{cor}">

            <div class="doacao-topo">
                <div>
                    <div class="doacao-nome">
                        📦 {seguro(lote['descricao'])}
                    </div>
                    <div class="doacao-codigo">
                        LOTE-{int(lote_id):04d}
                        • Cadastrado em
                        {data_br(lote.get('criado_em'))}
                    </div>
                </div>

                <span class="doacao-status"
                      style="color:{cor};background:{cor}20">
                    {seguro(STATUS.get(status_atual, status_atual))}
                </span>
            </div>

            <div class="doacao-detalhes">
                ⚖️ {float(lote['quantidade_kg']):g} kg
                &nbsp; • &nbsp;
                🥬 {seguro(lote.get('tipo') or 'Não classificado')}
                <div>🏪 {seguro(doador)}</div>
                <div>
                    ❄️ {seguro(lote['armazenamento']).capitalize()}
                </div>
                <div>
                    📅 Validade: {data_br(lote['validade'])}
                </div>
            </div>
        </div>
        """)

        # Permissões do lote
        lote_pertence_ao_usuario = (
            eh_doador
            and doador_usuario_id is not None
            and str(lote.get("doador_id")) == str(doador_usuario_id)
        )

        pode_gerenciar_lote = eh_admin or lote_pertence_ao_usuario

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button(
                "👁️ Visualizar",
                key=f"ver_{lote_id}",
                use_container_width=True,
            ):
                visualizar_lote(lote, doadores)

        with col2:
            if pode_gerenciar_lote:
                if st.button(
                    "✏️ Editar",
                    key=f"editar_{lote_id}",
                    disabled=status_atual in ("doado", "descartado"),
                    use_container_width=True,
                ):
                    editar_lote(lote)

        with col3:
            if pode_gerenciar_lote:
                if st.button(
                    "🗑️ Excluir",
                    key=f"excluir_{lote_id}",
                    disabled=status_atual in ("reservado", "doado"),
                    use_container_width=True,
                ):
                    excluir_lote(lote)

        with col4:
            if pode_gerenciar_lote:
                if st.button(
                    "🔄 Status",
                    key=f"status_{lote_id}",
                    disabled=status_atual in ("doado", "descartado"),
                    use_container_width=True,
                ):
                    alterar_status(lote)

        st.write("")

    st.caption(
        "Os status respeitam as regras do backend. "
        "'Reservado' não significa necessariamente "
        "'Em distribuição'."
    )

    st.stop()


# ==================================================
# PÁGINA ONGs — DADOS DO BACKEND
# ==================================================

if pagina == "🤝 ONGs":

    # O banner já contém o texto na própria imagem.
    # Renderizar diretamente evita títulos duplicados.

    banner_ongs = imagem_uri("ongs.png")

    if banner_ongs:
        st.html(f"""
        <style>
        .ong-banner {{
            border: 1px solid #27576A;
            border-radius: 22px;
            overflow: hidden;
            margin-bottom: 28px;
            background: #102A3D;
            animation: entrada .9s ease-out both;
        }}
        .ong-banner img {{
            display: block;
            width: 100%;
            height: auto;
            transition: transform .6s ease;
        }}
        .ong-banner:hover img {{
            transform: scale(1.012);
        }}
        @media(prefers-reduced-motion:reduce) {{
            .ong-banner,.ong-banner img {{
                animation: none;
                transition: none;
            }}
        }}
        </style>

        <div class="ong-banner">
            <img
                src="{banner_ongs}"
                alt="Rede Alimenta IA - Organizações que transformam vidas"
            >
        </div>
        """)
    else:
        st.warning(
            "Banner das ONGs não encontrado. "
            "Coloque ongs.png em app/assets/."
        )

    st.markdown("### 🤝 Organizações parceiras")

    st.caption(
        "Cadastre, consulte e gerencie as organizações "
        "participantes da Rede Alimenta IA."
    )

    st.write("")

    # Indicadores calculados com dados reais ou da sessão demo.
    total_ongs = len(ongs)

    capacidade_total = sum(
        float(o.get("capacidade_kg") or 0)
        for o in ongs
    )

    cidades = {
        (
            str(o.get("cidade") or "").strip().casefold(),
            str(o.get("estado") or "").strip().upper(),
        )
        for o in ongs
        if str(o.get("cidade") or "").strip()
    }

    com_necessidades = sum(
        1 for o in ongs
        if o.get("necessidades_alimentares")
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        criar_card(
            "🏢", str(total_ongs),
            "ONGs cadastradas", "green"
        )

    with c2:
        criar_card(
            "⚖️", f"{capacidade_total:,.0f} kg",
            "Capacidade cadastrada", "cyan"
        )

    with c3:
        criar_card(
            "📍", str(len(cidades)),
            "Cidades cadastradas", "blue"
        )

    with c4:
        criar_card(
            "🥬", str(com_necessidades),
            "ONGs com necessidades", "orange"
        )

    st.write("")
    st.write("")

    titulo_col, botao_col = st.columns(
        [4, 1],
        vertical_alignment="center",
    )

    with titulo_col:
        st.markdown("### Gerenciar ONGs")
        st.caption(
            "Consulte as organizações e mantenha "
            "suas informações atualizadas."
        )

    with botao_col:
        if eh_admin:        
            if st.button(
                "＋ Nova ONG",
                type="primary",
                use_container_width=True,
                key="botao_nova_ong",
            ):
                nova_ong()

    busca_col, uf_col = st.columns([3, 1])

    with busca_col:
        busca = st.text_input(
            "Pesquisar organizações",
            placeholder="Buscar por nome, CNPJ, cidade ou endereço...",
            key="busca_ongs",
        )

    estados = sorted({
        str(o.get("estado") or "").strip().upper()
        for o in ongs
        if o.get("estado")
    })

    with uf_col:
        filtro_uf = st.selectbox(
            "Filtrar por estado",
            ["Todos"] + estados,
            key="filtro_estado_ongs",
        )

    termo = busca.strip().casefold()
    termo_cnpj = "".join(c for c in busca if c.isdigit())

    filtradas = []

    for ong in ongs:
        campos = " ".join(
            str(ong.get(k) or "")
            for k in ("nome", "cnpj", "cidade", "endereco")
        ).casefold()

        cnpj_digitos = "".join(
            c for c in str(ong.get("cnpj") or "")
            if c.isdigit()
        )

        busca_ok = (
            not termo
            or termo in campos
            or (termo_cnpj and termo_cnpj in cnpj_digitos)
        )

        uf_ok = (
            filtro_uf == "Todos"
            or str(ong.get("estado") or "").upper() == filtro_uf
        )

        if busca_ok and uf_ok:
            filtradas.append(ong)

    st.caption(
        f"{len(filtradas)} organização(ões) encontrada(s)."
    )

    st.write("")

    if not filtradas:
        if not ongs:
            painel_vazio(
                "🏢",
                "Nenhuma ONG cadastrada",
                "Cadastre a primeira organização para "
                "construir a rede de parceiros.",
            )
        else:
            painel_vazio(
                "🔎",
                "Nenhuma ONG encontrada",
                "Altere a pesquisa ou o filtro de estado.",
            )

    else:
        for ong in filtradas:
            ong_id = ong["id"]

            nome = seguro(ong.get("nome") or "ONG")
            cidade = seguro(ong.get("cidade") or "—")
            estado = seguro(ong.get("estado") or "—")
            endereco = seguro(ong.get("endereco") or "—")

            capacidade = float(
                ong.get("capacidade_kg") or 0
            )

            necessidades = seguro(
                texto_necessidades(ong)
            )

            cnpj = seguro(
                formatar_cnpj(ong.get("cnpj"))
            )

            renderizar_html(f"""
                <div class="doacao-item">
                    <div class="doacao-topo">
                        <div>
                            <div style="
                                color:#21C58E;
                                font-size:12px;
                                font-weight:700;
                                letter-spacing:1.5px;
                                margin-bottom:8px;
                            ">
                                ORGANIZAÇÃO CADASTRADA
                            </div>

                            <div class="doacao-nome">
                                🏢 {nome}
                            </div>

                            <div class="doacao-codigo">
                                CNPJ: {cnpj}
                            </div>
                        </div>

                        <div style="
                            background:#103D46;
                            border:1px solid #216E70;
                            color:#66E9EC;
                            border-radius:12px;
                            padding:12px 18px;
                            font-weight:700;
                        ">
                            {capacidade:,.0f} kg
                        </div>
                    </div>

                    <div style="
                        border-top:1px solid #29425B;
                        margin:18px 0;
                    "></div>

                    <div style="
                        display:grid;
                        grid-template-columns:repeat(
                            auto-fit,minmax(190px,1fr)
                        );
                        gap:16px;
                        color:#D3E6E9;
                        font-size:14px;
                        line-height:1.7;
                    ">
                        <div>
                            <strong style="color:#66E9EC;">
                                📍 Localização
                            </strong>
                            <div>{cidade} - {estado}</div>
                            <div>{endereco}</div>
                        </div>

                        <div>
                            <strong style="color:#66E9EC;">
                                🥬 Necessidades alimentares
                            </strong>
                            <div>{necessidades}</div>
                        </div>
                    </div>
                </div>
            """)

            # Permissões da ONG
            pode_editar_ong = (
                eh_admin
                or (
                    eh_ong
                    and ong_usuario_id is not None
                    and str(ong_usuario_id) == str(ong_id)
                )
            )

            pode_excluir_ong = eh_admin

            # Mantém a visualização para usuários autorizados
            if pode_editar_ong and pode_excluir_ong:
                ver_col, editar_col, excluir_col = st.columns(3)
            elif pode_editar_ong:
                ver_col, editar_col = st.columns(2)
            else:
                ver_col = st.container()

            with ver_col:
                if st.button(
                    "👁️ Visualizar",
                    key=f"visualizar_ong_{ong_id}",
                    use_container_width=True,
                ):
                    visualizar_ong(ong_id)

            if pode_editar_ong:
                with editar_col:
                    if st.button(
                        "✏️ Editar",
                        key=f"editar_ong_{ong_id}",
                        use_container_width=True,
                    ):
                        editar_ong(ong_id)

            if pode_excluir_ong:
                with excluir_col:
                    if st.button(
                        "🗑️ Excluir",
                        key=f"abrir_excluir_ong_{ong_id}",
                        use_container_width=True,
                    ):
                        excluir_ong(ong_id)

            st.write("")

    st.stop()




# ==================================================
# MATCHINGS — ANÁLISE DE COMPATIBILIDADE
# ==================================================

def normalizar_matching(valor):
    import unicodedata

    texto = str(valor or "").strip().casefold()
    return "".join(
        letra
        for letra in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(letra)
    )


def obter_necessidades_matching(ong):
    necessidades = ong.get("necessidades_alimentares")

    if necessidades is None:
        necessidades = ong.get("necessidades")

    if isinstance(necessidades, list):
        return [
            str(item).strip()
            for item in necessidades
            if str(item).strip()
        ]

    if isinstance(necessidades, str):
        return [
            item.strip()
            for item in necessidades.split(",")
            if item.strip()
        ]

    return []


def avaliar_matching(lote, ong):
    """
    Triagem informativa usando os dados cadastrados.
    Não registra, reserva ou confirma matchings.
    """

    quantidade = float(lote.get("quantidade_kg") or 0)
    capacidade = float(ong.get("capacidade_kg") or 0)

    if lote.get("status") != "disponivel":
        return None

    if quantidade <= 0:
        return None

    if capacidade < quantidade:
        return None

    necessidades = obter_necessidades_matching(ong)
    tipo = normalizar_matching(lote.get("tipo"))

    # A mesma regra do servidor (api/routers/doacoes.py): ONG sem necessidades nao recebe, e o
    # lote so vai pra ONG que declarou a categoria dele. Lote sem tipo (o modelo falhou no
    # cadastro) so confere a capacidade. Antes a tela comparava texto e sugeria ONG sem
    # necessidades, que a API recusava com 409 na hora de doar.
    if not necessidades:
        return None

    if tipo:
        if tipo not in {normalizar_matching(n) for n in necessidades}:
            return None
        criterio = "Categoria declarada pela ONG e capacidade compatíveis"
        categoria = "Necessidade correspondente"
    else:
        criterio = "Capacidade compatível; lote ainda sem categoria"
        categoria = "Compatibilidade parcial"

    return {
        "lote": lote,
        "ong": ong,
        "quantidade": quantidade,
        "capacidade": capacidade,
        "criterio": criterio,
        "categoria": categoria,
        "necessidades": necessidades,
    }


def sugestoes_da_api(lote, ongs):
    """Ranking do POST /matching: a mesma regra da doacao, ordenado por distancia."""
    por_id = {ong.get("id"): ong for ong in ongs}
    resultado = []

    for item in cliente.sugerir_ongs(lote["id"])["ranking"]:
        ong = por_id.get(item["ong_id"]) or {"id": item["ong_id"], "nome": item.get("nome")}
        aproximada = " (aproximada)" if item.get("geo_aproximada") else ""
        resultado.append({
            "lote": lote,
            "ong": ong,
            "quantidade": float(lote.get("quantidade_kg") or 0),
            "capacidade": float(ong.get("capacidade_kg") or 0),
            "criterio": f"{item['posicao']}ª mais próxima: {item['distancia_km']:g} km{aproximada}",
            "categoria": "Necessidade correspondente",
            "necessidades": obter_necessidades_matching(ong),
            "distancia_km": item["distancia_km"],
            "score": item["score"],
        })

    return resultado


def montar_sugestoes_matching(lotes, ongs):
    resultado = []

    for lote in lotes:
        for ong in ongs:
            sugestao = avaliar_matching(lote, ong)

            if sugestao is not None:
                resultado.append(sugestao)

    resultado.sort(
        key=lambda item: (
            item["categoria"] != "Necessidade correspondente",
            str(item["ong"].get("nome") or "").casefold(),
        )
    )

    return resultado


# ==================================================
# PÁGINA MATCHINGS
# ==================================================

if pagina == "🔗 Matchings":

    # ----------------------------------------------
    # BANNER — MANTIDO
    # ----------------------------------------------

    banner_matching = imagem_uri("matchings.png")

    if banner_matching:
        st.html(f"""
        <style>
        .matching-banner {{
            border: 1px solid #27576A;
            border-radius: 22px;
            overflow: hidden;
            margin-bottom: 28px;
            background: #102A3D;
            animation: entrada .9s ease-out both;
        }}

        .matching-banner img {{
            display: block;
            width: 100%;
            height: auto;
            transition: transform .6s ease;
        }}

        .matching-banner:hover img {{
            transform: scale(1.012);
        }}

        @media(prefers-reduced-motion:reduce) {{
            .matching-banner,
            .matching-banner img {{
                animation: none;
                transition: none;
            }}
        }}
        </style>

        <div class="matching-banner">
            <img
                src="{banner_matching}"
                alt="Rede Alimenta IA - Matchings"
            >
        </div>
        """)
    else:
        st.warning(
            "Imagem matchings.png não encontrada em app/assets."
        )

    st.markdown("### 🔗 Análise inteligente de conexões")

    st.caption(
        "Descubra quais organizações podem receber "
        "um alimento disponível, considerando suas "
        "necessidades e capacidades cadastradas."
    )

    st.info(
        "Com a API conectada, o ranking do lote escolhido vem do servidor "
        "(mesma regra da doação, ordenado por distância) e a doação pode ser "
        "confirmada aqui. Os números gerais abaixo são uma triagem local."
    )

    # ----------------------------------------------
    # PREPARAÇÃO DOS DADOS
    # ----------------------------------------------

    lotes_disponiveis = [
        lote
        for lote in lotes
        if lote.get("status") == "disponivel"
        and float(lote.get("quantidade_kg") or 0) > 0
    ]

    sugestoes_gerais = montar_sugestoes_matching(
        lotes_disponiveis,
        ongs,
    )

    ids_com_sugestao = {
        str(item["lote"].get("id"))
        for item in sugestoes_gerais
    }

    lotes_sem_sugestao = [
        lote
        for lote in lotes_disponiveis
        if str(lote.get("id")) not in ids_com_sugestao
    ]

    total_com_sugestao = len(ids_com_sugestao)

    total_necessidades = sum(
        1
        for item in sugestoes_gerais
        if item["categoria"] == "Necessidade correspondente"
    )

    # ----------------------------------------------
    # INDICADORES PRÓPRIOS DE MATCHINGS
    # ----------------------------------------------

    st.markdown("### Visão geral da compatibilidade")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        criar_card(
            "🔗",
            str(len(sugestoes_gerais)),
            "Combinações potenciais",
            "green",
        )

    with col2:
        criar_card(
            "🎯",
            str(total_com_sugestao),
            "Lotes com sugestões",
            "cyan",
        )

    with col3:
        criar_card(
            "🥬",
            str(total_necessidades),
            "Necessidades correspondentes",
            "blue",
        )

    with col4:
        criar_card(
            "⚠️",
            str(len(lotes_sem_sugestao)),
            "Lotes sem sugestões",
            "orange",
        )

    st.caption(
        "Uma combinação potencial é apenas uma possibilidade "
        "de associação entre lote e ONG. Um mesmo lote pode "
        "aparecer em várias combinações."
    )

    st.write("")

    # ----------------------------------------------
    # SELECIONAR UM LOTE
    # ----------------------------------------------

    st.markdown("### 📦 Qual alimento deseja conectar?")

    st.caption(
        "Selecione um lote e descubra quais organizações "
        "atendem aos critérios básicos de compatibilidade."
    )

    if not lotes_disponiveis:

        painel_vazio(
            "📦",
            "Nenhum lote disponível",
            "Cadastre um lote ou verifique os status "
            "na página de Doações.",
        )

    else:

        opcoes_lotes = {
            str(lote["id"]): lote
            for lote in lotes_disponiveis
        }

        lote_escolhido_id = st.selectbox(
            "Selecione o alimento",
            options=list(opcoes_lotes.keys()),
            format_func=lambda identificador: (
                f"#{identificador} • "
                f"{opcoes_lotes[identificador].get('descricao', 'Alimento')} "
                f"• {float(opcoes_lotes[identificador].get('quantidade_kg') or 0):g} kg"
            ),
            key="matching_lote_selecionado",
        )

        lote_escolhido = opcoes_lotes[lote_escolhido_id]

        quantidade_escolhida = float(
            lote_escolhido.get("quantidade_kg") or 0
        )

        renderizar_html(f"""
        <div class="doacao-item">
            <div class="doacao-nome">
                📦 {seguro(lote_escolhido.get("descricao"))}
            </div>
            <div class="doacao-detalhes">
                ⚖️ {quantidade_escolhida:g} kg
                &nbsp; • &nbsp;
                🥬 {seguro(lote_escolhido.get("tipo") or "Não classificado")}
                <div>
                    📅 Validade:
                    {data_br(lote_escolhido.get("validade"))}
                </div>
                <div>
                    📋 Status: Disponível
                </div>
            </div>
        </div>
        """)

        # ------------------------------------------
        # ANÁLISE DO LOTE SELECIONADO
        # ------------------------------------------

        sugestoes_lote = [
            item
            for item in sugestoes_gerais
            if str(item["lote"].get("id")) == lote_escolhido_id
        ]

        if not cliente.demonstracao and (eh_admin or eh_doador):
            try:
                sugestoes_lote = sugestoes_da_api(lote_escolhido, ongs)
            except ErroAPI as erro:
                st.warning(
                    f"Ranking da API indisponível ({erro}). "
                    "Mostrando a triagem local, sem distância."
                )

        st.markdown("### 🎯 Organizações potencialmente compatíveis")

        st.caption(
            f"{len(sugestoes_lote)} organização(ões) "
            "atendem aos critérios desta triagem."
        )

        filtro_compatibilidade = st.selectbox(
            "Exibir",
            [
                "Todas as compatibilidades",
                "Necessidade correspondente",
                "Compatibilidade parcial",
            ],
            key="matching_filtro_compatibilidade",
        )

        if filtro_compatibilidade != "Todas as compatibilidades":
            sugestoes_lote = [
                item
                for item in sugestoes_lote
                if item["categoria"] == filtro_compatibilidade
            ]

        if not sugestoes_lote:

            painel_vazio(
                "🔎",
                "Nenhuma organização encontrada",
                "Nenhuma ONG atende aos critérios selecionados. "
                "Isso não significa necessariamente que "
                "não possa receber o alimento.",
            )

        else:

            for sugestao in sugestoes_lote:

                ong = sugestao["ong"]

                nome = seguro(ong.get("nome") or "Organização")
                cidade = seguro(ong.get("cidade") or "—")
                estado = seguro(ong.get("estado") or "—")

                capacidade = sugestao["capacidade"]
                criterio = seguro(sugestao["criterio"])
                categoria = seguro(sugestao["categoria"])

                necessidades = sugestao["necessidades"]

                if "distancia_km" in sugestao:
                    rodape = (
                        "Distância calculada no servidor • "
                        f"score {sugestao['score']:.2f} (menor é melhor)"
                    )
                else:
                    rodape = "Triagem local, sem distância • nada é registrado"

                texto_necessidades_ong = seguro(
                    ", ".join(necessidades)
                    if necessidades
                    else "Não informadas"
                )

                renderizar_html(f"""
                <div class="doacao-item"
                     style="border-left-color:#66E9EC;">

                    <div class="doacao-topo">
                        <div>
                            <div class="doacao-nome">
                                🏢 {nome}
                            </div>

                            <div class="doacao-codigo">
                                📍 {cidade} - {estado}
                            </div>
                        </div>

                        <span class="doacao-status"
                              style="
                                color:#66E9EC;
                                background:#103D46;
                                border:1px solid #216E70;
                              ">
                            {categoria}
                        </span>
                    </div>

                    <div class="doacao-detalhes">
                        ⚖️ Capacidade cadastrada:
                        {capacidade:g} kg

                        <div>
                            🥬 Necessidades:
                            {texto_necessidades_ong}
                        </div>

                        <div>
                            💡 Critério:
                            {criterio}
                        </div>
                    </div>

                    <div style="
                        color:#849CB1;
                        font-size:12px;
                        margin-top:12px;
                    ">
                        {seguro(rodape)}
                    </div>
                </div>
                """)

                pode_doar = "distancia_km" in sugestao and (eh_admin or eh_doador)
                if pode_doar and st.button(
                    f"✅ Confirmar doação para {ong.get('nome', 'ONG')}",
                    key=f"doar_{lote_escolhido_id}_{ong.get('id')}",
                ):
                    try:
                        cliente.confirmar_doacao(int(lote_escolhido["id"]), int(ong["id"]))
                    except ErroAPI as erro:
                        st.error(str(erro))
                    else:
                        concluir(
                            "Doação confirmada: o lote ficou reservado para "
                            f"{ong.get('nome', 'a ONG')}."
                        )

                with st.expander(
                    f"📊 Comparar capacidade — {ong.get('nome', 'ONG')}",
                    expanded=False,
                ):

                    percentual = (
                        quantidade_escolhida / capacidade * 100
                        if capacidade > 0
                        else 0
                    )

                    st.write(
                        f"**Quantidade do lote:** "
                        f"{quantidade_escolhida:g} kg"
                    )

                    st.write(
                        f"**Capacidade cadastrada da ONG:** "
                        f"{capacidade:g} kg"
                    )

                    st.progress(
                        min(max(percentual / 100, 0), 1)
                    )

                    st.caption(
                        f"O lote equivale a {percentual:.1f}% "
                        "da capacidade total cadastrada. "
                        "Isso não confirma espaço disponível "
                        "no momento."
                    )

                st.write("")

    # ----------------------------------------------
    # LOTES SEM SUGESTÕES
    # ----------------------------------------------

    st.divider()
    st.markdown("### ⚠️ Alimentos sem conexão potencial")

    st.caption(
        "Lotes disponíveis que não encontraram nenhuma "
        "organização compatível com os critérios atuais."
    )

    if not lotes_sem_sugestao:

        st.success(
            "Todos os lotes disponíveis possuem pelo menos "
            "uma sugestão de conexão pelos critérios atuais."
        )

    else:

        for lote in lotes_sem_sugestao:

            quantidade = float(
                lote.get("quantidade_kg") or 0
            )

            renderizar_html(f"""
            <div class="doacao-item"
                 style="border-left-color:#FF9F43;">

                <div class="doacao-nome">
                    📦 {seguro(lote.get("descricao") or "Alimento")}
                </div>

                <div class="doacao-detalhes">
                    Lote #{seguro(lote.get("id"))}
                    • {quantidade:g} kg
                    <div>
                        📅 Validade:
                        {data_br(lote.get("validade"))}
                    </div>
                </div>

                <div style="
                    color:#FFB86B;
                    font-size:13px;
                    margin-top:12px;
                ">
                    Nenhuma ONG atende aos critérios atuais
                    de capacidade e necessidades declaradas.
                </div>

            </div>
            """)

    # ----------------------------------------------
    # TRANSPARÊNCIA DA ANÁLISE
    # ----------------------------------------------

    st.divider()

    with st.expander("ℹ️ Como a compatibilidade é calculada?"):

        st.markdown("""
        **Critérios (os mesmos da API, `ml/matching.py`)**

        - O lote precisa estar disponível.
        - A ONG precisa ter declarado a categoria do lote
          (as 6 categorias que o modelo de IA atribui).
          ONG sem necessidades declaradas não recebe.
        - A capacidade cadastrada da ONG precisa
          aguentar o peso do lote.
        - Com a API conectada, as ONGs vêm ordenadas
          pela distância em linha reta até o doador, e o
          score é essa distância dividida por 100 km
          (menor é melhor).

        **Limitações importantes**

        - Distância em linha reta, não de rota.
        - ONG ou doador sem coordenada usa o centro da
          cidade: a distância sai marcada como aproximada.
        - A capacidade cadastrada não é capacidade livre.
        - Os números gerais desta tela são uma triagem
          local; só o ranking do lote escolhido vem da API.
        - Uma ONG pode aparecer para vários lotes ao
          mesmo tempo.
        """)

    st.stop()


# ==================================================
# FIM DA PÁGINA MATCHINGS
# ==================================================



# ==================================================
# RELATÓRIOS — DADOS CADASTRADOS
# ==================================================

if pagina == "📊 Relatórios":

    import csv
    import io
    from collections import defaultdict

    # ----------------------------------------------
    # BANNER
    # ----------------------------------------------

    banner_relatorios = imagem_uri("relatorios.png")

 
    if banner_relatorios:
        st.html(f"""
        <style>
        @keyframes relatoriosEntrada {{
            from {{
                opacity: 0;
                transform: translateY(18px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .relatorios-banner {{
            border: 1px solid #27576A;
            border-radius: 22px;
            overflow: hidden;
            margin-bottom: 28px;
            background: #102A3D;
            animation: relatoriosEntrada 0.9s ease-out both;
        }}

        .relatorios-banner img {{
            display: block;
            width: 100%;
            height: auto;
            transition: transform 0.6s ease;
        }}

        .relatorios-banner:hover img {{
            transform: scale(1.012);
        }}

        @media (prefers-reduced-motion: reduce) {{
            .relatorios-banner {{
                animation: none;
            }}

            .relatorios-banner img {{
                transition: none;
            }}
        }}
        </style>

        <div class="relatorios-banner">
            <img
                src="{banner_relatorios}"
                alt="Rede Alimenta IA - Relatórios"
            >
        </div>
        """)
    else:
        st.warning(
            "Salve relatorios.png na pasta app/assets."
        )

        st.warning(
            "Salve relatorios.png na pasta app/assets."
        )

    st.markdown("### 📊 Central de relatórios")

    st.caption(
        "Analise os registros de alimentos, doadores "
        "e organizações da Rede Alimenta IA."
    )

    if cliente.demonstracao:
        st.info(
            "Os indicadores abaixo utilizam os dados "
            "do ambiente demonstrativo desta sessão."
        )

    # ----------------------------------------------
    # FILTROS
    # ----------------------------------------------

    # ----------------------------------------------
    # INDICADORES DA API (os mesmos do GET /kpis)
    # ----------------------------------------------

    if not cliente.demonstracao:
        try:
            impacto = cliente.kpis_impacto()
            kpis_ia = cliente.kpis_ia() or {}
        except ErroAPI as erro:
            st.warning(f"Indicadores da API indisponíveis: {erro}")
        else:
            st.markdown("### 📈 Impacto e IA (calculados na API)")

            col1, col2, col3, col4 = st.columns(4)
            tempo = impacto.get("tempo_medio_match_s")

            with col1:
                criar_card("⚖️", f"{impacto['kg_doados']:g} kg", "Alimento entregue", "green")
            with col2:
                criar_card("🍽️", f"{impacto['refeicoes_geradas']:g}", "Refeições estimadas", "cyan")
            with col3:
                if tempo is None:
                    tempo_txt = "—"
                elif tempo < 3600:
                    tempo_txt = f"{tempo / 60:.0f} min"
                else:
                    tempo_txt = f"{tempo / 3600:.1f} h"
                criar_card("⏱️", tempo_txt, "Tempo médio até o match", "green")
            with col4:
                criar_card("🏢", str(impacto["ongs_atendidas"]), "ONGs atendidas", "cyan")

            st.caption(
                f"Refeições = kg entregues ÷ {impacto['fator_kg_por_refeicao']:g} kg. "
                "Esse fator é premissa do grupo; a única referência achada é dos EUA "
                "(Feeding America, cerca de 0,544 kg por refeição)."
            )

            modelo = kpis_ia.get("modelo")
            if modelo:
                st.caption(
                    f"Modelo de prioridade {modelo['versao']}: F1 macro "
                    f"{modelo['f1_macro_teste']:.3f} no teste, contra "
                    f"{modelo['f1_macro_baseline']:.3f} da regra que só olha os dias "
                    "até a validade. O ganho é pequeno e incerto."
                )
            for aviso in kpis_ia.get("avisos", []):
                st.warning(aviso)

            st.caption(
                "ONGs do demo: nome, CNPJ e endereço reais; capacidade e necessidades "
                "simuladas. As entidades não foram consultadas."
            )

    doacoes_mapa = []
    if not cliente.demonstracao:
        try:
            doacoes_mapa = cliente.listar_doacoes()
        except ErroAPI as erro:
            st.warning(f"Doações da API indisponíveis para o mapa: {erro}")

    paineis.mapa_de_calor(cliente, ongs, lotes, doacoes_mapa)
    paineis.seguranca()

    st.markdown("### 🔎 Filtrar registros")

    col_status, col_tipo = st.columns(2)

    tipos_disponiveis = sorted({
        str(lote.get("tipo"))
        for lote in lotes
        if lote.get("tipo")
    })

    with col_status:
        filtro_status_rel = st.selectbox(
            "Status do lote",
            ["Todos"] + list(STATUS.values()),
            key="relatorio_filtro_status",
        )

    with col_tipo:
        filtro_tipo_rel = st.selectbox(
            "Tipo de alimento",
            ["Todos"] + tipos_disponiveis,
            key="relatorio_filtro_tipo",
        )

    lotes_filtrados = []

    for lote in lotes:

        status_lote = STATUS.get(
            lote.get("status"),
            lote.get("status", ""),
        )

        if (
            filtro_status_rel != "Todos"
            and status_lote != filtro_status_rel
        ):
            continue

        if (
            filtro_tipo_rel != "Todos"
            and lote.get("tipo") != filtro_tipo_rel
        ):
            continue

        lotes_filtrados.append(lote)

    # ----------------------------------------------
    # INDICADORES
    # ----------------------------------------------

    total_lotes = len(lotes_filtrados)

    kg_total = sum(
        float(lote.get("quantidade_kg") or 0)
        for lote in lotes_filtrados
    )

    kg_doados = sum(
        float(lote.get("quantidade_kg") or 0)
        for lote in lotes_filtrados
        if lote.get("status") == "doado"
    )

    kg_disponiveis = sum(
        float(lote.get("quantidade_kg") or 0)
        for lote in lotes_filtrados
        if lote.get("status") == "disponivel"
    )

    st.markdown("### Visão geral dos registros")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        criar_card(
            "📦", str(total_lotes),
            "Lotes no filtro", "green"
        )

    with c2:
        criar_card(
            "⚖️", f"{kg_total:,.1f} kg",
            "Quantidade cadastrada", "cyan"
        )

    with c3:
        criar_card(
            "✅", f"{kg_doados:,.1f} kg",
            "Marcados como doados", "blue"
        )

    with c4:
        criar_card(
            "🥬", f"{kg_disponiveis:,.1f} kg",
            "Disponíveis", "orange"
        )

    st.caption(
        "Os indicadores respeitam os filtros selecionados. "
        "A quantidade cadastrada inclui todos os status, "
        "inclusive lotes descartados."
    )

    st.write("")

    
    # ==================================================
    # GRÁFICOS INTERATIVOS DE RELATÓRIOS
    # ==================================================

    from datetime import datetime

    import altair as alt

    st.markdown("### 📈 Análises gráficas")

    st.caption(
        "Escolha uma análise para visualizar os dados "
        "em diferentes formatos."
    )

    tipo_grafico = st.selectbox(
        "Selecione o relatório gráfico",
        [
            "📊 Colunas — Situação das doações",
            "📉 Barras — Tipos de alimentos",
            "🥧 Pizza — Participação dos doadores",
            "📈 Linha — Vencimento dos alimentos",
        ],
        key="relatorio_tipo_grafico",
    )

    # ----------------------------------------------
    # GRÁFICO DE COLUNAS — STATUS
    # ----------------------------------------------

    if tipo_grafico.startswith("📊"):

        st.markdown("#### Situação dos lotes")

        dados = [
            {
                "Status": nome,
                "Quantidade": sum(
                    1 for lote in lotes_filtrados
                    if STATUS.get(lote.get("status")) == nome
                ),
            }
            for nome in STATUS.values()
        ]

        grafico = (
            alt.Chart(alt.Data(values=dados))
            .mark_bar(
                cornerRadiusTopLeft=6,
                cornerRadiusTopRight=6,
                color="#21C58E",
            )
            .encode(
                x=alt.X(
                    "Status:N",
                    title="Situação do lote",
                    sort=None,
                ),
                y=alt.Y(
                    "Quantidade:Q",
                    title="Quantidade de lotes",
                ),
                tooltip=["Status:N", "Quantidade:Q"],
            )
            .properties(height=350)
        )

        st.altair_chart(
            grafico,
            use_container_width=True,
        )

    # ----------------------------------------------
    # GRÁFICO DE BARRAS — TIPOS
    # ----------------------------------------------

    elif tipo_grafico.startswith("📉"):

        st.markdown("#### Quantidade por tipo de alimento")

        agrupamento = defaultdict(float)

        for lote in lotes_filtrados:
            tipo = str(
                lote.get("tipo") or "Não classificado"
            )

            agrupamento[tipo] += float(
                lote.get("quantidade_kg") or 0
            )

        dados = [
            {
                "Tipo": tipo,
                "Quantidade (kg)": round(quantidade, 2),
            }
            for tipo, quantidade in agrupamento.items()
        ]

        if dados:

            grafico = (
                alt.Chart(alt.Data(values=dados))
                .mark_bar(
                    color="#66E9EC",
                    cornerRadiusEnd=6,
                )
                .encode(
                    y=alt.Y(
                        "Tipo:N",
                        sort="-x",
                        title="Tipo de alimento",
                    ),
                    x=alt.X(
                        "Quantidade (kg):Q",
                        title="Quantidade cadastrada (kg)",
                    ),
                    tooltip=[
                        "Tipo:N",
                        "Quantidade (kg):Q",
                    ],
                )
                .properties(height=350)
            )

            st.altair_chart(
                grafico,
                use_container_width=True,
            )

        else:
            st.info("Nenhum alimento encontrado.")

    # ----------------------------------------------
    # GRÁFICO DE PIZZA — DOADORES
    # ----------------------------------------------

    elif tipo_grafico.startswith("🥧"):

        st.markdown("#### Participação dos doadores")

        nomes = {
            str(doador.get("id")): str(
                doador.get("nome") or "Sem nome"
            )
            for doador in doadores
        }

        agrupamento = defaultdict(float)

        for lote in lotes_filtrados:

            nome = nomes.get(
                str(lote.get("doador_id")),
                "Doador não identificado",
            )

            agrupamento[nome] += float(
                lote.get("quantidade_kg") or 0
            )

        dados = [
            {
                "Doador": nome,
                "Quantidade (kg)": round(quantidade, 2),
            }
            for nome, quantidade in agrupamento.items()
            if quantidade > 0
        ]

        if dados:

            grafico = (
                alt.Chart(alt.Data(values=dados))
                .mark_arc(
                    innerRadius=65,
                    outerRadius=135,
                )
                .encode(
                    theta=alt.Theta(
                        "Quantidade (kg):Q",
                        stack=True,
                    ),
                    color=alt.Color(
                        "Doador:N",
                        scale=alt.Scale(
                            range=[
                                "#21C58E",
                                "#66E9EC",
                                "#579BFF",
                                "#FF9F43",
                                "#A78BFA",
                                "#FF6B6B",
                            ]
                        ),
                    ),
                    tooltip=[
                        "Doador:N",
                        "Quantidade (kg):Q",
                    ],
                )
                .properties(height=350)
            )

            st.altair_chart(
                grafico,
                use_container_width=True,
            )

            st.caption(
                "Participação calculada pelo peso "
                "dos lotes cadastrados, não pelo "
                "volume de entregas confirmadas."
            )

        else:
            st.info("Não há quantidades para analisar.")

    # ----------------------------------------------
    # GRÁFICO DE LINHA — VENCIMENTOS
    # ----------------------------------------------

    elif tipo_grafico.startswith("📈"):

        st.markdown("#### Distribuição dos vencimentos")

        agrupamento = defaultdict(float)

        for lote in lotes_filtrados:

            validade = lote.get("validade")

            if not validade:
                continue

            try:
                data_validade = datetime.fromisoformat(
                    str(validade)[:10]
                )

                mes = data_validade.strftime("%Y-%m")

                agrupamento[mes] += float(
                    lote.get("quantidade_kg") or 0
                )

            except (ValueError, TypeError):
                continue

        dados = [
            {
                "Mês": mes,
                "Quantidade (kg)": round(quantidade, 2),
            }
            for mes, quantidade in sorted(
                agrupamento.items()
            )
        ]

        if dados:

            grafico = (
                alt.Chart(alt.Data(values=dados))
                .mark_line(
                    color="#66E9EC",
                    point=True,
                    strokeWidth=3,
                )
                .encode(
                    x=alt.X(
                        "Mês:N",
                        title="Mês de vencimento",
                        sort=sorted(agrupamento.keys()),
                    ),
                    y=alt.Y(
                        "Quantidade (kg):Q",
                        title="Quantidade com vencimento (kg)",
                    ),
                    tooltip=[
                        "Mês:N",
                        "Quantidade (kg):Q",
                    ],
                )
                .properties(height=350)
            )

            st.altair_chart(
                grafico,
                use_container_width=True,
            )

            st.caption(
                "O gráfico agrupa os lotes pela data "
                "de validade cadastrada. Não representa "
                "o histórico de entregas."
            )

        else:
            st.info(
                "Não há datas de validade válidas "
                "para construir este gráfico."
            )


    # ----------------------------------------------
    # ANÁLISE DE DOADORES
    # ----------------------------------------------

    st.markdown("### 🤝 Participação dos doadores")

    kg_por_doador = defaultdict(float)
    lotes_por_doador = defaultdict(int)

    nomes_doadores = {
        str(doador.get("id")): str(
            doador.get("nome") or "Sem nome"
        )
        for doador in doadores
    }

    for lote in lotes_filtrados:

        nome = nomes_doadores.get(
            str(lote.get("doador_id")),
            "Doador não identificado",
        )

        kg_por_doador[nome] += float(
            lote.get("quantidade_kg") or 0
        )

        lotes_por_doador[nome] += 1

    if kg_por_doador:

        dados_doadores = [
            {
                "Doador": nome,
                "Lotes": lotes_por_doador[nome],
                "Quantidade cadastrada (kg)": round(
                    quantidade, 2
                ),
            }
            for nome, quantidade in sorted(
                kg_por_doador.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ]

        st.dataframe(
            dados_doadores,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "A tabela apresenta lotes cadastrados por "
            "doador, não necessariamente entregas realizadas."
        )

    else:
        st.info(
            "Nenhuma contribuição encontrada para os filtros."
        )

    # ----------------------------------------------
    # CAPACIDADE DAS ONGs
    # ----------------------------------------------

    st.markdown("### 🏢 Capacidade das organizações")

    if ongs:

        dados_ongs = [
            {
                "Organização": str(
                    ong.get("nome") or "Sem nome"
                ),
                "Cidade": str(
                    ong.get("cidade") or "—"
                ),
                "UF": str(
                    ong.get("estado") or "—"
                ),
                "Capacidade cadastrada (kg)": float(
                    ong.get("capacidade_kg") or 0
                ),
            }
            for ong in ongs
        ]

        dados_ongs.sort(
            key=lambda item: item[
                "Capacidade cadastrada (kg)"
            ],
            reverse=True,
        )

        st.dataframe(
            dados_ongs,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Capacidade total cadastrada pelas ONGs. "
            "Não representa capacidade livre ou "
            "quantidade efetivamente recebida."
        )

    else:
        st.info("Nenhuma ONG cadastrada.")

    # ----------------------------------------------
    # EXPORTAÇÃO CSV
    # ----------------------------------------------

    st.divider()
    st.markdown("### 📥 Exportar relatório")

    st.caption(
        "Baixe os lotes que correspondem aos filtros "
        "selecionados, incluindo identificação do doador."
    )

    linhas_csv = []

    for lote in lotes_filtrados:

        linhas_csv.append({
            "ID do lote": lote.get("id", ""),
            "Alimento": lote.get("descricao", ""),
            "Tipo": lote.get("tipo") or "",
            "Quantidade (kg)": lote.get(
                "quantidade_kg", 0
            ),
            "Validade": str(
                lote.get("validade") or ""
            ),
            "Armazenamento": lote.get(
                "armazenamento", ""
            ),
            "Status": STATUS.get(
                lote.get("status"),
                lote.get("status", ""),
            ),
            "Doador": nomes_doadores.get(
                str(lote.get("doador_id")),
                "Doador não identificado",
            ),
            "Cadastro": str(
                lote.get("criado_em") or ""
            ),
        })

    colunas_csv = [
        "ID do lote",
        "Alimento",
        "Tipo",
        "Quantidade (kg)",
        "Validade",
        "Armazenamento",
        "Status",
        "Doador",
        "Cadastro",
    ]

    arquivo_csv = io.StringIO()

    escritor = csv.DictWriter(
        arquivo_csv,
        fieldnames=colunas_csv,
        delimiter=";",
    )

    escritor.writeheader()
    escritor.writerows(linhas_csv)

    st.download_button(
        "⬇️ Baixar relatório de lotes (CSV)",
        data=arquivo_csv.getvalue().encode(
            "utf-8-sig"
        ),
        file_name="rede_alimenta_relatorio_lotes.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )

    st.caption(
        "O CSV contém somente os lotes exibidos "
        "pelos filtros. Nenhum dado é alterado "
        "durante a exportação."
    )

    st.stop()