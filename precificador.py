import streamlit as st
import pandas as pd
import requests
import re

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Validador Berke Motors", page_icon="🚗", layout="centered")

# CONTROLE DE TEMA (DARK / LIGHT MODE VIA CSS DINÂMICO)
st.sidebar.markdown("### 🎨 Aparência")
tema = st.sidebar.radio("Escolha o Modo de Visualização:", ["Dark Mode", "Light Mode"], label_visibility="collapsed")

# ADICIONANDO A LOGO DA BERKE MOTORS VIA URL LOGO ABAIXO DO SELETOR
st.sidebar.markdown("---") # Linha divisória discreta
url_logo = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSJMNw1kip4K6iiXA8nrfHPkAJcQsNtk0Elvw&s"
try:
    st.sidebar.image(url_logo, use_container_width=True)
except:
    st.sidebar.caption("⚠️ Erro ao carregar a logo a partir da URL.")

# DEFINIÇÃO DE CORES DINÂMICAS DE ACORDO COM O TEMA
cor_primaria = "#FF4B4B" if tema == "Dark Mode" else "#0066CC"
cor_card_bg = "#1E2229" if tema == "Dark Mode" else "#F0F2F6"
cor_texto = "#FAFAFA" if tema == "Dark Mode" else "#31333F"
cor_mediano_num = "#FFFFFF" if tema == "Dark Mode" else "#31333F"

