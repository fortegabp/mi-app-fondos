import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests

# 1. Configuración de la página web
st.set_page_config(page_title="Asesor IA Premium - Banca Privada", page_icon="🏛️", layout="wide")
st.title("🏛️ Asesor IA Premium - Quality Funds")

with st.sidebar:
    st.header("🔑 Configuración")
    api_key = st.text_input("Gemini API Key:", type="password")
    sheet_url = st.text_input("Google Sheets Link:")

if not api_key or not sheet_url:
    st.info("👈 Introduce las llaves en el menú lateral para operar.")
    st.stop()

@st.cache_data(ttl=600)
def cargar_datos(url):
    if "edit" in url:
        url = url.split("/edit")[0] + "/export?format=csv"
    # Forzamos punto y coma como separador profesional
    return pd.read_csv(url, sep=";") 

try:
    df_fondos = cargar_datos(sheet_url)
    st.sidebar.success(f"✅ Universo QF: {len(df_fondos)} fondos.")
except Exception as e:
    st.sidebar.error(f"❌ Error de conexión con Google Sheets: {e}")
    st.stop()

genai.configure(api_key=api_key)
modelo = genai.GenerativeModel('gemini-3-flash-preview')

tab1, tab2, tab3 = st.tabs(["💬 Asesor Patrimonial", "📥 Ingesta Masiva QF", "🏗️ Auditoría de Campos"])

# ==========================================
# PESTAÑA 1: ASESOR CFA/EFP
# ==========================================
with tab1:
    contexto = df_fondos.to_string(index=False)
    prompt_maestro = f"""
    Eres un Senior Wealth Manager con certificación CFA y EFP. 
    Tu fuente de verdad es este catálogo de Quality Funds:
    {contexto}
    
    INSTRUCCIONES:
    1. Analiza el riesgo-retorno (Sharpe, Alpha, Drawdown) antes de recomendar.
    2. Si el cliente es conservador, vigila la 'Duración' y el 'Max Drawdown'.
    3. Si el cliente busca impacto, prioriza fondos 'Artículo 9'.
    4. Cita SIEMPRE ISIN y comisiones.
    """
    
    if "chat" not in st.session_state:
        st.session_state.chat =[]
        
    for m in st.session_state.chat:
        with st.chat_message(m["r"]):
            st.markdown(m["t"])

    if q := st.chat_input("Perfil del cliente o consulta técnica..."):
        with st.chat_message("user"):
            st.markdown(q)
        st.session_state.chat.append({"r": "user", "t": q})
        
        with st.chat_message("assistant"):
            with st.spinner("Analizando fondos..."):
                try:
                    r = modelo.generate_content(prompt_maestro + "\n\nPregunta: " + q)
                    st.markdown(r.text)
                    st.session_state.chat.append({"r": "assistant", "t": r.text})
                except Exception as e:
                    st.error(f"Error IA: {e}")

