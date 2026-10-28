# pages/23_SerieCronologica.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.common import (
    format_number,
    get_distinct_events,
    get_distinct_provinces,
    get_parquet_path,
    show_data_corte,
)

st.set_page_config(page_title="Serie Cronológica", page_icon="🗓️", layout="wide")

st.markdown("<h1 style='text-align: center;'>🗓️ Serie Cronológica de Casos</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align: center;'>Casos en el tiempo (2018 → actualidad), con media móvil de 4 semanas.<br>"
    "<small>Cada fecha corresponde al inicio de la semana epidemiológica (domingo).</small></p>",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def cargar_series():
    """Carga solo las columnas necesarias y parsea la fecha de registro."""
    path = get_parquet_path().replace('\\', '/')
    df = pd.read_parquet(path, columns=[
        'FECHAREGISTROCLINICA', 'ANIO', 'SEMANA', 'PROVINCIA',
        'NOMBREEVENTOAGRP', 'CANTIDAD',
    ])
    df['FECHA'] = pd.to_datetime(df['FECHAREGISTROCLINICA'], errors='coerce')
    df = df.dropna(subset=['FECHA'])
    df['PROVINCIA'] = df['PROVINCIA'].astype(str)
    df['NOMBREEVENTOAGRP'] = df['NOMBREEVENTOAGRP'].astype(str)
    return df


df = cargar_series()

if df.empty:
    st.error("No hay datos con fecha de registro disponibles.")
    st.stop()

# ==================== FILTROS ====================
col_ev, col_pr = st.columns(2)
with col_ev:
    eventos = get_distinct_events()
    evento = st.selectbox("Evento", ["Todos"] + eventos)
with col_pr:
    provincias = get_distinct_provinces()
    provincia = st.selectbox("Provincia", ["Todos"] + provincias)

min_d = df['FECHA'].min().date()
max_d = df['FECHA'].max().date()

rango = st.date_input("Rango de fechas", (min_d, max_d),
                      min_value=min_d, max_value=max_d)

if isinstance(rango, (tuple, list)):
    if len(rango) == 2:
        d1, d2 = rango
    elif len(rango) == 1:
        d1 = d2 = rango[0]
    else:
        d1, d2 = min_d, max_d
else:
    d1 = d2 = rango

if d1 > d2:
    d1, d2 = d2, d1

f = df
if evento != "Todos":
    f = f[f['NOMBREEVENTOAGRP'] == evento]
if provincia != "Todos":
    f = f[f['PROVINCIA'] == provincia]

d1_ts, d2_ts = pd.Timestamp(d1), pd.Timestamp(d2)
f = f[(f['FECHA'] >= d1_ts) & (f['FECHA'] <= d2_ts)]

if f.empty:
    st.info("No hay datos para los filtros seleccionados.")
    st.stop()

# ==================== SERIE COMPLETA (semanas sin registros = 0) ====================
serie = f.groupby('FECHA', as_index=False)['CANTIDAD'].sum()
serie = serie.set_index('FECHA')
idx = pd.date_range(d1_ts, d2_ts, freq='D')
serie = serie.reindex(idx, fill_value=0)
serie.index.name = 'FECHA'
serie = serie.reset_index()
serie['CANTIDAD'] = serie['CANTIDAD'].astype(int)
# Media móvil de 4 semanas (28 días): suaviza la serie semanal
serie['MEDIA_4S'] = serie['CANTIDAD'].rolling(28, min_periods=7).mean().round(1)

# ==================== KPIs ====================
k1, k2, k3, k4 = st.columns(4)
total = int(serie['CANTIDAD'].sum())
pico = serie.loc[serie['CANTIDAD'].idxmax()]

with k1:
    st.metric("📌 Total casos", format_number(total))
with k2:
    st.metric("🔥 Semana pico", pico['FECHA'].strftime('%d/%m/%Y'),
              delta=f"{format_number(int(pico['CANTIDAD']))} casos",
              delta_color="off")
with k3:
    st.metric("📊 Promedio semanal", format_number(int(serie['CANTIDAD'].mean())))
with k4:
    st.metric("🗓️ Semanas con datos",
              format_number(int((serie['CANTIDAD'] > 0).sum())))

# ==================== GRÁFICO ====================
fig = go.Figure()
fig.add_trace(go.Bar(
    x=serie['FECHA'], y=serie['CANTIDAD'],
    name='Casos por semana', marker_color='#1f77b4', opacity=0.75,
    width=6.5 * 86400000,  # barras anchas: una semana
))
fig.add_trace(go.Scatter(
    x=serie['FECHA'], y=serie['MEDIA_4S'],
    name='Media móvil 4 semanas', mode='lines',
    line=dict(color='#ff7f0e', width=2),
))
fig.update_layout(
    barmode='overlay',
    xaxis_title='Fecha de registro (inicio de semana epidemiológica)',
    yaxis_title='Casos',
    legend_title='',
    height=520,
    template='plotly_white',
    hovermode='x unified',
    margin=dict(l=40, r=20, t=30, b=40),
)
st.plotly_chart(fig, width="stretch")

# ==================== DATOS / DESCARGA ====================
with st.expander("Ver datos de la serie"):
    tabla = serie.rename(columns={'FECHA': 'Fecha', 'CANTIDAD': 'Casos',
                                  'MEDIA_4S': 'Media 4 semanas'})
    st.dataframe(tabla, width="stretch")
    st.download_button(
        "Descargar CSV",
        tabla.to_csv(index=False).encode('utf-8'),
        "serie_cronologica.csv", "text/csv",
    )

st.markdown("---")
show_data_corte()
