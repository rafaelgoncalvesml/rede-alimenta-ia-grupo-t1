

import os
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st


class ErroAPI(Exception):

    pass





TRANSICOES = {

    "disponivel": {"reservado", "descartado"},

    "reservado": {"disponivel", "doado", "descartado"},

    "doado": set(),

    "descartado": set(),

}





def agora():

    return datetime.now(timezone.utc).isoformat()





def iniciar_demo():

    for chave, valor in {

        "demo_doadores": [],

        "demo_lotes": [],

        "demo_ongs": [],

        "demo_proximo_doador": 1,

        "demo_proximo_lote": 1,

    }.items():

        if chave not in st.session_state:

            st.session_state[chave] = valor





def configuracao_api():

    from dotenv import load_dotenv



    load_dotenv(

        Path(__file__).resolve().parents[2] / ".env",

        override=False,

    )



    url = os.getenv("REDE_ALIMENTA_API_URL", "").strip()



    try:

        segredo = st.secrets.get("REDE_ALIMENTA_API_URL")

        if segredo:

            url = segredo

    except (FileNotFoundError, KeyError):

        pass



    return str(url).strip().rstrip("/")





class ClienteAPI:

    def __init__(self):

        self.url = configuracao_api()

        self.demonstracao = not bool(self.url)

        self.token = st.session_state.get("api_access_token")

        iniciar_demo()





    def fazer_login(self, email, senha):

        try:

            resposta = requests.post(

                f"{self.url}/auth/login",

                json={"email": email, "senha": senha},

                timeout=60,

            )

            resposta.raise_for_status()

            dados = resposta.json()



            token = dados["access_token"]



            resposta_perfil = requests.get(

                f"{self.url}/auth/eu",

                headers={"Authorization": f"Bearer {token}"},

                timeout=30,

            )



            resposta_perfil.raise_for_status()

            perfil = resposta_perfil.json()
            if not isinstance(perfil, dict) or perfil.get("papel") not in ("admin", "doador", "ong"):
                raise ValueError("Perfil de acesso inválido retornado pela API")



            self.token = token

            st.session_state["api_access_token"] = token

            st.session_state["api_usuario"] = perfil



            return True



        except (requests.RequestException, ValueError, KeyError) as erro:

            raise ErroAPI(

                f"Não foi possível realizar o login: {erro}"

            ) from erro



    def requisicao(self, metodo, caminho, dados=None):

        try:

            resposta = requests.request(

                metodo,

                f"{self.url}{caminho}",

                json=dados,

                headers=(

                    {"Authorization": f"Bearer {self.token}"}

                    if self.token

                    else {}

                ),

                timeout=60,

            )



        except requests.RequestException as erro:

            raise ErroAPI(

                f"Não foi possível conectar à API: {erro}"

            ) from erro



        if resposta.status_code == 401 and self.token:

            self.token = None
            st.session_state.pop("api_access_token", None)
            st.session_state.pop("api_usuario", None)
            st.session_state["usuario_logado"] = False
            raise ErroAPI(
                "Sua sessão expirou ou não é mais válida. Faça login novamente."
            )



        if not resposta.ok:

            try:

                detalhe = resposta.json().get(

                    "detail", resposta.text

                )

            except (ValueError, AttributeError):

                detalhe = resposta.text



            if isinstance(detalhe, list):

                detalhe = "; ".join(

                    str(item.get("msg", item))

                    if isinstance(item, dict)

                    else str(item)

                    for item in detalhe

                )



            raise ErroAPI(

                f"Erro HTTP {resposta.status_code}: {detalhe}"

            )



        if resposta.status_code == 204:

            return None



        try:

            return resposta.json()

        except ValueError:

            return None



    def verificar_banco(self):

        if self.demonstracao:

            return {

                "status": "ok",

                "storage": "demo_streamlit",

            }

        return self.requisicao("GET", "/health/db")



    # ==========================================

    # DOADORES

    # ==========================================



    def listar_doadores(self):

        if not self.demonstracao:

            return self.requisicao("GET", "/doadores")



        return list(st.session_state.demo_doadores)



    def cadastrar_doador(self, dados):

        if not self.demonstracao:

            return self.requisicao("POST", "/doadores", dados)



        documento = "".join(

            c for c in dados["documento"] if c.isdigit()

        )



        esperado = (

            11 if dados["tipo_pessoa"] == "fisica" else 14

        )



        if len(documento) != esperado:

            raise ErroAPI(

                f"O documento precisa ter {esperado} dígitos."

            )



        if any(

            d["documento"] == documento

            for d in st.session_state.demo_doadores

        ):

            raise ErroAPI(

                "Já existe um doador com esse documento."

            )



        if not dados["nome"].strip() or not dados["cidade"].strip():

            raise ErroAPI("Informe nome e cidade.")



        if len(dados["estado"].strip()) != 2:

            raise ErroAPI("Informe uma UF válida.")



        novo = {

            **dados,

            "id": st.session_state.demo_proximo_doador,

            "documento": documento,

            "estado": dados["estado"].upper(),

            "criado_em": agora(),

        }



        st.session_state.demo_doadores.append(novo)

        st.session_state.demo_proximo_doador += 1

        return novo



    def buscar_doador(self, doador_id):

        if not self.demonstracao:

            return self.requisicao(

                "GET", f"/doadores/{doador_id}"

            )



        for doador in st.session_state.demo_doadores:

            if doador["id"] == doador_id:

                return dict(doador)



        raise ErroAPI("Doador não encontrado.")



    def atualizar_doador(self, doador_id, dados):

        if not self.demonstracao:

            return self.requisicao(

                "PUT", f"/doadores/{doador_id}", dados

            )



        self.buscar_doador(doador_id)



        for registro in st.session_state.demo_doadores:

            if registro["id"] == doador_id:

                registro.update(dados)

                return dict(registro)



        raise ErroAPI("Doador não encontrado.")



    # ==========================================

    # LOTES

    # ==========================================



    def listar_lotes(self):

        if not self.demonstracao:

            return self.requisicao("GET", "/lotes")



        return list(st.session_state.demo_lotes)



    def buscar_lote(self, lote_id):

        if not self.demonstracao:

            return self.requisicao(

                "GET", f"/lotes/{lote_id}"

            )



        for lote in st.session_state.demo_lotes:

            if lote["id"] == lote_id:

                return dict(lote)



        raise ErroAPI("Lote não encontrado.")



    def cadastrar_lote(self, dados):

        if not self.demonstracao:

            return self.requisicao("POST", "/lotes", dados)



        from datetime import date



        if not any(

            d["id"] == dados["doador_id"]

            for d in st.session_state.demo_doadores

        ):

            raise ErroAPI(

                "O doador selecionado não existe."

            )



        if float(dados["quantidade_kg"]) <= 0:

            raise ErroAPI(

                "A quantidade precisa ser positiva."

            )



        if date.fromisoformat(dados["validade"]) < date.today():

            raise ErroAPI(

                "A validade não pode estar vencida."

            )



        novo = {

            **dados,

            "id": st.session_state.demo_proximo_lote,

            "status": "disponivel",

            "prioridade": None,

            "criado_em": agora(),

        }



        st.session_state.demo_lotes.append(novo)

        st.session_state.demo_proximo_lote += 1

        return novo



    def atualizar_lote(self, lote_id, dados):

        if not self.demonstracao:

            return self.requisicao(

                "PUT", f"/lotes/{lote_id}", dados

            )



        lote = self.buscar_lote(lote_id)

        atual = lote["status"]



        if atual in ("doado", "descartado"):

            raise ErroAPI(

                "Lotes finalizados não podem ser editados."

            )



        novo_status = dados.get("status", atual)



        if (

            novo_status != atual

            and novo_status not in TRANSICOES[atual]

        ):

            raise ErroAPI(

                "Transição de status não permitida."

            )



        if "quantidade_kg" in dados:

            if float(dados["quantidade_kg"]) <= 0:

                raise ErroAPI("Quantidade inválida.")



        if "validade" in dados:

            from datetime import date



            if date.fromisoformat(dados["validade"]) < date.today():

                raise ErroAPI("Validade vencida.")



        for registro in st.session_state.demo_lotes:

            if registro["id"] == lote_id:

                registro.update(dados)

                return dict(registro)



        raise ErroAPI("Lote não encontrado.")



    def excluir_lote(self, lote_id):

        if not self.demonstracao:

            return self.requisicao(

                "DELETE", f"/lotes/{lote_id}"

            )



        lote = self.buscar_lote(lote_id)



        if lote["status"] in ("reservado", "doado"):

            raise ErroAPI(

                "Lotes reservados ou doados "

                "não podem ser excluídos."

            )



        st.session_state.demo_lotes = [

            l for l in st.session_state.demo_lotes

            if l["id"] != lote_id

        ]



    # ==========================================

    # ONGS

    # ==========================================



    def listar_ongs(self):

        if not self.demonstracao:

            return self.requisicao("GET", "/ongs")



        return list(st.session_state.demo_ongs)



    def buscar_ong(self, ong_id):

        if not self.demonstracao:

            return self.requisicao(

                "GET", f"/ongs/{ong_id}"

            )



        for ong in st.session_state.demo_ongs:

            if ong["id"] == ong_id:

                return dict(ong)



        raise ErroAPI("ONG não encontrada.")



    def cadastrar_ong(self, dados):

        if not self.demonstracao:

            return self.requisicao("POST", "/ongs", dados)



        cnpj = "".join(

            c for c in dados["cnpj"] if c.isdigit()

        )



        if len(cnpj) != 14:

            raise ErroAPI(

                "O CNPJ precisa ter 14 dígitos."

            )



        if any(

            o["cnpj"] == cnpj

            for o in st.session_state.demo_ongs

        ):

            raise ErroAPI(

                "Já existe uma ONG com esse CNPJ."

            )



        if not all(

            str(dados.get(campo, "")).strip()

            for campo in (

                "nome", "endereco", "cidade", "estado"

            )

        ):

            raise ErroAPI(

                "Preencha todos os campos obrigatórios."

            )



        if len(dados["estado"].strip()) != 2:

            raise ErroAPI("Informe uma UF válida.")



        if float(dados["capacidade_kg"]) < 0:

            raise ErroAPI(

                "A capacidade não pode ser negativa."

            )



        if "demo_proxima_ong" not in st.session_state:

            st.session_state.demo_proxima_ong = 1



        novo = {

            **dados,

            "id": st.session_state.demo_proxima_ong,

            "cnpj": cnpj,

            "estado": dados["estado"].strip().upper(),

            "criado_em": agora(),

        }



        st.session_state.demo_ongs.append(novo)

        st.session_state.demo_proxima_ong += 1

        return novo



    def atualizar_ong(self, ong_id, dados):

        if not self.demonstracao:

            return self.requisicao(

                "PUT", f"/ongs/{ong_id}", dados

            )



        ong = self.buscar_ong(ong_id)



        if (

            "cnpj" in dados

            and dados["cnpj"] != ong["cnpj"]

        ):

            raise ErroAPI(

                "O CNPJ não pode ser alterado."

            )



        if "capacidade_kg" in dados:

            if float(dados["capacidade_kg"]) < 0:

                raise ErroAPI(

                    "A capacidade não pode ser negativa."

                )



        for registro in st.session_state.demo_ongs:

            if registro["id"] == ong_id:

                registro.update(dados)

                return dict(registro)



        raise ErroAPI("ONG não encontrada.")



    def excluir_ong(self, ong_id):

        if not self.demonstracao:

            return self.requisicao(

                "DELETE", f"/ongs/{ong_id}"

            )



        self.buscar_ong(ong_id)



        st.session_state.demo_ongs = [

            ong for ong in st.session_state.demo_ongs

            if ong["id"] != ong_id

        ]

    # ==========================================
    # MATCHING, DOACOES E KPIS
    # ==========================================
    # So existem com a API conectada: no modo demonstracao nao ha servidor pra calcular distancia,
    # gravar doacao nem somar KPI, e inventar esses numeros na tela seria pior que nao mostrar.

    def _exige_api(self, acao):
        if self.demonstracao:
            raise ErroAPI(f"{acao} so funciona com a API conectada (REDE_ALIMENTA_API_URL).")

    def sugerir_ongs(self, lote_id):
        """Ranking do POST /matching/{lote_id}: {"ranking": [...], "descartadas": [...]}."""
        self._exige_api("O ranking de ONGs")
        return self.requisicao("POST", f"/matching/{lote_id}")

    def confirmar_doacao(self, lote_id, ong_id):
        """Reserva o lote pra ONG. Distancia e score sao calculados no servidor."""
        self._exige_api("Confirmar doacao")
        return self.requisicao("POST", "/doacoes", {"lote_id": lote_id, "ong_id": ong_id})

    def listar_doacoes(self):
        return [] if self.demonstracao else self.requisicao("GET", "/doacoes")

    def kpis_impacto(self):
        return None if self.demonstracao else self.requisicao("GET", "/kpis/impacto")

    def kpis_ia(self):
        return None if self.demonstracao else self.requisicao("GET", "/kpis/ia")
