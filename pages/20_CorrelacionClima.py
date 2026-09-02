import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from scipy import stats
import logging
from datetime import date, timedelta
from utils.common import query_duckdb, get_distinct_events, get_distinct_years
import warnings

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

# Silenciar avisos de deprecación molestos
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("streamlit").setLevel(logging.ERROR)

st.set_page_config(page_title="Correlación Clima-Epidemia", page_icon="🌡️", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .corr-header {
        background: linear-gradient(135deg, #0a1628 0%, #1a2e4a 100%);
        border-radius: 14px; padding: 22px; margin-bottom: 18px; text-align: center;
        border: 1px solid #00b4d8;
    }
    .corr-header h2 { color: #00b4d8; margin: 0; font-size: 1.7rem; }
    .corr-header p  { color: #a8b2d8; margin: 6px 0 0; font-size: .9rem; }
    .corr-card {
        background: #10253e; border-radius: 12px; padding: 18px; text-align: center;
        border: 1px solid #0f3460;
    }
    .corr-card h2 { font-size: 2.2rem; margin: 0; }
    .corr-card p  { color: #a8b2d8; font-size: .82rem; margin: 4px 0 0; }
    .insight-box {
        background: linear-gradient(90deg, #0a2040, #112d50);
        border-left: 4px solid #00b4d8; border-radius: 8px;
        padding: 14px 18px; color: #ccd6f6; font-size: .9rem; margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="corr-header">
    <h2>🌡️ Correlación Epidemiológica-Climática con Desfase (Lag)</h2>
    <p>Variable climática desplazada N semanas hacia adelante vs Casos — detecta el lag óptimo</p>
    <div style='margin-top: 10px; font-weight: bold; color: #ffeb3b; font-size: 1.1rem; border-top: 1px dashed rgba(255,255,255,0.2); padding-top: 8px;'>
        📅 Semana Epidemiológica Actual: {semana_actual} del {hoy.year}
    </div>
</div>
""", unsafe_allow_html=True)

# ── Cargar datos climáticos ────────────────────────────────────────────────────
@st.cache_data
def load_clima():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ClimaHisto.parquet')
    df = pd.read_parquet(path)
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    df['ANIO']  = df['Fecha'].dt.isocalendar().year.astype(int)
    df['SEMANA'] = df['Fecha'].dt.isocalendar().week.astype(int)
    df['Temp. Minima (°C)'] = pd.to_numeric(df['Temp. Minima (°C)'], errors='coerce')
    df['Temp. Maxima (°C)'] = pd.to_numeric(df['Temp. Maxima (°C)'], errors='coerce')
    df['Precipitación (mm)'] = pd.to_numeric(df.get('Precipitación (mm)', np.nan), errors='coerce')
    return df

with st.spinner("Cargando datos climáticos..."):
    df_clima = load_clima()

provincias_clima  = sorted(df_clima['PROVINCIA'].dropna().unique())
estaciones_all    = df_clima['Estación'].dropna().unique()

# ── Filtros ────────────────────────────────────────────────────────────────────
st.markdown("### ⚙️ Configuración del análisis")
col1, col2, col3 = st.columns(3)
with col1:
    events = get_distinct_events()
    evento = st.selectbox("Evento epidemiológico", events)
with col2:
    years = get_distinct_years()
    anio  = st.selectbox("Año", years)
with col3:
    tipo_temp = st.selectbox("Variable climática", ["Temp. Maxima (°C)", "Temp. Minima (°C)", "Precipitación (mm)"])

col4, col5, col6 = st.columns(3)
with col4:
    provincia_clima = st.selectbox("Provincia (clima)", provincias_clima, index=0)
with col5:
    estaciones_prov = sorted(df_clima[df_clima['PROVINCIA'] == provincia_clima]['Estación'].unique())
    estacion = st.selectbox("Estación meteorológica", estaciones_prov)
with col6:
    lag_max = st.slider("Lag máximo a analizar (semanas)", 1, 12, 8)

col7, col8 = st.columns(2)
with col7:
    lag_sel = st.slider("Lag a visualizar en gráfico principal", 0, lag_max, 3,
                        help="Desfase en semanas de la temperatura respecto a los casos")
with col8:
    incluir_anios_hist = st.checkbox("Incluir años históricos (-3 años)", value=False)

if st.button("🔬 Calcular Correlación", type="primary"):

    with st.spinner("Procesando datos..."):

        # ── Datos epidemiológicos ───────────────────────────────────────────────
        evento_sql = evento.replace("'", "''")
        anios = list(range(anio - 3, anio + 1)) if incluir_anios_hist else [anio]
        anios_str = ",".join(map(str, anios))

        query_epi = f"""
        SELECT ANIO, SEMANA, SUM(CANTIDAD) AS CASOS
        FROM {{parquet}}
        WHERE ANIO IN ({anios_str})
          AND NOMBREEVENTOAGRP = '{evento_sql}'
          AND SEMANA != 53
        GROUP BY ANIO, SEMANA
        ORDER BY ANIO, SEMANA
        """
        df_epi = query_duckdb(query_epi)

        if df_epi.empty:
            st.warning("No hay datos epidemiológicos para los filtros seleccionados.")
            st.stop()

        # ── Datos climáticos agrupados por semana epidemiológica ───────────────
        # Filtramos estrictamente por los mismos años seleccionados
        df_clima_filt = df_clima[
            (df_clima['PROVINCIA'] == provincia_clima) &
            (df_clima['Estación'] == estacion) &
            (df_clima['ANIO'].isin(anios))
        ].copy()

        if tipo_temp == 'Precipitación (mm)':
            clima_sem = df_clima_filt.groupby(['ANIO', 'SEMANA'])[tipo_temp].sum().reset_index()
        else:
            clima_sem = df_clima_filt.groupby(['ANIO', 'SEMANA'])[tipo_temp].mean().reset_index()
        clima_sem = clima_sem.rename(columns={tipo_temp: 'TEMP'})

        # ── Merge epi + clima ──────────────────────────────────────────────────
        # Fusionamos por año y semana para garantizar que comparamos lo mismo
        merged = df_epi.merge(clima_sem, on=['ANIO', 'SEMANA'], how='inner').sort_values(['ANIO', 'SEMANA'])

        if merged.empty:
            st.warning("No hay coincidencias entre datos epidemiológicos y climáticos.")
            st.stop()

        # ── Calcular correlaciones para cada lag ───────────────────────────────
        lags        = list(range(0, lag_max + 1))
        correlaciones = []
        pvalues     = []

        for lag in lags:
            temp_lagged = merged['TEMP'].shift(lag)   # temperatura adelantada lag semanas
            valid = ~(temp_lagged.isna() | merged['CASOS'].isna())
            if valid.sum() < 5:
                correlaciones.append(np.nan)
                pvalues.append(np.nan)
                continue
            r, p = stats.pearsonr(temp_lagged[valid], merged['CASOS'][valid])
            correlaciones.append(round(r, 4))
            pvalues.append(round(p, 4))

        df_corr = pd.DataFrame({'Lag (semanas)': lags, 'Correlación r': correlaciones, 'p-valor': pvalues})
        lag_optimo = lags[np.nanargmax([abs(c) for c in correlaciones])] if any(~np.isnan(c) for c in correlaciones) else lag_sel

        # ── Métricas ────────────────────────────────────────────────────────────
        idx_sel = min(lag_sel, len(correlaciones) - 1)
        r_sel   = correlaciones[idx_sel]
        p_sel   = pvalues[idx_sel]
        r_opt   = correlaciones[lag_optimo] if lag_optimo < len(correlaciones) else np.nan

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            color_r = '#00e676' if abs(r_sel or 0) > 0.5 else ('#ffd700' if abs(r_sel or 0) > 0.3 else '#e94560')
            st.markdown(f'<div class="corr-card"><h2 style="color:{color_r}">{r_sel:.3f}</h2><p>Correlación r (lag {lag_sel})</p></div>', unsafe_allow_html=True)
        with m2:
            sig = "✅ Significativo" if (p_sel or 1) < 0.05 else "⚠️ No significativo"
            st.markdown(f'<div class="corr-card"><h2 style="color:#a8b2d8">{p_sel:.3f}</h2><p>p-valor — {sig}</p></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="corr-card"><h2 style="color:#00b4d8">{lag_optimo}</h2><p>Lag óptimo (semanas)</p></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="corr-card"><h2 style="color:#7eb8f7">{r_opt:.3f}</h2><p>Correlación en lag óptimo</p></div>', unsafe_allow_html=True)

        # ── Insight automático ──────────────────────────────────────────────────
        if not np.isnan(r_opt):
            signo    = "positiva" if r_opt > 0 else "negativa"
            fuerza   = "fuerte" if abs(r_opt) > 0.6 else ("moderada" if abs(r_opt) > 0.3 else "débil")
            dir_text = "aumentan" if r_opt > 0 else "disminuyen"
            st.markdown(f"""
            <div class="insight-box">
            🧠 <b>Interpretación automática:</b> Existe una correlación <b>{fuerza} {signo}</b> (r={r_opt:.3f}) 
            entre <i>{tipo_temp}</i> de la estación <b>{estacion}</b> y los casos de <b>{evento}</b>
            con un desfase de <b>{lag_optimo} semanas</b>. 
            Esto sugiere que cuando {tipo_temp.lower()} sube, los casos <b>{dir_text}</b> aproximadamente 
            {lag_optimo} semana(s) después.
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # ── Gráfico principal: doble eje Y ─────────────────────────────────────
        st.markdown(f"#### 📊 {tipo_temp} (lag={lag_sel} sem) vs Casos de {evento}")
        temp_lagged_sel = merged['TEMP'].shift(lag_sel)

        # Serie de tiempo combinada
        fig_ts = make_subplots(specs=[[{"secondary_y": True}]])

        # Área de casos
        fig_ts.add_trace(go.Bar(
            x=list(range(len(merged))),
            y=merged['CASOS'],
            name='Casos',
            marker_color='rgba(233,69,96,0.6)',
            marker_line_color='rgba(233,69,96,0.9)',
            marker_line_width=1,
        ), secondary_y=False)

        # Línea de temperatura lagged
        fig_ts.add_trace(go.Scatter(
            x=list(range(len(merged))),
            y=temp_lagged_sel,
            name=f'{tipo_temp} (lag={lag_sel} sem)',
            mode='lines+markers',
            line=dict(color='#00b4d8', width=2),
            marker=dict(size=4),
        ), secondary_y=True)

        # Etiquetas del eje X: "ANIO-SEM"
        labels_x = [f"SE{int(r['SEMANA'])}/{int(r['ANIO'])}" for _, r in merged.iterrows()]
        tick_step = max(1, len(labels_x) // 12)

        fig_ts.update_layout(
            template='plotly_dark',
            height=430,
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                tickvals=list(range(0, len(labels_x), tick_step)),
                ticktext=labels_x[::tick_step],
                tickangle=-45
            )
        )
        fig_ts.update_yaxes(title_text="Casos", secondary_y=False, color='#e94560')
        fig_ts.update_yaxes(title_text=f"{tipo_temp} (lag={lag_sel})", secondary_y=True, color='#00b4d8')
        st.plotly_chart(fig_ts, width="stretch")

        # ── Gráfico de correlación por lag ─────────────────────────────────────
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.markdown("#### 🔗 Correlación de Pearson por Lag")
            colores_barra = ['#00e676' if l == lag_optimo else ('#00b4d8' if l == lag_sel else '#4a6fa5') for l in lags]
            fig_lag = go.Figure()
            fig_lag.add_trace(go.Bar(
                x=lags, y=correlaciones,
                marker_color=colores_barra,
                text=[f"{c:.3f}" if not np.isnan(c) else 'N/A' for c in correlaciones],
                textposition='outside',
                name='r de Pearson'
            ))
            fig_lag.add_hline(y=0, line_color='white', line_dash='dash', line_width=1)
            fig_lag.add_hline(y=0.5,  line_color='#00e676', line_dash='dot', line_width=1,
                              annotation_text='Corr. fuerte (0.5)')
            fig_lag.add_hline(y=-0.5, line_color='#00e676', line_dash='dot', line_width=1)
            fig_lag.update_layout(
                xaxis_title='Lag (semanas)', yaxis_title='r de Pearson',
                template='plotly_dark', height=320,
                yaxis=dict(range=[-1, 1]),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_lag, width="stretch")

        with col_g2:
            st.markdown(f"#### 📈 Diagrama de dispersión (lag={lag_sel})")
            valid_idx = ~(temp_lagged_sel.isna() | merged['CASOS'].isna())
            fig_sc = go.Figure()
            fig_sc.add_trace(go.Scatter(
                x=temp_lagged_sel[valid_idx],
                y=merged['CASOS'][valid_idx],
                mode='markers',
                marker=dict(color=merged['SEMANA'][valid_idx], colorscale='Viridis',
                            showscale=True, size=7, colorbar=dict(title='Semana')),
                text=[f"SE{int(r['SEMANA'])}/{int(r['ANIO'])}" for _, r in merged[valid_idx].iterrows()],
                hovertemplate='%{text}<br>Temp: %{x:.1f}°C<br>Casos: %{y}'
            ))
            # Línea de tendencia
            if valid_idx.sum() >= 3:
                x_v = temp_lagged_sel[valid_idx].values
                y_v = merged['CASOS'][valid_idx].values
                m, b, _, _, _ = stats.linregress(x_v, y_v)
                x_line = np.linspace(x_v.min(), x_v.max(), 50)
                fig_sc.add_trace(go.Scatter(
                    x=x_line, y=m * x_line + b,
                    mode='lines', line=dict(color='#e94560', width=2, dash='dash'),
                    name='Tendencia'
                ))
            fig_sc.update_layout(
                xaxis_title=f'{tipo_temp} (lag={lag_sel})',
                yaxis_title='Casos',
                template='plotly_dark', height=320, showlegend=False,
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_sc, width="stretch")

        # ── Tabla de correlaciones ─────────────────────────────────────────────
        with st.expander("📋 Tabla de correlaciones por lag"):
            df_corr['Significativo (p<0.05)'] = df_corr['p-valor'].apply(
                lambda p: '✅ Sí' if (p is not None and not np.isnan(p) and p < 0.05) else '❌ No')
            df_corr['Lag óptimo'] = df_corr['Lag (semanas)'].apply(
                lambda l: '⭐ Óptimo' if l == lag_optimo else '')
            st.dataframe(df_corr.style.map(lambda x: 'background-color: #0f3460', subset=['Lag óptimo'])
                                      .background_gradient(subset=['Correlación r'], cmap='RdYlGn'),
                         width="stretch")
