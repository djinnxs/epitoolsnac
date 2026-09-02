import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import os
import io
import os
from openpyxl import Workbook
from openpyxl.styles import PatternFill
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

Api_key = os.getenv('OPENWEATHER_API_KEY', '')
base_url_weather = 'https://api.openweathermap.org/data/2.5/weather'

# Configuracion de la página
st.set_page_config(page_title="Epidemiologia", page_icon=":bar_chart:", layout="wide")

# Título de la página
st.markdown(
    '<center><h3 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;">🌅 Clima en tiempo real e histórico</h3></center>',
    unsafe_allow_html=True,
)

# Parte 1: Clima en tiempo real
st.markdown("<h5>Clima en tiempo real</h5>", unsafe_allow_html=True)

city = st.text_input("Ingrese una ciudad/provincia:")

consultar_tiempo_real = st.button("Consultar Tiempo Real")
if consultar_tiempo_real and city:
    request_url = f"{base_url_weather}?appid={Api_key}&q={city},AR&lang=es"
    response = requests.get(request_url)
    if response.status_code == 200:
        data = response.json()
        weather = data["weather"][0]["description"]
        temperature = round(data["main"]["temp"] - 273.15, 2)
        feels_like = round(data["main"]["feels_like"] - 273.15, 2)
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        wind_dir = data["wind"]["deg"]
        st.write(f"Clima: {weather}")
        st.write(f"Temperatura: {temperature}°C")
        st.write(f"Sensación térmica: {feels_like}°C")
        st.write(f"Humedad: {humidity}%")
        st.write(f"Velocidad del viento: {wind_speed} m/s")
        st.write(f"Dirección del viento: {wind_dir} grados")
    else:
        st.write("Error al obtener la información del clima.")

# Parte 2: Clima histórico
st.markdown("---")
st.markdown("<h5>🌅 Datos del clima histórico</h5>", unsafe_allow_html=True)

@st.cache_data
def load_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, 'data', 'ClimaHisto.parquet')
    df = pd.read_parquet(path)
    df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
    df["Temp. Minima (°C)"] = pd.to_numeric(df["Temp. Minima (°C)"], errors="coerce").round(1)
    df["Temp. Maxima (°C)"] = pd.to_numeric(df["Temp. Maxima (°C)"], errors="coerce").round(1)
    df["Precipitación (mm)"] = pd.to_numeric(df.get("Precipitación (mm)", np.nan), errors="coerce").round(1)
    return df

df = load_data()

# Selectores de provincia y estación
provincias = sorted(df["PROVINCIA"].unique())
provincia_seleccionada = st.selectbox("Seleccione una provincia:", provincias)

estaciones = sorted(df[df["PROVINCIA"] == provincia_seleccionada]["Estación"].unique())
estacion_seleccionada = st.selectbox("Seleccione una estación:", estaciones)

# Rango de fechas
col1, col2 = st.columns(2)
with col1:
    fecha_inicio = st.date_input("Fecha de inicio", min_value=df["Fecha"].min(), max_value=df["Fecha"].max())
with col2:
    fecha_fin = st.date_input("Fecha de fin", min_value=df["Fecha"].min(), max_value=df["Fecha"].max())

consultar = st.button("Consultar")

if consultar:
    datos_filtrados = df[(df["PROVINCIA"] == provincia_seleccionada) &
                         (df["Estación"] == estacion_seleccionada) &
                         (df["Fecha"] >= fecha_inicio) &
                         (df["Fecha"] <= fecha_fin)]
    datos_mostrar = datos_filtrados[["PROVINCIA", "Estación", "Temp. Minima (°C)", "Temp. Maxima (°C)", "Precipitación (mm)", "Fecha"]].sort_values("Fecha")

    def custom_color_scale(val, min_val, max_val):
        if pd.isna(val) or pd.isna(min_val) or pd.isna(max_val) or min_val == max_val:
            return "background-color: rgba(173, 216, 230, 0.0)"
        normalized = (val - min_val) / (max_val - min_val)
        return f"background-color: rgba(173, 216, 230, {normalized:.2f})"

    styled = (
        datos_mostrar.style.format({"Temp. Minima (°C)": "{:.1f}", "Temp. Maxima (°C)": "{:.1f}", "Precipitación (mm)": "{:.1f}"}, na_rep="-")
        .apply(lambda x: [custom_color_scale(v, x.min(), x.max()) for v in x], subset=["Temp. Minima (°C)", "Temp. Maxima (°C)"])
    )
    st.dataframe(styled)

    def to_excel(df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Datos históricos")
            workbook = writer.book
            worksheet = writer.sheets["Datos históricos"]
            if not df.empty:
                for col in ["C", "D"]:
                    cells = worksheet[col]
                    vals = [cell.value for cell in cells[1:] if cell.value is not None]
                    if vals:
                        min_temp = min(vals)
                        max_temp = max(vals)
                        for cell in cells[1:]:
                            if cell.value is not None:
                                if max_temp != min_temp:
                                    normalized = (cell.value - min_temp) / (max_temp - min_temp)
                                else:
                                    normalized = 0.5
                                color = f"{int(255 - 82*normalized):02X}{int(255 - 39*normalized):02X}FF"
                                cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        output.seek(0)
        return output.getvalue()

    excel_data = to_excel(datos_mostrar)
    st.download_button(
        label="Descargar datos en Excel",
        data=excel_data,
        file_name="datos_historicos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
