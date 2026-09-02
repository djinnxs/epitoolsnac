# pages/14_Tendencia.py - Análisis de Tendencias Epidemiológicas
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.common import query_duckdb, get_distinct_events
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Modelos estadísticos
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

st.set_page_config(page_title="Tendencias", page_icon="📈", layout="wide")
st.title("📈 Análisis de Tendencias Epidemiológicas")
st.markdown("Predicción con modelos estadísticos considerando estacionalidad del hemisferio sur")

# Función para tests de estacionaridad
def test_stationarity(timeseries):
    results = {}
    if len(timeseries.dropna()) < 10:
        return None
    
    adf_result = adfuller(timeseries.dropna(), autolag='AIC')
    results['adf'] = {
        'statistic': adf_result[0],
        'p_value': adf_result[1],
        'is_stationary': adf_result[1] < 0.05
    }

    kpss_result = kpss(timeseries.dropna(), regression='ct', nlags='auto')
    results['kpss'] = {
        'statistic': kpss_result[0],
        'p_value': kpss_result[1],
        'is_stationary': kpss_result[1] > 0.05
    }
    return results

# Función para convertir semana epidemiológica a fecha
def epiweek_to_date(year, week):
    jan_1 = datetime(year, 1, 1)
    days_to_sunday = (6 - jan_1.weekday()) % 7
    first_sunday = jan_1 + timedelta(days=days_to_sunday)
    target_date = first_sunday + timedelta(weeks=(week - 1))
    return target_date

# Cargar datos desde Parquet usando DuckDB
query = """
SELECT ANIO, SEMANA, NOMBREEVENTOAGRP, CANTIDAD
FROM {parquet}
WHERE ANIO >= 2018 AND SEMANA != 53
"""
df = query_duckdb(query)

if df is None or df.empty:
    st.error("⚠️ No hay datos disponibles para el análisis.")
    st.stop()

# FILTROS
st.markdown("### 🎯 Configuración")
col1, col2, col3 = st.columns(3)
with col1:
    events = get_distinct_events()
    evento = st.selectbox("🦠 Patología", events)
with col2:
    año_actual = datetime.now().year
    año_futuro = st.selectbox("📅 Año a Predecir", [año_actual + 1])
with col3:
    modelo_seleccionado = st.selectbox(
        "🔬 Modelo",
        ["Prophet", "SARIMA", "ETS"] if PROPHET_AVAILABLE else ["SARIMA", "ETS"]
    )
st.markdown("---")

# Preparar datos
df_evento = df[df["NOMBREEVENTOAGRP"] == evento].copy()
if df_evento.empty:
    st.warning(f"No hay datos suficientes para {evento}")
    st.stop()

df_ts = df_evento.groupby(["ANIO", "SEMANA"])["CANTIDAD"].sum().reset_index()
df_ts['fecha'] = df_ts.apply(lambda x: epiweek_to_date(int(x['ANIO']), int(x['SEMANA'])), axis=1)
df_ts = df_ts.sort_values('fecha').reset_index(drop=True)

# Calcular periodos de predicción
último_año = int(df_ts['ANIO'].max())
última_semana = int(df_ts[df_ts['ANIO'] == último_año]['SEMANA'].max())
periodos_prediccion = (52 - última_semana) + 52 

st.info(f"Histórico: {df_ts['ANIO'].min()}-{último_año} | Prediciendo {periodos_prediccion} semanas.")

# TABS
tab1, tab2, tab3 = st.tabs(["📊 Serie & Descomposición", "🔍 Diagnóstico", "🎯 Predicción"])

with tab1:
    st.subheader("Serie Temporal Histórica")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_ts['fecha'], y=df_ts['CANTIDAD'], mode='lines', name='Casos'))
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width="stretch")

    if len(df_ts) >= 104:
        st.subheader("Descomposición STL")
        try:
            stl = STL(df_ts.set_index('fecha')['CANTIDAD'], seasonal=53, period=52)
            res = stl.fit()
            fig_stl = make_subplots(rows=4, cols=1, subplot_titles=('Original', 'Tendencia', 'Estacionalidad', 'Residuos'))
            fig_stl.add_trace(go.Scatter(x=df_ts['fecha'], y=df_ts['CANTIDAD']), row=1, col=1)
            fig_stl.add_trace(go.Scatter(x=df_ts['fecha'], y=res.trend), row=2, col=1)
            fig_stl.add_trace(go.Scatter(x=df_ts['fecha'], y=res.seasonal), row=3, col=1)
            fig_stl.add_trace(go.Scatter(x=df_ts['fecha'], y=res.resid), row=4, col=1)
            fig_stl.update_layout(height=700, showlegend=False)
            st.plotly_chart(fig_stl, width="stretch")
        except Exception as e:
            st.warning(f"No se pudo realizar la descomposición: {e}")

