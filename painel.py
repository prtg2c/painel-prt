import os
from io import StringIO
from github import Github
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Meu Painel de Investimentos", layout="wide")
st.title("📈 Meu Painel de Investimentos")

ARQUIVO_DADOS = "carteira.csv"


def usar_github():
    return "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets


def carregar_carteira():
    if usar_github():
        try:
            g = Github(st.secrets["GITHUB_TOKEN"])
            repo = g.get_repo(st.secrets["GITHUB_REPO"])
            conteudo = repo.get_contents(ARQUIVO_DADOS)
            df = pd.read_csv(StringIO(conteudo.decoded_content.decode("utf-8")))
            if "Preco_Medio" not in df.columns:
                df["Preco_Medio"] = 0.0
            return df
        except Exception as e:
            st.error(f"Erro ao ler carteira do GitHub: {e}")

    if os.path.exists(ARQUIVO_DADOS):
        df = pd.read_csv(ARQUIVO_DADOS)
        if "Preco_Medio" not in df.columns:
            df["Preco_Medio"] = 0.0
        return df

    dados_iniciais = pd.DataFrame({
        "Ticker": ["MDNE3.SA", "VIVA3.SA", "FIQE3.SA", "HGLG11.SA", "VOO", "QQQM", "SCHD"],
        "Quantidade": [45.0, 40.0, 250.0, 6.0, 0.85, 2.15, 17.5],
        "Preco_Medio": [22.0, 25.0, 4.0, 160.0, 500.0, 200.0, 28.0],
    })
    salvar_carteira(dados_iniciais)
    return dados_iniciais


def salvar_carteira(df):
    csv_texto = df.to_csv(index=False)

    if usar_github():
        try:
            g = Github(st.secrets["GITHUB_TOKEN"])
            repo = g.get_repo(st.secrets["GITHUB_REPO"])
            try:
                arquivo_remoto = repo.get_contents(ARQUIVO_DADOS)
                repo.update_file(
                    path=ARQUIVO_DADOS,
                    message="Atualização da carteira via Streamlit",
                    content=csv_texto,
                    sha=arquivo_remoto.sha,
                )
            except Exception:
                repo.create_file(
                    path=ARQUIVO_DADOS,
                    message="Criação inicial da carteira via Streamlit",
                    content=csv_texto,
                )
            return
        except Exception as e:
            st.error(f"Erro ao salvar no GitHub: {e}")

    df.to_csv(ARQUIVO_DADOS, index=False)


@st.cache_data(ttl=300)
def buscar_dados_ativo(ticker):
    try:
        ativo = yf.Ticker(ticker)
        historico = ativo.history(period="5d")
        preco_hoje = None
        variacao_dia = 0.0

        if len(historico) >= 2:
            preco_ontem = float(historico["Close"].iloc[-2])
            preco_hoje = float(historico["Close"].iloc[-1])
            variacao_dia = ((preco_hoje - preco_ontem) / preco_ontem) * 100
        elif len(historico) == 1:
            preco_hoje = float(historico["Close"].iloc[-1])

        dy_pct = 0.0
        try:
            info = ativo.info
            dy_raw = info.get("dividendYield")
            if dy_raw is not None:
                dy_pct = dy_raw * 100 if dy_raw < 1 else dy_raw
        except Exception:
            dy_pct = 0.0

        if preco_hoje is not None:
            return round(preco_hoje, 2), round(variacao_dia, 2), round(dy_pct, 2)
        return None, 0.0, 0.0
    except Exception:
        return None, 0.0, 0.0


st.sidebar.header("Câmbio e Controles")

if usar_github():
    st.sidebar.success("☁️ Sincronizado com GitHub")
else:
    st.sidebar.info("💻 Modo Local (CSV)")

cotacao_dolar, var_dolar, _ = buscar_dados_ativo("USDBRL=X")
if cotacao_dolar is None:
    cotacao_dolar = 5.50
    var_dolar = 0.0

st.sidebar.metric("Cotação Dólar (USDBRL)", f"R$ {cotacao_dolar:.2f}", delta=f"{var_dolar:.2f}%")

