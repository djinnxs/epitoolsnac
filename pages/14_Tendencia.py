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

# Clima (covariable) — opcional
CLIMA_PARQUET = str(Path(__file__).resolve().parent.parent / "data" / "ClimaHisto.parquet")
def cargar_temperatura_semanal():
    """Promedio nacional de temperatura media por semana epidemiológica (covariable exog)."""
    try:
        if not Path(CLIMA_PARQUET).exists():
            return None
        clima = pd.read_parquet(CLIMA_PARQUET)
        clima["Fecha"] = pd.to_datetime(clima["Fecha"], errors="coerce")
        clima = clima.dropna(subset=["Fecha"])
        clima["TEMP_MEDIA"] = (clima.get("Temp. Maxima (°C)") + clima.get("Temp. Minima (°C)")) / 2
        clima = clima.dropna(subset=["TEMP_MEDIA"])
        # Semana epidemiológica
        clima["ANIO"] = clima["Fecha"].dt.isocalendar().year
        clima["SEMANA"] = clima["Fecha"].dt.isocalendar().week
        temp = clima.groupby(["ANIO", "SEMANA"])["TEMP_MEDIA"].mean().reset_index()
        temp["fecha"] = temp.apply(lambda x: epiweek_to_date(int(x["ANIO"]), int(x["SEMANA"])), axis=1)
        return temp[["fecha", "TEMP_MEDIA"]].sort_values("fecha")
    except Exception:
        return None

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

# ==================== HELPERS MEJORADOS ====================

def bootstrap_ic(y_pred_centro, residuos, steps, alpha=0.2, n_sims=500, seed=42):
    """Cuantiles 80% vía bootstrap bloqueado sobre residuos (estilo TimesFM: punto + incertidumbre calibrada)."""
    rng = np.random.default_rng(seed)
    if residuos is None or len(residuos) < 10:
        # Sin residuos suficientes, banda simétrica fija (±10%)
        low = np.maximum(y_pred_centro * 0.9, 0)
        high = y_pred_centro * 1.1
        return low, high
    residuos = np.asarray(residuos, dtype=float)
    residuos = residuos[~np.isnan(residuos)]
    block = max(1, int(len(residuos) ** 0.5))
    sims = np.empty((n_sims, steps))
    for i in range(n_sims):
        start = int(rng.integers(0, max(1, len(residuos) - block + 1)))
        idx = (start + np.arange(steps)) % len(residuos)
        sims[i] = y_pred_centro + residuos[idx]
    low = np.percentile(sims, alpha / 2 * 100, axis=0)
    high = np.percentile(sims, (1 - alpha / 2) * 100, axis=0)
    return np.maximum(low, 0), np.maximum(high, 0)

