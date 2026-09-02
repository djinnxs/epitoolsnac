import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import os
import warnings
import logging
from datetime import date, timedelta
from utils.common import query_duckdb, get_distinct_years, get_distinct_provinces

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

st.set_page_config(page_title="Alertas Automáticas Nacionales", page_icon="🚨", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }

    .ews-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border-radius: 16px; padding: 24px; margin-bottom: 20px; text-align: center;
        border: 1px solid #e94560;
    }
    .ews-header h2 { color: #e94560; font-size: 1.8rem; margin: 0; }
    .ews-header p  { color: #a8b2d8; margin: 8px 0 0; }

    .alert-rojo    { background: linear-gradient(90deg, #3d0a10, #220005); border-left: 6px solid #ff4b2b;
                     border-radius: 12px; padding: 18px; margin: 10px 0; color: #ffffff;
                     box-shadow: 0 4px 15px rgba(233, 69, 96, 0.1); }
    .alert-amarillo{ background: linear-gradient(90deg, #3d2c00, #221a00); border-left: 6px solid #ffd700;
                     border-radius: 12px; padding: 18px; margin: 10px 0; color: #ffffff; }
    .alert-verde   { background: linear-gradient(90deg, #0a2d12, #001a08); border-left: 6px solid #00e676;
                     border-radius: 12px; padding: 18px; margin: 10px 0; color: #ffffff; }

    .alert-title  { font-weight: 700; font-size: 1.1rem; color: #ffffff !important; display: block; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.5)); }
    .alert-detail { font-size: 0.9rem; color: #f0f2f6; margin-top: 8px; line-height: 1.4; }
    .alert-val    { font-weight: 800; color: #ffffff; font-size: 1.05rem; }
    
    .badge-rojo    { background: #ff4b2b; color: white; border-radius: 6px; padding: 4px 12px; font-size:.8rem; font-weight:700; }
    .badge-amarillo{ background: #ffd700; color: #000; border-radius: 6px; padding: 4px 12px; font-size:.8rem; font-weight:700; }
    .badge-verde   { background: #00e676; color: #000; border-radius: 6px; padding: 4px 12px; font-size:.8rem; font-weight:700; }

    .stat-box { background: #16213e; border-radius: 12px; padding: 16px; text-align: center;
                border: 1px solid #0f3460; }
    .stat-box h2 { font-size: 2rem; margin: 0; }
    .stat-box p  { color: #a8b2d8; font-size: .8rem; margin: 4px 0 0; }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="ews-header">
    <h2>🚨 Sistema de Alerta Temprana (EWS) Automático</h2>
    <p>Escaneo en tiempo real de todos los eventos y departamentos — detecta brotes sin búsqueda manual</p>
    <div style='margin-top: 12px; font-weight: bold; color: #ffd700; font-size: 1.2rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 10px;'>
        📅 Semana Epidemiológica Actual: {semana_actual} del {hoy.year}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Filtros ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    years = get_distinct_years()
    anio  = st.selectbox("Año de análisis", years)
with col2:
    semana_actual = get_epi_week(date.today())
    semana = st.number_input("Semana epidemiológica", min_value=1, max_value=52,
                             value=min(semana_actual, 52))
with col3:
    umbral_pct_alerta = st.slider(
        "% de alerta (percentil de zona Alerta)", 50, 90, 75,
        help="Percentil del corredor endémico. 75=Q75 clásico (zona Alerta)"
    )

col4, col5 = st.columns(2)
with col4:
    provincias = get_distinct_provinces()
    provincia_seleccionada = st.selectbox(
        "Filtrar por provincia",
        ["Nacional"] + provincias,
        index=0,
        help="Selecciona una provincia para limitar el análisis, o deja Nacional para revisar todo el país."
    )
with col5:
    min_casos = st.number_input("Casos mínimos para mostrar", min_value=0, value=5)

if st.button("🔍 Escanear Brotes Automáticamente", type="primary"):

    with st.spinner("Analizando todos los eventos y departamentos... (puede tomar unos segundos)"):

        # ── Cargar datos históricos (5 años antes) para cuartiles ─────────────
        anio_desde = anio - 5
        geo_filter = f"AND PROVINCIA = '{provincia_seleccionada}'" if provincia_seleccionada != "Nacional" else ""

        query_hist = f"""
        SELECT DEPARTAMENTO, NOMBREEVENTOAGRP, ANIO, SEMANA, SUM(CANTIDAD) AS CANTIDAD
        FROM {{parquet}}
        WHERE ANIO >= {anio_desde}
          AND ANIO <  {anio}
          AND SEMANA = {semana}
          AND SEMANA != 53
          {geo_filter}
        GROUP BY DEPARTAMENTO, NOMBREEVENTOAGRP, ANIO, SEMANA
        """
        df_hist = query_duckdb(query_hist)

        # ── Cargar datos del año actual ───────────────────────────────────────
        query_act = f"""
        SELECT DEPARTAMENTO, NOMBREEVENTOAGRP, SUM(CANTIDAD) AS CANTIDAD_ACTUAL
        FROM {{parquet}}
        WHERE ANIO = {anio}
          AND SEMANA = {semana}
          AND SEMANA != 53
          {geo_filter}
        GROUP BY DEPARTAMENTO, NOMBREEVENTOAGRP
        """
        df_actual = query_duckdb(query_act)

        # ── Cargar datos semana anterior (para variación %) ───────────────────
        sem_prev = max(1, semana - 1)
        query_prev = f"""
        SELECT DEPARTAMENTO, NOMBREEVENTOAGRP, SUM(CANTIDAD) AS CANTIDAD_PREV
        FROM {{parquet}}
        WHERE ANIO = {anio}
          AND SEMANA = {sem_prev}
          {geo_filter}
        GROUP BY DEPARTAMENTO, NOMBREEVENTOAGRP
        """
        df_prev = query_duckdb(query_prev)

    if df_hist.empty or df_actual.empty:
        st.warning("No hay datos suficientes para el análisis.")
        st.stop()

    # ── Calcular cuartiles por (DEPARTAMENTO, EVENTO) ─────────────────────────
    cuartiles = df_hist.groupby(['DEPARTAMENTO', 'NOMBREEVENTOAGRP'])['CANTIDAD'].agg(
        q25=lambda x: x.quantile(0.25),
        q50=lambda x: x.quantile(0.50),
        q75=lambda x: x.quantile(umbral_pct_alerta / 100),
        media=lambda x: x.mean()
    ).reset_index()

    # ── Merge con datos actuales ───────────────────────────────────────────────
    merged = df_actual.merge(cuartiles, on=['DEPARTAMENTO', 'NOMBREEVENTOAGRP'], how='left')
    merged = merged.merge(df_prev, on=['DEPARTAMENTO', 'NOMBREEVENTOAGRP'], how='left')
    merged['CANTIDAD_PREV'] = merged['CANTIDAD_PREV'].fillna(0)

    # ── Clasificar alertas ────────────────────────────────────────────────────
    def clasificar(row):
        ca = row['CANTIDAD_ACTUAL']
        if pd.isna(row['q75']):
            return 'Sin datos históricos', 'gris'
        if ca >= row['q75']:
            return 'Alerta', 'rojo'
        elif ca >= row['q50']:
            return 'Precaución', 'amarillo'
        else:
            return 'Normal', 'verde'

    merged[['estado', 'color']] = merged.apply(
        lambda r: pd.Series(clasificar(r)), axis=1
    )

    # Variación porcentual respecto a semana anterior
    merged['variacion_pct'] = np.where(
        merged['CANTIDAD_PREV'] > 0,
        ((merged['CANTIDAD_ACTUAL'] - merged['CANTIDAD_PREV']) / merged['CANTIDAD_PREV'] * 100).round(1),
        np.nan
    )

    # Filtrar por casos mínimos
    merged = merged[merged['CANTIDAD_ACTUAL'] >= min_casos]

    # ── Métricas resumen ──────────────────────────────────────────────────────
    n_rojo    = (merged['color'] == 'rojo').sum()
    n_amarillo= (merged['color'] == 'amarillo').sum()
    n_verde   = (merged['color'] == 'verde').sum()
    n_total   = len(merged)

    st.markdown(f"### 📊 Resumen SE{semana} — {anio}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="stat-box"><h2 style="color:#e94560">{n_rojo}</h2><p>🚨 Alertas (Brotes)</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="stat-box"><h2 style="color:#ffd700">{n_amarillo}</h2><p>⚠️ Precauciones</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="stat-box"><h2 style="color:#00e676">{n_verde}</h2><p>✅ Situación Normal</p></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="stat-box"><h2 style="color:#a8b2d8">{n_total}</h2><p>Pares evento-depto analizados</p></div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Filtro de visualización ───────────────────────────────────────────────
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        filtro_estado = st.multiselect(
            "Filtrar por estado",
            ['Alerta', 'Precaución', 'Normal'],
            default=['Alerta', 'Precaución']
        )
    with col_f2:
        buscar = st.text_input("🔍 Buscar evento o departamento", "")

    df_show = merged.copy()
    if filtro_estado:
        df_show = df_show[df_show['estado'].isin(filtro_estado)]
    if buscar:
        mask = (df_show['NOMBREEVENTOAGRP'].str.contains(buscar, case=False, na=False) |
                df_show['DEPARTAMENTO'].str.contains(buscar, case=False, na=False))
        df_show = df_show[mask]

    # Ordenar: Alertas primero, luego Precaución, luego normal
    orden_estado = {'Alerta': 0, 'Precaución': 1, 'Normal': 2, 'Sin datos históricos': 3}
    df_show['_ord'] = df_show['estado'].map(orden_estado)
    df_show = df_show.sort_values(['_ord', 'CANTIDAD_ACTUAL'], ascending=[True, False]).drop(columns='_ord')

    # ── Renderizar tarjetas de alerta ─────────────────────────────────────────
    st.markdown(f"**{len(df_show)} situaciones encontradas**")

    emojis   = {'rojo': '🚨', 'amarillo': '⚠️', 'verde': '✅', 'gris': 'ℹ️'}
    colores  = {'rojo': 'rojo', 'amarillo': 'amarillo', 'verde': 'verde', 'gris': 'verde'}
    badges   = {'rojo': 'ALERTA', 'amarillo': 'PRECAUCIÓN', 'verde': 'NORMAL', 'gris': 'SIN HIST.'}

    for _, row in df_show.iterrows():
        c      = row['color']
        emoji  = emojis[c]
        badge  = badges[c]
        var_str = f"▲ {row['variacion_pct']:.1f}% vs SE{sem_prev}" if not np.isnan(row.get('variacion_pct', np.nan)) else ''
        q75_str = f"{row['q75']:.0f}" if not pd.isna(row.get('q75')) else 'N/A'

        st.markdown(f"""
        <div class="alert-{colores[c]}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="alert-title">{emoji} <b>{row['NOMBREEVENTOAGRP']}</b> — <i>{row['DEPARTAMENTO']}</i></span>
                <span class="badge-{colores[c]}">{badge}</span>
            </div>
            <div class="alert-detail">
                Casos semana {int(semana)}: <span class="alert-val">{int(row['CANTIDAD_ACTUAL'])}</span>
                &nbsp;|&nbsp; Umbral Q{umbral_pct_alerta}: <span style="font-weight:600">{q75_str}</span>
                &nbsp;|&nbsp; Mediana histórica: <span>{row['media']:.0f}</span>
                <br>
                <span style="color:{'#ffaaaa' if row.get('variacion_pct',0)>0 else '#aaffaa'}; font-weight:600">{var_str}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Tabla descargable ─────────────────────────────────────────────────────
    with st.expander("📋 Ver tabla completa y descargar"):
        cols_export = ['DEPARTAMENTO', 'NOMBREEVENTOAGRP', 'CANTIDAD_ACTUAL',
                       'CANTIDAD_PREV', 'variacion_pct', 'q50', 'q75', 'media', 'estado']
        df_export = df_show[cols_export].rename(columns={
            'DEPARTAMENTO': 'Departamento',
            'NOMBREEVENTOAGRP': 'Evento',
            'CANTIDAD_ACTUAL': f'Casos SE{semana}',
            'CANTIDAD_PREV': f'Casos SE{sem_prev}',
            'variacion_pct': 'Variación %',
            'q50': 'Mediana (Q50)',
            'q75': f'Umbral Alerta (Q{umbral_pct_alerta})',
            'media': 'Media histórica',
            'estado': 'Estado'
        })
        st.dataframe(df_export, width="stretch")

        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Alertas')
        st.download_button(
            "📥 Descargar Excel de Alertas",
            data=output.getvalue(),
            file_name=f"alertas_SE{semana}_{anio}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
