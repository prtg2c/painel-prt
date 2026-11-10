import os
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

# Configuração da página
st.set_page_config(page_title="Meu Painel de Investimentos", layout="wide")
st.title("📈 Meu Painel de Investimentos")

ARQUIVO_DADOS = "carteira.csv"


# Função para carregar dados salvos ou criar carteira inicial de exemplo
def carregar_carteira():
    if os.path.exists(ARQUIVO_DADOS):
        df = pd.read_csv(ARQUIVO_DADOS)
        if "Preco_Medio" not in df.columns:
            df["Preco_Medio"] = 0.0
        return df

    # Cria a carteira inicial com os seus ativos e valores de exemplo
    dados_iniciais = pd.DataFrame({
        "Ticker": [
            "MDNE3.SA",
            "VIVA3.SA",
            "FIQE3.SA",
            "HGLG11.SA",
            "VOO",
            "QQQM",
            "SCHD",
        ],
        "Quantidade": [45.0, 40.0, 250.0, 6.0, 0.85, 2.15, 17.50],
        "Preco_Medio": [12.00, 22.00, 3.80, 155.00, 480.00, 180.00, 27.00],
    })
    salvar_carteira(dados_iniciais)
    return dados_iniciais


# Função para salvar dados no CSV
def salvar_carteira(df):
    df.to_csv(ARQUIVO_DADOS, index=False)


# Função para buscar cotação atual no Yahoo Finance
@st.cache_data(ttl=300)
def buscar_cotacao(ticker):
    try:
        ativo = yf.Ticker(ticker)
        historico = ativo.history(period="1d")
        if not historico.empty:
            return round(float(historico["Close"].iloc[-1]), 2)
        return None
    except Exception:
        return None


# --- BARRA LATERAL: Dólar, Adicionar e Atualizar ---
st.sidebar.header("Câmbio e Controles")

cotacao_dolar = buscar_cotacao("USDBRL=X") or 5.50
st.sidebar.metric("Cotação Dólar (USDBRL)", f"R$ {cotacao_dolar:.2f}")

