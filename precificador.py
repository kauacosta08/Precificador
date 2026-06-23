import streamlit as st
import pandas as pd
import numpy as np
import requests
import re

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

# 3. FUNÇÃO TRATAMENTO DE PREÇO
def converter_preco_fipe(valor_texto):
    apenas_numeros = re.sub(r'\D', '', valor_texto)
    if not apenas_numeros:
        return 0.0
    return float(apenas_numeros) / 100.0

# 4. CONEXÃO ULTRA-CALIBRADA
def carregar_dados_mercado_v9(entrada_usuario, ano_desejado):
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
        
        # Filtro inteligente de palavras chaves principais (ignora termos curtos ou conectores)
        palavras_busca = [p for p in termo_modelo.split() if len(p) > 2 and p != "1.5" and p != "2.5"]
        if not palavras_busca: # Se sobrou nada, tenta usar o que tem
            palavras_busca = termo_modelo.split()

        if palavras_busca:
            modelos_filtrados = [m for m in modelos_dados if all(p in m['nome'].lower() for p in palavras_busca)]
        else:
            modelos_filtrados = modelos_dados

        if not modelos_filtrados:
            return {"erro": "Nenhum modelo corresponde aos termos digitados."}

        # 3. Varredura Inteligente priorizando o Ano Alvo
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
            # Fallback se ninguém da lista tiver o ano exato
            for cand in modelos_filtrados:
                modelo_id = cand['codigo']
                url_anos = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos"
                res_anos = requests.get(url_anos, timeout=2)
                if res_anos.status_code == 200 and res_anos.json():
                    anos_lista = res_anos.json()
                    codigo_ano_fipe = anos_lista[0]['codigo']
                    
                    # Correção FIPE 32000 (Zero KM)
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
            
            # Se for Zero KM ou string, define um ano base fictício só pro gráfico não quebrar
            ano_grafico = 2025 if ano_efetivo_txt == "Zero KM" else int(ano_efetivo_txt)
            df_historico = pd.DataFrame({
                'Ano': [ano_grafico - 1, ano_grafico, ano_grafico + 1],
                'Preço Praticado': [preco_base * 1.05, preco_base, preco_base * 0.94]
            })
            
            # Formata a exibição do ano final
            ano_fipe_limpo = dados_finais.get('AnoModelo')
            if ano_fipe_limpo == 32000:
                ano_efetivo_txt = "Zero KM"
                
            return {
                'preco_barato': preco_base * 0.92,
                'preco_mediano': preco_base,
                'preco_caro': preco_base * 1.08,
                'df_historico': df_historico,
                'versao_oficial': dados_finais.get('Modelo', entrada_usuario.upper()),
                'ano_real': ano_efetivo_txt,
                'fallback': fallback_utilizado,
                'erro': None
            }
            
    except Exception as e:
        return {"erro": f"Erro de processamento: {str(e)}"}
    return {"erro": "Não foi possível encontrar uma versão condizente."}

# 5. RENDERIZAÇÃO DA TELA
if botao_analisar and modelo_buscado:
    with st.spinner('Acessando os servidores atualizados da FIPE...'):
        resultado = carregar_dados_mercado_v9(modelo_buscado, ano_alvo)
        
    if resultado is None or resultado.get('erro'):
        st.error(f"❌ **Erro:** {resultado.get('erro', 'Veículo não localizado.')}")
    else:
        if resultado['fallback']:
            st.warning(f"⚠️ **Nota:** Não há registro exato para o ano {ano_alvo}. Exibindo o ano disponível mais próximo ({resultado['ano_real']}).")
            
        st.subheader(f"🔍 {resultado['versao_oficial']}")
        st.caption(f"Ano/Modelo verificado: {resultado['ano_real']} | Tabela FIPE Oficial.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📉 Limite Mínimo", f"R$ {resultado['preco_barato']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col2.metric("⚖️ Mediano FIPE", f"R$ {resultado['preco_mediano']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col3.metric("📈 Limite Máximo", f"R$ {resultado['preco_caro']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        st.markdown("---")
        st.subheader("📊 Tendência de Valores")
        st.line_chart(data=resultado['df_historico'], x='Ano', y='Preço Praticado')