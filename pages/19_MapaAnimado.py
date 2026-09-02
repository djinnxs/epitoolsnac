import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
import geopandas as gpd
import os
import warnings
import logging
from datetime import date, timedelta
from utils.common import query_duckdb, get_distinct_events, get_distinct_years

# Lógica de Semana Epidemiológica (como en Calendario)
def get_epi_week(fecha):
    """Semana epidemiológica (semanas inician en domingo, SE1 contiene el 4 de enero)."""
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

# Silenciador de avisos molestos
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("streamlit").setLevel(logging.ERROR)

st.set_page_config(page_title="Mapa Animado", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    .map-header {
        background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 100%);
        border-radius: 14px; padding: 20px; margin-bottom: 16px; text-align: center;
        border: 1px solid #4a90d9;
    }
    .map-header h2 { color: #4a90d9; margin: 0; font-size: 1.7rem; }
    .map-header p  { color: #a8b2d8; margin: 6px 0 0; font-size: .9rem; }
    .info-pill {
        display: inline-block; background: #1e3a5f; border-radius: 20px;
        padding: 4px 14px; margin: 3px; color: #7eb8f7; font-size: .82rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="map-header">
    <h2>🗺️ Mapa Animado de Propagación Espacio-Temporal</h2>
    <p>Observa cómo avanza un evento epidemiológico semana a semana en el territorio — dale ▶ Play</p>
    <div style='margin-top: 10px; font-weight: bold; color: #ffeb3b; font-size: 1.1rem; border-top: 1px dotted rgba(255,255,255,0.2); padding-top: 8px;'>
        📅 Semana Epidemiológica Actual: {semana_actual} del {hoy.year}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Cargar GeoJSON ─────────────────────────────────────────────────────────────
@st.cache_data
def load_geojson():
    geojson_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'departamento.json')
    gdf = gpd.read_file(geojson_path)
    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.01, preserve_topology=True)
    return gdf

@st.cache_data
def load_population():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'proyecciones_depto_indec.parquet')
    df   = pd.read_parquet(path)
    df   = df[df['sexo_nombre'] == 'Ambos sexos']
    df   = df.groupby(['ano', 'juri'], as_index=False)['poblacion'].sum()
    df['juri'] = df['juri'].astype(str).str.zfill(5)
    return df

with st.spinner("Cargando datos geográficos..."):
    gdf       = load_geojson()
    pop_df    = load_population()

# ── Filtros ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    years  = get_distinct_years()
    anio   = st.selectbox("Año", years)
with col2:
    events = get_distinct_events()
    evento = st.selectbox("Evento", events)
with col3:
    metrica = st.selectbox("Métrica", ["Casos", "Tasa x100k"])

col4, col5 = st.columns(2)
with col4:
    velocidad = st.select_slider(
        "Velocidad de animación (ms por frame)",
        options=[200, 500, 800, 1200, 2000],
        value=800
    )
with col5:
    sem_rango = st.slider("Rango de semanas a animar", 1, 52, (1, 52))

