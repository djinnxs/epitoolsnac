import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta
from utils.common import query_duckdb, get_distinct_events, get_distinct_departments, get_distinct_years

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

st.set_page_config(page_title="Nowcasting", page_icon="🔬", layout="wide")

st.markdown("""
<style>
    .nowcast-metric {background: linear-gradient(135deg,#1a1a2e,#16213e); border-radius:12px; padding:16px; text-align:center; border:1px solid #0f3460;}
    .nowcast-metric h2 {color:#e94560; margin:0; font-size:2rem;}
    .nowcast-metric p  {color:#a8b2d8; margin:4px 0 0; font-size:.85rem;}
    .info-box {background:#0f3460; border-radius:8px; padding:12px; border-left:4px solid #e94560; color:#ccd6f6; font-size:.9rem; margin-bottom:12px;}
</style>
""", unsafe_allow_html=True)

st.markdown(f'''<center>
    <h3 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;">🔬 Nowcasting — Estimación de casos en tiempo real</h3>
    <div style="background-color: #1a1a2e; color: #ffeb3b; padding: 10px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #e94560;">
        📅 Semana Epidemiológica Actual: <b>{semana_actual}</b> del {hoy.year}
    </div>
</center>''', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
<b>¿Qué es el Nowcasting?</b> Las últimas 2-4 semanas epidemiológicas <i>siempre</i> están incompletas porque
los establecimientos tardan en reportar. Este módulo calcula un <b>factor de completitud histórico</b> por semana
del año y lo usa para estimar cuántos casos <i>realmente ocurrieron</i>, sin esperar que los registros se estabilicen.
</div>
""", unsafe_allow_html=True)

# ── Filtros ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    events = get_distinct_events()
    evento = st.selectbox("Evento", events)
with col2:
    years = get_distinct_years()
    anio = st.selectbox("Año de análisis", years)
with col3:
    semanas_incompletas = st.slider("Semanas recientes a corregir", 2, 6, 4)

col4, col5 = st.columns(2)
with col4:
    nivel = st.radio("Nivel geográfico", ["Provincia", "Departamento"], horizontal=True)
with col5:
    if nivel == "Departamento":
        deptos = get_distinct_departments()
        depto = st.selectbox("Departamento", deptos)
    else:
        depto = None

if st.button("🔬 Calcular Nowcasting", type="primary"):

    # Ya calculada al inicio

    # ── Cargar datos históricos (años anteriores para calcular factor de completitud)
    anios_hist = list(range(anio - 4, anio))
    anios_str   = ",".join(map(str, anios_hist))
    evento_sql  = evento.replace("'", "''")

    where_geo = f"AND DEPARTAMENTO = '{depto.replace(chr(39), chr(39)*2)}'" if depto else ""

    query_hist = f"""
    SELECT ANIO, SEMANA, SUM(CANTIDAD) AS CANTIDAD
    FROM {{parquet}}
    WHERE ANIO IN ({anios_str})
      AND NOMBREEVENTOAGRP = '{evento_sql}'
      AND SEMANA <= 52
      {where_geo}
    GROUP BY ANIO, SEMANA
    ORDER BY ANIO, SEMANA
    """
    df_hist = query_duckdb(query_hist)

    # ── Cargar datos del año actual ─────────────────────────────────────────────
    query_actual = f"""
    SELECT SEMANA, SUM(CANTIDAD) AS CANTIDAD
    FROM {{parquet}}
    WHERE ANIO = {anio}
      AND NOMBREEVENTOAGRP = '{evento_sql}'
      AND SEMANA <= 52
      {where_geo}
    GROUP BY SEMANA
    ORDER BY SEMANA
    """
    df_actual = query_duckdb(query_actual)

    if df_hist.empty or df_actual.empty:
        st.warning("No hay suficientes datos para calcular el nowcasting.")
        st.stop()

    # ── Calcular factor de completitud histórico ────────────────────────────────
    # Para cada año histórico, calculamos cuántos casos se reportaron acumulado hasta
    # cada semana, respecto al total final del año.
    factores = {}
    for sem in range(1, 53):
        ratios = []
        for yr in anios_hist:
            df_yr = df_hist[df_hist['ANIO'] == yr]
            total_yr = df_yr['CANTIDAD'].sum()
            if total_yr == 0:
                continue
            hasta_sem = df_yr[df_yr['SEMANA'] <= sem]['CANTIDAD'].sum()
            ratios.append(hasta_sem / total_yr)
        factores[sem] = np.mean(ratios) if ratios else 1.0

    # ── Construir curva observada y nowcast ─────────────────────────────────────
    semanas_all = list(range(1, 53))
    casos_obs   = []
    casos_now   = []
    casos_low   = []
    casos_high  = []

    acum_obs = 0
    for sem in semanas_all:
        row = df_actual[df_actual['SEMANA'] == sem]
        c   = int(row['CANTIDAD'].values[0]) if not row.empty else 0
        acum_obs += c
        casos_obs.append(acum_obs if sem <= semana_actual else None)

        # Para las últimas semanas aplicamos corrección
        if sem > semana_actual:
            casos_now.append(None); casos_low.append(None); casos_high.append(None)
        elif sem >= semana_actual - semanas_incompletas and factores.get(sem, 1.0) > 0:
            factor     = factores[sem]
            estimado   = acum_obs / factor
            incert     = estimado * 0.10  # ±10% de incertidumbre
            casos_now.append(round(estimado))
            casos_low.append(round(estimado - incert))
            casos_high.append(round(estimado + incert))
        else:
            casos_now.append(None); casos_low.append(None); casos_high.append(None)

    # ── Corrección puntual por semana (no acumulado) ────────────────────────────
    casos_obs_sem   = []
    casos_now_sem   = []
    casos_low_sem   = []
    casos_high_sem  = []

    for sem in semanas_all:
        row = df_actual[df_actual['SEMANA'] == sem]
        c   = int(row['CANTIDAD'].values[0]) if not row.empty else 0
        casos_obs_sem.append(c if sem <= semana_actual else None)

        if sem > semana_actual:
            casos_now_sem.append(None); casos_low_sem.append(None); casos_high_sem.append(None)
        elif sem >= semana_actual - semanas_incompletas and factores.get(sem, 1.0) > 0:
            # factor puntual: promedio de casos en esa semana vs total del año
            ratios_sem = []
            for yr in anios_hist:
                df_yr   = df_hist[df_hist['ANIO'] == yr]
                total   = df_yr['CANTIDAD'].sum()
                sem_val = df_yr[df_yr['SEMANA'] == sem]['CANTIDAD'].sum()
                if total > 0:
                    ratios_sem.append(sem_val / total)
            f_sem = np.mean(ratios_sem) if ratios_sem else 0.0
            if f_sem > 0:
                est = c / f_sem
                inc = est * 0.15
                casos_now_sem.append(round(est))
                casos_low_sem.append(round(max(0, est - inc)))
                casos_high_sem.append(round(est + inc))
            else:
                casos_now_sem.append(c); casos_low_sem.append(c); casos_high_sem.append(c)
        else:
            casos_now_sem.append(None); casos_low_sem.append(None); casos_high_sem.append(None)

    # ── Métricas resumen ────────────────────────────────────────────────────────
    total_obs  = sum(x for x in casos_obs_sem if x is not None)
    last_est   = next((x for x in reversed(casos_now_sem) if x is not None), total_obs)
    last_obs   = next((x for x in reversed(casos_obs_sem) if x is not None), 0)
    factor_ult = last_est / last_obs if last_obs > 0 else 1.0

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="nowcast-metric"><h2>{total_obs:,}</h2><p>Casos reportados SE{semana_actual}</p></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="nowcast-metric"><h2>{last_est:,}</h2><p>Nowcast semana actual</p></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="nowcast-metric"><h2>{factor_ult:.2f}x</h2><p>Factor de corrección</p></div>', unsafe_allow_html=True)
    with m4:
        casos_faltantes = max(0, last_est - last_obs)
        st.markdown(f'<div class="nowcast-metric"><h2>~{casos_faltantes:,}</h2><p>Casos aún no reportados (est.)</p></div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Gráfico ─────────────────────────────────────────────────────────────────
    fig = go.Figure()

    # Banda de incertidumbre
    sems_valid = [s for s, v in zip(semanas_all, casos_now_sem) if v is not None]
    high_valid = [v for v in casos_high_sem if v is not None]
    low_valid  = [v for v in casos_low_sem  if v is not None]

    fig.add_trace(go.Scatter(
        x=sems_valid + sems_valid[::-1],
        y=high_valid + low_valid[::-1],
        fill='toself', fillcolor='rgba(233,69,96,0.15)',
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo='skip', name='Intervalo ±15%'
    ))

    # Casos observados
    fig.add_trace(go.Bar(
        x=semanas_all,
        y=casos_obs_sem,
        name='Casos reportados',
        marker_color='rgba(100,149,237,0.7)',
        marker_line_color='rgba(100,149,237,1)',
        marker_line_width=1
    ))

    # Nowcast
    fig.add_trace(go.Scatter(
        x=sems_valid,
        y=[casos_now_sem[i] for i, s in enumerate(semanas_all) if s in sems_valid],
        name='Nowcast (estimación)',
        mode='markers+lines',
        line=dict(color='#e94560', width=2, dash='dot'),
        marker=dict(size=8, symbol='diamond', color='#e94560')
    ))

    # Línea de semana actual
    fig.add_vline(x=semana_actual, line_dash='dash', line_color='yellow',
                  annotation_text=f"SE{semana_actual} (hoy)", annotation_position="top right")

    geo_label = depto if depto else "Nacional"
    fig.update_layout(
        title=f"Nowcasting — {evento} | {geo_label} | {anio}",
        xaxis_title="Semana Epidemiológica",
        yaxis_title="Casos",
        template="plotly_dark",
        height=500,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, width="stretch")

    # ── Tabla de factores ───────────────────────────────────────────────────────
    with st.expander("📋 Factores de completitud histórica por semana"):
        df_factores = pd.DataFrame({
            'Semana': list(factores.keys()),
            'Factor de completitud (acumulado)': [round(v, 4) for v in factores.values()],
            'Completitud %': [f"{v*100:.1f}%" for v in factores.values()]
        })
        st.dataframe(df_factores, width="stretch")
        st.caption(f"Basado en {len(anios_hist)} años históricos: {anios_hist}")
