import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta
from utils.common import query_duckdb, get_distinct_years

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

st.set_page_config(page_title="Rastreador de Sindemias", page_icon="🦠", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .sind-header {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a0f2e 50%, #2e1a0f 100%);
        border-radius: 14px; padding: 22px; margin-bottom: 18px; text-align: center;
        border: 1px solid #ff6b35;
    }
    .sind-header h2 { color: #ff6b35; margin: 0; font-size: 1.7rem; }
    .sind-header p  { color: #a8b2d8; margin: 6px 0 0; font-size: .9rem; }
    .alerta-colapso {
        background: linear-gradient(90deg, #2d0a00, #3d1200);
        border: 2px solid #ff6b35; border-radius: 12px;
        padding: 18px; margin: 12px 0;
        color: #ffe0d0;
        animation: pulse 2s ease-in-out infinite;
    }
    .alerta-colapso b { color: #ff9070; }
    @keyframes pulse {
        0%, 100% { border-color: #ff6b35; }
        50%       { border-color: #ff0000; box-shadow: 0 0 15px rgba(255,0,0,0.4); }
    }
    .metric-sind { background: #1a1a2e; border-radius: 10px; padding: 14px; text-align: center;
                   border: 1px solid #2d2d5e; }
    .metric-sind h2 { font-size: 1.8rem; margin: 0; }
    .metric-sind p  { color: #a8b2d8; font-size: .8rem; margin: 4px 0 0; }
    .preset-chip {
        display: inline-block; background: #1e2a3e; border: 1px solid #4a6fa5;
        border-radius: 20px; padding: 4px 12px; margin: 3px;
        color: #7eb8f7; font-size: .82rem; cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="sind-header">
    <h2>🦠 Rastreador de Sindemias — Superposición de Patógenos</h2>
    <p>Analiza la presión simultánea de múltiples eventos sobre el sistema de salud — ¿hay riesgo de colapso?</p>
    <div style='margin-top: 10px; font-weight: bold; color: #ffeb3b; font-size: 1.1rem; border-top: 1px dotted rgba(255,255,255,0.2); padding-top: 8px;'>
        📅 Semana Epidemiológica Actual: {semana_actual} del {hoy.year}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Presets de sindemias ───────────────────────────────────────────────────────
PRESETS = {
    "🌬️ Respiratorio Invierno": ["INFLUENZA - ENFERMEDAD TIPO INFLUENZA (ETI)", "IRAG", "BRONQUIOLITIS", "NEUMONIA"],
    "🦟 Vectorial (Artrópodos)": ["DENGUE", "PALUDISMO/MALARIA", "LEISHMANIASIS", "CHAGAS"],
    "🧒 Pediátrico": ["BRONQUIOLITIS", "NEUMONIA", "MENINGITIS-ENCEFALITIS", "VARICELA"],
    "🦠 Gastrointestinal": ["HEPATITIS VIRALES", "SINDROME UREMICO HEMOLITICO (SUH)"],
}

# ── Filtros ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 2])
with col1:
    years = get_distinct_years()
    anio  = st.selectbox("Año", years)

with col2:
    preset_elegido = st.selectbox("Preset de sindemia", ["-- Personalizado --"] + list(PRESETS.keys()))

# Cargar lista de eventos disponibles
@st.cache_data
def get_all_events():
    from utils.common import query_duckdb
    df = query_duckdb("SELECT DISTINCT NOMBREEVENTOAGRP FROM {parquet} ORDER BY NOMBREEVENTOAGRP")
    return df['NOMBREEVENTOAGRP'].tolist() if not df.empty else []

all_events = get_all_events()

if preset_elegido != "-- Personalizado --":
    default_ev = [e for e in PRESETS[preset_elegido] if e in all_events]
else:
    default_ev = all_events[:4] if len(all_events) >= 4 else all_events

eventos_sel = st.multiselect(
    "Eventos a analizar (seleccioná los patógenos a superponer)",
    options=all_events,
    default=default_ev,
    help="Seleccioná 2 o más eventos para ver su efecto combinado sobre el sistema de salud."
)

col3, col4, col5 = st.columns(3)
with col3:
    nivel_geo = st.radio("Nivel geográfico", ["Total provincia", "Por departamento"], horizontal=True)
with col4:
    umbral_colapso = st.number_input(
        "Umbral de alerta de colapso (casos totales combinados)",
        min_value=10, max_value=500000, value=5000,
        step=500,
        help="Si la suma de casos combinados supera este valor en una semana, se emite alerta de colapso. Ajustá según la escala de tu región."
    )
with col5:
    comparar_anio_ant = st.checkbox("Comparar con año anterior", value=True)

if len(eventos_sel) < 2:
    st.info("Seleccioná al menos 2 eventos para analizar la sindemia.")
    st.stop()

if st.button("🦠 Analizar Sindemia", type="primary"):

    with st.spinner("Calculando superposición de patógenos..."):

        eventos_sql = "', '".join([e.replace("'", "''") for e in eventos_sel])
        anios_query = f"{anio - 1}, {anio}" if comparar_anio_ant else str(anio)

        geo_group = "DEPARTAMENTO, " if nivel_geo == "Por departamento" else ""
        geo_sel   = f", DEPARTAMENTO" if nivel_geo == "Por departamento" else ""

        query = f"""
        SELECT ANIO, SEMANA, NOMBREEVENTOAGRP{geo_sel}, SUM(CANTIDAD) AS CASOS
        FROM {{parquet}}
        WHERE ANIO IN ({anios_query})
          AND NOMBREEVENTOAGRP IN ('{eventos_sql}')
          AND SEMANA != 53
        GROUP BY ANIO, SEMANA, {geo_group}NOMBREEVENTOAGRP
        ORDER BY ANIO, SEMANA
        """
        df = query_duckdb(query)

    if df.empty:
        st.warning("No hay datos para la combinación seleccionada.")
        st.stop()

    df_anio = df[df['ANIO'] == anio].copy()

    # ── Total combinado por semana ─────────────────────────────────────────────
    total_semana = df_anio.groupby('SEMANA')['CASOS'].sum().reset_index().rename(columns={'CASOS': 'TOTAL'})

    # ── Sugerir umbral automático si el actual parece demasiado bajo ──────────
    mediana_total  = total_semana['TOTAL'].median()
    p90_total      = int(total_semana['TOTAL'].quantile(0.90))
    if umbral_colapso < mediana_total:
        st.info(
            f"💡 **Sugerencia:** El umbral actual ({umbral_colapso:,}) es menor a la mediana semanal "
            f"({mediana_total:,.0f} casos), lo que activa la alerta en casi todas las semanas. "
            f"Para este conjunto de datos se recomienda un umbral de al menos **{p90_total:,} casos** (percentil 90)."
        )

    # ── Métricas ───────────────────────────────────────────────────────────────
    pico_total   = total_semana['TOTAL'].max()
    sem_pico     = int(total_semana.loc[total_semana['TOTAL'].idxmax(), 'SEMANA'])
    semanas_alerta = (total_semana['TOTAL'] > umbral_colapso).sum()
    total_acum   = total_semana['TOTAL'].sum()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-sind"><h2 style="color:#ff6b35">{int(pico_total):,}</h2><p>Casos combinados en pico (SE{sem_pico})</p></div>', unsafe_allow_html=True)
    with m2:
        color_al = '#e94560' if semanas_alerta > 0 else '#00e676'
        st.markdown(f'<div class="metric-sind"><h2 style="color:{color_al}">{semanas_alerta}</h2><p>Semanas con riesgo de colapso (>{umbral_colapso:,} casos)</p></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-sind"><h2 style="color:#7eb8f7">{total_acum:,}</h2><p>Total acumulado combinado {anio}</p></div>', unsafe_allow_html=True)
    with m4:
        n_eventos = df_anio['NOMBREEVENTOAGRP'].nunique()
        st.markdown(f'<div class="metric-sind"><h2 style="color:#a8b2d8">{n_eventos}</h2><p>Patógenos circulando simultáneamente</p></div>', unsafe_allow_html=True)

    # ── Alerta de colapso ──────────────────────────────────────────────────────
    if semanas_alerta > 0:
        sems_col  = total_semana[total_semana['TOTAL'] > umbral_colapso]['SEMANA'].tolist()
        # Máximo 8 semanas listadas; si hay más, resumir
        if len(sems_col) <= 8:
            sems_str = ", ".join([f"SE{s}" for s in sems_col])
        else:
            sems_str = (
                ", ".join([f"SE{s}" for s in sems_col[:4]])
                + f" ... y {len(sems_col) - 4} semanas más"
            )
        pico_sem   = int(total_semana.loc[total_semana['TOTAL'].idxmax(), 'SEMANA'])
        pico_casos = int(total_semana['TOTAL'].max())
        # Nombres cortos de eventos
        nombres_ev = ', '.join([e.split('(')[0].strip()[:28] for e in eventos_sel[:3]])
        if len(eventos_sel) > 3:
            nombres_ev += f' (+{len(eventos_sel)-3} más)'
        st.markdown(f"""
        <div class="alerta-colapso">
            🚨 <b>ALERTA DE COLAPSO POTENCIAL</b><br>
            En <b>{len(sems_col)} semanas</b> ({sems_str}) la carga combinada de
            <b>{nombres_ev}</b> superó el umbral de <b>{umbral_colapso:,} casos</b>.<br>
            📍 Pico máximo: <b>SE{pico_sem}</b> con <b>{pico_casos:,} casos combinados</b>.<br>
            Las autoridades sanitarias deberían reforzar la capacidad de internación y UTI.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Stacked Area Chart principal ───────────────────────────────────────────
    st.markdown(f"#### 📊 Superposición de Patógenos — {anio}")

    paleta = ['#e94560', '#00b4d8', '#7eb8f7', '#ffd700', '#00e676', '#ff6b35', '#a78bfa', '#f472b6']

    fig = go.Figure()

    for i, ev in enumerate(eventos_sel):
        df_ev = df_anio[df_anio['NOMBREEVENTOAGRP'] == ev].groupby('SEMANA')['CASOS'].sum().reset_index()
        # Completar semanas faltantes con 0
        df_complete = pd.DataFrame({'SEMANA': range(1, 53)})
        df_complete = df_complete.merge(df_ev, on='SEMANA', how='left').fillna(0)

        color = paleta[i % len(paleta)]
        fig.add_trace(go.Scatter(
            x=df_complete['SEMANA'],
            y=df_complete['CASOS'],
            name=ev,
            stackgroup='uno',
            mode='lines',
            line=dict(width=0.5, color=color),
            fillcolor=color.replace('#', 'rgba(').replace(')', ',0.7)') if '(' in color else color,
            hovertemplate='%{fullData.name}<br>SE%{x}: <b>%{y}</b> casos<extra></extra>'
        ))

    # Línea de umbral de colapso
    fig.add_hline(y=umbral_colapso, line_dash='dash', line_color='#e94560',
                  line_width=2, annotation_text=f"Umbral colapso ({umbral_colapso:,})",
                  annotation_position="top right")

    fig.update_layout(
        xaxis_title="Semana Epidemiológica",
        yaxis_title="Casos",
        template="plotly_dark",
        height=480,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, font=dict(size=10)),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        xaxis=dict(range=[1, 52], dtick=4)
    )
    st.plotly_chart(fig, width="stretch")

    # ── Comparación con año anterior ───────────────────────────────────────────
    if comparar_anio_ant:
        st.markdown(f"#### 📉 Comparación {anio - 1} vs {anio} — Carga Total Combinada")

        df_ant = df[df['ANIO'] == anio - 1].groupby('SEMANA')['CASOS'].sum().reset_index()
        df_act = df[df['ANIO'] == anio].groupby('SEMANA')['CASOS'].sum().reset_index()

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Scatter(
            x=df_ant['SEMANA'], y=df_ant['CASOS'],
            name=str(anio - 1), line=dict(color='#a8b2d8', width=2, dash='dot'),
            fill='tozeroy', fillcolor='rgba(168,178,216,0.1)'
        ))
        fig_comp.add_trace(go.Scatter(
            x=df_act['SEMANA'], y=df_act['CASOS'],
            name=str(anio), line=dict(color='#ff6b35', width=2),
            fill='tozeroy', fillcolor='rgba(255,107,53,0.2)'
        ))
        fig_comp.add_hline(y=umbral_colapso, line_dash='dash', line_color='#e94560', line_width=1)
        fig_comp.update_layout(
            xaxis_title="Semana Epidemiológica", yaxis_title="Casos combinados",
            template='plotly_dark', height=350,
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_comp, width="stretch")

    # ── Composición por evento ─────────────────────────────────────────────────
    col_pie, col_top = st.columns(2)
    with col_pie:
        st.markdown("#### 🥧 Composición por evento (total anual)")
        tot_ev = df_anio.groupby('NOMBREEVENTOAGRP')['CASOS'].sum().reset_index()
        tot_ev['short'] = tot_ev['NOMBREEVENTOAGRP'].str[:25] + '...'
        fig_pie = px.pie(tot_ev, values='CASOS', names='short',
                         hole=0.4, color_discrete_sequence=paleta,
                         template='plotly_dark')
        fig_pie.update_layout(height=320, paper_bgcolor='rgba(0,0,0,0)',
                              legend=dict(font=dict(size=9)))
        fig_pie.update_traces(textinfo='percent+value')
        st.plotly_chart(fig_pie, width="stretch")

    with col_top:
        st.markdown("#### 📅 Semanas de mayor carga combinada")
        top_sem = total_semana.sort_values('TOTAL', ascending=False).head(10)
        fig_top = px.bar(top_sem, x='SEMANA', y='TOTAL',
                         color='TOTAL', color_continuous_scale='YlOrRd',
                         labels={'SEMANA': 'Semana', 'TOTAL': 'Casos'},
                         template='plotly_dark')
        fig_top.update_layout(height=320, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        st.plotly_chart(fig_top, width="stretch")
