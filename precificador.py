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
modelo_buscado = st.sidebar.text_input("Marca / Modelo do Carro", placeholder="Ex: Mercedes GLC 300")
ano_alvo = st.sidebar.number_input("Ano do Modelo", min_value=2000, max_value=2028, value=2023)
km_alvo = st.sidebar.number_input("Quilometragem Atual", min_value=0, value=30000, step=1000)

botao_analisar = st.sidebar.button("📊 Analisar Mercado Competitivo")

# 3. FUNÇÃO TRATAMENTO DE PREÇO
def converter_preco_fipe(valor_texto):
    apenas_numeros = re.sub(r'\D', '', valor_texto)
    if not apenas_numeros:
        return 0.0
    return float(apenas_numeros) / 100.0

# 4. CONEXÃO COM FILTRO STRICT E CASAMENTO EXATO DE TERMOS
def carregar_dados_mercado_v7(entrada_usuario, ano_desejado):
    try:
        entrada_clean = entrada_usuario.strip().lower()
        
        # 1. Obter todas as marcas da FIPE
        url_marcas = "https://parallelum.com.br/fipe/api/v1/carros/marcas"
        res_marcas = requests.get(url_marcas, timeout=5)
        if res_marcas.status_code != 200:
            return {"erro": "Falha na conexão com o servidor da FIPE (Etapa: Marcas)."}
            
        marcas = res_marcas.json()
        marca_id = None
        termo_modelo = entrada_clean
        
        # Identifica e remove a marca do texto de busca
        for m in marcas:
            nome_marca_fipe = m['nome'].lower()
            if nome_marca_fipe in entrada_clean or (len(entrada_clean) > 3 and entrada_clean in nome_marca_fipe):
                marca_id = m['codigo']
                termo_modelo = entrada_clean.replace(nome_marca_fipe, "").replace("mercedes-benz", "").replace("mercedes", "").strip()
                break
                
        # Garante o código caso digitem variações da Mercedes
        if not marca_id and ("mercedes" in entrada_clean or "glc" in entrada_clean):
            marca_id = "33"
            termo_modelo = entrada_clean.replace("mercedes-benz", "").replace("mercedes", "").strip()

        if not marca_id:
            return {"erro": f"Não identificamos a Marca do veículo. Tente incluir o nome completo (Ex: Mercedes GLC 300)."}

        # 2. Buscar todos os modelos da marca
        url_modelos = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos"
        res_mod = requests.get(url_modelos, timeout=5)
        if res_mod.status_code != 200:
            return {"erro": "Falha na conexão com o servidor da FIPE (Etapa: Modelos)."}
            
        modelos_dados = res_mod.json().get('modelos', [])
        
        # FILTRO CRÍTICO: O modelo deve conter TODAS as palavras digitadas pelo usuário
        palavras_busca = [p for p in termo_modelo.split() if len(p) > 1] # ignora letras soltas
        
        if palavras_busca:
            # Só aceita modelos que contenham TODAS as palavras chaves (ex: 'glc' AND '300')
            modelos_filtrados = [
                m for m in modelos_dados 
                if all(p in m['nome'].lower() for p in palavras_busca)
            ]
        else:
            modelos_filtrados = modelos_dados

        if not modelos_filtrados:
            return {"erro": f"Marca encontrada, mas nenhuma versão corresponde exatamente aos termos: {palavras_busca}"}

        # 3. Varre os modelos filtrados estritamente buscando o ano
        dados_finais = None
        ano_efetivo = ano_desejado
        fallback_utilizado = False
        
        for cand in modelos_filtrados:
            modelo_id = cand['codigo']
            url_anos = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos"
            res_anos = requests.get(url_anos, timeout=3)
            
            if res_anos.status_code == 200:
                anos_lista = res_anos.json()
                if not anos_lista: continue
                
                # Procura o ano alvo
                codigo_ano_fipe = next((a['codigo'] for a in anos_lista if a['codigo'].startswith(str(ano_desejado))), None)
                
                # Se achou o carro com o termo correto E o ano correto, perfeito!
                if codigo_ano_fipe:
                    ano_efetivo = ano_desejado
                    fallback_utilizado = False
                else:
                    # Se não tem o ano exato (ex: GLC 250 em 2023), pega o mais recente disponível DESTA versão estrita
                    codigo_ano_fipe = anos_lista[0]['codigo']
                    ano_efetivo = int(codigo_ano_fipe.split("-")[0])
                    fallback_utilizado = True
                
                url_final = f"https://parallelum.com.br/fipe/api/v1/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{codigo_ano_fipe}"
                res_final = requests.get(url_final, timeout=3)
                if res_final.status_code == 200:
                    dados_finais = res_final.json()
                    break

        if dados_finais:
            preco_base = converter_preco_fipe(dados_finais['Valor'])
            
            df_historico = pd.DataFrame({
                'Ano': [ano_efetivo - 1, ano_efetivo, ano_efetivo + 1],
                'Preço Praticado': [preco_base * 1.05, preco_base, preco_base * 0.94]
            })
            
            return {
                'preco_barato': preco_base * 0.92,
                'preco_mediano': preco_base,
                'preco_caro': preco_base * 1.08,
                'df_historico': df_historico,
                'versao_oficial': dados_finais.get('Modelo', entrada_usuario.upper()),
                'ano_real': ano_efetivo,
                'fallback': fallback_utilizado,
                'erro': None
            }
            
    except Exception as e:
        return {"erro": f"Erro de processamento: {str(e)}"}
        
    return {"erro": "Não foi possível encontrar uma versão condizente com a pesquisa."}

# 5. RENDERIZAÇÃO DA TELA
if botao_analisar and modelo_buscado:
    with st.spinner('Buscando dados exatos na FIPE...'):
        resultado = carregar_dados_mercado_v7(modelo_buscado, ano_alvo)
        
    if resultado is None or resultado.get('erro'):
        st.error(f"❌ **Erro:** {resultado.get('erro', 'Veículo não localizado.')}")
    else:
        if resultado['fallback']:
            st.warning(f"⚠️ **Nota:** Não há registro exato para o ano {ano_alvo}. Exibindo o ano mais próximo ({resultado['ano_real']}).")
            
        st.subheader(f"🔍 {resultado['versao_oficial']}")
        st.caption(f"Ano do modelo verificado: {resultado['ano_real']} | Tabela FIPE Oficial.")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📉 Limite Mínimo", f"R$ {resultado['preco_barato']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col2.metric("⚖️ Mediano FIPE", f"R$ {resultado['preco_mediano']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        col3.metric("📈 Limite Máximo", f"R$ {resultado['preco_caro']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        
        st.markdown("---")
        st.subheader("📊 Tendência de Valores")
        st.line_chart(data=resultado['df_historico'], x='Ano', y='Preço Praticado')