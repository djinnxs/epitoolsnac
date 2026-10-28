# pages/3_CasosSemana.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import math

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils.common import (
    PALETA,
    get_data_corte,
    query_duckdb,
    show_data_corte,
    show_semana_actual,
    style_fig,
)

st.set_page_config(page_title="Epidemiologia", page_icon=":bar_chart:", layout="wide")
show_semana_actual()

# Solo el título sin logo
st.markdown('<center><h3 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;">&#x1F4C8; Casos por semana por año</h3></center>', unsafe_allow_html=True)

# DuckDB query
query = """
SELECT ANIO, SEMANA, NOMBREEVENTOAGRP, GRUPO, CANTIDAD
FROM {parquet}
WHERE SEMANA != 53
"""
df = query_duckdb(query)

if df.empty:
    st.warning("No hay datos disponibles.")
    st.stop()

# Filtros: fila 1 -> Evento | Grupo etario ; fila 2 -> Años | Semana
col1, col2 = st.columns(2)
with col1:
    evento = st.selectbox("Evento", sorted(df["NOMBREEVENTOAGRP"].dropna().unique()))
with col2:
    # Orden fijo para grupos etarios
    GRUPO_ORDER = [
        "< 6 m",
        "6 a 11 m",
        "12 a 23 m",
        "2 a 4",
        "5 a 9",
        "10 a 14",
        "15 a 19",
        "20 a 24",
        "25 a 34",
        "35 a 44",
        "45 a 64",
        "65 a 74",
        ">= a 75",
        "Pediát <3",
        "Pediát >=3",
        "Adultos <60",
        "Adultos >=60",
        "Edad Sin Esp."
    ]
    available_grupos = list(df["GRUPO"].dropna().unique())
    ordered_grupos = [g for g in GRUPO_ORDER if g in available_grupos]
    remaining_grupos = sorted([g for g in available_grupos if g not in ordered_grupos])
    grupo_options = ordered_grupos + remaining_grupos
    grupo = st.multiselect("Grupo etario", grupo_options)

col3, col4 = st.columns(2)
available_years = sorted(df["ANIO"].dropna().unique())
default_years = available_years[:2] if len(available_years) >= 2 else available_years
with col3:
    anios = st.multiselect("Años", available_years, default=list(default_years))
with col4:
    # Por defecto, la última semana con datos (corte), no la 52.
    _corte = get_data_corte()
    _sem_default = _corte["semana"] if _corte and 1 <= _corte["semana"] <= 52 else 52
    semana = st.selectbox("Semana", list(range(1, 53)), index=_sem_default - 1)

# Aplicar filtros
df_filt = df.copy()
df_filt = df_filt[df_filt["NOMBREEVENTOAGRP"] == evento]
if grupo:
    df_filt = df_filt[df_filt["GRUPO"].isin(grupo)]
if anios:
    df_filt = df_filt[df_filt["ANIO"].isin(anios)]

# Pivot y reindex hasta la semana seleccionada
df_pivot = df_filt.pivot_table(values="CANTIDAD", index="SEMANA", columns="ANIO", aggfunc='sum', fill_value=0)
df_pivot = df_pivot.reindex(range(1, semana + 1), fill_value=0)

tab_linea, tab_grid = st.tabs(["📈 Comparación por año", "🔳 Small multiples (grilla por año)"])

with tab_linea:
    if df_pivot.empty:
        st.warning("No hay datos para la combinación de filtros seleccionada.")
    else:
        fig = px.line(
            df_pivot,
            x=df_pivot.index,
            y=df_pivot.columns,
            title=f"{evento} - Comparación por Año (hasta semana {semana})",
        )
        style_fig(fig, height=460, x_title="Semana epidemiológica", y_title="Casos")
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "Cada línea es un año. El eje X es la **semana epidemiológica** (1 a 52), "
            "así los años quedan comparables semana a semana."
        )

with tab_grid:
    st.markdown(f"**Small multiples — {evento}** · cada panel es un año (hasta SE {semana})")

    df_all = df[df["NOMBREEVENTOAGRP"] == evento]
    if grupo:
        df_all = df_all[df_all["GRUPO"].isin(grupo)]

    piv_all = df_all.pivot_table(values="CANTIDAD", index="SEMANA", columns="ANIO", aggfunc="sum", fill_value=0)
    piv_all = piv_all.reindex(range(1, semana + 1), fill_value=0)

    if piv_all.empty:
        st.warning("No hay datos para la combinación de filtros seleccionada.")
    else:
        years_all = [int(c) for c in piv_all.columns]
        ncols = min(4, len(years_all))
        nrows = math.ceil(len(years_all) / ncols)
        alto = 165 * nrows + 90

        fig_grid = make_subplots(
            rows=nrows,
            cols=ncols,
            shared_xaxes=True,
            subplot_titles=[str(y) for y in years_all],
            vertical_spacing=0.10 if nrows > 1 else 0.16,
            horizontal_spacing=0.05,
        )

        for i, year in enumerate(years_all):
            r, c = divmod(i, ncols)
            r += 1
            c += 1
            y_vals = piv_all[year].to_numpy()
            destacado = year in [int(a) for a in anios]
            color = PALETA[0] if destacado else "#b9b9b9"

            fig_grid.add_trace(
                go.Scatter(
                    x=piv_all.index,
                    y=y_vals,
                    mode="lines",
                    line=dict(color=color, width=2.4 if destacado else 1.4),
                    showlegend=False,
                    hovertemplate=f"{year} · SE %{{x}}<br>%{{y}} casos<extra></extra>",
                ),
                row=r,
                col=c,
            )

            if destacado and len(y_vals) and y_vals.max() > 0:
                idx_pico = int(y_vals.argmax())
                xp, yp = int(piv_all.index[idx_pico]), int(y_vals[idx_pico])
                fig_grid.add_trace(
                    go.Scatter(
                        x=[xp], y=[yp], mode="markers",
                        marker=dict(color=color, size=7),
                        showlegend=False, hoverinfo="skip",
                    ),
                    row=r,
                    col=c,
                )
                fig_grid.add_annotation(
                    x=xp, y=yp,
                    text=f"máx {yp:,}".replace(",", "."),
                    showarrow=False, yshift=12,
                    font=dict(size=9, color=color),
                    row=r, col=c,
                )

        fig_grid.update_xaxes(range=[1, semana], tickfont=dict(size=9), row=None, col=None)
        fig_grid.update_yaxes(tickfont=dict(size=9), row=None, col=None)
        style_fig(
            fig_grid,
            height=alto,
            titulo=f"Small multiples por año — {evento} (SE 1 a {semana})",
            hovermode="closest",
            mostrar_leyenda=False,
        )
        st.plotly_chart(fig_grid, width="stretch")
        st.caption(
            "Los años elegidos en el filtro se resaltan en azul (con su pico marcado); "
            "el resto queda en gris como referencia. Cada panel mantiene su propia escala "
            "para comparar la **forma** de la curva, no el volumen."
        )

show_data_corte()
