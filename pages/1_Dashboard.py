# pages/1_Dashboard.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.express as px
import pandas as pd
import plotly.figure_factory as ff
from collections import OrderedDict
import duckdb
from utils.common import get_parquet_path, check_parquet_exists, load_population_province, format_number, style_argentina

# Configuración
st.set_page_config(page_title="Epidemiologia - Dashboard Nacional", page_icon="Chart", layout="wide")

# ==================== CARGA DE DATOS DESDE PARQUET ====================
@st.cache_data(ttl=3600)
def load_data():
    parquet_path = check_parquet_exists('base_semanal.parquet')
    if not parquet_path:
        st.error("No se encontró base_semanal.parquet")
        st.stop()

    clean_path = str(parquet_path).replace("\\", "/")
    
    # Agregamos LOCALIDAD a la consulta
    df = duckdb.query(f"""
        SELECT 
            CODIGO_PROVINCIA, PROVINCIA, DEPARTAMENTO, LOCALIDAD,
            ANIO, SEMANA, ID_SNVS_EVENTO_AGRP, NOMBREEVENTOAGRP,
            IDEDAD, GRUPO, CANTIDAD, FECHAREGISTROCLINICA
        FROM read_parquet('{clean_path}')
    """).df()
    
    df["FECHAREGISTROCLINICA"] = pd.to_datetime(df["FECHAREGISTROCLINICA"], errors='coerce')
    df["NOMBREEVENTOAGRP"] = df["NOMBREEVENTOAGRP"].astype(str)
    
    # Normalización de textos para filtros
    if 'DEPARTAMENTO' in df.columns:
        df['DEPARTAMENTO'] = df['DEPARTAMENTO'].astype(str).str.title()
    if 'LOCALIDAD' in df.columns:
        df['LOCALIDAD'] = df['LOCALIDAD'].astype(str).str.title()
        
    return df

# CARGAMOS PRIMERO
df = load_data()

# Muestra rápida
if st.checkbox("Usar datos de muestra (para desarrollo rápido)"):
    df = df.sample(n=1000, random_state=42).reset_index(drop=True)

# ==================== RANGO DE FECHAS ====================
if not df.empty:
    startDate = df["FECHAREGISTROCLINICA"].min().date()
    endDate = df["FECHAREGISTROCLINICA"].max().date()
else:
    startDate = pd.Timestamp("2023-01-01").date()
    endDate = pd.Timestamp("2023-12-31").date()

col1, col2 = st.columns(2)
with col1:
    date1 = st.date_input("Fecha inicial", startDate)
    date1 = pd.Timestamp(date1)
with col2:
    date2 = st.date_input("Fecha final", endDate)
    date2 = pd.Timestamp(date2)

# ==================== FILTROS (NACIONALES) ====================
st.sidebar.header("Filtros:")

ANIO = st.sidebar.multiselect("Elije el año", sorted(df["ANIO"].dropna().unique()))

col_evento, col_provincia = st.columns(2)

with col_evento:
    EVENTO = st.multiselect("Evento", ["Todos"] + sorted(df["NOMBREEVENTOAGRP"].unique()), default=["Todos"])

with col_provincia:
    provincias_disponibles = sorted(df["PROVINCIA"].dropna().unique())
    PROVINCIA = st.multiselect("Provincia", ["Todos"] + provincias_disponibles, default=["Todos"])

col_grupo = st.columns(1)[0]
with col_grupo:
    GRUPO_ORDER = [
        "< 6 m","6 a 11 m","12 a 23 m","2 a 4","5 a 9","10 a 14",
        "15 a 19","20 a 24","25 a 34","35 a 44","45 a 64",
        "65 a 74",">= a 75","Pediát <3","Pediát >=3",
        "Adultos <60","Adultos >=60","Edad Sin Esp."
    ]
    available = list(df["GRUPO"].dropna().unique())
    ordered = [g for g in GRUPO_ORDER if g in available]
    remaining = sorted([g for g in available if g not in ordered])
    GRUPO = st.multiselect("Grupo Etario", ["Todos"] + ordered + remaining, default=["Todos"])