def metricas_error(y_true, y_pred):
    """MAPE y RMSE (ambos robustos a ceros)."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) == 0:
        return float('nan'), float('nan')
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mask = y_true != 0
    if mask.sum() == 0:
        mape = float('nan')
    else:
        mape = float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / y_true[mask]) * 100)
    return mape, rmse

def backtest_walkforward(y, horizon=13, n_rets=3, exog=None):
    """Backtest walk-forward: HFV-STYLE. Devuelve {modelo: {mape, rmse, preds, reales}}."""
    resultados = {}
    y = pd.Series(y).reset_index(drop=True)
    exog_s = pd.Series(exog).reset_index(drop=True) if exog is not None else None
    n = len(y)
    if n < horizon * (n_rets + 1):
        return {}
    puntos = []
    for r in range(n_rets):
        split = n - horizon * (n_rets - r)
        train_y = y.iloc[:split]
        test_y = y.iloc[split:split + horizon]
        if len(test_y) < horizon:
            continue
        # SARIMA
        try:
            exog_train = exog_s.iloc[:split].values if exog_s is not None else None
            res = SARIMAX(train_y.values, order=(1,1,1), seasonal_order=(1,1,1,52),
                          exog=exog_train).fit(disp=False)
            pred = np.maximum(res.forecast(steps=horizon), 0)
            puntos.append({
                'model': 'SARIMA', 'real': test_y.values, 'pred': pred,
                'mape': metricas_error(test_y.values, pred)[0],
                'rmse': metricas_error(test_y.values, pred)[1],
            })
        except Exception:
            pass
        # ETS
        try:
            res_ets = ExponentialSmoothing(train_y.values, seasonal_periods=52,
                                           trend='add', seasonal='add').fit()
            pred_ets = np.maximum(res_ets.forecast(horizon), 0)
            puntos.append({
                'model': 'ETS', 'real': test_y.values, 'pred': pred_ets,
                'mape': metricas_error(test_y.values, pred_ets)[0],
                'rmse': metricas_error(test_y.values, pred_ets)[1],
            })
        except Exception:
            pass
    # Consolidar por modelo
    for m in {'SARIMA', 'ETS'}:
        subset = [p for p in puntos if p['model'] == m]
        if subset:
            reales = np.concatenate([p['real'] for p in subset])
            preds = np.concatenate([p['pred'] for p in subset])
            mape, rmse = metricas_error(reales, preds)
            resultados[m] = {'mape': mape, 'rmse': rmse}
    return resultados

backtest_walkforward_cached = st.cache_data(backtest_walkforward)

def deseasonalizar_predecir(y_series, steps, alpha=0.2):
    """Predice la tendencia deseasonalizada y la recompone con la estacionalidad (enfoque TimesFM de separar patrones)."""
    x = y_series.reset_index(drop=True)
    n = len(x)
    try:
        seas_period = 52 if n >= 104 else (13 if n >= 26 else len(x))
        # 'seasonal' (ventana de STL) debe ser un entero impar >= 3
        seas_win = min(seas_period, n // 2)
        if seas_win % 2 == 0:
            seas_win += 1
        seas_win = max(seas_win, 3)
        stl = STL(x, seasonal=seas_win, period=seas_period).fit()
        trend = stl.trend
        seasonal = stl.seasonal
        resid = stl.resid
        # Predecir tendencia con ETS sobre la serie deseasonalizada (trend + resid)
        deseas = (trend + resid).interpolate().bfill().ffill()
        try:
            model = ExponentialSmoothing(deseas.astype(float), trend='add').fit()
            trend_pred = np.maximum(model.forecast(steps), 0)
        except Exception:
            # fallback: última tendencia + media resid
            last_trend = trend.dropna().iloc[-1]
            slope = (trend.dropna().iloc[-1] - trend.dropna().iloc[min(5, len(trend.dropna())-1)]) / min(5, len(trend.dropna())-1)
            trend_pred = np.maximum(np.arange(1, steps+1) * slope + last_trend, 0)
        # Reconstruir estacionalidad futura usando el promedio de la estacionalidad del mismo segmento
        seas_vals = seasonal.to_numpy()
        seasonal_mean = pd.Series(seas_vals).groupby(np.arange(len(seas_vals)) % seas_period).mean()
        seg_pred = [seasonal_mean.iloc[k % seas_period] for k in range(steps)]
        y_pred = np.maximum(trend_pred + np.asarray(seg_pred), 0)
        # IC por bootstrap sobre el residuo
        low, high = bootstrap_ic(y_pred, resid.dropna(), steps, alpha=alpha)
        return y_pred, low, high
    except Exception as e:
        return None, None, str(e)

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
    opciones_modelo = (["Prophet", "SARIMA", "SARIMA + Clima", "ETS", "Deseasonalizada"]
                       if PROPHET_AVAILABLE else
                       ["SARIMA", "SARIMA + Clima", "ETS", "Deseasonalizada"])
    modelo_seleccionado = st.selectbox("🔬 Modelo", opciones_modelo)
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

# Covariable de temperatura (clima) alineada al histórico — solo si está disponible
temp_semanal = cargar_temperatura_semanal()
exog_temp = None
if temp_semanal is not None and not temp_semanal.empty:
    temp_merged = df_ts[['fecha']].merge(temp_semanal, on='fecha', how='left')['TEMP_MEDIA']
    exog_temp = temp_merged.ffill().bfill().values

# Backtest (walk-forward) — disponible para SARIMA/ETS (cacheado para no refitear en cada interacción)
# cache_data requiere argumentos hashables → pasar tuplas y reemplazar NaN en exog.
_exog_bt = None
if exog_temp is not None:
    _exog_bt = tuple(0.0 if (x is None or (isinstance(x, float) and np.isnan(x))) else float(x) for x in exog_temp)
resultados_backtest = backtest_walkforward_cached(
    tuple(float(x) for x in df_ts['CANTIDAD'].values), horizon=13, n_rets=3,
    exog=_exog_bt
)

# TABS
tab1, tab2, tab3, tab4 = st.tabs(["📊 Serie & Descomposición", "🔍 Diagnóstico", "🎯 Predicción", "⚖️ Comparación (Backtest)"])

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
    future_dates = pd.date_range(start=fecha_corte + timedelta(weeks=1), periods=periodos_prediccion, freq='W')
    fig_pred = go.Figure()
    fig_pred.add_trace(go.Scatter(x=df_ts['fecha'], y=df_ts['CANTIDAD'], name='Histórico', line=dict(color='blue')))

    y_centro = None
    ic_low = ic_high = None
    color_pred = 'red'

    # --- MODELO PROPHET ---
    if modelo_seleccionado == "Prophet" and PROPHET_AVAILABLE:
        df_p = df_ts[['fecha', 'CANTIDAD']].rename(columns={'fecha': 'ds', 'CANTIDAD': 'y'})
        m = Prophet(yearly_seasonality=True, weekly_seasonality=False)
        m.fit(df_p)
        future = m.make_future_dataframe(periods=periodos_prediccion, freq='W')
        forecast = m.predict(future)
        y_centro = forecast[forecast['ds'] > fecha_corte]['yhat'].values
        ic_low = forecast[forecast['ds'] > fecha_corte]['yhat_lower'].values
        ic_high = forecast[forecast['ds'] > fecha_corte]['yhat_upper'].values

    # --- MODELO SARIMA (con o sin clima) ---
    elif modelo_seleccionado in ("SARIMA", "SARIMA + Clima"):
        try:
            usar_clima = (modelo_seleccionado == "SARIMA + Clima") and exog_temp is not None
            kwargs = {}
            if usar_clima:
                kwargs['exog'] = exog_temp
            model = SARIMAX(df_ts['CANTIDAD'], order=(1,1,1), seasonal_order=(1,1,1,52), **kwargs)
            res = model.fit(disp=False)
            y_centro = np.maximum(res.forecast(steps=periodos_prediccion), 0)
            # IC 80% bootstrap sobre residuos
            resid = res.resid[~np.isnan(res.resid)] if hasattr(res, 'resid') else None
            ic_low, ic_high = bootstrap_ic(y_centro, resid, periodos_prediccion)
            if usar_clima:
                color_pred = 'orange'
                st.caption("🧊 Modelo SARIMA con covariable de temperatura (meteostat)")
            else:
                color_pred = 'red'
        except Exception as e:
            st.error(f"Error en SARIMA: {e}")

    # --- MODELO ETS ---
    elif modelo_seleccionado == "ETS":
        try:
            model = ExponentialSmoothing(df_ts['CANTIDAD'], seasonal_periods=52, trend='add', seasonal='add')
            res = model.fit()
            # residuos = valores − ajustados (para el bootstrap del IC 80%)
            fitted = res.fittedvalues if hasattr(res, 'fittedvalues') else None
            resid = None
            if fitted is not None:
                resid = (df_ts['CANTIDAD'].values[:len(fitted)] - fitted[:len(df_ts)]) 
            y_centro = np.maximum(res.forecast(periodos_prediccion), 0)
            ic_low, ic_high = bootstrap_ic(y_centro, resid, periodos_prediccion)
            color_pred = 'green'
        except Exception as e:
            st.error(f"Error en ETS: {e}")

    # --- MODELO DESEASONALIZADA (STL + ETS) ---
    elif modelo_seleccionado == "Deseasonalizada":
        try:
            y_centro, ic_low, ic_high = deseasonalizar_predecir(
                df_ts['CANTIDAD'], periodos_prediccion, alpha=0.2)
            if y_centro is None:
                st.error(f"Error en Deseasonalizada: {ic_high}")
            else:
                color_pred = 'purple'
                st.caption("🧩 Predicción de la tendencia deseasonalizada (STL) recomponiendo la estacionalidad — estilo TimesFM")
        except Exception as e:
            st.error(f"Error en Deseasonalizada: {e}")

    # Graficar resultado
    if y_centro is not None:
        fig_pred.add_trace(go.Scatter(x=future_dates[:len(y_centro)], y=y_centro,
                                      name=f'Predicción {modelo_seleccionado}',
                                      line=dict(color=color_pred, dash='dash')))
        if ic_low is not None and ic_high is not None:
            n_ic = min(len(ic_low), len(ic_high), len(future_dates))
            fig_pred.add_trace(go.Scatter(x=future_dates[:n_ic], y=ic_high[:n_ic],
                                          mode='lines', line=dict(width=0), showlegend=False))
            fig_pred.add_trace(go.Scatter(x=future_dates[:n_ic], y=ic_low[:n_ic],
                                          mode='lines', fill='tonexty', fillcolor='rgba(255,0,0,0.1)',
                                          name='IC 80%', line=dict(width=0)))

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

with tab4:
    st.subheader("Comparación de Modelos (Backtest Walk-Forward)")
    if resultados_backtest:
        df_cmp = pd.DataFrame([
            {'Modelo': k, 'MAPE (%)': round(v['mape'], 2), 'RMSE': round(v['rmse'], 2)}
            for k, v in resultados_backtest.items()
        ])
        mejor_mape = df_cmp.loc[df_cmp['MAPE (%)'].idxmin()]['Modelo'] if not df_cmp.empty else '—'
        st.success(f"🏆 El modelo con menor error (MAPE) en holdout fue: **{mejor_mape}**")
        st.dataframe(df_cmp, use_container_width=True)
        st.caption("El backtest retiene las últimas semanas y predice hacia adelante (walk-forward). "
                   "Menor MAPE/RMSE = mejor precisión. SARIMA + Clima usa temperatura si está disponible.")
    else:
        st.info("No hay datos suficientes para ejecutar el backtest (se necesitan ~52 semanas de histórico).")

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray;'>📅 Semanas Epidemiológicas | 🌎 Hemisferio Sur</div>", unsafe_allow_html=True)
