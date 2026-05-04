import streamlit as st
import pandas as pd
import google.generativeai as genai

# 1. Configuración de la página web
st.set_page_config(page_title="Asesor IA - Quality Funds", page_icon="💼", layout="centered")
st.title("💼 Asesor IA - Banca Privada")
st.markdown("Consulta el universo de fondos aprobados de Quality Funds.")

# 2. Menú lateral para meter tus llaves (API Key y Enlace)
with st.sidebar:
    st.header("Configuración")
    api_key = st.text_input("Introduce tu API Key de Gemini:", type="password")
    sheet_url = st.text_input("Pega el enlace de tu Google Sheets:")
    st.markdown("---")
    st.caption("Tus datos están seguros y no se guardan en ningún servidor.")

# Si no has metido las llaves, la app se pausa aquí
if not api_key or not sheet_url:
    st.info("👈 Por favor, introduce tu API Key y el enlace a tu Excel en el menú de la izquierda.")
    st.stop()

# 3. Leer tu Excel de Google Sheets
@st.cache_data(ttl=600)  # Guarda los datos 10 minutos para no leer el excel cada segundo
def cargar_datos(url):
    # Truco informático: convertir el enlace de lectura en un enlace de descarga automática CSV
    if "edit?usp=sharing" in url or "edit" in url:
        url = url.split("/edit")[0] + "/export?format=csv"
    
    # Leer el Excel
    df = pd.read_csv(url)
    return df

try:
    df_fondos = cargar_datos(sheet_url)
    st.sidebar.success(f"✅ ¡Conectado! {len(df_fondos)} fondos en la base de datos.")
except Exception as e:
    st.sidebar.error("❌ Error al leer el Excel. Asegúrate de que el enlace es correcto y tiene permisos de 'Lector' para cualquiera.")
    st.stop()

# 4. Configurar la Inteligencia Artificial
genai.configure(api_key=api_key)
modelo = genai.GenerativeModel('gemini-3.1-pro')

# Convertimos tu Excel a texto para que la IA lo lea
contexto_fondos = df_fondos.to_string(index=False)

# Las reglas estrictas para la IA
prompt_sistema = f"""
Eres un Banquero Privado Senior. Tu trabajo es recomendar fondos y crear carteras para tus clientes.
Aquí tienes la base de datos con los ÚNICOS fondos que tienes aprobados por Quality Funds:

{contexto_fondos}

REGLAS ESTRICTAS:
1. NUNCA recomiendes ni menciones un fondo que no esté en la base de datos de arriba.
2. Si te piden un tipo de fondo que no tienes, pide disculpas y di que actualmente no hay fondos de ese tipo aprobados por Quality Funds.
3. Cuando hables de un fondo, da su ISIN, su nivel de riesgo y sus comisiones para que quede constancia legal.
4. Tu tono debe ser profesional, elitista, educado y persuasivo.
5. Puedes estructurar la respuesta usando listas, viñetas y negritas para facilitar la lectura.
"""

# 5. Interfaz de Chat
if "mensajes" not in st.session_state:
    st.session_state.mensajes =[]

# Mostrar el historial del chat
for msg in st.session_state.mensajes:
    with st.chat_message(msg["rol"]):
        st.markdown(msg["texto"])

# Cajón para que tú escribas
if pregunta := st.chat_input("Escribe el perfil de tu cliente o el fondo que buscas..."):
    # Mostrar tu pregunta
    with st.chat_message("user"):
        st.markdown(pregunta)
    st.session_state.mensajes.append({"rol": "user", "texto": pregunta})

    # Mostrar la respuesta de la IA
    with st.chat_message("assistant"):
        with st.spinner("Analizando fondos de Quality Funds..."):
            try:
                # Juntamos las reglas, la base de datos y tu pregunta
                consulta_completa = prompt_sistema + "\n\nPregunta del asesor: " + pregunta
                respuesta = modelo.generate_content(consulta_completa)
                st.markdown(respuesta.text)
                st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta.text})
           except Exception as e:
                st.error(f"Fallo exacto de la IA: {e}")
