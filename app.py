import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests

# 1. Configuración de la página web
st.set_page_config(page_title="Asesor IA - Quality Funds", page_icon="💼", layout="wide")
st.title("💼 Asesor IA - Banca Privada")

# 2. Menú lateral para meter tus llaves
with st.sidebar:
    st.header("Configuración")
    api_key = st.text_input("Introduce tu API Key de Gemini:", type="password")
    sheet_url = st.text_input("Pega el enlace de tu Google Sheets:")

if not api_key or not sheet_url:
    st.info("👈 Introduce tu API Key y el enlace a tu Excel en el menú izquierdo.")
    st.stop()

# 3. Leer tu Excel de Google Sheets
@st.cache_data(ttl=600)
def cargar_datos(url):
    if "edit?usp=sharing" in url or "edit" in url:
        url = url.split("/edit")[0] + "/export?format=csv"
    return pd.read_csv(url, sep=";") 

try:
    df_fondos = cargar_datos(sheet_url)
    st.sidebar.success(f"✅ Conectado: {len(df_fondos)} fondos.")
except Exception as e:
    st.sidebar.error(f"❌ Error al leer el Excel: {e}")
    st.stop()

# 4. Configurar la IA
genai.configure(api_key=api_key)
modelo = genai.GenerativeModel('gemini-3-flash-preview') 

# 5. PESTAÑAS
tab1, tab2, tab3 = st.tabs(["💬 Asesor IA", "📥 Extractor Masivo", "🏗️ Arquitectura (Análisis JSON)"])

# ==========================================
# PESTAÑA 1: EL ASESOR IA (CHATBOT)
# ==========================================
with tab1:
    contexto_fondos = df_fondos.to_string(index=False)
    prompt_sistema = f"""
    Eres un Banquero Privado Senior. 
    Catálogo de Quality Funds:
    {contexto_fondos}
    
    REGLAS:
    1. NO recomiendes fondos fuera del catálogo.
    2. Da siempre ISIN, riesgo y comisiones.
    3. Tono profesional y analítico.
    """
    
    if "mensajes" not in st.session_state:
        st.session_state.mensajes =[]

    for msg in st.session_state.mensajes:
        with st.chat_message(msg["rol"]):
            st.markdown(msg["texto"])

    if pregunta := st.chat_input("Escribe el perfil de tu cliente..."):
        with st.chat_message("user"):
            st.markdown(pregunta)
        st.session_state.mensajes.append({"rol": "user", "texto": pregunta})

        with st.chat_message("assistant"):
            with st.spinner("Analizando fondos..."):
                try:
                    respuesta = modelo.generate_content(prompt_sistema + "\n\nPregunta: " + pregunta)
                    st.markdown(respuesta.text)
                    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta.text})
                except Exception as e:
                    st.error(f"Error IA: {e}")

# ==========================================
# PESTAÑA 2: EL EXTRACTOR MASIVO
# ==========================================
with tab2:
    st.markdown("Pega tu lista de ISINs para formatear en bloque a Google Sheets.")
    lista_isins = st.text_area("ISINs (uno por línea):", height=100)
    
    if st.button("Extraer a CSV"):
        if lista_isins.strip():
            isins =[i.strip() for i in lista_isins.split('\n') if i.strip()]
            datos_json_acumulados = ""
            barra = st.progress(0)
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            for i, isin in enumerate(isins):
                url_api = f"https://www.fundinfo.com/es/ES-priv/fund/Data?&OFST020000={isin}"
                try:
                    res = requests.get(url_api, headers=headers, timeout=10)
                    datos_json_acumulados += f"\n--- {isin} ---\n{res.text}"
                except:
                    pass
                barra.progress((i + 1) / len(isins))
            
           prompt_extraccion = f"""
            Actúa como un parser de datos. Lee este JSON y extrae los valores correspondientes a los siguientes códigos/conceptos. 
            Devuelve ÚNICAMENTE UNA FILA de texto separada por punto y coma (;), respetando ESTE ORDEN EXACTO:[OFST020000]; [OFST010110]; [OFST001020];[OFST010410]; [OFST020400];[OFST350100]; [OFST010230]; [OFST023200];[OFEP010900]; [OFEP060200]; Sharpe 3A; Alpha 3A; Beta 3A; Tracking Error 3A; Max Drawdown; Rentabilidad YTD; Rentabilidad 1A; Rentabilidad 3A; Rentabilidad 5A; Cuartil 3A; [OFRE000520];[OFRE000560]; [OFRE000500];[OFPH000465]; [OFPH000485]; [OFEE200400];[OFEE201000]; [OFST820110];[OFST452200]; [OFST451028]; [OFST451305];[OFST020300]; [OFST410700];[OFST400230]; [OFST020600];[OFST010300]; Sesgo del Gestor; Comentario Quality Funds
            
            Datos en crudo:
            {datos_json_acumulados}
            
            Reglas: 
            1. Formato español (comas para decimales, sin símbolo %). 
            2. Para los datos que no tengan código OF-ID oficial (como el Sharpe o Alpha), búscalo en el JSON bajo el nombre que le dé Fundinfo.
            3. Si un dato no existe en el JSON, escribe 'null' (manteniendo el punto y coma).
            """

# ==========================================
# PESTAÑA 3: ARQUITECTURA (ANÁLISIS PROFUNDO)
# ==========================================
with tab3:
    st.subheader("Buscador de Campos en Crudo (Fundinfo)")
    st.markdown("Introduce un ISIN para ver **absolutamente todos** los datos que devuelve la API, organizados en una tabla.")
    
    isin_test = st.text_input("ISIN a investigar:", "LU1213836080")
    
    if st.button("Analizar Estructura del Fondo"):
        url_test = f"https://www.fundinfo.com/es/ES-priv/fund/Data?&OFST020000={isin_test}"
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            respuesta = requests.get(url_test, headers=headers)
            json_data = respuesta.json()
            
            # Función para aplanar el JSON y leer todas las claves ocultas
            def aplanar_diccionario(d, parent_key='', sep='_'):
                items =[]
                if isinstance(d, list):
                    # Si es una lista, iteramos por sus elementos
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
            
            # Crear un DataFrame con las claves reales de FundInfo
            df_analisis = pd.DataFrame({
                "Nombre del Campo (Key)": list(datos_planos.keys()),
                "Valor devuelto": list(datos_planos.values())
            })
            
            st.success(f"Se han detectado {len(df_analisis)} campos de datos para el fondo {isin_test}.")
            
            # Mostrar la tabla en pantalla completa
            st.dataframe(df_analisis, use_container_width=True, height=600)
            
            st.info("💡 Fíjate en la columna 'Nombre del Campo'. Selecciona de la tabla los que te interesen para la base de datos (por ejemplo campos de ESG, Ratios o Drawdown) y dímelos en el chat. Al darme solo el nombre del campo, el chat no te bloqueará.")
            
        except Exception as e:
            st.error(f"No se ha podido leer el JSON. Error: {e}")
