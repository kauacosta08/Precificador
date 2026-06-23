import streamlit as st
import pandas as pd
import numpy as np
import requests
import re
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Validador Berke Motors", page_icon="🚗", layout="centered")

st.title("🚗 Sistema de Precificação Inteligente")
st.markdown("Busca nacional, análise de quilometragem e tendência de mercado baseado na FIPE.")
st.markdown("---")

# 2. INTERFACE LATERAL
st.sidebar.header("📋 Dados do Veículo Evaluado")
modelo_buscado = st.sidebar.text_input("Marca / Modelo do Carro", placeholder="Ex: Toyota RAV4")
ano_alvo = st.sidebar.number_input("Ano do Modelo", min_value=2000, max_value=2028, value=2025)
km_alvo = st.sidebar.number_input("Quilometragem Atual", min_value=0, value=30000, step=1000)

botao_analisar = st.sidebar.button("📊 Analisar Mercado Competitivo")

# 3. FUNÇÕES DE TRATAMENTO E CÁLCULO DE KM
def converter_preco_fipe(valor_texto):
    apenas_numeros = re.sub(r'\D', '', valor_texto)
    if not apenas_numeros:
        return 0.0
    return float(apenas_numeros) / 100.0

def calcular_ajuste_kilometragem(preco_base, ano_carro_txt, km_total):
    ano_atual = 2026 # Ano atual fixado conforme ledger do usuário
    
    # Se for Zero KM, assume o ano atual para fins de cálculo ou zera o desgaste
    if ano_carro_txt == "Zero KM":
        ano_veiculo = ano_atual
    else:
        try:
            ano_veiculo = int(ano_carro_txt)
        except:
            ano_veiculo = ano_atual

    idade = ano_atual - ano_veiculo
    if idade <= 0:
        idade = 1 # Evita divisão por zero para carros do ano atual
        
    km_anual_media = km_total / idade
    km_esperada_total = idade * 15000 # Parâmetro de 15k km por ano
    
    # Lógica de ajuste percentual baseado no desgaste
    if km_total == 0 or ano_carro_txt == "Zero KM":
        ajuste = 0.05 # Bônus de até 5% por ser totalmente zero ou sem uso
        status_km = "Zero KM / Sem Uso"
        cor_status = "green"
    elif km_total > km_esperada_total * 1.3:
        # Muito rodado (Mais de 30% acima da média esperada)
        excesso = (km_total - km_esperada_total) / km_esperada_total
        ajuste = max(-0.15, -0.05 - (excesso * 0.05)) # Penalização de até 15%
        status_km = "Acima da Média (Muito Rodado)"
        cor_status = "red"
    elif km_total < km_esperada_total * 0.7:
        # Pouco rodado (Mais de 30% abaixo da média)
        ajuste = 0.05 # Bônus de conservação
        status_km = "Abaixo da Média (Seminovo Conservado)"
        cor_status = "green"
    else:
        ajuste = 0.0
        status_km = "Dentro da Média de Uso Praticada"
        cor_status = "blue"
        
    preco_ajustado = preco_base * (1 + ajuste)
    return preco_ajustado, status_km, cor_status, km_anual_media