# ==================== CONFIGURACIÓN DE VISTA ====================
columna_valor = "CANTIDAD"
label_valor = "Casos"

# ==================== LÓGICA DE FILTRADO ====================
@st.cache_data
def filter_dataframe(df, date1, date2, ANIO, EVENTO, PROVINCIA, GRUPO):
    f = df[(df["FECHAREGISTROCLINICA"] >= date1) & 
           (df["FECHAREGISTROCLINICA"] <= date2)].copy()
    
    if ANIO: 
        f = f[f["ANIO"].isin(ANIO)]
    if EVENTO and EVENTO != ["Todos"]: 
        f = f[f["NOMBREEVENTOAGRP"].isin(EVENTO)]
    if PROVINCIA and PROVINCIA != ["Todos"]: 
        f = f[f["PROVINCIA"].isin(PROVINCIA)]
    if GRUPO and GRUPO != ["Todos"]: 
        f = f[f["GRUPO"].isin(GRUPO)]
    
    return f

filtered_df = filter_dataframe(df, date1, date2, ANIO, EVENTO, PROVINCIA, GRUPO)

# ==================== VISUALIZACIONES ====================

# 1. Gráfico por Provincia
PROVINCIA_df = filtered_df.groupby("PROVINCIA", as_index=False)["CANTIDAD"].sum().sort_values("CANTIDAD", ascending=False)

@st.cache_data
def create_provincia_chart(df, col):
    fig = px.bar(df, x="PROVINCIA", y=col,
                 text=[format_number(x, 0) for x in df[col]],
                 template="seaborn",
                 labels={"PROVINCIA": "Provincia", col: label_valor},
                 title=f"{label_valor} por Provincia")
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_tickangle=45)
    return fig

col1, col2 = st.columns(2)
with col1:
    st.subheader(f"{label_valor} por Provincia")
    if not PROVINCIA_df.empty:
        st.plotly_chart(create_provincia_chart(PROVINCIA_df, columna_valor), width="stretch")
    else:
        st.info("No hay datos para mostrar.")

# 2. Donut por evento
@st.cache_data
def create_pie_chart(df, col):
    fig = px.pie(df, values=col, names="NOMBREEVENTOAGRP", hole=0.5)
    fig.update_traces(textposition="outside", textinfo='percent+label')
    return fig

with col2:
    st.subheader(f"{label_valor} por Evento")
    if not filtered_df.empty:
        st.plotly_chart(create_pie_chart(filtered_df, "CANTIDAD"), width="stretch")

# Descargas
cl1, cl2 = st.columns(2)
with cl1:
    with st.expander("Ver datos de Provincias"):
        st.dataframe(
            style_argentina(PROVINCIA_df.style.background_gradient(cmap="Blues", subset=["CANTIDAD"])),
            width="stretch"
        )
        st.download_button("Descargar datos Provincias", PROVINCIA_df.to_csv(index=False).encode('utf-8'), "PROVINCIAS.csv", "text/csv")
with cl2:
    with st.expander("Ver datos de Eventos"):
        eventos_df = filtered_df.groupby("NOMBREEVENTOAGRP", as_index=False)["CANTIDAD"].sum()
        st.dataframe(
            style_argentina(eventos_df.style.background_gradient(cmap="Oranges", subset=['CANTIDAD'])),
            width="stretch"
        )
        st.download_button("Descargar datos Eventos", eventos_df.to_csv(index=False).encode('utf-8'), "Eventos.csv", "text/csv")

# 3. Serie de tiempo
@st.cache_data
def create_time_series(df, col):
    df_copy = df.copy()
    df_copy["mes_año"] = df_copy["FECHAREGISTROCLINICA"].dt.to_period("M")
    linechart = pd.DataFrame(df_copy.groupby(df_copy["mes_año"].dt.strftime("%Y : %b"))["CANTIDAD"].sum()).reset_index()
    
    if col == "Tasas":
        # Necesitamos población por año para la serie de tiempo
        pob_prov = load_population_province()
        pob_prov['juri_nombre'] = pob_prov['juri_nombre'].astype(str).str.title()

        def get_pob(row):
            anio = int(row['mes_año'].split(' : ')[0])
            p = pob_prov[pob_prov['ano'] == anio]['poblacion'].sum()
            return p if p > 0 else 1

        linechart['poblacion'] = linechart.apply(get_pob, axis=1)
        linechart['Tasas'] = (linechart['CANTIDAD'] / linechart['poblacion']) * 100000
        
    fig = px.line(linechart, x="mes_año", y=col, labels={col: label_valor}, height=500, template="gridon")
    return fig, linechart

