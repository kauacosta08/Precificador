import streamlit as st
import pandas as pd
import requests
import re

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Validador Berke Motors", page_icon="🚗", layout="centered")

st.title("🚗 Sistema de Precificação Inteligente")
st.markdown("Busca oficial, análise de quilometragem e tendência de mercado baseado na FIPE.")
st.markdown("---")

# Funções auxiliares de preço e KM
def converter_preco_fipe(valor_texto):
    apenas_numeros = re.sub(r'\D', '', valor_texto)
    if not apenas_numeros:
        return 0.0
    return float(apenas_numeros) / 100.0

def calcular_ajuste_kilometragem(preco_base, ano_carro_txt, km_total):
    ano_atual = 2026
    
    # Se na FIPE for Zero KM, tratamos o ano dele como o ano atual (2026) para fins de cálculo
    if ano_carro_txt == "Zero KM":
        ano_veiculo = ano_atual
    else:
        try:
            ano_veiculo = int(ano_carro_txt)
        except:
            ano_veiculo = ano_atual

    idade = ano_atual - ano_veiculo
    if idade <= 0:
        idade = 1
        
    km_anual_media = km_total / idade
    km_esperada_total = idade * 15000
    
    # Correção: Só é considerado "Zero KM" de fato se a quilometragem também for 0
    if ano_carro_txt == "Zero KM" and km_total == 0:
        ajuste = 0.05
        status_km = "Zero KM / Sem Uso"
        cor_status = "green"
    elif km_total == 0:
        ajuste = 0.05
        status_km = "Zero KM / Sem Uso"
        cor_status = "green"
    elif km_total > km_esperada_total * 1.3:
        excesso = (km_total - km_esperada_total) / km_esperada_total
        ajuste = max(-0.15, -0.05 - (excesso * 0.05))
        status_km = "Acima da Média (Muito Rodado)"
        cor_status = "red"
    elif km_total < km_esperada_total * 0.7:
        ajuste = 0.05
        status_km = "Abaixo da Média (Seminovo Conservado)"
        cor_status = "green"
    else:
        ajuste = 0.0
        status_km = "Dentro da Média de Uso Praticada"
        cor_status = "blue"
        
    preco_ajustado = preco_base * (1 + ajuste)
    return preco_ajustado, status_km, cor_status, km_anual_media

# Caching para evitar lentidão e requisições repetidas ao servidor da FIPE
@st.cache_data(ttl=3600)
def obter_marcas():
    try:
        res = requests.get("https://parallelum.com.br/fipe/api/v1/carros/marcas", timeout=5)
        return res.json() if res.status_code == 200 else []
    except:
        return []