if st.button("▶ Generar Mapa Animado", type="primary"):

    evento_sql = evento.replace("'", "''")

    query = f"""
    SELECT DEPARTAMENTO, COD_DEPTO, SEMANA, SUM(CANTIDAD) AS CANTIDAD
    FROM {{parquet}}
    WHERE ANIO = {anio}
      AND NOMBREEVENTOAGRP = '{evento_sql}'
      AND SEMANA BETWEEN {sem_rango[0]} AND {sem_rango[1]}
      AND SEMANA != 53
    GROUP BY DEPARTAMENTO, COD_DEPTO, SEMANA
    ORDER BY SEMANA
    """
    df = query_duckdb(query)

    if df.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        st.stop()

    # ── Normalizar COD_DEPTO ────────────────────────────────────────────────────
    df['COD_DEPTO'] = df['COD_DEPTO'].astype(str).str.zfill(5)

    # ── Merge con GeoJSON ───────────────────────────────────────────────────────
    gdf = gdf.rename(columns={'in1': 'COD_DEPTO'})

    # ── Completar todas las combinaciones semana × departamento ────────────────
    all_deptos = gdf['COD_DEPTO'].unique()
    all_sems   = range(sem_rango[0], sem_rango[1] + 1)

    idx = pd.MultiIndex.from_product([all_sems, all_deptos], names=['SEMANA', 'COD_DEPTO'])
    df_full = pd.DataFrame(index=idx).reset_index()
    df_full = df_full.merge(df[['COD_DEPTO', 'SEMANA', 'CANTIDAD']], on=['COD_DEPTO', 'SEMANA'], how='left')
    df_full['CANTIDAD'] = df_full['CANTIDAD'].fillna(0)

    # ── Calcular tasa si es necesario ───────────────────────────────────────────
    if metrica == "Tasa x100k":
        pop_anio = pop_df[pop_df['ano'] == anio][['juri', 'poblacion']]
        df_full  = df_full.merge(pop_anio, left_on='COD_DEPTO', right_on='juri', how='left')
        df_full['TASA']    = (df_full['CANTIDAD'] / df_full['poblacion'].replace(0, pd.NA)) * 100000
        df_full['TASA']    = df_full['TASA'].round(2).fillna(0)
        color_col = 'TASA'
        color_label = 'Tasa x100k'
    else:
        color_col = 'CANTIDAD'
        color_label = 'Casos'
    
    # Calcular un máximo razonable para la escala de colores (basado en p95)
    max_val = df_full[color_col].quantile(0.95)
    if max_val == 0: max_val = 1

    # ── Merge final con nombres de departamento y etiquetas ────────────────────
    mapeo_nombres = gdf[['COD_DEPTO', 'nam']].set_index('COD_DEPTO')['nam'].to_dict()
    df_full['Departamento'] = df_full['COD_DEPTO'].map(mapeo_nombres)
    df_full['SEMANA_LABEL'] = 'SE ' + df_full['SEMANA'].astype(str).str.zfill(2)

    # ── Generar mapa animado ────────────────────────────────────────────────────
    # Convertimos el GeoDF a un diccionario GeoJSON estable
    gdf_dict = gdf.__geo_interface__

    fig = px.choropleth_map(
        df_full,
        geojson=gdf_dict,
        locations='COD_DEPTO',
        featureidkey="properties.COD_DEPTO",
        color=color_col,
        animation_frame='SEMANA_LABEL',
        animation_group='COD_DEPTO',
        hover_name='Departamento',
        hover_data={color_col: ':.2f', 'SEMANA': True, 'COD_DEPTO': False, 'SEMANA_LABEL': False},
        map_style='carto-darkmatter',
        center={'lat': -34.5, 'lon': -64.0},
        zoom=4.0,
        color_continuous_scale='YlOrRd',
        range_color=[0, max_val],
        labels={color_col: color_label, 'SEMANA': 'Semana'}
    )

    fig.update_layout(
        height=680,
        margin=dict(l=0, r=0, t=40, b=0),
        title_text=f"🎬 {evento} — {color_label} por Departamento — {anio}",
        title_x=0.5,
        title_font=dict(size=16, color='white'),
        paper_bgcolor='#0a0a1a',
        font_color='white',
        coloraxis_colorbar=dict(title=color_label, thickness=15),
    )

    # Configurar velocidad de animación
    fig.layout.updatemenus[0].buttons[0].args[1]['frame']['duration'] = velocidad
    fig.layout.updatemenus[0].buttons[0].args[1]['transition']['duration'] = velocidad // 2

    # Actualizar nombres en el hover usando los datos originales para que sea más amigable
    st.plotly_chart(fig, width="stretch", config={'displayModeBar': True})

    # ── Estadísticas complementarias ────────────────────────────────────────────
    st.markdown("---")
    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown("#### 📈 Evolución semanal total (Nacional)")
        evol = df.groupby('SEMANA')['CANTIDAD'].sum().reset_index()
        import plotly.graph_objects as go
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=evol['SEMANA'], y=evol['CANTIDAD'],
            marker_color='rgba(74,144,217,0.8)',
            name='Casos'
        ))
        fig2.update_layout(
            xaxis_title='Semana Epidemiológica', yaxis_title='Casos',
            template='plotly_dark', height=300,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig2, width="stretch")

    with col_s2:
        st.markdown("#### 🏆 Top 10 Departamentos (total del período)")
        top = df.groupby('DEPARTAMENTO')['CANTIDAD'].sum().nlargest(10).reset_index()
        fig3 = px.bar(
            top, x='CANTIDAD', y='DEPARTAMENTO', orientation='h',
            color='CANTIDAD', color_continuous_scale='YlOrRd',
            labels={'CANTIDAD': 'Casos', 'DEPARTAMENTO': 'Departamento'},
            template='plotly_dark'
        )
        fig3.update_layout(
            height=300, showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig3, width="stretch")
