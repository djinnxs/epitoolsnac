# pages/23_Ranking.py — Ranking de provincias por semana epidemiológica (bump chart)
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.common import (
    PALETA,
    get_data_corte,
    get_distinct_events,
    get_distinct_years,
    load_population_province,
    query_duckdb,
    show_data_corte,
    show_semana_actual,
    style_fig,
)

st.set_page_config(page_title="Ranking por Semana", page_icon="🏆", layout="wide")
show_semana_actual()

st.title("🏆 Ranking de provincias por semana epidemiológica")
st.markdown(
    "Cómo cambia el orden de las provincias **semana a semana** (bump chart). "
    "El puesto 1 es la provincia con más casos (o mayor tasa) en esa semana; "
    "las líneas que suben indican provincias que están ganando peso relativo."
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    evento = st.selectbox("Evento", get_distinct_events())
with col2:
    anio = st.selectbox("Año", get_distinct_years())
with col3:
    ventana = st.slider("Últimas semanas", min_value=4, max_value=30, value=16, step=1)
with col4:
    metrica = st.selectbox("Métrica", ["Casos", "Tasa x100k"])

evento_sql = evento.replace("'", "''")
query = f"""
SELECT PROVINCIA, CODIGO_PROVINCIA, SEMANA, SUM(CANTIDAD) AS CANTIDAD
FROM {{parquet}}
WHERE ANIO = {anio}
  AND NOMBREEVENTOAGRP = '{evento_sql}'
  AND SEMANA != 53
GROUP BY PROVINCIA, CODIGO_PROVINCIA, SEMANA
ORDER BY SEMANA
"""
df = query_duckdb(query)

if df.empty:
    st.warning("No hay datos para el evento y año seleccionados.")
    st.stop()

sem_max = int(df["SEMANA"].max())
semanas = list(range(max(1, sem_max - ventana + 1), sem_max + 1))
df = df[df["SEMANA"].isin(semanas)].copy()

df["CODIGO_PROVINCIA"] = df["CODIGO_PROVINCIA"].astype(str).str.zfill(2)

if metrica == "Tasa x100k":
    pob = load_population_province(anio)
    if pob.empty:
        st.warning("No hay datos de población para ese año; se muestran casos absolutos.")
        metrica = "Casos"
    else:
        pob = pob[pob["sexo_nombre"] == "Ambos sexos"].copy()
        pob = pob.groupby("juri", as_index=False)["poblacion"].sum()
        pob["juri"] = pob["juri"].astype(str).str.zfill(2)
        df = df.merge(pob[["juri", "poblacion"]], left_on="CODIGO_PROVINCIA", right_on="juri", how="left")
        df["VALOR"] = df["CANTIDAD"] / df["poblacion"] * 100000
else:
    df["VALOR"] = df["CANTIDAD"]

pivot = (
    df.pivot_table(index="PROVINCIA", columns="SEMANA", values="VALOR", aggfunc="sum", fill_value=0)
    .reindex(columns=semanas, fill_value=0)
)

if pivot.empty:
    st.warning("No hay datos suficientes para armar el ranking.")
    st.stop()

# Top 12 provincias por volumen acumulado en la ventana
totales = pivot.sum(axis=1).sort_values(ascending=False)
top = totales.head(12).index.tolist()
pivot_top = pivot.loc[top]

rank = pivot_top.rank(axis=0, ascending=False, method="min")

# ── KPIs ──────────────────────────────────────────────────────────────────────
ult, pri = semanas[-1], semanas[0]
lider = pivot_top[ult].idxmax()
casos_lider = pivot_top.loc[lider, ult]

mejoras = (rank[pri] - rank[ult]).dropna().sort_values(ascending=False)
sube = mejoras.index[0] if len(mejoras) else None
baja = mejoras.index[-1] if len(mejoras) else None

k1, k2, k3, k4 = st.columns(4)
k1.metric("Líder actual", lider.title(), f"{casos_lider:,.1f}".replace(",", "."))
k2.metric("Mayor suba", sube.title() if sube else "—",
          f"{mejoras.loc[sube]:+.0f} puestos" if sube is not None else None)
k3.metric("Mayor caída", baja.title() if baja else "—",
          f"{mejoras.loc[baja]:+.0f} puestos" if baja is not None else None)
k4.metric("Semanas analizadas", f"{len(semanas)}", f"SE {semanas[0]} a {ult}")

# ── Bump chart ────────────────────────────────────────────────────────────────
fig = go.Figure()
for i, prov in enumerate(pivot_top.index):
    color = PALETA[i % len(PALETA)]
    fig.add_trace(go.Scatter(
        x=semanas,
        y=rank.loc[prov].values,
        mode="lines+markers",
        name=prov.title(),
        line=dict(color=color, width=2.6 if i == 0 else 1.9),
        marker=dict(size=6, color=color),
        hovertemplate=(
            f"<b>{prov.title()}</b><br>SE %{{x}}<br>"
            f"Puesto %{{y}}<extra></extra>"
        ),
    ))

style_fig(
    fig,
    height=620,
    titulo=f"Ranking semanal — {evento} {anio} ({metrica})",
    x_title="Semana epidemiológica",
    y_title="Puesto (1 = mayor valor)",
    hovermode="closest",
)
fig.update_yaxes(autorange="reversed", dtick=1, range=[len(pivot_top) + 0.5, 0.5])
fig.update_xaxes(dtick=1)
st.plotly_chart(fig, width="stretch")
st.caption(
    "Cada línea es una provincia del top 12 por volumen. El eje Y está invertido: "
    "arriba = mejor puesto. Sirve para ver relevos de liderazgo y brotes que escalan rápido."
)

# ── Tabla de posiciones ───────────────────────────────────────────────────────
st.subheader("Tabla de posiciones")
tabla = pd.DataFrame({
    "Provincia": [p.title() for p in pivot_top.index],
    f"Valor SE {ult}": pivot_top[ult].round(1).values,
    "Promedio ventana": pivot_top.mean(axis=1).round(1).values,
    f"Puesto SE {ult}": rank[ult].astype(int).values,
    f"Puesto SE {pri}": rank[pri].astype(int).values,
    "Cambio": (rank[pri] - rank[ult]).astype(int).values,
})
tabla = tabla.sort_values(f"Puesto SE {ult}")
st.dataframe(tabla, width="stretch", hide_index=True)

csv = tabla.to_csv(index=False).encode("utf-8-sig")
st.download_button("Descargar CSV", csv, f"ranking_{evento}_{anio}_SE{ult}.csv", "text/csv")

st.caption("Cambio positivo = la provincia subió puestos (mejor posición) en la ventana analizada.")
show_data_corte()