# ESTILIZAÇÃO CSS AVANÇADA
st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {"#0E1117" if tema == "Dark Mode" else "#FFFFFF"};
        color: {cor_texto};
    }}
    /* Efeito hover nas caixas de seleção/input */
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{
        background-color: {cor_card_bg} !important;
        color: {cor_texto} !important;
        border: 1px solid {"#2d3139" if tema == "Dark Mode" else "#e2e4e9"} !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important;
    }}
    div[data-baseweb="select"] > div:hover, div[data-baseweb="input"] > div:hover {{
        transform: scale(1.01);
        border-color: {cor_primaria} !important;
        box-shadow: 0px 4px 15px { "rgba(255, 75, 75, 0.2)" if tema == "Dark Mode" else "rgba(0, 102, 204, 0.15)" } !important;
    }}
    input {{
        color: {cor_texto} !important;
    }}
    /* Efeito hover no botão principal */
    button[data-testid="stBaseButton-primary"] {{
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }}
    button[data-testid="stBaseButton-primary"]:hover {{
        transform: scale(1.005);
        box-shadow: 0px 5px 20px { "rgba(255, 75, 75, 0.4)" if tema == "Dark Mode" else "rgba(0, 102, 204, 0.3)" } !important;
    }}
    /* Estilização dos Cards customizados de Preço */
    .card-preco {{
        background-color: {cor_card_bg};
        padding: 22px 15px;
        border-radius: 12px;
        text-align: center;
        border-left: 6px solid #ccc;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
        margin-bottom: 15px;
    }}
    
    @media print {{
        .stSidebar, div[data-testid="stSidebarCollapseButton"], button {{
            display: none !important;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# TÍTULO PRINCIPAL EM MAIÚSCULO
st.title("🚗 SISTEMA DE PRECIFICAÇÃO INTELIGENTE")
st.markdown("Busca ultra-rápida, dados oficiais em tempo real e cálculo contínuo de quilometragem.")
st.markdown("---")

# Funções auxiliares de preço e KM
def formatar_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def converter_preco_fipe(valor_texto):
    apenas_numeros = re.sub(r'\D', '', valor_texto)
    if not apenas_numeros:
        return 0.0
    return float(apenas_numeros) / 100.0

def calcular_ajuste_kilometragem_continuo(preco_base, ano_carro_txt, km_total):
    ano_atual = 2026
    
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
    km_esperada_total = min(250000, idade * 15000)
    
    if km_total == 0:
        ajuste = 0.10
        status_km = "Zero KM / Sem Uso (Estado de Fábrica)"
        cor_status = "green"
    else:
        desvio = km_total / km_esperada_total
        
        if desvio < 1.0:
            ajuste = (1.0 - desvio) * 0.07
            status_km = f"Abaixo da Média de Uso (~{km_anual_media:,.0f} km/ano)"
            cor_status = "green"
        elif desvio > 1.0:
            ajuste = max(-0.20, (1.0 - desvio) * 0.08)
            status_km = f"Acima da Média de Uso (~{km_anual_media:,.0f} km/ano)"
            cor_status = "red"
        else:
            ajuste = 0.0
            status_km = "Exatamente na Média de Uso do Mercado"
            cor_status = "blue"
        
    preco_ajustado = preco_base * (1 + ajuste)
    return preco_ajustado, status_km, cor_status, km_anual_media

# Funções de API com cache
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

# 2. INTERFACE CENTRALIZADA
st.subheader("📋 Preencha os Dados do Veículo")

col_esquerda, col_direita = st.columns(2)

with col_esquerda:
    marcas_lista = obter_marcas()
    if marcas_lista:
        opcoes_marcas = {m['nome']: m['codigo'] for m in marcas_lista}
        marca_selecionada = st.selectbox("1. Marca", options=list(opcoes_marcas.keys()))
        marca_id = opcoes_marcas[marca_selecionada]
    else:
        st.error("Erro ao carregar marcas.")
        marca_id = None

    modelos_lista = obter_modelos(marca_id) if marca_id else []
    if modelos_lista:
        opcoes_modelos = {m['nome']: m['codigo'] for m in modelos_lista}
        modelo_selecionado = st.selectbox("2. Modelo", options=list(opcoes_modelos.keys()))
        modelo_id = opcoes_modelos[modelo_selecionado]
    else:
        st.warning("Aguardando seleção da marca...")
        modelo_id = None

with col_direita:
    anos_lista = obter_anos(marca_id, modelo_id) if (marca_id and modelo_id) else []
    if anos_lista:
        opcoes_anos = {}
        for a in anos_lista:
            nome_exibicao = a['nome'].replace("32000", "Zero KM")
            opcoes_anos[nome_exibicao] = a['codigo']
            
        ano_selecionado = st.selectbox("3. Ano / Modelo", options=list(opcoes_anos.keys()))
        ano_id = opcoes_anos[ano_selecionado]
    else:
        st.warning("Aguardando seleção do modelo...")
        ano_id = None

    km_alvo = st.number_input("4. Quilometragem Atual", min_value=0, value=30000, step=1000)

st.markdown(" ")
botao_analisar = st.button("📊 ANALISAR MERCADO COMPETITIVO", use_container_width=True, type="primary")
st.markdown("---")

# 3. PROCESSAMENTO E EXIBIÇÃO DO LAUDO
if botao_analisar and ano_id:
    with st.spinner('Processando laudo de precificação...'):
        try:
            url_final = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}"
            res_final = requests.get(url_final, timeout=5)
            
            if res_final.status_code == 200:
                dados = res_final.json()
                preco_base = converter_preco_fipe(dados['Valor'])
                
                ano_cru = ano_id.split("-")[0]
                ano_efetivo_txt = "Zero KM" if ano_cru == "32000" or dados.get('AnoModelo') == 32000 else ano_cru
                
                preco_mediano, status_km, cor_status, km_anual = calcular_ajuste_kilometragem_continuo(preco_base, ano_efetivo_txt, km_alvo)
                
                ano_grafico = 2026 if ano_efetivo_txt == "Zero KM" else int(ano_efetivo_txt)
                df_historico = pd.DataFrame({
                    'Ano': [ano_grafico - 1, ano_grafico, ano_grafico + 1],
                    'Preço Praticado': [preco_mediano * 1.05, preco_mediano, preco_mediano * 0.94]
                })
                
                nome_modelo_limpo = dados['Modelo'].replace("32000", "Zero KM")
                st.subheader(f"🔍 {nome_modelo_limpo}")
                st.caption(f"Código FIPE: {dados['CodigoFipe']} | Mês de Referência: {dados['MesReferencia']}")
                
                if cor_status == "red":
                    st.error(f"🚨 **Diagnóstico de Quilometragem:** {status_km}. Veículo acima da média de uso esperada. Depreciação aplicada.")
                elif cor_status == "green":
                    st.success(f"💎 **Diagnóstico de Quilometragem:** {status_km}. Excelente nível de conservação. Valorização aplicada.")
                else:
                    st.info(f"ℹ️ **Diagnóstico de Quilometragem:** {status_km}.")

                # CARDS VISUAIS DE PREÇO AMPLIADOS E CORRIGIDOS
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"""
                    <div class='card-preco' style='border-left-color: #e74c3c;'>
                        <span style='font-size: 0.95em; opacity: 0.85; font-weight: bold;'>📉 Compra (Margem)</span><br>
                        <strong style='font-size: 1.5em; color: {"#ff6b6b" if tema == "Dark Mode" else "#c0392b"};'>{formatar_brl(preco_mediano * 0.92)}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with col2:
                    st.markdown(f"""
                    <div class='card-preco' style='border-left-color: #9b59b6;'>
                        <span style='font-size: 0.95em; opacity: 0.85; font-weight: bold;'>⚖️ Mediano Ajustado</span><br>
                        <strong style='font-size: 1.7em; color: {cor_mediano_num};'>{formatar_brl(preco_mediano)}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with col3:
                    st.markdown(f"""
                    <div class='card-preco' style='border-left-color: #2ecc71;'>
                        <span style='font-size: 0.95em; opacity: 0.85; font-weight: bold;'>📈 Venda (Teto)</span><br>
                        <strong style='font-size: 1.5em; color: {"#2ecc71" if tema == "Dark Mode" else "#27ae60"};'>{formatar_brl(preco_mediano * 1.08)}</strong>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                st.subheader("📊 Tendência de Valores")
                st.line_chart(data=df_historico, x='Ano', y='Preço Praticado')
                
                # BOTÃO DE IMPRESSÃO
                st.markdown("<br>", unsafe_allow_html=True)
                st.button("🖨️ Imprimir Laudo / Salvar PDF", on_click=None, use_container_width=True)
                st.components.v1.html(
                    """
                    <script>
                    const botando = window.parent.document.querySelectorAll('button');
                    botando.forEach(button => {
                        if (button.innerText.includes('Imprimir Laudo')) {
                            button.onclick = function() { window.parent.print(); }
                        }
                    });
                    </script>
                    """, height=0
                )
            else:
                st.error("Erro ao obter dados finais da FIPE.")
        except Exception as e:
            st.error(f"Erro de processamento: {str(e)}")

# VERSÃO DO APP NO RODAPÉ
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.caption("<div style='text-align: right; color: #bfbfbf; font-size: 0.8em;'>v2.4</div>", unsafe_allow_html=True)