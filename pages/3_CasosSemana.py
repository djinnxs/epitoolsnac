# pages/3_CasosSemana.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import plotly.express as px
from utils.common import query_duckdb

st.set_page_config(page_title="Epidemiologia", page_icon=":bar_chart:", layout="wide")

# Solo el título sin logo
st.markdown('<center><h3 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;">&#x1F4C8; Casos por semana por año</h3></center>', unsafe_allow_html=True)

# DuckDB query
query = """
SELECT ANIO, SEMANA, NOMBREEVENTOAGRP, GRUPO, CANTIDAD
FROM {parquet}
WHERE SEMANA != 53
"""
df = query_duckdb(query)

if df.empty:
    st.warning("No hay datos disponibles.")
    st.stop()

# Filtros: fila 1 -> Evento | Grupo etario ; fila 2 -> Años | Semana
col1, col2 = st.columns(2)
with col1:
	evento = st.selectbox("Evento", sorted(df["NOMBREEVENTOAGRP"].dropna().unique()))
with col2:
	# Orden fijo para grupos etarios
	GRUPO_ORDER = [
		"< 6 m",
		"6 a 11 m",
		"12 a 23 m",
		"2 a 4",
		"5 a 9",
		"10 a 14",
		"15 a 19",
		"20 a 24",
		"25 a 34",
		"35 a 44",
		"45 a 64",
		"65 a 74",
		">= a 75",
		"Pediát <3",
		"Pediát >=3",
		"Adultos <60",
		"Adultos >=60",
		"Edad Sin Esp."
	]
	available_grupos = list(df["GRUPO"].dropna().unique())
	ordered_grupos = [g for g in GRUPO_ORDER if g in available_grupos]
	remaining_grupos = sorted([g for g in available_grupos if g not in ordered_grupos])
	grupo_options = ordered_grupos + remaining_grupos
	grupo = st.multiselect("Grupo etario", grupo_options)

col3, col4 = st.columns(2)
available_years = sorted(df["ANIO"].dropna().unique())
default_years = available_years[:2] if len(available_years) >= 2 else available_years
with col3:
	anios = st.multiselect("Años", available_years, default=list(default_years))
with col4:
	semana = st.selectbox("Semana", list(range(1, 53)), index=51)

# Aplicar filtros
df_filt = df.copy()
df_filt = df_filt[df_filt["NOMBREEVENTOAGRP"] == evento]
if grupo:
	df_filt = df_filt[df_filt["GRUPO"].isin(grupo)]
if anios:
	df_filt = df_filt[df_filt["ANIO"].isin(anios)]

# Pivot y reindex hasta la semana seleccionada
df_pivot = df_filt.pivot_table(values="CANTIDAD", index="SEMANA", columns="ANIO", aggfunc='sum', fill_value=0)
df_pivot = df_pivot.reindex(range(1, semana + 1), fill_value=0)

if df_pivot.empty:
	st.warning("No hay datos para la combinación de filtros seleccionada.")
else:
	fig = px.line(df_pivot, x=df_pivot.index, y=df_pivot.columns, title=f"{evento} - Comparación por Año (hasta semana {semana})")
	fig.update_xaxes(title="Semana")
	fig.update_yaxes(title="Cantidad")
	st.plotly_chart(fig, width="stretch")