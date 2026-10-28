# pages/24_RetrasoReporte.py — Atraso y completitud del reporte por fuente
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.common import (
    get_data_corte,
    get_distinct_events,
    get_distinct_years,
    query_duckdb,
    show_data_corte,
    show_semana_actual,
    style_fig,
)

st.set_page_config(page_title="Retraso de Reporte", page_icon="⏳", layout="wide")
show_semana_actual()

st.title("⏳ Atraso y completitud del reporte por fuente")
st.markdown(
    "Detecta **qué provincias y eventos dejaron de reportar** (o reportan con atraso) "
    "respecto del último corte nacional. Es el control de calidad semanal de la base."
)

st.info(
    "**Nota metodológica.** La base registra la *fecha de registro* (que define la semana "
    "epidemiológica del dato), pero **no** la fecha del evento clínico. Por eso no se puede "
    "reconstruir el triángulo clásico de backfill (casos por semana de ocurrencia vs semana "
    "de notificación). Lo que sí se mide acá —y es igual de útil— es el **atraso de cada "
    "fuente**: cuántas semanas pasaron entre su último dato cargado y el corte nacional."
)

col1, col2 = st.columns(2)
with col1:
    anio = st.selectbox("Año", get_distinct_years())
with col2:
    evento = st.selectbox("Evento", ["Todos los eventos"] + get_distinct_events())

filtro_evento = "" if evento == "Todos los eventos" else f"AND NOMBREEVENTOAGRP = '{evento.replace(chr(39), chr(39) * 2)}'"

query = f"""
SELECT PROVINCIA, NOMBREEVENTOAGRP, SEMANA, SUM(CANTIDAD) AS CANTIDAD
FROM {{parquet}}
WHERE ANIO = {anio}
  {filtro_evento}
GROUP BY PROVINCIA, NOMBREEVENTOAGRP, SEMANA
"""
df = query_duckdb(query)

if df.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

corte = get_data_corte()
corte_se = corte["semana"] if (corte and corte["anio"] == anio) else int(df["SEMANA"].max())
df = df[df["SEMANA"] <= corte_se]

st.markdown(f"**Corte de referencia:** SE {corte_se} de {anio} · {df['PROVINCIA'].nunique()} provincias con datos")

tab_prov, tab_evento, tab_heat = st.tabs([
    "🏥 Por provincia",
    "🦠 Por evento",
    "🔥 Mapa de calor de reporte",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Atraso por provincia
# ─────────────────────────────────────────────────────────────────────────────
with tab_prov:
    ult_prov = df.groupby("PROVINCIA")["SEMANA"].max()
    atraso = (corte_se - ult_prov).astype(int)

    recientes = df[df["SEMANA"] > corte_se - 4].groupby("PROVINCIA")["CANTIDAD"].sum()

    tabla_prov = pd.DataFrame({
        "Provincia": ult_prov.index,
        "Última SE con datos": ult_prov.values,
        "Atraso (SE)": atraso.values,
        "Casos últimas 4 SE": [int(recientes.get(p, 0)) for p in ult_prov.index],
    }).sort_values(["Atraso (SE)", "Casos últimas 4 SE"], ascending=[False, False])

    al_dia = int((tabla_prov["Atraso (SE)"] <= 1).sum())
    atrasadas = int((tabla_prov["Atraso (SE)"] >= 2).sum())
    peor = tabla_prov.iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Provincias al día", f"{al_dia}", f"de {len(tabla_prov)}")
    k2.metric("Provincias atrasadas", f"{atrasadas}", "≥ 2 semanas", delta_color="inverse")
    k3.metric("Atraso promedio", f"{tabla_prov['Atraso (SE)'].mean():.1f} SE")
    k4.metric("Peor caso", str(peor["Provincia"]).title(), f"{int(peor['Atraso (SE)'])} SE de atraso", delta_color="inverse")

    colores = ["#2ca02c" if a <= 1 else "#ff7f0e" if a <= 2 else "#d62728" for a in tabla_prov["Atraso (SE)"]]

    fig = go.Figure(go.Bar(
        x=tabla_prov["Atraso (SE)"],
        y=[p.title() for p in tabla_prov["Provincia"]],
        orientation="h",
        marker_color=colores,
        text=tabla_prov["Atraso (SE)"],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Atraso: %{x} semanas<extra></extra>",
    ))
    style_fig(
        fig,
        height=max(380, 26 * len(tabla_prov) + 90),
        titulo=f"Atraso de reporte por provincia — {evento} ({anio})",
        x_title="Semanas de atraso respecto del corte",
        y_title=None,
        hovermode="closest",
        mostrar_leyenda=False,
    )
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=10))
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, width="stretch")

    st.caption("Verde: al día (0-1 SE). Naranja: 2 SE. Rojo: 3 o más semanas sin datos.")
    st.dataframe(tabla_prov, width="stretch", hide_index=True)

    csv = tabla_prov.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Descargar CSV", csv, f"atraso_provincias_{anio}.csv", "text/csv")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Atraso por evento