@st.cache_data(ttl=1800)
def obter_modelos(marca_id):
    if not marca_id: return []
    try:
        res = requests.get(f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos", timeout=5)
        return res.json().get('modelos', []) if res.status_code == 200 else []
    except:
        return []

@st.cache_data(ttl=1800)
def obter_anos(marca_id, modelo_id):
    if not marca_id or not modelo_id: return []
    try:
        res = requests.get(f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos", timeout=5)
        return res.json() if res.status_code == 200 else []
    except:
        return []

# 2. INTERFACE DE SELEÇÃO DINÂMICA
st.sidebar.header("📋 Dados do Veículo")

marcas_lista = obter_marcas()
if marcas_lista:
    opcoes_marcas = {m['nome']: m['codigo'] for m in marcas_lista}
    marca_selecionada = st.sidebar.selectbox("1. Selecione a Marca", options=list(opcoes_marcas.keys()))
    marca_id = opcoes_marcas[marca_selecionada]
else:
    st.sidebar.error("Erro ao carregar marcas.")
    marca_id = None

modelos_lista = obter_modelos(marca_id) if marca_id else []
if modelos_lista:
    opcoes_modelos = {m['nome']: m['codigo'] for m in modelos_lista}
    modelo_selecionado = st.sidebar.selectbox("2. Selecione o Modelo", options=list(opcoes_modelos.keys()))
    modelo_id = opcoes_modelos[modelo_selecionado]
else:
    st.sidebar.warning("Aguardando marca...")
    modelo_id = None

anos_lista = obter_anos(marca_id, modelo_id) if (marca_id and modelo_id) else []
if anos_lista:
    # Remove o texto "32000" do menu visual, trocando por "Zero KM"
    opcoes_anos = {}
    for a in anos_lista:
        nome_exibicao = a['nome'].replace("32000", "Zero KM")
        opcoes_anos[nome_exibicao] = a['codigo']
        
    ano_selecionado = st.sidebar.selectbox("3. Selecione o Ano/Modelo", options=list(opcoes_anos.keys()))
    ano_id = opcoes_anos[ano_selecionado]
else:
    st.sidebar.warning("Aguardando modelo...")
    ano_id = None

km_alvo = st.sidebar.number_input("Quilometragem Atual", min_value=0, value=30000, step=1000)
botao_analisar = st.sidebar.button("📊 Analisar Mercado Competitivo")

# 3. PROCESSAMENTO E EXIBIÇÃO DO LAUDO
if botao_analisar and ano_id:
    with st.spinner('Buscando dados oficiais...'):
        try:
            url_final = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}"
            res_final = requests.get(url_final, timeout=5)
            
            if res_final.status_code == 200:
                dados = res_final.json()
                preco_base = converter_preco_fipe(dados['Valor'])
                
                # Identifica se o código bruto da FIPE é o marcador de Zero KM
                ano_cru = ano_id.split("-")[0]
                ano_efetivo_txt = "Zero KM" if ano_cru == "32000" or dados.get('AnoModelo') == 32000 else ano_cru
                
                # Executa o cálculo corrigido de Km
                preco_mediano, status_km, cor_status, km_anual = calcular_ajuste_kilometragem(preco_base, ano_efetivo_txt, km_alvo)
                
                ano_grafico = 2026 if ano_efetivo_txt == "Zero KM" else int(ano_efetivo_txt)
                df_historico = pd.DataFrame({
                    'Ano': [ano_grafico - 1, ano_grafico, ano_grafico + 1],
                    'Preço Praticado': [preco_mediano * 1.05, preco_mediano, preco_mediano * 0.94]
                })
                
                # Limpa a exibição do nome do modelo se contiver o texto do ano bizarro
                nome_modelo_limpo = dados['Modelo'].replace("32000", "Zero KM")
                st.subheader(f"🔍 {nome_modelo_limpo}")
                st.caption(f"Código FIPE: {dados['CodigoFipe']} | Mês de Referência: {dados['MesReferencia']}")
                
                if cor_status == "red":
                    st.error(f"🚨 **Diagnóstico de Quilometragem:** {status_km} (~{km_anual:,.0f} km/ano). Preço depreciado.")
                elif cor_status == "green":
                    st.success(f"💎 **Diagnóstico de Quilometragem:** {status_km}. Valorização aplicada ao preço.")
                else:
                    st.info(f"ℹ️ **Diagnóstico de Quilometragem:** {status_km} (~{km_anual:,.0f} km/ano).")

                col1, col2, col3 = st.columns(3)
                col1.metric("📉 Preço de Compra (Margem)", f"R$ {preco_mediano * 0.92:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                col2.metric("⚖️ Mediano Ajustado", f"R$ {preco_mediano:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                col3.metric("📈 Limite Máximo (Venda)", f"R$ {preco_mediano * 1.08:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                
                st.markdown("---")
                st.subheader("📊 Tendência de Valores")
                st.line_chart(data=df_historico, x='Ano', y='Preço Praticado')
            else:
                st.error("Erro ao obter dados finais da FIPE.")
        except Exception as e:
            st.error(f"Erro de processamento: {str(e)}")