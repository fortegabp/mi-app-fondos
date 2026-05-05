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
# PESTAÑA 2: EXTRACTOR PREMIUM
# ==========================================
with tab2:
    st.markdown("### 📥 Extractor de Datos de Alta Calidad")
    isins_input = st.text_area("Lista de ISINs (uno por línea):", height=150)
    
    if st.button("Generar Tabla Openfunds"):
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
                    
                    prompt_extraccion = f"""
                    Actúa como un parser de datos. Lee este JSON y extrae los valores correspondientes a los siguientes códigos/conceptos. 
                    Devuelve ÚNICAMENTE UNA FILA de texto separada por punto y coma (;), respetando ESTE ORDEN EXACTO:
                    [OFST020000]; [OFST010110]; [OFST001020];[OFST010410]; [OFST020400];[OFST350100]; [OFST010230]; [OFST023200];[OFEP010900]; [OFEP060200]; Sharpe 3A; Alpha 3A; Beta 3A; Tracking Error 3A; Max Drawdown; Rentabilidad YTD; Rentabilidad 1A; Rentabilidad 3A; Rentabilidad 5A; Cuartil 3A; [OFRE000520]; [OFRE000560];[OFRE000500]; [OFPH000465];[OFPH000485]; [OFEE200400]; [OFEE201000];[OFST820110]; [OFST452200];[OFST451028]; [OFST451305];[OFST020300]; [OFST410700]; [OFST400230];[OFST020600]; [OFST010300]; Sesgo del Gestor; Comentario Quality Funds
                    
                    Datos en crudo:
                    {datos_json}
                    
                    Reglas: 
                    1. Formato español (comas para decimales, sin símbolo %). 
                    2. Para los datos que no tengan código OF-ID oficial (como el Sharpe o Alpha), búscalo en el JSON bajo el nombre que le dé Fundinfo.
                    3. Si un dato no existe en el JSON, escribe 'null' (manteniendo el punto y coma).
                    4. NUNCA añadas saltos de línea dentro de la fila.
                    """
                    row = modelo.generate_content(prompt_extraccion).text
                    res_list.append(row.strip())
                except Exception as e:
                    res_list.append(f"{isin};Error en conexión o IA: {e};;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                
                progress.progress((idx + 1) / len(isins))
            
            st.subheader("📋 Tabla lista para copiar a Google Sheets")
            st.code("\n".join(res_list), language="csv")

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