with tab2:
    st.subheader("Tests de Estacionaridad")
    stat_results = test_stationarity(df_ts['CANTIDAD'])
    if stat_results:
        c1, c2 = st.columns(2)
        c1.metric("ADF p-value", f"{stat_results['adf']['p_value']:.4f}", "Estacionaria" if stat_results['adf']['is_stationary'] else "No Estacionaria")
        c2.metric("KPSS p-value", f"{stat_results['kpss']['p_value']:.4f}", "Estacionaria" if stat_results['kpss']['is_stationary'] else "No Estacionaria")

    st.subheader("Patrón Estacional Promedio")
    seasonal = df_ts.groupby('SEMANA')['CANTIDAD'].mean().reset_index()
    fig_s = go.Figure(go.Bar(x=seasonal['SEMANA'], y=seasonal['CANTIDAD'], marker_color='lightblue'))
    fig_s.update_layout(height=300, xaxis_title="Semana Epidemiológica")
    st.plotly_chart(fig_s, width="stretch")

with tab3:
    st.subheader(f"Predicción Modelo {modelo_seleccionado}")
    
    fecha_corte = df_ts['fecha'].max()
    fig_pred = go.Figure()
    fig_pred.add_trace(go.Scatter(x=df_ts['fecha'], y=df_ts['CANTIDAD'], name='Histórico', line=dict(color='blue')))

    # --- MODELO PROPHET ---
    if modelo_seleccionado == "Prophet" and PROPHET_AVAILABLE:
        df_p = df_ts[['fecha', 'CANTIDAD']].rename(columns={'fecha': 'ds', 'CANTIDAD': 'y'})
        m = Prophet(yearly_seasonality=True, weekly_seasonality=False)
        m.fit(df_p)
        future = m.make_future_dataframe(periods=periodos_prediccion, freq='W')
        forecast = m.predict(future)
        
        y_pred = forecast[forecast['ds'] > fecha_corte]
        fig_pred.add_trace(go.Scatter(x=y_pred['ds'], y=y_pred['yhat'], name='Predicción', line=dict(color='red', dash='dash')))
        fig_pred.add_trace(go.Scatter(x=y_pred['ds'], y=y_pred['yhat_upper'], mode='lines', line=dict(width=0), showlegend=False))
        fig_pred.add_trace(go.Scatter(x=y_pred['ds'], y=y_pred['yhat_lower'], mode='lines', fill='tonexty', fillcolor='rgba(255,0,0,0.1)', name='IC', line=dict(width=0)))

    # --- MODELO SARIMA ---
    elif modelo_seleccionado == "SARIMA":
        try:
            model = SARIMAX(df_ts['CANTIDAD'], order=(1,1,1), seasonal_order=(1,1,1,52))
            res = model.fit(disp=False)
            y_pred_vals = res.forecast(steps=periodos_prediccion)
            y_pred_vals = np.maximum(y_pred_vals, 0)
            
            future_dates = pd.date_range(start=fecha_corte + timedelta(weeks=1), periods=periodos_prediccion, freq='W')
            fig_pred.add_trace(go.Scatter(x=future_dates, y=y_pred_vals, name='Predicción SARIMA', line=dict(color='red', dash='dash')))
        except Exception as e:
            st.error(f"Error en SARIMA: {e}")

    # --- MODELO ETS ---
    elif modelo_seleccionado == "ETS":
        try:
            model = ExponentialSmoothing(df_ts['CANTIDAD'], seasonal_periods=52, trend='add', seasonal='add')
            res = model.fit()
            y_pred_vals = res.forecast(periodos_prediccion)
            y_pred_vals = np.maximum(y_pred_vals, 0)
            
            future_dates = pd.date_range(start=fecha_corte + timedelta(weeks=1), periods=periodos_prediccion, freq='W')
            fig_pred.add_trace(go.Scatter(x=future_dates, y=y_pred_vals, name='Predicción ETS', line=dict(color='green', dash='dash')))
        except Exception as e:
            st.error(f"Error en ETS: {e}")

    # SOLUCIÓN DEFINITIVA AL ERROR DE PROMEDIO DE FECHAS
    fig_pred.add_shape(
        type="line", x0=fecha_corte, x1=fecha_corte, y0=0, y1=1, yref="paper",
        line=dict(color="gray", width=1.5, dash="dot")
    )
    fig_pred.add_annotation(
        x=fecha_corte, y=1, yref="paper", text="Inicio Predicción",
        showarrow=False, textangle=-90, xanchor="left"
    )

    fig_pred.update_layout(height=500, hovermode='x unified', xaxis_title="Fecha", yaxis_title="Casos")
    st.plotly_chart(fig_pred, width="stretch")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>📅 Semanas Epidemiológicas | 🌎 Hemisferio Sur</div>", unsafe_allow_html=True)