if st.sidebar.button("🔄 Atualizar Cotações Agora"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()
st.sidebar.header("Gerenciar Carteira")
st.sidebar.markdown("**Regras:** Brasil (`.SA`) em **R$** | EUA em **US$**.")

with st.sidebar.form("form_adicionar"):
    novo_ticker = st.text_input("Código do Ativo (Ticker)").upper().strip()
    nova_qtd = st.number_input("Quantidade", min_value=0.0001, format="%.4f")
    novo_pm = st.number_input("Preço Médio (na moeda original)", min_value=0.01, format="%.2f")
    btn_adicionar = st.form_submit_button("Salvar / Atualizar Ativo")

    if btn_adicionar and novo_ticker:
        df_atual = carregar_carteira()
        if novo_ticker in df_atual["Ticker"].values:
            df_atual.loc[df_atual["Ticker"] == novo_ticker, "Quantidade"] = nova_qtd
            df_atual.loc[df_atual["Ticker"] == novo_ticker, "Preco_Medio"] = novo_pm
        else:
            novo_registro = pd.DataFrame({
                "Ticker": [novo_ticker],
                "Quantidade": [nova_qtd],
                "Preco_Medio": [novo_pm],
            })
            df_atual = pd.concat([df_atual, novo_registro], ignore_index=True)
        salvar_carteira(df_atual)
        st.sidebar.success(f"{novo_ticker} salvo com sucesso!")
        st.rerun()

df_carteira = carregar_carteira()

if df_carteira.empty:
    st.info("Sua carteira está vazia. Adicione seus ativos na barra lateral esquerda.")
else:
    regioes = list()
    moedas = list()
    cotacoes_atuais = list()
    variacoes_hoje = list()
    dividend_yields = list()
    totais_investidos_brl = list()
    totais_atuais_brl = list()
    lucros_brl = list()
    rentabilidades_pct = list()
    total_exterior_usd = 0.0

    with st.spinner("Buscando cotações, variações e dividendos..."):
        for index, row in df_carteira.iterrows():
            ticker = row["Ticker"]
            qtd = row["Quantidade"]
            pm = row["Preco_Medio"]
            preco, var_dia, dy = buscar_dados_ativo(ticker)

            if preco is not None:
                cotacoes_atuais.append(preco)
                dividend_yields.append(dy)

                if var_dia > 0:
                    variacoes_hoje.append(f"🟢 ▲ +{var_dia:.2f}%")
                elif var_dia < 0:
                    variacoes_hoje.append(f"🔴 ▼ {var_dia:.2f}%")
                else:
                    variacoes_hoje.append("⚪ 0.00%")

                eh_brasil = ticker.endswith(".SA")
                fator_cambio = 1.0 if eh_brasil else cotacao_dolar
                moeda_ativo = "BRL" if eh_brasil else "USD"
                regiao_ativo = "Brasil (Nacional)" if eh_brasil else "Exterior (Internacional)"

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
                variacoes_hoje.append("-")
                dividend_yields.append(0.0)
                totais_investidos_brl.append(0.0)
                totais_atuais_brl.append(0.0)
                lucros_brl.append(0.0)
                rentabilidades_pct.append(0.0)

    df_carteira["Mercado"] = regioes
    df_carteira["Moeda"] = moedas
    df_carteira["Cotação Atual"] = cotacoes_atuais
    df_carteira["Hoje"] = variacoes_hoje
    df_carteira["DY (12m)"] = dividend_yields
    df_carteira["Investido (R$)"] = totais_investidos_brl
    df_carteira["Atual (R$)"] = totais_atuais_brl
    df_carteira["Lucro/Prejuízo (R$)"] = lucros_brl
    df_carteira["Rentab. (%)"] = rentabilidades_pct

    total_investido = df_carteira["Investido (R$)"].sum()
    patrimonio_atual = df_carteira["Atual (R$)"].sum()
    lucro_total = patrimonio_atual - total_investido
    rentab_total = (lucro_total / total_investido * 100) if total_investido > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Investido (R$)", f"R$ {total_investido:,.2f}")
    m2.metric("Patrimônio Total (R$)", f"R$ {patrimonio_atual:,.2f}", delta=f"{rentab_total:.2f}%")

    sinal_lucro = "-" if lucro_total < 0 else ""
    m3.metric("Lucro / Prejuízo Total", f"R$ {lucro_total:,.2f}", delta=f"{sinal_lucro}R$ {abs(lucro_total):,.2f}")
    m4.metric("Patrimônio Exterior (US$)", f"US$ {total_exterior_usd:,.2f}")

    st.divider()
    st.subheader("Desempenho por Ativo")

    def colorir_lucro(val):
        cor = "#2ecc71" if val > 0 else ("#e74c3c" if val < 0 else "inherit")
        return f"color: {cor}; font-weight: bold"

    df_estilizado = df_carteira.style.map(colorir_lucro, subset=["Lucro/Prejuízo (R$)", "Rentab. (%)"])

    cols_cfg = {
        "Quantidade": st.column_config.NumberColumn(format="%.4f"),
        "Preco_Medio": st.column_config.NumberColumn("Preço Médio", format="%.2f"),
        "Cotação Atual": st.column_config.NumberColumn(format="%.2f"),
        "DY (12m)": st.column_config.NumberColumn(format="%.2f%%"),
        "Investido (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        "Atual (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        "Lucro/Prejuízo (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        "Rentab. (%)": st.column_config.NumberColumn(format="%.2f%%"),
    }

    st.dataframe(df_estilizado, use_container_width=True, hide_index=True, column_config=cols_cfg)

    with st.expander("🗑️ Remover um ativo da carteira"):
        ativo_remover = st.selectbox("Selecione o ativo:", ["Selecione..."] + df_carteira["Ticker"].tolist())
        if ativo_remover != "Selecione...":
            if st.button("Confirmar Remoção"):
                df_carteira = df_carteira[df_carteira["Ticker"] != ativo_remover]