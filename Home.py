import streamlit as st
import base64
import os
import warnings
import logging

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("streamlit").setLevel(logging.ERROR)

st.set_page_config(page_title="Epidemiologia", page_icon=":bar_chart:", layout="wide")

# --- ENCABEZADO Y LOGO ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

logo_path = os.path.join(os.path.dirname(__file__), "data", "Epidemio.png")

if os.path.exists(logo_path):
    img_b64 = get_base64_of_bin_file(logo_path)
    # Flexbox para alinear perfectamente la imagen y el texto
    st.markdown(f'''
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
        <img src="data:image/png;base64,{img_b64}" width="100">
        <h1 style="font-weight:900; color:#1f77b4; margin:0;">SEI - Sistema de Epidemiología Interactiva</h1>
    </div>
    ''', unsafe_allow_html=True)
else:
    st.markdown('''
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
        <h1 style="margin:0;">🦠</h1>
        <h1 style="font-weight:900; color:#1f77b4; margin:0;">SEI - Sistema de Epidemiología Interactiva</h1>
    </div>
    ''', unsafe_allow_html=True)

st.markdown("---")

# --- MENÚ DE NAVEGACIÓN ---
st.markdown("### 🧭 Menú Principal")

# Secciones del menú
menu_cols1 = st.columns(3)
menu_cols2 = st.columns(3)

with menu_cols1[0]:
    st.markdown("#### 📊 Resumen")
    st.page_link("pages/1_Dashboard.py", label="Dashboard Principal", icon="📈")
    st.page_link("pages/3_CasosSemana.py", label="Casos por Semana", icon="📅")
    st.page_link("pages/8_Calendario.py", label="Calendario Epidemio.", icon="📆")
    st.page_link("pages/14_Tendencia.py", label="Tendencias", icon="📉")

with menu_cols1[1]:
    st.markdown("#### 🗺️ Geografía")
    st.page_link("pages/4_Mapas.py", label="Mapas Estáticos", icon="📍")
    st.page_link("pages/19_MapaAnimado.py", label="Mapa Animado", icon="🎞️")
    st.page_link("pages/22_Semaforo.py", label="Semáforo de Riesgo", icon="🚦")
    
with menu_cols1[2]:
    st.markdown("#### 🔬 Análisis")
    st.page_link("pages/2_Corredores.py", label="Corredores Endémicos", icon="📊")
    st.page_link("pages/5_Tasas.py", label="Tasas de Incidencia", icon="🔢")
    st.page_link("pages/9_Mediana.py", label="Análisis de Medianas", icon="⚖️")
    st.page_link("pages/7_Poblacion.py", label="Datos Poblacionales", icon="👥")
    st.page_link("pages/6_Tablas.py", label="Explorador de Tablas", icon="🗄️")
    st.page_link("pages/15_Avanzado.py", label="Análisis Avanzado", icon="🔬")

st.markdown("<br>", unsafe_allow_html=True)

with menu_cols2[0]:
    st.markdown("#### 🌦️ Entorno y Clima")
    st.page_link("pages/12_Clima.py", label="Clima Actual/Histórico", icon="🌤️")
    st.page_link("pages/20_CorrelacionClima.py", label="Correlación Climática", icon="🌡️")
    st.page_link("pages/21_Sindemias.py", label="Sindemias", icon="🔄")

with menu_cols2[1]:
    st.markdown("#### 🤖 Inteligencia")
    st.page_link("pages/17_Nowcasting.py", label="Nowcasting", icon="🔮")
    st.page_link("pages/18_Alertas.py", label="Sistema de Alertas", icon="🔔")
    st.page_link("pages/11_Rumores.py", label="Gestión de Rumores", icon="🗣️")
    st.page_link("pages/13_IA.py", label="Asistente IA", icon="🧠")

with menu_cols2[2]:
    st.markdown("#### ℹ️ Otros")
    st.page_link("pages/30_About.py", label="Acerca de SEI", icon="ℹ️")

st.markdown("---")