st.subheader(f'Análisis serie de tiempo ({label_valor})')
if not filtered_df.empty:
    fig2, linechart = create_time_series(filtered_df, columna_valor)
    st.plotly_chart(fig2, width="stretch")
    with st.expander("Datos Serie de tiempo:"):
        st.write(linechart.T.style.background_gradient(cmap="Blues"))
        st.download_button('Descargar datos', linechart.to_csv(index=False).encode("utf-8"), "SerieTiempo.csv", "text/csv")

# 4. Treemap (Provincia -> Departamento)
@st.cache_data
def create_treemap(df, col):
    df_tree = df.groupby(["PROVINCIA", "DEPARTAMENTO", "NOMBREEVENTOAGRP"], as_index=False)["CANTIDAD"].sum()
    
    if col == "Tasas":
        df_tree = pd.merge(df_tree, PROVINCIA_df[['PROVINCIA', 'poblacion']], on='PROVINCIA', how='left')
        df_tree['Tasas'] = (df_tree['CANTIDAD'] / df_tree['poblacion']) * 100000
        
    fig = px.treemap(df_tree, path=["PROVINCIA", "DEPARTAMENTO"],
                     values=col, hover_data=[col], color="PROVINCIA",
                     title=f"Distribución Jerárquica ({label_valor}): Provincia -> Departamento")
    fig.update_layout(width=800, height=650)
    return fig

st.subheader(f"Vista detallada ({label_valor}): Provincia y Departamento")
if not filtered_df.empty:
    st.plotly_chart(create_treemap(filtered_df, columna_valor), width="stretch")

# 5. Tabla de ejemplo
st.subheader("Resumen de datos")
with st.expander("Ver tabla resumen"):
    if not filtered_df.empty:
        # Muestra columnas relevantes para el análisis nacional
        cols_view = ["PROVINCIA", "DEPARTAMENTO", "NOMBREEVENTOAGRP", "GRUPO", "ANIO", "SEMANA", "CANTIDAD"]
        # Filtrar solo columnas que existen
        cols_view = [c for c in cols_view if c in filtered_df.columns]
        
        sample = filtered_df.head(10)[cols_view]
        fig = ff.create_table(sample, colorscale="Spectral")
        st.plotly_chart(fig, width="stretch")

# 6. Tabla pivot mensual
meses_espanol = OrderedDict({1:'Ene',2:'Feb',3:'Mar',4:'Abr',5:'May',6:'Jun',7:'Jul',8:'Ago',9:'Sep',10:'Oct',11:'Nov',12:'Dic'})
meses_orden = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

@st.cache_data
def create_pivot_table(df):
    df_copy = df.copy()
    df_copy["month_num"] = df_copy["FECHAREGISTROCLINICA"].dt.month
    df_copy["month"] = df_copy["month_num"].map(meses_espanol)
    pivot = pd.pivot_table(df_copy, values="CANTIDAD", index="NOMBREEVENTOAGRP",
                           columns="month", fill_value=0, aggfunc="sum")
    # Reordenar columnas
    cols_existentes = [col for col in meses_orden if col in pivot.columns]
    pivot = pivot[cols_existentes]
    return pivot

st.markdown("### Tabla por evento y mes")
if not filtered_df.empty:
    pivot = create_pivot_table(filtered_df)
    st.write(pivot.style.background_gradient(cmap="Blues", axis=1))
    st.download_button("Descargar tabla mensual", pivot.to_csv().encode('utf-8'), "tabla_mensual.csv", "text/csv")
else:
    st.info("No hay datos")

st.markdown("---")
st.caption(f"Total de registros filtrados: **{len(filtered_df):,}** casos")
