# pages/17_Nowcasting.py — Curva epidémica semanal con banda de referencia (nowcasting)
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.common import (
    PALETA,
    get_data_corte,
    get_distinct_departments,
    get_distinct_events,
    get_distinct_years,
    query_duckdb,
    show_data_corte,
    show_semana_actual,
    style_fig,
)

st.set_page_config(page_title="Nowcasting", page_icon="🔬", layout="wide")
show_semana_actual()

st.title("🔬 Nowcasting y curva epidémica semanal")
st.markdown(
    "Compara las **últimas semanas epidemiológicas** con lo que se esperaría según los años "
    "previos, para detectar posibles **subregistros** (semanas que todavía no terminaron de "
    "cargarse) y anticipar el nivel real de la curva."
)

st.markdown("""
<style>
    .nowcast-metric {background: linear-gradient(135deg,#1a1a2e,#16213e); border-radius:12px; padding:16px; text-align:center; border:1px solid #0f3460;}
    .nowcast-metric h2 {color:#e94560; margin:0; font-size:2rem;}
    .nowcast-metric p  {color:#a8b2d8; margin:4px 0 0; font-size:.85rem;}
    .info-box {background:#0f3460; border-radius:8px; padding:12px; border-left:4px solid #e94560; color:#ccd6f6; font-size:.9rem; margin-bottom:12px;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
<b>¿Cómo se estima?</b> Para cada semana epidemiológica se calcula la <b>mediana</b> de los
últimos 5 años y su banda p10–p90, y se ajusta por el nivel del año actual (casos acumulados
hasta el corte vs. la mediana histórica). Si las últimas semanas quedan por debajo de la banda,
es señal de <b>reporte incompleto</b>, no necesariamente de menos casos.
<br><br>
<b>Por qué no se usa el método clásico (CDC/ECDC):</b> ese método necesita la fecha del evento
para estimar el retraso de notificación. Esta base solo guarda la <b>fecha de registro</b>
(que es la que define la semana), así que el retraso no es reconstruible. La referencia
histórica es la alternativa correcta con los datos disponibles.
</div>
""", unsafe_allow_html=True)

# ── Filtros ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    evento = st.selectbox("Evento", get_distinct_events())
with col2:
    anio = st.selectbox("Año de análisis", get_distinct_years())
with col3:
    semanas_incompletas = st.slider("Semanas recientes a evaluar", 2, 6, 4)

col4, col5 = st.columns(2)
with col4:
    nivel = st.radio("Nivel geográfico", ["Provincia", "Departamento"], horizontal=True)
with col5:
    if nivel == "Departamento":
        depto = st.selectbox("Departamento", get_distinct_departments())
    else:
        depto = None

corte = get_data_corte()
semana_ref = corte["semana"] if (corte and corte["anio"] == anio) else 52
st.caption(
    f"Semana de referencia: **SE {semana_ref} de {anio}** (última con datos). "
    "Las estimaciones se aplican a las últimas semanas cargadas en la base."
)

