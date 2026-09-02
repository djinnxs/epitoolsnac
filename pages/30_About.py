# pages/16_About.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

st.set_page_config(page_title="Acerca de", page_icon="Information", layout="wide")

st.markdown("<h2 style='text-align: center; color: #1f77b4;'>Análisis Epidemiológico </h2>", unsafe_allow_html=True)


st.markdown("---")

st.markdown("""
<span style="font-size: 20px;">Esta aplicación ha sido creada para proporcionar análisis epidemiológico rápido, 
visual y accesible.</span>
""", unsafe_allow_html=True)

st.markdown("### Creado por:")
st.markdown("**Julio Adrián Tapia**")
st.markdown("[LinkedIn](https://www.linkedin.com/in/julio-tapia-78557697/)")

st.markdown("### Contacto:")
st.markdown("djinnxs@gmail.com")


st.success("¡Gracias por usar la app demo!")