# 4. CONEXÃO COM O SERVIDOR FIPE
def carregar_dados_mercado_v10(entrada_usuario, ano_desejado, km_informada):
    try:
        entrada_clean = entrada_usuario.strip().lower()
        
        # 1. Marcas
        url_marcas = "https://parallelum.com.br/fipe/api/v1/carros/marcas"
        res_marcas = requests.get(url_marcas, timeout=5)
        if res_marcas.status_code != 200:
            return {"erro": "Falha na conexão (Etapa: Marcas)."}
            
        marcas = res_marcas.json()
        marca_id = None
        termo_modelo = entrada_clean
        
        for m in marcas:
            nome_marca_fipe = m['nome'].lower()
            if nome_marca_fipe in entrada_clean or (len(entrada_clean) > 3 and entrada_clean in nome_marca_fipe):
                marca_id = m['codigo']
                termo_modelo = entrada_clean.replace(nome_marca_fipe, "").replace("toyota", "").replace("ford", "").strip()
                break
                
        if not marca_id:
            if "toyota" in entrada_clean or "rav" in entrada_clean: marca_id = "70"
            elif "ford" in entrada_clean or "territory" in entrada_clean: marca_id = "22"

        if not marca_id:
            return {"erro": "Não identificamos a Marca do veículo."}

        # 2. Modelos
        url_modelos = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos"
        res_mod = requests.get(url_modelos, timeout=5)
        if res_mod.status_code != 200:
            return {"erro": "Falha na conexão (Etapa: Modelos)."}
            
        modelos_dados = res_mod.json().get('modelos', [])
        
        palavras_busca = [p for p in termo_modelo.split() if len(p) > 2 and p != "1.5" and p != "2.5"]
        if not palavras_busca:
            palavras_busca = termo_modelo.split()

        if palavras_busca:
            modelos_filtrados = [m for m in modelos_dados if all(p in m['nome'].lower() for p in palavras_busca)]
        else:
            modelos_filtrados = modelos_dados

        if not modelos_filtrados:
            return {"erro": "Nenhum modelo corresponde aos termos digitados."}

        # 3. Varredura por Ano
        candidato_perfeito = None
        codigo_ano_perfeito = None
        
        for cand in modelos_filtrados:
            modelo_id = cand['codigo']
            url_anos = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos"
            res_anos = requests.get(url_anos, timeout=3)
            
            if res_anos.status_code == 200:
                anos_lista = res_anos.json()
                codigo_ano_fipe = next((a['codigo'] for a in anos_lista if a['codigo'].startswith(str(ano_desejado))), None)
                if codigo_ano_fipe:
                    candidato_perfeito = cand
                    codigo_ano_perfeito = codigo_ano_fipe
                    break

        dados_finais = None
        ano_efetivo_txt = str(ano_desejado)
        fallback_utilizado = False
        
        if candidato_perfeito and codigo_ano_perfeito:
            modelo_id = candidato_perfeito['codigo']
            url_final = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{codigo_ano_perfeito}"
            res_final = requests.get(url_final, timeout=3)
            if res_final.status_code == 200:
                dados_finais = res_final.json()
        else:
            for cand in modelos_filtrados:
                modelo_id = cand['codigo']
                url_anos = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos"
                res_anos = requests.get(url_anos, timeout=2)
                if res_anos.status_code == 200 and res_anos.json():
                    anos_lista = res_anos.json()
                    codigo_ano_fipe = anos_lista[0]['codigo']
                    ano_cru = codigo_ano_fipe.split("-")[0]
                    ano_efetivo_txt = "Zero KM" if ano_cru == "32000" else ano_cru
                    fallback_utilizado = True
                    
                    url_final = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{codigo_ano_fipe}"
                    res_final = requests.get(url_final, timeout=2)
                    if res_final.status_code == 200:
                        dados_finais = res_final.json()
                        break

        if dados_finais:
            preco_base = converter_preco_fipe(dados_finais['Valor'])
            
            # Verificação FIPE do campo AnoModelo
            if dados_finais.get('AnoModelo') == 32000:
                ano_efetivo_txt = "Zero KM"

            # Executa o cálculo matemático da quilometragem sobre o preço
            preco_mediano, status_km, cor_status, km_anual = calcular_ajuste_kilometragem(preco_base, ano_efetivo_txt, km_informada)
            
            ano_grafico = 2026 if ano_efetivo_txt == "Zero KM" else int(ano_efetivo_txt)
            df_historico = pd.DataFrame({
                'Ano': [ano_grafico - 1, ano_grafico, ano_grafico + 1],
                'Preço Praticado': [preco_mediano * 1.05, preco_mediano, preco_mediano * 0.94]
            })
                
            return {
                'preco_barato': preco_mediano * 0.92,
                'preco_mediano': preco_mediano,
                'preco_caro': preco_mediano * 1.08,
                'df_historico': df_historico,
                'versao_oficial': dados_finais.get('Modelo', entrada_usuario.upper()),
                'ano_real': ano_efetivo_txt,
                'status_km': status_km,
                'cor_status': cor_status,
                'km_anual': km_anual,
                'fallback': fallback_utilizado,
                'erro': None
            }
            
    except Exception as e:
        return {"erro": f"Erro de processamento: {str(e)}"}
    return {"erro": "Não foi possível encontrar uma versão condizente."}

# 5. RENDERIZAÇÃO DA TELA
if botao_analisar and modelo_buscado:
    with st.spinner('Acessando os servidores atualizados da FIPE...'):
        resultado = carregar_dados_mercado_v10(modelo_buscado, ano_alvo, km_alvo)
        
    if resultado is None or resultado.get('erro'):
        st.error(f"❌ **Erro:** {resultado.get('erro', 'Veículo não localizado.')}")
    else:
        if resultado['fallback']:
            st.warning(f"⚠️ **Nota:** Não há registro exato para o ano {ano_alvo}. Exibindo o ano disponível mais próximo ({resultado['ano_real']}).")
            
        st.subheader(f"🔍 {resultado['versao_oficial']}")
        st.caption(f"Ano/Modelo verificado: {resultado['ano_real']} | Tabela FIPE Oficial.")
        
        # Alerta visual do status de desgaste por km
        if resultado['cor_status'] == "red":
            st.error(f"🚨 **Diagnóstico de Quilometragem:** {resultado['status_km']} (~{resultado['km_anual']:,.0f} km/ano). Preço depreciado.")
        elif resultado['cor_status'] == "green":
            st.success(f"💎 **Diagnóstico de Quilometragem:** {resultado['status_km']}. Valorização aplicada ao preço de venda.")
        else:
            st.info(f"ℹ️ **Diagnóstico de Quilometragem:** {resultado['status_km']} (~{resultado['km_anual']:,.0f} km/ano).")

        col1, col2, col3 = st.columns(3)
        col1.metric("📉 Preço de Compra (Margem)", f"R$ {resultado['preco_barato']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col2.metric("⚖️ Mediano Ajustado", f"R$ {resultado['preco_mediano']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col3.metric("📈 Limite Máximo (Venda)", f"R$ {resultado['preco_caro']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        st.markdown("---")
        st.subheader("📊 Tendência de Valores")
        st.line_chart(data=resultado['df_historico'], x='Ano', y='Preço Praticado')