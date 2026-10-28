import os

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.common import (
    BIVAR_COLORS,
    download_excel,
    get_distinct_events,
    get_distinct_years,
    get_parquet_path,
    query_duckdb,
    show_semana_actual,
)

st.set_page_config(page_title="Epidemiologia - Mapas Nacionales", page_icon=":world_map:", layout="wide")
show_semana_actual()
st.title("🌎 Mapas Nacionales de Casos y Tasas")


@st.cache_data
def load_geojson_files():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    geojson_prov = os.path.join(base_dir, 'data', 'provincia.json')
    geojson_depto = os.path.join(base_dir, 'data', 'departamento.json')

    try:
        gdf_prov = gpd.read_file(geojson_prov)
        gdf_prov['geometry'] = gdf_prov['geometry'].simplify(tolerance=0.01, preserve_topology=True)

        if os.path.exists(geojson_depto):
            gdf_depto = gpd.read_file(geojson_depto)
            gdf_depto['geometry'] = gdf_depto['geometry'].simplify(tolerance=0.01, preserve_topology=True)
        else:
            st.error("Archivo departamento.json no encontrado.")
            st.stop()

        return gdf_prov, gdf_depto
    except Exception as e:
        st.error(f"Error cargando GeoJSON: {e}")
        st.stop()


@st.cache_data
def load_population_data():
    prov_parquet = get_parquet_path('poblacionxprovinciaindec.parquet')
    dept_parquet = get_parquet_path('proyecciones_depto_indec.parquet')

    try:
        poblacion_prov = pd.read_parquet(prov_parquet)
        poblacion_depto = pd.read_parquet(dept_parquet)

        poblacion_depto["juri"] = poblacion_depto["juri"].astype(str).str.zfill(5)
        poblacion_depto = poblacion_depto[poblacion_depto["sexo_nombre"] == "Ambos sexos"]
        poblacion_depto = poblacion_depto.groupby(["ano", "juri", "juri_nombre"], as_index=False)["poblacion"].sum()

        poblacion_prov = poblacion_prov[poblacion_prov["sexo_nombre"] == "Ambos sexos"]
        poblacion_prov = poblacion_prov.groupby(["ano", "juri", "juri_nombre"], as_index=False)["poblacion"].sum()

        return poblacion_prov, poblacion_depto
    except Exception as e:
        st.error(f"Error cargando población desde Parquet: {e}")
        st.stop()


with st.spinner('Cargando datos geográficos y de población...'):
    gdf_prov, gdf_depto = load_geojson_files()
    poblacion_prov, poblacion_depto = load_population_data()

col1, col2, col3 = st.columns(3)
with col1:
    years = get_distinct_years()
    anio = st.selectbox("Año", years)
with col2:
    events = get_distinct_events()
    evento = st.selectbox("Evento", events)
with col3:
    metrica = st.selectbox("Métrica", ["Casos", "Tasa x100k"])

if st.button("Generar Mapas", key="gen_map_btn"):
    st.session_state.generate_map = True
elif "generate_map" not in st.session_state:
    st.session_state.generate_map = False

if not st.session_state.generate_map:
    st.info("Selecciona los filtros y haz clic en 'Generar Mapas' para visualizar.")
    st.stop()

escaped_event = evento.replace("'", "''")
query = f"""
SELECT CODIGO_PROVINCIA, PROVINCIA, DEPARTAMENTO, COD_DEPTO, ANIO, SEMANA, NOMBREEVENTOAGRP, CANTIDAD
FROM {{parquet}}
WHERE ANIO = {anio} AND NOMBREEVENTOAGRP = '{escaped_event}'
"""
filtered = query_duckdb(query)

if filtered.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

filtered['CODIGO_PROVINCIA'] = filtered['CODIGO_PROVINCIA'].astype(str).str.zfill(2)
filtered['COD_DEPTO'] = filtered['COD_DEPTO'].astype(str).str.zfill(5)

# Agrupamos datos por nivel territorial
df_agrupado = filtered.groupby(['PROVINCIA', 'DEPARTAMENTO', 'ANIO', 'NOMBREEVENTOAGRP'], as_index=False).agg({
    'CODIGO_PROVINCIA': 'first',
    'COD_DEPTO': 'first',
    'CANTIDAD': 'sum'
})

