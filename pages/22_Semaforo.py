import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import os
from datetime import date, timedelta
from utils.common import query_duckdb, get_distinct_events, get_distinct_years

# Lógica de Semana Epidemiológica (como en Calendario)
def get_epi_week(fecha):
    """Semana epidemiologica (semanas inician en domingo, SE1 contiene el 4 de enero)."""
    anio = fecha.year
    def inicio_se_1(year):
        cuatro_enero = date(year, 1, 4)
        retroceso = (cuatro_enero.weekday() + 1) % 7
        return cuatro_enero - timedelta(days=retroceso)
    inicio_actual = inicio_se_1(anio)
    if fecha < inicio_actual:
        inicio_anterior = inicio_se_1(anio - 1)
        return ((fecha - inicio_anterior).days // 7) + 1
    inicio_proximo = inicio_se_1(anio + 1)
    if fecha >= inicio_proximo:
        return 1
    return ((fecha - inicio_actual).days // 7) + 1

hoy = date.today()
semana_actual = get_epi_week(hoy)
import warnings

# Silenciar avisos de deprecación que ensucian la consola
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
# También intentamos silenciar avisos específicos de Streamlit si es posible vía python
import logging
logging.getLogger("streamlit").setLevel(logging.ERROR)

st.set_page_config(page_title="Semáforo de Riesgo", page_icon="🚦", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .sem-header {
        background: linear-gradient(135deg, #0a1a0a 0%, #1a2e1a 50%, #0f1f0f 100%);
        border-radius: 14px; padding: 22px; margin-bottom: 18px; text-align: center;
        border: 1px solid #00e676;
    }
    .sem-header h2 { color: #00e676; margin: 0; font-size: 1.7rem; }
    .sem-header p  { color: #a8b2d8; margin: 6px 0 0; font-size: .9rem; }
    .legend-box {
        display: flex; gap: 16px; justify-content: center; margin: 12px 0;
        flex-wrap: wrap;
    }
    .leg-item {
        display: flex; align-items: center; gap: 8px;
        background: #1a1a2e; border-radius: 8px; padding: 8px 14px;
        font-size: .85rem; color: #ccd6f6;
    }
    .dot { width: 16px; height: 16px; border-radius: 50%; display: inline-block; }
    .rojo    { background: #e94560; }
    .amarillo{ background: #ffd700; }
    .verde   { background: #00e676; }
    .gris    { background: #8892b0; }
    .summary-card {
        border-radius: 12px; padding: 16px; text-align: center;
        font-weight: 700; font-size: 1.4rem;
    }
    .card-rojo    { background: linear-gradient(135deg,#2d0a0f,#1a0005); border: 1px solid #e94560; color: #e94560; }
    .card-amarillo{ background: linear-gradient(135deg,#2d2000,#1a1200); border: 1px solid #ffd700; color: #ffd700; }
    .card-verde   { background: linear-gradient(135deg,#0a2d12,#001a08); border: 1px solid #00e676; color: #00e676; }
    .card-gris    { background: linear-gradient(135deg,#1a1a2e,#0f0f1a); border: 1px solid #8892b0; color: #8892b0; }
    .formula-box {
        background: #0f1f3d; border: 1px solid #1e3f6e; border-radius: 10px;
        padding: 12px 18px; font-size: .85rem; color: #a8e6cf; margin: 10px 0;
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="sem-header">
    <h2>🚦 Semáforo de Riesgo Comunitario Integral</h2>
    <p>Índice sintético de riesgo al estilo CDC — Verde / Amarillo / Rojo — sin necesidad de interpretar tasas</p>
    <div style='margin-top: 10px; font-weight: bold; color: #ffeb3b; font-size: 1.1rem; border-top: 1px dashed rgba(255,255,255,0.2); padding-top: 8px;'>
        📅 Semana Epidemiológica Actual: {semana_actual} del {hoy.year}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Leyenda ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="legend-box">
    <div class="leg-item"><span class="dot verde"></span>Verde: Riesgo BAJO — situación bajo control</div>
    <div class="leg-item"><span class="dot amarillo"></span>Amarillo: Riesgo MEDIO — monitoreo activo recomendado</div>
    <div class="leg-item"><span class="dot rojo"></span>Rojo: Riesgo ALTO — intervención urgente recomendada</div>
    <div class="leg-item"><span class="dot gris"></span>Sin datos: insuficiente para clasificar</div>
</div>
""", unsafe_allow_html=True)

with st.expander("📐 ¿Cómo se calcula el Índice de Riesgo?"):
    st.markdown("""
    <div class="formula-box">
    Riesgo = componente_tasa + componente_variacion + componente_corredor
    <br><br>
    • componente_tasa: 0 si Tasa &lt; p25(hist) | 0.5 si p25≤Tasa&lt;p75 | 1.5 si Tasa ≥ p75
    <br>
    • componente_variacion: 0 si var%&lt;0 | 0.5 si 0≤var%&lt;50 | 1.0 si var%≥50
    <br>
    • componente_corredor: 1.0 si casos_actuales > Q75 del corredor endémico | 0 en otro caso
    <br><br>
    🟢 Riesgo &lt; 1.0 → VERDE &nbsp;|&nbsp; 🟡 1.0 ≤ Riesgo &lt; 2.0 → AMARILLO &nbsp;|&nbsp; 🔴 Riesgo ≥ 2.0 → ROJO
    </div>
    """, unsafe_allow_html=True)

# ── Cargar GeoJSON ─────────────────────────────────────────────────────────────
@st.cache_data
def load_geo():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'departamento.json')
    gdf  = gpd.read_file(path)
    gdf['geometry'] = gdf['geometry'].simplify(0.01, preserve_topology=True)
    return gdf

@st.cache_data
def load_pop():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'proyecciones_depto_indec.parquet')
    df   = pd.read_parquet(path)
    df   = df[df['sexo_nombre'] == 'Ambos sexos']
    df   = df.groupby(['ano', 'juri'], as_index=False)['poblacion'].sum()
    df['juri'] = df['juri'].astype(str).str.zfill(5)
    return df

with st.spinner("Cargando datos geográficos..."):
    gdf    = load_geo()
    pop_df = load_pop()

# ── Filtros ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    years  = get_distinct_years()
    anio   = st.selectbox("Año", years)
with col2:
    events = get_distinct_events()
    evento = st.selectbox("Evento", events)
with col3:
    semana_actual = get_epi_week(date.today())
    semana = st.number_input("Semana epidemiológica", 1, 52, min(semana_actual, 52))

col4, col5 = st.columns(2)
with col4:
    peso_tasa  = st.slider("Peso componente tasa", 0.0, 2.0, 1.0, 0.1)
with col5:
    peso_corr  = st.slider("Peso componente corredor", 0.0, 2.0, 1.0, 0.1)

if st.button("🚦 Calcular Semáforo", type="primary"):

    with st.spinner("Calculando índice de riesgo por departamento..."):

        evento_sql  = evento.replace("'", "''")
        anio_desde  = anio - 5

        # ── 1. Datos semana actual ─────────────────────────────────────────────
        q_act = f"""
        SELECT DEPARTAMENTO, COD_DEPTO, CODIGO_PROVINCIA, SUM(CANTIDAD) AS CASOS_ACT
        FROM {{parquet}}
        WHERE ANIO = {anio} AND SEMANA = {semana}
          AND NOMBREEVENTOAGRP = '{evento_sql}'
        GROUP BY DEPARTAMENTO, COD_DEPTO, CODIGO_PROVINCIA
        """
        df_act = query_duckdb(q_act)

        # ── 2. Datos semana anterior ───────────────────────────────────────────
        sem_prev = max(1, semana - 1)
        q_prev = f"""
        SELECT DEPARTAMENTO, SUM(CANTIDAD) AS CASOS_PREV
        FROM {{parquet}}
        WHERE ANIO = {anio} AND SEMANA = {sem_prev}
          AND NOMBREEVENTOAGRP = '{evento_sql}'
        GROUP BY DEPARTAMENTO
        """
        df_prev = query_duckdb(q_prev)

        # ── 3. Datos históricos para cuartiles (corredor + percentil tasa) ─────
        q_hist = f"""
        SELECT DEPARTAMENTO, ANIO, SEMANA, SUM(CANTIDAD) AS CASOS_HIST
        FROM {{parquet}}
        WHERE ANIO BETWEEN {anio_desde} AND {anio - 1}
          AND SEMANA = {semana}
          AND NOMBREEVENTOAGRP = '{evento_sql}'
        GROUP BY DEPARTAMENTO, ANIO, SEMANA
        """
        df_hist = query_duckdb(q_hist)

    if df_act.empty:
        st.warning("No hay datos para la selección. Verificá el año, semana y evento.")
        st.stop()

    # ── Normalizar códigos ─────────────────────────────────────────────────────
    df_act['COD_DEPTO'] = df_act['COD_DEPTO'].astype(str).str.zfill(5)

    # ── Cuartiles históricos por departamento ──────────────────────────────────
    if not df_hist.empty:
        cuart = df_hist.groupby('DEPARTAMENTO')['CASOS_HIST'].agg(
            p25=lambda x: x.quantile(0.25),
            p50='median',
            p75=lambda x: x.quantile(0.75),
            media='mean'
        ).reset_index()
    else:
        cuart = pd.DataFrame(columns=['DEPARTAMENTO', 'p25', 'p50', 'p75', 'media'])

    # ── Merge todo ─────────────────────────────────────────────────────────────
    df = df_act.merge(df_prev, on='DEPARTAMENTO', how='left')
    df = df.merge(cuart, on='DEPARTAMENTO', how='left')

    # ── Población para tasa ────────────────────────────────────────────────────
    pop_anio = pop_df[pop_df['ano'] == anio][['juri', 'poblacion']]
    df = df.merge(pop_anio, left_on='COD_DEPTO', right_on='juri', how='left')

    # ── Calcular componentes del índice ───────────────────────────────────────
    df['CASOS_PREV'] = df['CASOS_PREV'].fillna(0)
    df['poblacion']  = df['poblacion'].replace(0, pd.NA)

    df['TASA'] = (df['CASOS_ACT'] / df['poblacion'] * 100000).round(2)

    # Variación % respecto a semana anterior
    df['VAR_PCT'] = np.where(
        df['CASOS_PREV'] > 0,
        ((df['CASOS_ACT'] - df['CASOS_PREV']) / df['CASOS_PREV'] * 100).round(1),
        np.where(df['CASOS_ACT'] > 0, 100.0, 0.0)
    )

    def comp_tasa(row):
        if pd.isna(row['p25']) or pd.isna(row['TASA']):
            return 0.5
        if row['TASA'] < row['p25']:   return 0.0
        if row['TASA'] < row['p75']:   return 0.5
        return 1.5

    def comp_variacion(var):
        if pd.isna(var) or var < 0:    return 0.0
        if var < 50:                    return 0.5
        return 1.0

    def comp_corredor(row):
        if pd.isna(row['p75']):         return 0.0
        return peso_corr if row['CASOS_ACT'] > row['p75'] else 0.0

    df['C_TASA']  = df.apply(comp_tasa, axis=1) * peso_tasa
    df['C_VAR']   = df['VAR_PCT'].apply(comp_variacion)
    df['C_CORR']  = df.apply(comp_corredor, axis=1)
    df['RIESGO']  = df['C_TASA'] + df['C_VAR'] + df['C_CORR']

    def semaforo(r):
        if pd.isna(r): return 'Sin datos', '#8892b0', 0
        if r < 1.0:    return 'BAJO 🟢',   '#00e676',  1
        if r < 2.0:    return 'MEDIO 🟡',  '#ffd700',  2
        return         'ALTO 🔴',          '#e94560',  3

    df[['NIVEL', 'COLOR_HEX', 'NIVEL_NUM']] = df['RIESGO'].apply(
        lambda r: pd.Series(semaforo(r))
    )

    # ── Resumen por nivel ──────────────────────────────────────────────────────
    st.markdown(f"### 📊 Resumen Semafórico — {evento} | SE{semana} — {anio}")
    n_rojo   = (df['NIVEL_NUM'] == 3).sum()
    n_amar   = (df['NIVEL_NUM'] == 2).sum()
    n_verde  = (df['NIVEL_NUM'] == 1).sum()
    n_gris   = (df['NIVEL_NUM'] == 0).sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="summary-card card-rojo">🔴 {n_rojo}<br><span style="font-size:.75rem;font-weight:400">Riesgo ALTO</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="summary-card card-amarillo">🟡 {n_amar}<br><span style="font-size:.75rem;font-weight:400">Riesgo MEDIO</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="summary-card card-verde">🟢 {n_verde}<br><span style="font-size:.75rem;font-weight:400">Riesgo BAJO</span></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="summary-card card-gris">⚪ {n_gris}<br><span style="font-size:.75rem;font-weight:400">Sin datos</span></div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Mapa del semáforo ──────────────────────────────────────────────────────
    gdf = gdf.rename(columns={'in1': 'COD_DEPTO'})
    merge  = gdf.merge(df, on='COD_DEPTO', how='left')

    col_map, col_tabla = st.columns([3, 2])

    with col_map:
        st.markdown("#### 🗺️ Mapa Semafórico por Departamento")

        # Mapa de riesgo continuo (más expresivo)
        merge['NIVEL_NUM'] = merge['NIVEL_NUM'].fillna(0)
        merge['HOVER_TEXT'] = (
            merge.get('DEPARTAMENTO', merge['COD_DEPTO']).fillna(merge['COD_DEPTO']) +
            "<br>Riesgo: " + merge['NIVEL'].fillna('Sin datos').astype(str) +
            "<br>Casos: " + merge['CASOS_ACT'].fillna(0).astype(int).astype(str) +
            "<br>Tasa: " + merge['TASA'].fillna(0).round(1).astype(str) + " x100k" +
            "<br>Variación: " + merge['VAR_PCT'].fillna(0).round(1).astype(str) + "%"
        )

        fig_map = px.choropleth_map(
            merge,
            geojson=merge.geometry.__geo_interface__,
            locations=merge.index,
            color='NIVEL_NUM',
            color_continuous_scale=[(0, '#8892b0'), (0.33, '#00e676'), (0.66, '#ffd700'), (1.0, '#e94560')],
            range_color=[0, 3],
            hover_name='DEPARTAMENTO',
            custom_data=['NIVEL', 'CASOS_ACT', 'TASA', 'VAR_PCT', 'RIESGO'],
            map_style='carto-darkmatter',
            center={"lat": -38.0, "lon": -63.0},
            zoom=3,
        )

        fig_map.update_traces(
            hovertemplate=(
                "<b>%{hovertext}</b><br>"
                "Nivel: %{customdata[0]}<br>"
                "Casos: %{customdata[1]:.0f}<br>"
                "Tasa: %{customdata[2]:.1f} x100k<br>"
                "Variación: %{customdata[3]:.1f}%<br>"
                "Índice de Riesgo: %{customdata[4]:.2f}<extra></extra>"
            )
        )

        fig_map.update_layout(
            height=600,
            margin=dict(l=0, r=0, t=30, b=0),
            coloraxis_showscale=False,
            paper_bgcolor='#0a0a1a',
        )
        st.plotly_chart(fig_map, width="stretch")

    with col_tabla:
        st.markdown("#### 📋 Ranking de Riesgo")

        cols_show = ['DEPARTAMENTO', 'NIVEL', 'RIESGO', 'CASOS_ACT', 'TASA', 'VAR_PCT']
        cols_exist = [c for c in cols_show if c in df.columns]
        df_tabla = df[cols_exist].copy()
        df_tabla = df_tabla.rename(columns={
            'DEPARTAMENTO': 'Departamento',
            'NIVEL': 'Nivel',
            'RIESGO': 'Índice',
            'CASOS_ACT': 'Casos',
            'TASA': 'Tasa x100k',
            'VAR_PCT': 'Var%'
        })
        df_tabla = df_tabla.sort_values('Índice', ascending=False)
        df_tabla['Índice'] = df_tabla['Índice'].round(2)
        df_tabla['Tasa x100k'] = df_tabla['Tasa x100k'].round(1)
        df_tabla['Var%'] = df_tabla['Var%'].round(1)

        def color_nivel(val):
            if 'ALTO' in str(val):  return 'color: #e94560; font-weight: bold'
            if 'MEDIO' in str(val): return 'color: #ffd700; font-weight: bold'
            if 'BAJO' in str(val):  return 'color: #00e676; font-weight: bold'
            return 'color: #8892b0'

        st.dataframe(
            df_tabla.style.map(color_nivel, subset=['Nivel'])
                          .background_gradient(subset=['Índice'], cmap='RdYlGn_r')
                          .format({'Índice': '{:.2f}', 'Casos': '{:.0f}', 'Tasa x100k': '{:.1f}', 'Var%': '{:.1f}%'}),
            height=560,
            width="stretch"
        )

        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_tabla.to_excel(writer, index=False, sheet_name='Semaforo')
        st.download_button(
            "📥 Descargar Excel Semáforo",
            data=output.getvalue(),
            file_name=f"semaforo_{evento[:20]}_SE{semana}_{anio}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # ── Detalle de los componentes ─────────────────────────────────────────────
    with st.expander("🔍 Detalle de componentes del índice por departamento"):
        cols_det = ['DEPARTAMENTO', 'CASOS_ACT', 'CASOS_PREV', 'VAR_PCT', 'TASA',
                    'p50', 'p75', 'C_TASA', 'C_VAR', 'C_CORR', 'RIESGO', 'NIVEL']
        cols_ex  = [c for c in cols_det if c in df.columns]
        st.dataframe(df[cols_ex].sort_values('RIESGO', ascending=False), width="stretch")
