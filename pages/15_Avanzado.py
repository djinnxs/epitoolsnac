import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils.common import query_duckdb
import warnings

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Análisis Avanzado", page_icon=":chart_with_upwards_trend:", layout="wide")
st.title("📊 Análisis Avanzado")

# DuckDB query
query = """
SELECT PROVINCIA, DEPARTAMENTO, ANIO, SEMANA, NOMBREEVENTOAGRP, GRUPO, CANTIDAD
FROM {parquet}
"""
df = query_duckdb(query)

if df.empty:
    st.error("No hay datos disponibles")
    st.stop()

# Selector de tipo de análisis
analisis_tipo = st.selectbox(
    "Selecciona el tipo de análisis",
    ["Tendencia Temporal", "Correlación por Evento", "Distribución por Grupo Etario", "Comparativa por departamento"]
)

# 1. TENDENCIA TEMPORAL
if analisis_tipo == "Tendencia Temporal":
    st.subheader("Tendencia de Casos por Evento")
    
    eventos = sorted(df["NOMBREEVENTOAGRP"].unique())
    evento_seleccionado = st.selectbox("Selecciona un evento", eventos)
    
    df_evento = df[df["NOMBREEVENTOAGRP"] == evento_seleccionado]
    df_temporal = df_evento.groupby(["ANIO", "SEMANA"])["CANTIDAD"].sum().reset_index()
    df_temporal["fecha"] = df_temporal["ANIO"].astype(str) + "-W" + df_temporal["SEMANA"].astype(str).str.zfill(2)
    
    fig = px.line(
        df_temporal,
        x="fecha",
        y="CANTIDAD",
        title=f"Tendencia de {evento_seleccionado}",
        labels={"CANTIDAD": "Casos", "fecha": "Año-Semana"},
        markers=True
    )
    fig.update_layout(hovermode="x unified", height=500)
    st.plotly_chart(fig, width="stretch")
    
    # Tabla de datos
    st.dataframe(df_temporal[["ANIO", "SEMANA", "CANTIDAD"]], width="stretch")

# 2. CORRELACIÓN POR EVENTO
elif analisis_tipo == "Correlación por Evento":
    st.subheader("Comparación de Eventos por Año")
    
    anio_seleccionado = st.selectbox("Selecciona un año", sorted(df["ANIO"].unique(), reverse=True))
    
    df_anio = df[df["ANIO"] == anio_seleccionado]
    df_eventos = df_anio.groupby("NOMBREEVENTOAGRP")["CANTIDAD"].sum().reset_index()
    df_eventos = df_eventos.sort_values("CANTIDAD", ascending=False)
    
    fig = px.bar(
        df_eventos,
        x="NOMBREEVENTOAGRP",
        y="CANTIDAD",
        title=f"Casos por Evento en {anio_seleccionado}",
        labels={"CANTIDAD": "Casos", "NOMBREEVENTOAGRP": "Evento"},
        color="CANTIDAD",
        color_continuous_scale="Blues"
    )
    fig.update_layout(height=500, xaxis_tickangle=-45)
    st.plotly_chart(fig, width="stretch")
    
    st.dataframe(df_eventos, width="stretch")

# 3. DISTRIBUCIÓN POR GRUPO ETARIO
elif analisis_tipo == "Distribución por Grupo Etario":
    st.subheader("Distribución por Grupo Etario")
    
    eventos = sorted(df["NOMBREEVENTOAGRP"].unique())
    evento_seleccionado = st.selectbox("Selecciona un evento", eventos)
    
    df_evento = df[df["NOMBREEVENTOAGRP"] == evento_seleccionado]
    df_grupos = df_evento.groupby("GRUPO")["CANTIDAD"].sum().reset_index()
    df_grupos = df_grupos.dropna(subset=["GRUPO"])
    df_grupos = df_grupos.sort_values("CANTIDAD", ascending=False)
    
    fig = px.pie(
        df_grupos,
        names="GRUPO",
        values="CANTIDAD",
        title=f"Distribución de {evento_seleccionado} por Grupo Etario"
    )
    fig.update_layout(height=600)
    st.plotly_chart(fig, width="stretch")
    
    st.dataframe(df_grupos, width="stretch")

# 4. COMPARATIVA POR DEPARTAMENTO
elif analisis_tipo == "Comparativa por departamento":
    st.subheader("Comparación por Departamento")
    
    evento_seleccionado = st.selectbox("Selecciona un evento", sorted(df["NOMBREEVENTOAGRP"].unique()))
    anio_seleccionado = st.selectbox("Selecciona un año", sorted(df["ANIO"].unique(), reverse=True))
    
    df_filtrado = df[(df["NOMBREEVENTOAGRP"] == evento_seleccionado) & (df["ANIO"] == anio_seleccionado)]
    df_departamentos = df_filtrado.groupby("DEPARTAMENTO")["CANTIDAD"].sum().reset_index()
    df_departamentos = df_departamentos.sort_values("CANTIDAD", ascending=False)
    
    fig = px.bar(
        df_departamentos,
        x="DEPARTAMENTO",
        y="CANTIDAD",
        title=f"{evento_seleccionado} por Departamento ({anio_seleccionado})",
        labels={"CANTIDAD": "Casos", "DEPARTAMENTO": "Departamento"},
        color="CANTIDAD",
        color_continuous_scale="Reds"
    )
    fig.update_layout(height=500, xaxis_tickangle=-45)
    st.plotly_chart(fig, width="stretch")
    
    st.dataframe(df_departamentos, width="stretch")