if st.button("🔬 Calcular estimación", type="primary"):
    anios_hist = list(range(anio - 5, anio))
    anios_str = ",".join(map(str, anios_hist))
    evento_sql = evento.replace("'", "''")
    where_geo = f"AND DEPARTAMENTO = '{depto.replace(chr(39), chr(39) * 2)}'" if depto else ""

    df_hist = query_duckdb(f"""
    SELECT ANIO, SEMANA, SUM(CANTIDAD) AS CANTIDAD
    FROM {{parquet}}
    WHERE ANIO IN ({anios_str})
      AND NOMBREEVENTOAGRP = '{evento_sql}'
      AND SEMANA <= 52
      {where_geo}
    GROUP BY ANIO, SEMANA
    ORDER BY ANIO, SEMANA
    """)

    df_actual = query_duckdb(f"""
    SELECT SEMANA, SUM(CANTIDAD) AS CANTIDAD
    FROM {{parquet}}
    WHERE ANIO = {anio}
      AND NOMBREEVENTOAGRP = '{evento_sql}'
      AND SEMANA <= 52
      {where_geo}
    GROUP BY SEMANA
    ORDER BY SEMANA
    """)

    if df_hist.empty or df_actual.empty:
        st.warning("No hay suficientes datos para calcular la estimación.")
        st.stop()

    # ── Nivel del año actual vs. histórico (para escalar la referencia) ────────
    cum_actual = df_actual.loc[df_actual["SEMANA"] <= semana_ref, "CANTIDAD"].sum()
    cum_hist = (
        df_hist[df_hist["SEMANA"] <= semana_ref]
        .groupby("ANIO")["CANTIDAD"].sum()
    )
    base_nivel = float(cum_hist.median()) if len(cum_hist) else 0.0
    factor_nivel = (cum_actual / base_nivel) if base_nivel > 0 else 1.0

    # ── Referencia por semana (mediana y banda p10-p90 de años previos) ────────
    piv = (
        df_hist.pivot_table(index="SEMANA", columns="ANIO", values="CANTIDAD", aggfunc="sum")
        .reindex(range(1, 53))
    )
    ref_med = piv.median(axis=1)
    ref_p10 = piv.quantile(0.10, axis=1)
    ref_p90 = piv.quantile(0.90, axis=1)

    esperado = ref_med * factor_nivel
    banda_low = ref_p10 * factor_nivel
    banda_high = ref_p90 * factor_nivel

    observado = df_actual.set_index("SEMANA")["CANTIDAD"].reindex(range(1, 53)).fillna(0)

    # ── KPIs ───────────────────────────────────────────────────────────────────
    semanas_recientes = list(range(max(1, semana_ref - semanas_incompletas + 1), semana_ref + 1))
    obs_reciente = observado.loc[semanas_recientes]
    esp_reciente = esperado.loc[semanas_recientes]

    total_obs = float(observado.loc[:semana_ref].sum())
    last_obs = float(observado.get(semana_ref, 0))
    last_esp = float(esperado.get(semana_ref, 0))
    brecha = float(np.maximum(esp_reciente.fillna(0) - obs_reciente.fillna(0), 0).sum())
    ratio_ult = (last_obs / last_esp * 100) if last_esp > 0 else None

    def fmt(n):
        return f"{int(round(float(n))):,}".replace(",", ".")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="nowcast-metric"><h2>{fmt(total_obs)}</h2><p>Casos observados hasta SE{semana_ref}</p></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="nowcast-metric"><h2>{fmt(last_obs)}</h2><p>Observados en SE{semana_ref}</p></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="nowcast-metric"><h2>{fmt(last_esp)}</h2><p>Esperados en SE{semana_ref} (referencia)</p></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="nowcast-metric"><h2>~{fmt(brecha)}</h2><p>Brecha acumulada últimas {semanas_incompletas} SE</p></div>', unsafe_allow_html=True)

    st.caption(
        ("La última semana está en el **" + f"{ratio_ult:.0f}%" + "** de la referencia histórica."
         if ratio_ult is not None else "")
    )

    st.markdown("---")

    # ── Gráfico: curva epidémica + banda de referencia ─────────────────────────
    fig = go.Figure()

    # Banda p10-p90 de la referencia
    sems_banda = [s for s in range(1, 53) if pd.notna(banda_low.get(s)) and pd.notna(banda_high.get(s))]
    fig.add_trace(go.Scatter(
        x=sems_banda + sems_banda[::-1],
        y=[banda_high.get(s) for s in sems_banda] + [banda_low.get(s) for s in sems_banda[::-1]],
        fill="toself", fillcolor="rgba(233,69,96,0.12)",
        line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
        name="Banda de referencia (p10-p90)",
    ))

    # Casos observados
    colores_barras = [
        "rgba(233,69,96,0.55)" if (s is not None and s >= semana_ref - semanas_incompletas + 1)
        else "rgba(31,119,180,0.75)"
        for s in range(1, 53)
    ]
    fig.add_trace(go.Bar(
        x=list(range(1, 53)),
        y=[observado.get(s) if s <= semana_ref else None for s in range(1, 53)],
        name="Casos observados",
        marker_color=colores_barras,
        marker_line_width=0,
    ))

    # Referencia esperada
    fig.add_trace(go.Scatter(
        x=sems_banda,
        y=[esperado.get(s) for s in sems_banda],
        name="Esperado (mediana histórica ajustada)",
        mode="lines",
        line=dict(color=PALETA[1], width=2, dash="dot"),
    ))

    fig.add_vline(x=semana_ref, line_dash="dash", line_color="#7f7f7f",
                  annotation_text=f"SE{semana_ref} (último dato)", annotation_position="top right")

    geo_label = depto if depto else "Nacional"
    style_fig(
        fig,
        height=520,
        titulo=f"Curva epidémica semanal — {evento} | {geo_label} | {anio}",
        x_title="Semana Epidemiológica",
        y_title="Casos",
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Barras azules: semanas con reporte completo. Barras rosadas: últimas "
        f"{semanas_incompletas} semanas, todavía sujetas a carga. La banda muestra el rango "
        "histórico esperado para cada semana del año."
    )

    # ── Detalle numérico ───────────────────────────────────────────────────────
    st.markdown("##### Detalle de las semanas evaluadas")
    detalle = pd.DataFrame({
        "SE": semanas_recientes,
        "Observado": [int(observado.get(s, 0)) for s in semanas_recientes],
        "Esperado (referencia)": [int(round(esperado.get(s, 0))) for s in semanas_recientes],
        "p10": [int(round(banda_low.get(s, 0))) for s in semanas_recientes],
        "p90": [int(round(banda_high.get(s, 0))) for s in semanas_recientes],
    })
    detalle["Observado / Esperado"] = [
        f"{(o / e * 100):.0f}%" if e > 0 else "—"
        for o, e in zip(detalle["Observado"], detalle["Esperado (referencia)"])
    ]
    st.dataframe(detalle, width="stretch", hide_index=True)

    with st.expander("📋 Cómo se construyó la referencia"):
        st.markdown(
            f"- Años usados: **{anios_hist[0]} a {anios_hist[-1]}** (misma geografía y evento).\n"
            f"- Casos acumulados del año {anio} hasta SE{semana_ref}: **{fmt(cum_actual)}**.\n"
            f"- Mediana histórica acumulada a la misma semana: **{fmt(base_nivel)}**.\n"
            f"- Factor de nivel aplicado: **{factor_nivel:.2f}×**.\n"
            "- La banda p10-p90 resume la variabilidad entre años: si el valor observado cae "
            "por debajo, conviene revisar si la semana terminó de cargarse."
        )
        tabla_ref = pd.DataFrame({
            "SE": sems_banda,
            "Mediana histórica": [int(round(ref_med.get(s, 0))) for s in sems_banda],
            "p10": [int(round(ref_p10.get(s, 0))) for s in sems_banda],
            "p90": [int(round(ref_p90.get(s, 0))) for s in sems_banda],
        })
        st.dataframe(tabla_ref, width="stretch", hide_index=True)

show_data_corte()