if st.sidebar.button("🔄 Atualizar Cotações Agora"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Gerenciar Carteira")
st.sidebar.markdown("""
**Regras de preenchimento:**
* **Brasil (`.SA`):** informe o Preço Médio em **Reais (R$)**.
* **EUA (sem `.SA`):** informe o Preço Médio em **Dólares (US$)**.
""")

with st.sidebar.form("form_adicionar"):
    novo_ticker = st.text_input("Código do Ativo (Ticker)").upper().strip()
    nova_qtd = st.number_input("Quantidade", min_value=0.0001, format="%.4f")
    novo_pm = st.number_input(
        "Preço Médio (na moeda original)", min_value=0.01, format="%.2f"
    )
    btn_adicionar = st.form_submit_button("Salvar / Atualizar Ativo")

    if btn_adicionar and novo_ticker:
        df_atual = carregar_carteira()
        if novo_ticker in df_atual["Ticker"].values:
            df_atual.loc[df_atual["Ticker"] == novo_ticker, "Quantidade"] = (
                nova_qtd
            )
            df_atual.loc[df_atual["Ticker"] == novo_ticker, "Preco_Medio"] = (
                novo_pm
            )
        else:
            novo_registro = pd.DataFrame({
                "Ticker": [novo_ticker],
                "Quantidade": [nova_qtd],
                "Preco_Medio": [novo_pm],
            })
            df_atual = pd.concat([df_atual, novo_registro], ignore_index=True)
        salvar_carteira(df_atual)
        st.sidebar.success(f"{novo_ticker} atualizado!")
        st.rerun()

# --- PAINEL PRINCIPAL ---
df_carteira = carregar_carteira()

if df_carteira.empty:
    st.info(
        "Sua carteira está vazia. Adicione seus ativos na barra lateral esquerda."
    )
else:
    regioes = []
    moedas = []
    cotacoes_atuais = []
    totais_investidos_brl = []
    totais_atuais_brl = []
    lucros_brl = []
    rentabilidades_pct = []
    total_exterior_usd = 0.0

    with st.spinner("Buscando cotações e calculando rentabilidade..."):
        for index, row in df_carteira.iterrows():
            ticker = row["Ticker"]
            qtd = row["Quantidade"]
            pm = row["Preco_Medio"]
            preco = buscar_cotacao(ticker)

            if preco is not None:
                cotacoes_atuais.append(preco)
                eh_brasil = ticker.endswith(".SA")
                fator_cambio = 1.0 if eh_brasil else cotacao_dolar
                moeda_ativo = "BRL" if eh_brasil else "USD"
                regiao_ativo = "Brasil (Nacional)" if eh_brasil else "Exterior (Internacional)"

                # Soma o valor atual em dólar apenas para ativos de fora do Brasil
                if not eh_brasil:
                    total_exterior_usd += preco * qtd

                custo_brl = pm * qtd * fator_cambio
                valor_atual_brl = preco * qtd * fator_cambio
                lucro = valor_atual_brl - custo_brl
                pct = ((preco - pm) / pm * 100) if pm > 0 else 0.0

                regioes.append(regiao_ativo)
                moedas.append(moeda_ativo)
                totais_investidos_brl.append(round(custo_brl, 2))
                totais_atuais_brl.append(round(valor_atual_brl, 2))
                lucros_brl.append(round(lucro, 2))
                rentabilidades_pct.append(round(pct, 2))
            else:
                regioes.append("Indefinido")
                moedas.append("Erro")
                cotacoes_atuais.append(0.0)
                totais_investidos_brl.append(0.0)
                totais_atuais_brl.append(0.0)
                lucros_brl.append(0.0)
                rentabilidades_pct.append(0.0)

    df_carteira["Mercado"] = regioes
    df_carteira["Moeda"] = moedas
    df_carteira["Cotação Atual"] = cotacoes_atuais
    df_carteira["Investido (R$)"] = totais_investidos_brl
    df_carteira["Atual (R$)"] = totais_atuais_brl
    df_carteira["Lucro/Prejuízo (R$)"] = lucros_brl
    df_carteira["Rentab. (%)"] = rentabilidades_pct

    # --- MÉTRICAS PRINCIPAIS NO TOPO (4 COLUNAS) ---
    total_investido = df_carteira["Investido (R$)"].sum()
    patrimonio_atual = df_carteira["Atual (R$)"].sum()
    lucro_total = patrimonio_atual - total_investido
    rentab_total = (
        (lucro_total / total_investido * 100) if total_investido > 0 else 0.0
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        label="Total Investido (R$)",
        value=f"R$ {total_investido:,.2f}",
    )
    m2.metric(
        label="Patrimônio Total (R$)",
        value=f"R$ {patrimonio_atual:,.2f}",
        delta=f"{rentab_total:.2f}%",
    )
    m3.metric(
        label="Lucro / Prejuízo Total",
        value=f"R$ {lucro_total:,.2f}",
        delta=f"R$ {lucro_total:,.2f}",
    )
    m4.metric(
        label="Patrimônio Exterior (US$)",
        value=f"US$ {total_exterior_usd:,.2f}",
        help="Soma atual apenas dos ativos fora do Brasil, na moeda original (Dólar).",
    )

    st.divider()

    # --- TABELA EM LARGURA TOTAL ---
    st.subheader("Desempenho por Ativo")

    def colorir_lucro(val):
        cor = "#2ecc71" if val > 0 else ("#e74c3c" if val < 0 else "inherit")
        return f"color: {cor}; font-weight: bold"

    df_estilizado = df_carteira.style.map(
        colorir_lucro, subset=["Lucro/Prejuízo (R$)", "Rentab. (%)"]
    )

    st.dataframe(
        df_estilizado,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Quantidade": st.column_config.NumberColumn(format="%.4f"),
            "Preco_Medio": st.column_config.NumberColumn(
                "Preço Médio", format="%.2f"
            ),
            "Cotação Atual": st.column_config.NumberColumn(format="%.2f"),
            "Investido (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Atual (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Lucro/Prejuízo (R$)": st.column_config.NumberColumn(
                format="R$ %.2f"
            ),
            "Rentab. (%)": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    # Opção para remover um ativo
    with st.expander("🗑️ Remover um ativo da carteira"):
        ativo_remover = st.selectbox(
            "Selecione o ativo:",
            ["Selecione..."] + df_carteira["Ticker"].tolist(),
        )
        if ativo_remover != "Selecione...":
            if st.button("Confirmar Remoção"):
                df_carteira = df_carteira[
                    df_carteira["Ticker"] != ativo_remover
                ]
                salvar_carteira(
                    df_carteira[["Ticker", "Quantidade", "Preco_Medio"]]
                )
                st.rerun()

    st.divider()

    # --- DOIS GRÁFICOS ABAIXO DA GRID ---
    df_validos = df_carteira[df_carteira["Atual (R$)"] > 0]

    if not df_validos.empty:
        col_graf1, col_graf2 = st.columns(2)

        with col_graf1:
            st.subheader("Distribuição por Ativo (%)")
            fig_ativos = px.pie(
                df_validos,
                values="Atual (R$)",
                names="Ticker",
                hole=0.4,
            )
            fig_ativos.update_traces(
                textposition="inside", textinfo="percent+label"
            )
            fig_ativos.update_layout(height=420)
            st.plotly_chart(fig_ativos, use_container_width=True)

        with col_graf2:
            st.subheader("Brasil vs. Exterior (%)")
            df_regiao = (
                df_validos.groupby("Mercado", as_index=False)["Atual (R$)"]
                .sum()
            )
            fig_regiao = px.pie(
                df_regiao,
                values="Atual (R$)",
                names="Mercado",
                hole=0.4,
                color="Mercado",
                color_discrete_map={
                    "Brasil (Nacional)": "#27ae60",
                    "Exterior (Internacional)": "#2980b9",
                },
            )
            fig_regiao.update_traces(
                textposition="inside", textinfo="percent+label"
            )
            fig_regiao.update_layout(height=420)
            st.plotly_chart(fig_regiao, use_container_width=True)
