import streamlit as st
import pandas as pd
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import PyPDF2
import os
import re
import io

# ==========================================
# 1. CONFIGURACIÓN DEL ARQUITECTO (Rutas Locales)
# ==========================================
st.set_page_config(page_title="Torre de Control - Banca Privada", page_icon="🏛️", layout="wide")

# ATENCIÓN: Confirma que estas rutas son exactas en tu PC
RUTA_CREDENCIALES = r"G:\Mi unidad\App_Banca_Privada_QF\credenciales.json"
RUTA_PDFS = r"G:\Mi unidad\App_Banca_Privada_QF\PDFs_Fondos"
NOMBRE_GSHEET = "Base_Datos_Quality_Funds"

# ==========================================
# 2. INTERFAZ Y CONEXIONES (Sidebar)
# ==========================================
with st.sidebar:
    st.header("🔑 Llaves del Sistema")
    api_key = st.text_input("Gemini API Key:", type="password")
    
    st.markdown("---")
    st.markdown("### Estado de Conexiones")
    
    # Intentar conectar a Google Sheets al arrancar
    try:
        scope =["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(RUTA_CREDENCIALES, scope)
        gs_client = gspread.authorize(creds)
        db_maestra = gs_client.open(NOMBRE_GSHEET)
        st.success("✅ GSheets: Conectado")
    except Exception as e:
        st.error(f"❌ GSheets Error: {e}")
        db_maestra = None

    if not api_key:
        st.warning("Introduce la API Key de Gemini para activar la IA.")
        st.stop()
    else:
        st.success("✅ IA Gemini: Activada")
        genai.configure(api_key=api_key)
        modelo = genai.GenerativeModel('gemini-3-flash-preview')

st.title("🏛️ Torre de Control Data-Warehouse (Multi-Fuente)")
st.markdown("Panel de orquestación institucional. Elige la fuente a inyectar en tu Golden Record.")

# Creamos las 4 pestañas de inyección
tab_qf, tab_of, tab_inv, tab_ms = st.tabs([
    "📑 1. Fichas QF (PDF)", 
    "🌐 2. Openfunds API", 
    "📊 3. INVERNOS (Excel)", 
    "🩺 4. Morningstar X-Ray"
])

# Funciones de ayuda
def buscar_isin(texto):
    match = re.search(r'[A-Z]{2}[A-Z0-9]{10}', texto)
    return match.group(0) if match else None

def guardar_en_gsheets(hoja_nombre, lista_datos):
    """Añade una fila a la pestaña correspondiente en Google Sheets"""
    if db_maestra:
        hoja = db_maestra.worksheet(hoja_nombre)
        hoja.append_row(lista_datos)

# ==========================================
# MÓDULO 1: PDFs QUALITY FUNDS (Nivel Cualitativo)
# ==========================================
with tab_qf:
    st.header("Extracción Cualitativa CFA (Fichas PDF)")
    st.info(f"📁 Directorio de lectura: `{RUTA_PDFS}`")
    
    if st.button("Escanear y Procesar Fichas QF Nuevas", type="primary"):
        with st.spinner("Leyendo PDFs y aplicando IA..."):
            try:
                for archivo in os.listdir(RUTA_PDFS):
                    if archivo.endswith(".pdf"):
                        ruta_completa = os.path.join(RUTA_PDFS, archivo)
                        texto = ""
                        with open(ruta_completa, 'rb') as f:
                            lector = PyPDF2.PdfReader(f)
                            for pagina in lector.pages:
                                texto += pagina.extract_text() + " "
                        
                        isin = buscar_isin(texto)
                        if isin:
                            st.write(f"Procesando: **{isin}** ({archivo})...")
                            prompt = f"""
                            Eres un CFA. Extrae y sintetiza del siguiente texto:
                            1. Filosofía de Inversión (15 palabras max)
                            2. Sesgo del Gestor (15 palabras max)
                            3. Comentario Quality Funds (Resumen de por qué lo seleccionan)
                            
                            Devuelve ÚNICAMENTE UNA LÍNEA separando con punto y coma (;):
                            Filosofia;Sesgo;Comentario
                            
                            Texto: {texto[:10000]}
                            """
                            respuesta = modelo.generate_content(prompt).text.replace("\n", "").strip()
                            datos = respuesta.split(";")
                            
                            # Guardamos en la hoja RAW_PDF_QF (ISIN + 3 campos)
                            fila_a_guardar = [isin] + datos
                            guardar_en_gsheets("RAW_PDF_QF", fila_a_guardar)
                            st.success(f"✅ {isin} inyectado en RAW_PDF_QF.")
            except Exception as e:
                st.error(f"Error procesando PDFs: {e}")

# ==========================================
# MÓDULO 2: OPENFUNDS API (Carcasa Estructural)
# ==========================================
with tab_of:
    st.header("Extracción Estructural Openfunds")
    isins_of = st.text_area("Pega los ISINs a consultar en Fundinfo (uno por línea):")
    
    if st.button("Descargar JSONs e Inyectar"):
        if isins_of:
            lista_isins =[i.strip() for i in isins_of.split('\n') if i.strip()]
            for isin in lista_isins:
                try:
                    url = f"https://www.fundinfo.com/es/ES-priv/fund/Data?&OFST020000={isin}"
                    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    datos_json = res.text
                    
                    prompt = f"""Extrae del JSON y devuelve UNA SOLA LÍNEA separada por punto y coma (;):
                    Nombre del Fondo;Gestora;Categoria EFAMA;Benchmark;Riesgo SRI;TER %;Divisa Base;Articulo SFDR
                    
                    Usa deducción semántica. Cambia decimales a porcentajes españoles (ej. 1,45%). Si no existe pon N/A. SIN COMILLAS NI EXPLICACIONES.
                    JSON: {datos_json}"""
                    
                    respuesta = modelo.generate_content(prompt).text.replace("\n", "").strip()
                    datos = [isin] + respuesta.split(";")
                    guardar_en_gsheets("RAW_OPENFUNDS", datos)
                    st.success(f"✅ {isin} inyectado en RAW_OPENFUNDS.")
                except Exception as e:
                    st.error(f"Error con {isin}: {e}")

# ==========================================
# MÓDULO 3: INVERNOS (Rentabilidades Tácticas - FUERZA BRUTA)
# ==========================================
with tab_inv:
    st.header("Actualizador Táctico de INVERNOS")
    st.markdown("Sube el Excel de INVERNOS. *Aviso: Esto sobrescribirá la pestaña `RAW_INVERNOS` para tener la foto táctica más actual (0 tokens gastados).*")
    
    archivo_excel = st.file_uploader("Sube el Excel de Invernos (.xlsx o .xls)", type=["xlsx", "xls"])
    
    if st.button("Procesar Excel e Inyectar"):
        if archivo_excel and db_maestra:
            with st.spinner("Procesando matriz tabular..."):
                try:
                    # Leemos el Excel con Pandas
                    df = pd.read_excel(archivo_excel)
                    
                    # Limpieza básica: quitar filas sin ISIN
                    if 'ISIN' in df.columns:
                        df = df.dropna(subset=['ISIN'])
                        
                        # Rellenar vacíos con texto en blanco para que Google Sheets no de error
                        df = df.fillna("")
                        
                        # Convertir el DataFrame a una lista de listas
                        datos_a_subir = [df.columns.values.tolist()] + df.values.tolist()
                        
                        # Sobrescribimos la pestaña completa
                        hoja_inv = db_maestra.worksheet("RAW_INVERNOS")
                        hoja_inv.clear()
                        hoja_inv.update(values=datos_a_subir, range_name="A1")
                        
                        st.success(f"✅ Matriz de INVERNOS inyectada con éxito ({len(df)} fondos actualizados).")
                    else:
                        st.error("No se ha encontrado la columna 'ISIN' en el Excel.")
                except Exception as e:
                    st.error(f"Error procesando INVERNOS: {e}")

# ==========================================
# MÓDULO 4: MORNINGSTAR X-RAY (Las Tripas Médicas)
# ==========================================
with tab_ms:
    st.header("Escáner Médico Morningstar X-Ray")
    col1, col2 = st.columns([1, 3])
    
    with col1:
        isin_ms = st.text_input("ISIN del Fondo:")
    with col2:
        texto_ms = st.text_area("Pega el texto bruto (corta-pega) del X-Ray aquí:", height=200)
        
    if st.button("Extraer Asset Allocation e Inyectar"):
        if isin_ms and texto_ms:
            with st.spinner("Diseccionando cartera..."):
                try:
                    prompt = f"""Eres un CFA. Analiza este texto bruto de Morningstar X-Ray de un fondo.
                    Extrae estos datos EXACTOS y devuélvelos en UNA SOLA LÍNEA separada por punto y coma (;):
                    % Acciones; % Obligaciones; % Efectivo; % USA/América; % Europa; % Asia; PER (Precio/Beneficio); Precio/Valor Contable.
                    
                    Si alguno no existe, pon N/A. Formatea los números a formato español (ej. 45,37%).
                    SIN EXPLICACIONES, SIN MARKDOWN, SOLO LA LÍNEA DE DATOS.
                    
                    Texto X-Ray:
                    {texto_ms[:8000]}
                    """
                    respuesta = modelo.generate_content(prompt).text.replace("\n", "").strip()
                    datos = [isin_ms] + respuesta.split(";")
                    
                    guardar_en_gsheets("RAW_MORNINGSTAR", datos)
                    st.success(f"✅ Tripas del fondo {isin_ms} inyectadas en RAW_MORNINGSTAR.")
                except Exception as e:
                    st.error(f"Error IA: {e}")