tab_mapa, tab_biv, tab_carto = st.tabs([
    "🗺️ Provincia / Departamento",
    "🎨 Bivariado (incidencia × tendencia)",
    "🔵 Cartograma (burbujas)",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Mapas tradicionales por provincia y departamento
# ─────────────────────────────────────────────────────────────────────────────
with tab_mapa:
    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("Nivel Provincia")
        agrupado_prov = df_agrupado.groupby(["PROVINCIA", "CODIGO_PROVINCIA"], as_index=False)["CANTIDAD"].sum()
        merge_prov = gdf_prov.merge(agrupado_prov, left_on='in1', right_on='CODIGO_PROVINCIA', how='left')
        merge_prov["CANTIDAD"] = merge_prov["CANTIDAD"].fillna(0)

        poblacion_prov_filtrada = poblacion_prov[poblacion_prov["ano"] == anio].copy()
        poblacion_prov_filtrada['juri'] = poblacion_prov_filtrada['juri'].astype(str).str.zfill(2)
        merge_prov = merge_prov.merge(
            poblacion_prov_filtrada[['juri', 'poblacion']],
            left_on='CODIGO_PROVINCIA',
            right_on='juri',
            how='left'
        )
        merge_prov["TASA"] = (merge_prov["CANTIDAD"] / merge_prov["poblacion"]) * 100000
        merge_prov["TASA"] = merge_prov["TASA"].round(2)

        if metrica == "Tasa x100k":
            color_col_prov = "TASA"
            title_prov = f"Tasa x100k - {evento} (Provincia)"
        else:
            color_col_prov = "CANTIDAD"
            title_prov = f"Casos - {evento} (Provincia)"

        fig_prov = px.choropleth_map(
            merge_prov,
            geojson=merge_prov.geometry.__geo_interface__,
            locations=merge_prov.index,
            color=color_col_prov,
            hover_name="nam",
            hover_data={color_col_prov: ':.2f', "poblacion": True, "CANTIDAD": True} if metrica == "Tasa x100k" else {color_col_prov: True, "CANTIDAD": True},
            map_style="carto-positron",
            center={"lat": -38.0, "lon": -63.0},
            zoom=3,
            color_continuous_scale="Reds" if metrica == "Casos" else "Blues"
        )
        fig_prov.update_layout(
            height=600,
            margin=dict(l=0, r=0, t=30, b=0),
            title_text=title_prov,
            title_x=0.5
        )
        st.plotly_chart(fig_prov, width="stretch", config={'displayModeBar': False})

        if not merge_prov.empty:
            cols_prov = ["nam", "CANTIDAD"]
            rename_prov = {"nam": "Provincia", "CANTIDAD": "Casos"}
            if "poblacion" in merge_prov.columns:
                cols_prov.append("poblacion")
                rename_prov["poblacion"] = "Población"
            if color_col_prov not in cols_prov:
                cols_prov.append(color_col_prov)
                rename_prov[color_col_prov] = "Tasas"

            tabla_prov = merge_prov[cols_prov].copy()
            tabla_prov = tabla_prov.rename(columns=rename_prov)
            tabla_prov["Provincia"] = tabla_prov["Provincia"].str.title()
            tabla_prov = tabla_prov.drop_duplicates()
            if "Tasas" in tabla_prov.columns:
                tabla_prov = tabla_prov.sort_values("Tasas", ascending=False)
            if not tabla_prov.empty:
                st.write("Datos por Provincia")
                cols_mostrar = [c for c in ["Provincia", "Casos", "Población", "Tasas"] if c in tabla_prov.columns]
                st.dataframe(tabla_prov[cols_mostrar], width="stretch")
                excel_prov, name_prov = download_excel(tabla_prov, "mapa_provincia.xlsx")
                st.download_button("Descargar Excel Provincia", excel_prov, name_prov)

    with right_col:
        st.subheader("Nivel Departamento")
        agrupado_depto = df_agrupado.groupby(["DEPARTAMENTO", "COD_DEPTO", "PROVINCIA"], as_index=False)["CANTIDAD"].sum()
        merge_depto = gdf_depto.merge(agrupado_depto, left_on='in1', right_on='COD_DEPTO', how='left')
        merge_depto["CANTIDAD"] = merge_depto["CANTIDAD"].fillna(0)

        poblacion_depto_filtrada = poblacion_depto[poblacion_depto["ano"] == anio].copy()
        merge_depto = merge_depto.merge(
            poblacion_depto_filtrada[['juri', 'poblacion']],
            left_on='COD_DEPTO',
            right_on='juri',
            how='left'
        )

        merge_depto["TASA"] = (merge_depto["CANTIDAD"] / merge_depto["poblacion"]) * 100000
        merge_depto["TASA"] = merge_depto["TASA"].round(2)

        if metrica == "Tasa x100k":
            color_col_depto = "TASA"
            title_depto = f"Tasa x100k - {evento} (Departamento)"
        else:
            color_col_depto = "CANTIDAD"
            title_depto = f"Casos - {evento} (Departamento)"

        fig_depto = px.choropleth_map(
            merge_depto,
            geojson=merge_depto.geometry.__geo_interface__,
            locations=merge_depto.index,
            color=color_col_depto,
            hover_name="DEPARTAMENTO",
            hover_data={"PROVINCIA": True, color_col_depto: ':.2f' if metrica == "Tasa x100k" else True, "poblacion": True, "CANTIDAD": True},
            map_style="carto-positron",
            center={"lat": -38.0, "lon": -63.0},
            zoom=3,
            color_continuous_scale="Reds" if metrica == "Casos" else "Blues"
        )
        fig_depto.update_layout(
            height=600,
            margin=dict(l=0, r=0, t=30, b=0),
            title_text=title_depto,
            title_x=0.5
        )
        st.plotly_chart(fig_depto, width="stretch", config={'displayModeBar': False})

        if not merge_depto.empty:
            cols_depto = ["DEPARTAMENTO", "PROVINCIA", "CANTIDAD"]
            rename_depto = {"DEPARTAMENTO": "Departamento", "PROVINCIA": "Provincia", "CANTIDAD": "Casos"}
            if "poblacion" in merge_depto.columns:
                cols_depto.append("poblacion")
                rename_depto["poblacion"] = "Población"
            if color_col_depto not in cols_depto and color_col_depto != "CANTIDAD":
                cols_depto.append(color_col_depto)
                rename_depto[color_col_depto] = "Tasas"

            tabla_depto = merge_depto[cols_depto].copy()
            tabla_depto = tabla_depto.rename(columns=rename_depto)
            tabla_depto["Departamento"] = tabla_depto["Departamento"].str.title()
            tabla_depto["Provincia"] = tabla_depto["Provincia"].str.title()
            if "Población" in tabla_depto.columns:
                tabla_depto = tabla_depto.dropna(subset=["Casos", "Población"])
            tabla_depto = tabla_depto.drop_duplicates()
            if "Tasas" in tabla_depto.columns:
                tabla_depto = tabla_depto.sort_values("Tasas", ascending=False)
            if not tabla_depto.empty:
                st.write("Datos por Departamento")
                cols_mostrar = [c for c in ["Departamento", "Provincia", "Casos", "Población", "Tasas"] if c in tabla_depto.columns]
                st.dataframe(tabla_depto[cols_mostrar], width="stretch")
                excel_depto, name_depto = download_excel(tabla_depto, "mapa_departamento.xlsx")
                st.download_button("Descargar Excel Departamento", excel_depto, name_depto)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Mapa bivariado: incidencia (últimas 4 SE) × tendencia
# ─────────────────────────────────────────────────────────────────────────────
with tab_biv:
    st.markdown(
        "**¿Qué combina?** El **color** resume dos cosas a la vez: el *nivel* de incidencia de las "
        "últimas 4 semanas epidemiológicas y la *tendencia* respecto de las 4 semanas anteriores. "
        "Sirve para detectar de un vistazo dónde hay **más casos y además están subiendo**."
    )

    sql_sem = f"""
    SELECT COD_DEPTO, SEMANA, SUM(CANTIDAD) AS CANTIDAD
    FROM {{parquet}}
    WHERE ANIO = {anio} AND NOMBREEVENTOAGRP = '{escaped_event}'
    GROUP BY COD_DEPTO, SEMANA
    ORDER BY SEMANA
    """
    df_sem = query_duckdb(sql_sem)

    if df_sem.empty:
        st.warning("No hay datos semanales para los filtros seleccionados.")
    else:
        df_sem['COD_DEPTO'] = df_sem['COD_DEPTO'].astype(str).str.zfill(5)
        sem_max = int(df_sem['SEMANA'].max())
        rec_min = max(1, sem_max - 3)
        prev_max = sem_max - 4
        prev_min = max(1, sem_max - 7)

        reciente = df_sem[df_sem['SEMANA'] >= rec_min].groupby('COD_DEPTO')['CANTIDAD'].sum()
        previo = df_sem[(df_sem['SEMANA'] >= prev_min) & (df_sem['SEMANA'] <= prev_max)].groupby('COD_DEPTO')['CANTIDAD'].sum()

        biv = merge_depto[['COD_DEPTO', 'DEPARTAMENTO', 'PROVINCIA', 'CANTIDAD', 'poblacion', 'geometry']].copy()
        biv['RECIENTE'] = biv['COD_DEPTO'].map(reciente).fillna(0)
        biv['PREVIO'] = biv['COD_DEPTO'].map(previo).fillna(0)
        biv['INC_REC'] = (biv['RECIENTE'] / biv['poblacion']) * 100000
        biv['TEND'] = np.where(
            biv['PREVIO'] > 0,
            (biv['RECIENTE'] - biv['PREVIO']) / biv['PREVIO'] * 100,
            np.nan,
        )

        validos = biv.dropna(subset=['INC_REC', 'poblacion'])
        if len(validos) >= 3:
            c1, c2 = validos['INC_REC'].quantile([1 / 3, 2 / 3]).tolist()
        else:
            c1, c2 = 0.0, 0.0

        def clasificar_inc(v):
            if pd.isna(v):
                return None
            if v <= c1:
                return "baja"
            if v <= c2:
                return "media"
            return "alta"

        def clasificar_tend(v):
            if pd.isna(v):
                return "estable"
            if v <= -10:
                return "baja"
            if v < 10:
                return "estable"
            return "alta"

        biv['CAT_INC'] = biv['INC_REC'].apply(clasificar_inc)
        biv['CAT_TEND'] = biv['TEND'].apply(clasificar_tend)
        biv['CATEGORIA'] = np.where(
            biv['CAT_INC'].notna(),
            "Inc. " + biv['CAT_INC'].astype(str) + " · Tend. " + biv['CAT_TEND'].astype(str),
            "Sin datos",
        )

        colores = dict(BIVAR_COLORS)
        colores["Sin datos"] = "#f2f2f2"

        fig_biv = px.choropleth_map(
            biv,
            geojson=biv.geometry.__geo_interface__,
            locations=biv.index,
            color="CATEGORIA",
            color_discrete_map=colores,
            category_orders={"CATEGORIA": list(BIVAR_COLORS) + ["Sin datos"]},
            hover_name="DEPARTAMENTO",
            hover_data={
                "PROVINCIA": True,
                "CANTIDAD": True,
                "RECIENTE": True,
                "PREVIO": True,
                "INC_REC": ':.2f',
                "TEND": ':.1f',
                "poblacion": True,
            },
            map_style="carto-positron",
            center={"lat": -38.0, "lon": -63.0},
            zoom=3,
            labels={"INC_REC": "Incidencia x100k (4 SE)", "TEND": "Tendencia %"},
        )
        fig_biv.update_layout(
            height=640,
            margin=dict(l=0, r=0, t=50, b=0),
            title_text=f"Bivariado — {evento} {anio} · incidencia SE {rec_min}-{sem_max} vs tendencia",
            title_x=0.5,
            legend=dict(title="Incidencia · Tendencia", orientation="v", yanchor="top", y=0.98, x=0.01, bgcolor="rgba(255,255,255,0.75)"),
        )
        st.plotly_chart(fig_biv, width="stretch", config={'displayModeBar': False})

        # Leyenda explicativa 3x3
        st.markdown("##### Cómo leer el color")
        filas = [("Inc. alta", "alta"), ("Inc. media", "media"), ("Inc. baja", "baja")]
        cols = [("Tend. baja", "baja"), ("Tend. estable", "estable"), ("Tend. alta", "alta")]
        html = '<table style="border-collapse:collapse; font-size:.9rem;">'
        html += '<tr><th></th>' + ''.join(f'<th style="padding:6px 14px;">{c[0]}</th>' for c in cols) + '</tr>'
        for nombre_fila, fila in filas:
            html += f'<tr><th style="padding:6px 14px; text-align:right;">{nombre_fila}</th>'
            for _, col in cols:
                color = BIVAR_COLORS[f"Inc. {fila} · Tend. {col}"]
                html += f'<td style="background:{color}; padding:14px 20px;"></td>'
            html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)
        st.caption(
            "Incidencia = casos de las últimas 4 SE cada 100.000 habitantes (terciles del país). "
            "Tendencia = variación % de esas 4 SE contra las 4 anteriores (baja ≤ -10%, alta ≥ +10%). "
            "Los departamentos sin datos de población o sin semanas previas quedan en gris."
        )

        tabla_biv = biv[['DEPARTAMENTO', 'PROVINCIA', 'CANTIDAD', 'RECIENTE', 'PREVIO', 'INC_REC', 'TEND', 'CATEGORIA']].copy()
        tabla_biv.columns = ['Departamento', 'Provincia', 'Casos año', f'Casos SE {rec_min}-{sem_max}', 'Casos 4 SE previas', 'Incidencia x100k', 'Tendencia %', 'Categoría']
        tabla_biv = tabla_biv.sort_values(['Incidencia x100k', 'Tendencia %'], ascending=False)
        st.dataframe(
            tabla_biv.style.format({
                'Incidencia x100k': '{:,.1f}',
                'Tendencia %': '{:+,.1f}',
            }, thousands='.', decimal=','),
            width="stretch",
            height=320,
        )
        excel_biv, name_biv = download_excel(tabla_biv, f"mapa_bivariado_{evento}_{anio}.xlsx")
        st.download_button("Descargar Excel bivariado", excel_biv, name_biv)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Cartograma de símbolos proporcionales (burbujas por provincia)
# ─────────────────────────────────────────────────────────────────────────────
with tab_carto:
    st.markdown(
        "**Cartograma de símbolos proporcionales.** Cada provincia se ubica en su centro "
        "geográfico: el **tamaño** de la burbuja representa los casos y el **color** la tasa "
        "cada 100.000 habitantes. Es la forma práctica de hacer un cartograma sin deformar "
        "los límites reales del país."
    )

    carto = merge_prov.dropna(subset=['poblacion']).copy()
    centros = carto.geometry.representative_point()
    carto['lon'] = centros.x
    carto['lat'] = centros.y

    if carto.empty:
        st.warning("No hay datos de población para el año seleccionado.")
    else:
        fig_carto = px.scatter_map(
            carto,
            lat='lat',
            lon='lon',
            size='CANTIDAD',
            color='TASA',
            hover_name='nam',
            hover_data={
                'CANTIDAD': True,
                'TASA': ':.1f',
                'poblacion': True,
                'lat': False,
                'lon': False,
            },
            size_max=55,
            zoom=3,
            center={"lat": -38.0, "lon": -63.0},
            map_style="carto-positron",
            color_continuous_scale="Reds",
            labels={'TASA': 'Tasa x100k', 'CANTIDAD': 'Casos'},
        )
        fig_carto.update_layout(
            height=640,
            margin=dict(l=0, r=0, t=50, b=0),
            title_text=f"Cartograma de burbujas — {evento} {anio} (tamaño: casos · color: tasa x100k)",
            title_x=0.5,
        )
        st.plotly_chart(fig_carto, width="stretch", config={'displayModeBar': False})
        st.caption(
            "Útil para comparar provincias grandes y despobladas contra provincias chicas y densas: "
            "el tamaño muestra el volumen absoluto y el color el riesgo relativo."
        )