# ==========================================
# PESTAÑA 2: EXTRACTOR PREMIUM (CFA ARCHITECTURE)
# ==========================================
with tab2:
    st.markdown("### 📥 Extractor de Datos de Alta Calidad (Golden Record)")
    st.markdown("Extrae y mapea semánticamente los datos en crudo para insertarlos en Google Sheets.")
    isins_input = st.text_area("Lista de ISINs (uno por línea):", height=150)
    
    if st.button("Generar Tabla Openfunds", type="primary"):
        res_list =[]
        progress = st.progress(0)
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        if isins_input.strip():
            isins =[i.strip() for i in isins_input.split('\n') if i.strip()]
            
            for idx, isin in enumerate(isins):
                url = f"https://www.fundinfo.com/es/ES-priv/fund/Data?&OFST020000={isin}"
                try:
                    res = requests.get(url, headers=headers, timeout=10)
                    datos_json = res.text
                    
                    prompt_extraccion = f"""Eres un Arquitecto de Datos y Wealth Manager (CFA). Tu tarea es procesar el siguiente texto/JSON en crudo de un fondo de inversión y convertirlo a nuestro "Golden Record" de 38 columnas.

REGLAS DE ARQUITECTURA DE DATOS (OBLIGATORIAS E INQUEBRANTABLES):

1. MAPEO SEMÁNTICO (CERO NULOS LITERALES): El JSON no usa las etiquetas literales de Openfunds. Deduce el campo por su significado financiero. Solo usa 'N/A' si el dato es absoluta y matemáticamente inexistente. NUNCA devuelvas la palabra 'null'.
2. SÍNTESIS CUALITATIVA (ANTI-RUIDO LEGAL): Si encuentras textos legales largos (como el objetivo de inversión 'OFEP040400'), NO LO COPIES literalmente. Sintetízalo en una sola frase de máximo 15 palabras para la columna [OFST010300] Filosofia de Inversion (ej. "Renta Variable Global orientada a Growth, ESG Art.8"). Descarta textos de advertencia legal ('OFEP040300').
3. FORMATEO MATEMÁTICO (ESTÁNDAR ESPAÑA): Todo dato de rentabilidad, volatilidad, coste o ratio que venga en decimal (ej. 0.1412) DEBE ser convertido a porcentaje con formato español (ej. 14,12%). 
4. FORMATO DE SALIDA (CSV PLANO): Devuelve UNA ÚNICA LÍNEA de texto. Cada campo separado EXCLUSIVAMENTE por punto y coma (;).
5. ORDEN ESTRICTO DE LAS 38 COLUMNAS (Respétalo rigurosamente):
[OFST020000] ISIN;[OFST010110] Nombre del Fondo;[OFST001020] Gestora;[OFST010410] Divisa Base;[OFST020400] Politica Distribucion;[OFST350100] Categoria EFAMA;[OFST010230] Hedge Fund Strategy;[OFST023200] Benchmark;[OFEP010900] Riesgo (SRI 1-7);[OFEP060200] Volatilidad Anualizada 3A;Sharpe 3A;Alpha 3A;Beta 3A;Tracking Error 3A;Max Drawdown;Rentabilidad YTD %;Rentabilidad 1 Anio %;Rentabilidad 3 Anios %;Rentabilidad 5 Anios %;Cuartil 3A;[OFRE000520] Geografias Top 3;[OFRE000560] Sectores Top 3;[OFRE000500] Top 10 Posiciones;[OFPH000465] Modified Duration;[OFPH000485] Yield to Maturity;[OFEE200400] Articulo SFDR;[OFEE201000] Considera PAI;[OFST820110] Carbon Intensity Scope 1&2;[OFST452200] Gastos Corrientes (TER %);[OFST451028] Comision Exito %;[OFST451305] Comision Entrada %;[OFST020300] Liquidez;[OFST410700] Liquidacion (Dias);[OFST400230] Minima Inversion Inicial;[OFST020600] Is RDR Compliant;[OFST010300] Filosofia de Inversion;Sesgo del Gestor;Comentario Quality Funds

TEXTO/JSON EN CRUDO A PROCESAR:
{datos_json}

INSTRUCCIÓN FINAL: Genera ÚNICAMENTE la fila separada por punto y coma. Sin viñetas, sin comillas extra y sin bloques de código ```csv.
"""
                    # Ejecución del motor IA
                    respuesta = modelo.generate_content(prompt_extraccion)
                    
                    # Sanitización del output (eliminar saltos de línea internos y bloques markdown)
                    row_clean = respuesta.text.replace("```csv", "").replace("```", "").replace("\n", " ").strip()
                    res_list.append(row_clean)
                    
                except Exception as e:
                    res_list.append(f"{isin};Error en conexión o IA: {e};" + ";" * 36)
                
                progress.progress((idx + 1) / len(isins))
            
            st.success("Extracción y mapeo completados con éxito.")
            st.subheader("📋 Tabla lista para copiar a Google Sheets")
            # Mostramos el resultado como código CSV
            st.code("\n".join(res_list), language="text")

# ==========================================
# PESTAÑA 3: ARQUITECTURA (ANÁLISIS PROFUNDO)
# ==========================================
with tab3:
    st.subheader("Buscador de Campos en Crudo (Fundinfo)")
    st.markdown("Introduce un ISIN para ver **absolutamente todos** los datos que devuelve la API.")
    
    isin_test = st.text_input("ISIN a investigar:", "LU1213836080")
    
    if st.button("Analizar Estructura del Fondo"):
        url_test = f"https://www.fundinfo.com/es/ES-priv/fund/Data?&OFST020000={isin_test}"
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            respuesta = requests.get(url_test, headers=headers)
            json_data = respuesta.json()
            
            def aplanar_diccionario(d, parent_key='', sep='_'):
                items =[]
                if isinstance(d, list):
                    for i, v in enumerate(d):
                        items.extend(aplanar_diccionario(v, f"{parent_key}[{i}]", sep=sep).items())
                elif isinstance(d, dict):
                    for k, v in d.items():
                        new_key = f"{parent_key}{sep}{k}" if parent_key else k
                        if isinstance(v, dict) or isinstance(v, list):
                            items.extend(aplanar_diccionario(v, new_key, sep=sep).items())
                        else:
                            items.append((new_key, str(v)))
                return dict(items)

            datos_planos = aplanar_diccionario(json_data)
            
            df_analisis = pd.DataFrame({
                "Nombre del Campo (Key)": list(datos_planos.keys()),
                "Valor devuelto": list(datos_planos.values())
            })
            
            st.success(f"Se han detectado {len(df_analisis)} campos de datos para el fondo {isin_test}.")
            st.dataframe(df_analisis, use_container_width=True, height=600)
            
        except Exception as e:
            st.error(f"No se ha podido leer el JSON. Error: {e}")
