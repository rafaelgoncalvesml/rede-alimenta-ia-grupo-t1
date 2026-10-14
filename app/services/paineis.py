"""Blocos de Relatorios que o PDF pede alem dos KPIs da API: mapa de calor e seguranca (SAST)."""
from datetime import datetime

import altair as alt
import pydeck as pdk
import streamlit as st
from services import painel


def _data(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except (AttributeError, ValueError):
        return iso or "?"


def mapa_de_calor(cliente, ongs, lotes, doacoes):
    st.markdown("### 🗺️ Onde a rede atua")

    historico = painel.carrega_historico()
    opcoes = []
    if historico:
        opcoes.append("Histórico simulado (jun a set/2026)")
    if not cliente.demonstracao:
        opcoes.append("Doações registradas na API")
    if not opcoes:
        st.info("Sem histórico no disco e sem API conectada: nada para desenhar no mapa.")
        return

    fonte = st.radio("Dados do mapa", opcoes, horizontal=True, key="mapa_fonte")
    if fonte.startswith("Histórico"):
        pontos = painel.kg_entregue_por_ong(historico["ongs"], historico["lotes"], historico["doacoes"])
        st.warning(
            "Tudo aqui é simulado: 12 ONGs inventadas, 2 por cidade, e doações geradas por "
            "`data/gerar_historico_simulado.py`. O mapa mostra o formato, não a realidade."
        )
    else:
        pontos = painel.kg_entregue_por_ong(ongs, lotes, doacoes)
        st.caption("Só entram lotes já entregues (status doado) com doação confirmada.")

    if not pontos:
        st.info("Ainda não há entrega registrada nesta fonte.")
        return

    centro_lat = sum(p["latitude"] for p in pontos) / len(pontos)
    centro_lon = sum(p["longitude"] for p in pontos) / len(pontos)
    camadas = [
        pdk.Layer(
            "HeatmapLayer", data=pontos, get_position="[longitude, latitude]",
            get_weight="kg", radiusPixels=70, opacity=0.8,
        ),
        pdk.Layer(
            "ScatterplotLayer", data=pontos, get_position="[longitude, latitude]",
            get_radius=500, radius_min_pixels=4, get_fill_color=[33, 197, 142, 230], pickable=True,
        ),
    ]
    st.pydeck_chart(
        pdk.Deck(
            layers=camadas,
            initial_view_state=pdk.ViewState(latitude=centro_lat, longitude=centro_lon, zoom=8.3),
            map_provider="carto", map_style="dark",
            tooltip={"text": "{ong}\n{cidade}/{estado}\n{kg} kg em {doacoes} doações"},
        ),
        use_container_width=True,
    )
    st.caption(
        "Quanto mais quente a mancha, mais kg a ONG daquela região recebeu. "
        "É onde a comida chegou, não uma medida de carência: não temos dado de necessidade por bairro."
    )

    por_cidade = painel.kg_por_cidade(pontos)
    grafico = (
        alt.Chart(alt.Data(values=por_cidade))
        .mark_bar(cornerRadiusTopRight=6, cornerRadiusBottomRight=6, color="#21C58E")
        .encode(
            y=alt.Y("cidade:N", sort="-x", title=None),
            x=alt.X("kg:Q", title="kg entregues"),
            tooltip=["cidade:N", "estado:N", "kg:Q", "doacoes:Q"],
        )
        .properties(height=max(120, 34 * len(por_cidade)))
    )
    st.altair_chart(grafico, use_container_width=True)


def seguranca():
    st.markdown("### 🛡️ Segurança do pipeline (SAST)")

    dados = painel.carrega_seguranca()
    if not dados:
        st.info("Sem `app/dados/seguranca.json`. Gere com `python infra/gerar_seguranca.py`.")
        return

    resumo = painel.resumo_seguranca(dados)
    medido = dados["medido_agora"]
    bandit = medido["bandit"]
    auditoria = sum(item["vulnerabilidades"] for item in medido["pip_audit"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Security gates no CI", f"{resumo['gates_ok']}/{resumo['gates_total']}")
    col2.metric("Bandit: alta, média, baixa", f"{bandit['alta']}, {bandit['media']}, {bandit['baixa']}")
    col3.metric("Vulnerabilidades (pip-audit)", auditoria, help="Soma das 4 listas de dependências")
    col4.metric("Achados corrigidos", resumo["mitigadas"])

    ci = dados.get("ci")
    if ci:
        st.markdown(
            f"CI na `main` (commit `{ci['commit']}`, {_data(ci['em'])}): "
            + ", ".join(
                f"{'✅' if gate['status'] == 'passou' else '❌'} {gate['nome']}" for gate in dados["gates"]
            )
            + f". [Ver execução]({ci['url']})"
        )
    testes = medido["testes"]
    st.caption(
        f"Testes: {testes['passaram']} passaram, {testes['falharam']} falharam. Ruff: {medido['ruff']}. "
        f"Arquivo gerado em {_data(dados['gerado_em'])} por `{dados['gerado_por']}`."
    )

    with st.expander("O que foi corrigido"):
        st.dataframe(
            [
                {"Item": item["item"], "Achados": item["achados"], "Origem": item["origem"]}
                for item in dados["mitigadas"]
            ],
            hide_index=True, use_container_width=True,
        )
        st.caption("A soma dos achados vem da tabela acima; as fontes estão em docs/security/.")

    with st.expander("O que ficou aceito (sem correção publicada)"):
        st.dataframe(
            [
                {"CVE": item["cve"], "Pacote": item["pacote"], "Por que aceitamos": item["motivo"]}
                for item in dados["aceitos"]
            ],
            hide_index=True, use_container_width=True,
        )
        st.caption("Leitura nossa do código, não teste de exploração. Reavaliar quando a Debian corrigir.")

    for aviso in dados.get("avisos", []):
        st.caption(aviso)
