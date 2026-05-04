import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests

# 1. Configuración de la página web
st.set_page_config(page_title="Asesor IA - Quality Funds", page_icon="💼", layout="centered")
st.title("💼 Asesor IA - Banca Privada")
st.markdown("Herramienta exclusiva de consulta y extracción (Estándar Openfunds).")

# 2. Menú lateral para meter tus llaves
with st.sidebar:
    st.header("Configuración")
    api_key = st.text_input("Introduce tu API Key de Gemini:", type="password")
    sheet_url = st.text_input("Pega el enlace de tu Google Sheets:")
    st.markdown("---")
    st.caption("Tus datos están seguros y no se guardan en ningún servidor.")

if not api_key or not sheet_url:
    st.info("👈 Por favor, introduce tu API Key y el enlace a tu Excel en el menú de la izquierda.")
    st.stop()

# 3. Leer tu Excel de Google Sheets
@st.cache_data(ttl=600)
def cargar_datos(url):
    if "edit?usp=sharing" in url or "edit" in url:
        url = url.split("/edit")[0] + "/export?format=csv"
    return pd.read_csv(url, sep=";") # Le decimos que el separador es el punto y coma

try:
    df_fondos = cargar_datos(sheet_url)
    st.sidebar.success(f"✅ ¡Conectado! {len(df_fondos)} fondos en la base de datos.")
except Exception as e:
    st.sidebar.error(f"❌ Error al leer el Excel. Detalle: {e}")
    st.stop()

# 4. Configurar la IA
genai.configure(api_key=api_key)
modelo = genai.GenerativeModel('gemini-3-flash-preview') # O gemini-1.5-pro-latest si el 3.1 no está activo aún

# 5. Crear las dos Pestañas de la Aplicación
tab1, tab2 = st.tabs(["💬 Asesor IA", "📥 Extractor Masivo (Fundinfo)"])

# ==========================================
# PESTAÑA 1: EL ASESOR IA (CHATBOT)
# ==========================================
with tab1:
    contexto_fondos = df_fondos.to_string(index=False)
    prompt_sistema = f"""
    Eres un Banquero Privado Senior. Tu trabajo es recomendar fondos y crear carteras para tus clientes.
    Aquí tienes la base de datos con los ÚNICOS fondos que tienes aprobados por Quality Funds:
    
    {contexto_fondos}
    
    REGLAS ESTRICTAS:
    1. NUNCA recomiendes un fondo que no esté en la base de datos.
    2. Cuando hables de un fondo, da su ISIN, nivel de riesgo y comisiones.
    3. Tu tono debe ser profesional y persuasivo.
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
                    consulta_completa = prompt_sistema + "\n\nPregunta: " + pregunta
                    respuesta = modelo.generate_content(consulta_completa)
                    st.markdown(respuesta.text)
                    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta.text})
                except Exception as e:
                    st.error(f"Fallo de la IA: {e}")


# ==========================================
# PESTAÑA 2: EL EXTRACTOR MASIVO
# ==========================================
with tab2:
    st.subheader("Extracción automática desde Fundinfo")
    st.markdown("Pega aquí tu lista de ISINs (uno debajo de otro). La aplicación se conectará a Fundinfo, descargará los datos y la IA los formateará en bloque para tu Google Sheets.")
    
    lista_isins = st.text_area("Lista de ISINs (Ej: FR0007038138)", height=150)
    
    if st.button("Extraer y Generar Tabla"):
        if not lista_isins.strip():
            st.warning("Pega al menos un ISIN.")
        else:
            isins =[i.strip() for i in lista_isins.split('\n') if i.strip()]
            
            # Recolectar datos de internet (Scraping de la API de Fundinfo)
            datos_json_acumulados = ""
            barra_progreso = st.progress(0)
            texto_estado = st.empty()
            
            headers = {'User-Agent': 'Mozilla/5.0'} # Para que la web no nos bloquee
            
            for i, isin in enumerate(isins):
                texto_estado.text(f"Descargando datos de {isin} ({i+1}/{len(isins)})...")
                url_api = f"https://www.fundinfo.com/es/ES-priv/fund/Data?&OFST020000={isin}"
                try:
                    res = requests.get(url_api, headers=headers, timeout=10)
                    datos_json_acumulados += f"\n--- FONDO: {isin} ---\n{res.text}"
                except Exception as e:
                    datos_json_acumulados += f"\n--- FONDO: {isin} ---\nERROR AL DESCARGAR"
                
                barra_progreso.progress((i + 1) / len(isins))
            
            texto_estado.text("Procesando los datos con la Inteligencia Artificial... (puede tardar unos segundos)")
            
            # El Prompt estricto para extraer en bloque
            prompt_extraccion = f"""
            Aquí tienes una recopilación de datos JSON de varios fondos de inversión:
            {datos_json_acumulados}
            
            Tu tarea es extraer los datos y construir una tabla CSV separada EXCLUSIVAMENTE por punto y coma (;).
            REGLAS ESTRICTAS:
            1. No escribas NADA de texto antes ni después de la tabla. Nada de "Aquí tienes la tabla". SOLO devuelve las filas.
            2. Debe haber exactamente 24 columnas por fila. Si falta un dato, pon un espacio vacío entre los punto y coma.
            3. No pongas la fila de cabecera. Solo dame las filas de los fondos.
            4. Las comisiones y rentabilidades dales formato numérico español (ej. 1,50%).
            
            Orden exacto de las 24 columnas:
            ISIN; Nombre; Gestora; Divisa; Politica (Acum/Dist); Clase de Activo; Liquidez; Dias Liquidacion; TER; Comision Exito; Comision Entrada; SRI; Horizonte; Volatilidad; YTD; 1A; 3A; 5A; Articulo SFDR; Considera PAI; Geografias (Top 3); Sectores (Top 3); Top 10 Posiciones; Filosofia
            """
            
            try:
                resultado_ia = modelo.generate_content(prompt_extraccion)
                texto_estado.success("¡Extracción Completada! Copia el bloque de abajo y pégalo en tu Google Sheets.")
                
                # Mostramos el resultado en una caja de código para que lo copie con un botón
                st.code(resultado_ia.text, language="csv")
                
            except Exception as e:
                st.error(f"Error al procesar con la IA: {e}")
