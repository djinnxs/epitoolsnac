import streamlit as st
import pandas as pd
import geopandas as gpd
import os
import plotly.express as px
from utils.common import (
    query_duckdb,
    download_excel,
    get_distinct_years,
    get_distinct_events,
    get_parquet_path
)

st.set_page_config(page_title="Epidemiologia - Mapas Nacionales", page_icon=":world_map:", layout="wide")
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

query = """
SELECT CODIGO_PROVINCIA, PROVINCIA, DEPARTAMENTO, COD_DEPTO, ANIO, NOMBREEVENTOAGRP, CANTIDAD
FROM {parquet}
WHERE ANIO = {anio} AND NOMBREEVENTOAGRP = '{evento}'
"""
escaped_event = evento.replace("'", "''")
sql = query.format(parquet="{parquet}", anio=anio, evento=escaped_event)
filtered = query_duckdb(sql)

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

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Nivel Provincia")
    agrupado_prov = df_agrupado.groupby(["PROVINCIA", "CODIGO_PROVINCIA"], as_index=False)["CANTIDAD"].sum()
    merge_prov = gdf_prov.merge(agrupado_prov, left_on='in1', right_on='CODIGO_PROVINCIA', how='left')
    merge_prov["CANTIDAD"] = merge_prov["CANTIDAD"].fillna(0)

    if metrica == "Tasa x100k":
        poblacion_prov_filtrada = poblacion_prov[poblacion_prov["ano"] == anio].copy()
        poblacion_prov_filtrada['juri'] = poblacion_prov_filtrada['juri'].astype(str).str.zfill(2)
        merge_prov = merge_prov.merge(
            poblacion_prov_filtrada,
            left_on='CODIGO_PROVINCIA',
            right_on='juri',
            how='left'
        )
        merge_prov["TASA"] = (merge_prov["CANTIDAD"] / merge_prov["poblacion"]) * 100000
        merge_prov["TASA"] = merge_prov["TASA"].round(2)
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
    st.plotly_chart(fig_prov, use_container_width=True, config={'displayModeBar': False})

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
        tabla_prov.rename(columns=rename_prov, inplace=True)
        tabla_prov["Provincia"] = tabla_prov["Provincia"].str.title()
        tabla_prov = tabla_prov.drop_duplicates()
        if "Tasas" in tabla_prov.columns:
            tabla_prov = tabla_prov.sort_values("Tasas", ascending=False)
        if not tabla_prov.empty:
            st.write("Datos por Provincia")
            cols_mostrar = [c for c in ["Provincia", "Casos", "Población", "Tasas"] if c in tabla_prov.columns]
            st.dataframe(tabla_prov[cols_mostrar], use_container_width=True)
            excel_prov, name_prov = download_excel(tabla_prov, "mapa_provincia.xlsx")
            st.download_button("Descargar Excel Provincia", excel_prov, name_prov)

with right_col:
    st.subheader("Nivel Departamento")
    agrupado_depto = df_agrupado.groupby(["DEPARTAMENTO", "COD_DEPTO", "PROVINCIA"], as_index=False)["CANTIDAD"].sum()
    merge_depto = gdf_depto.merge(agrupado_depto, left_on='in1', right_on='COD_DEPTO', how='left')
    merge_depto["CANTIDAD"] = merge_depto["CANTIDAD"].fillna(0)

    poblacion_depto_filtrada = poblacion_depto[poblacion_depto["ano"] == anio].copy()
    merge_depto = merge_depto.merge(
        poblacion_depto_filtrada,
        left_on='COD_DEPTO',
        right_on='juri',
        how='left'
    )

    if metrica == "Tasa x100k":
        merge_depto["TASA"] = (merge_depto["CANTIDAD"] / merge_depto["poblacion"]) * 100000
        merge_depto["TASA"] = merge_depto["TASA"].round(2)
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
    st.plotly_chart(fig_depto, use_container_width=True, config={'displayModeBar': False})

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
        tabla_depto.rename(columns=rename_depto, inplace=True)
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
            st.dataframe(tabla_depto[cols_mostrar], use_container_width=True)
            excel_depto, name_depto = download_excel(tabla_depto, "mapa_departamento.xlsx")
            st.download_button("Descargar Excel Departamento", excel_depto, name_depto)