# ─────────────────────────────────────────────────────────────────────────────
with tab_evento:
    ult_ev = df.groupby("NOMBREEVENTOAGRP")["SEMANA"].max()
    total_ev = df.groupby("NOMBREEVENTOAGRP")["CANTIDAD"].sum()
    atraso_ev = (corte_se - ult_ev).astype(int)

    tabla_ev = pd.DataFrame({
        "Evento": ult_ev.index,
        "Casos en el año": [int(total_ev.get(e, 0)) for e in ult_ev.index],
        "Última SE con datos": ult_ev.values,
        "Atraso (SE)": atraso_ev.values,
    })
    tabla_ev = tabla_ev.sort_values("Casos en el año", ascending=False).head(20)
    tabla_ev = tabla_ev.sort_values("Atraso (SE)", ascending=False)

    colores_ev = ["#2ca02c" if a <= 1 else "#ff7f0e" if a <= 2 else "#d62728" for a in tabla_ev["Atraso (SE)"]]

    fig_ev = go.Figure(go.Bar(
        x=tabla_ev["Atraso (SE)"],
        y=tabla_ev["Evento"],
        orientation="h",
        marker_color=colores_ev,
        text=tabla_ev["Atraso (SE)"],
        textposition="outside",
        customdata=tabla_ev["Casos en el año"],
        hovertemplate="<b>%{y}</b><br>Atraso: %{x} SE<br>Casos en el año: %{customdata:,}<extra></extra>",
    ))
    style_fig(
        fig_ev,
        height=max(420, 24 * len(tabla_ev) + 100),
        titulo=f"Atraso de reporte por evento (top 20 por volumen) — {anio}",
        x_title="Semanas de atraso respecto del corte",
        hovermode="closest",
        mostrar_leyenda=False,
    )
    fig_ev.update_yaxes(autorange="reversed", tickfont=dict(size=10))
    fig_ev.update_xaxes(dtick=1)
    st.plotly_chart(fig_ev, width="stretch")

    st.dataframe(tabla_ev, width="stretch", hide_index=True)
    st.caption(
        "Un evento con muchas semanas de atraso puede deberse a que ya no circula "
        "(no hay casos nuevos) o a que dejó de notificarse. Conviene revisarlo con la vigilancia."
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Mapa de calor: provincia × semana (huecos de reporte)
# ─────────────────────────────────────────────────────────────────────────────
with tab_heat:
    n_sem = st.slider("Semanas a mostrar", min_value=6, max_value=26, value=12, step=1)
    semanas = list(range(max(1, corte_se - n_sem + 1), corte_se + 1))

    piv = (
        df[df["SEMANA"].isin(semanas)]
        .pivot_table(index="PROVINCIA", columns="SEMANA", values="CANTIDAD", aggfunc="sum", fill_value=0)
        .reindex(columns=semanas, fill_value=0)
    )

    # Ordenar por atraso (las fuentes más atrasadas arriba)
    orden = (corte_se - df.groupby("PROVINCIA")["SEMANA"].max()).sort_values(ascending=False)
    piv = piv.reindex([p for p in orden.index if p in piv.index])

    if piv.empty:
        st.warning("No hay datos para el período seleccionado.")
    else:
        fig_heat = go.Figure(go.Heatmap(
            z=piv.values,
            x=[f"SE{s}" for s in piv.columns],
            y=[p.title() for p in piv.index],
            colorscale="Blues",
            hovertemplate="<b>%{y}</b><br>%{x}<br>Casos: %{z}<extra></extra>",
            colorbar=dict(title="Casos"),
        ))
        style_fig(
            fig_heat,
            height=max(420, 24 * len(piv) + 120),
            titulo=f"Reporte semanal por provincia — últimas {n_sem} SE ({evento})",
            x_title="Semana epidemiológica",
            hovermode="closest",
            mostrar_leyenda=False,
        )
        fig_heat.update_yaxes(autorange="reversed", tickfont=dict(size=10))
        st.plotly_chart(fig_heat, width="stretch")
        st.caption(
            "Las celdas **blancas** son semanas sin ningún registro para esa provincia: "
            "pueden ser semanas sin casos o semanas sin reporte. Las provincias más atrasadas "
            "aparecen arriba, así los huecos se leen de un vistazo."
        )

show_data_corte()
