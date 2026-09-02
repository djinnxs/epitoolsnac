import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import os

sys.path.append(str(Path(__file__).resolve().parent.parent))

from utils.common import (
    query_duckdb,
    download_excel,
    get_distinct_years,
    get_distinct_events,
    get_distinct_provinces,
    get_distinct_departments,
    get_parquet_path,
    load_population_province,
    load_population_department,
    style_argentina
)

st.set_page_config(page_title="Epidemiología - Tasas Nacionales", page_icon=":bar_chart:", layout="wide")

st.title("📊 Tasas de Casos")

@st.cache_data
def load_rs_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, 'data', 'RS.csv'),
        os.path.join(base_dir, 'data', 'RegionesSanitarias.csv'),
        os.path.join(base_dir, 'data', 'RSPBA.csv'),
    ]
    for csv_path in candidates:
        if os.path.exists(csv_path):
            try:
                df_rs = pd.read_csv(csv_path, sep=';', dtype={'CODIGO_LOCALIDAD': str})
                df_rs['CODIGO_LOCALIDAD'] = df_rs['CODIGO_LOCALIDAD'].str.zfill(5)
                return df_rs
            except Exception:
                continue
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_departments_by_province(provincia):
    path = get_parquet_path().replace('\\', '/')
    q = f"SELECT DISTINCT DEPARTAMENTO FROM '{path}' WHERE PROVINCIA = '{provincia}' AND DEPARTAMENTO IS NOT NULL ORDER BY DEPARTAMENTO"
    df = query_duckdb(q)
    return df['DEPARTAMENTO'].tolist() if not df.empty else []

years = get_distinct_years()
events = get_distinct_events()
provincias = get_distinct_provinces()

col1, col2 = st.columns(2)
with col1:
    anio = st.selectbox("Año", years)
with col2:
    evento = st.selectbox("Evento", events)

col3, col4 = st.columns(2)
with col3:
    prov_opciones = ["Todas"] + provincias
    filtro_provincia = st.selectbox("Provincia", prov_opciones)

with col4:
    if filtro_provincia and filtro_provincia != "Todas":
        deptos_disponibles = get_departments_by_province(filtro_provincia)
    else:
        deptos_disponibles = get_distinct_departments()
    filtro_depto = st.multiselect("Departamento", deptos_disponibles)

mostrar_rs = False
if filtro_provincia and filtro_provincia.lower() == "buenos aires":
    mostrar_rs = st.checkbox("Ver por Región Sanitaria", value=False)

if st.button('🚀 Generar Tabla de Tasas', type="primary"):
    st.session_state.generar_tasas = True

if st.session_state.get("generar_tasas"):
    poblacion_prov = load_population_province(anio)
    poblacion_depto = load_population_department(anio)

    if not poblacion_prov.empty:
        poblacion_prov = poblacion_prov[poblacion_prov["sexo_nombre"] == "Ambos sexos"]
        poblacion_prov = poblacion_prov.groupby(["ano", "juri", "juri_nombre"], as_index=False)["poblacion"].sum()
        poblacion_prov["juri"] = poblacion_prov["juri"].astype(str).str.zfill(2)

    if not poblacion_depto.empty:
        poblacion_depto = poblacion_depto[poblacion_depto["sexo_nombre"] == "Ambos sexos"]
        poblacion_depto = poblacion_depto.groupby(["ano", "juri", "juri_nombre"], as_index=False)["poblacion"].sum()
        poblacion_depto["juri"] = poblacion_depto["juri"].astype(str).str.zfill(5)

    where_parts = [f"ANIO = {anio}", f"NOMBREEVENTOAGRP = '{evento}'"]
    if filtro_provincia and filtro_provincia != "Todas":
        where_parts.append(f"PROVINCIA = '{filtro_provincia}'")
    if filtro_depto:
        depto_str = ", ".join([f"'{d}'" for d in filtro_depto])
        where_parts.append(f"DEPARTAMENTO IN ({depto_str})")

    sql_query = f"""
    SELECT CODIGO_PROVINCIA, PROVINCIA, DEPARTAMENTO, COD_DEPTO, ANIO, NOMBREEVENTOAGRP, CANTIDAD
    FROM {{parquet}}
    WHERE {' AND '.join(where_parts)}
    """
    filtered = query_duckdb(sql_query)

    if filtered.empty:
        st.warning(f"No se encontraron registros para los filtros seleccionados.")
    else:
        filtered['CODIGO_PROVINCIA'] = filtered['CODIGO_PROVINCIA'].astype(str).str.zfill(2)
        filtered['COD_DEPTO'] = filtered['COD_DEPTO'].astype(str).str.zfill(5)

        if mostrar_rs and filtro_provincia.lower() == "buenos aires":
            st.subheader(f"Tasas por Región Sanitaria - {evento} ({anio})")
            df_rs = load_rs_data()
            if df_rs.empty:
                st.warning("No se encontró archivo de Regiones Sanitarias. Verificá que exista RS.csv, RegionesSanitarias.csv o RSPBA.csv en data/")
            else:
                df_rs_merged = filtered.merge(df_rs, left_on='COD_DEPTO', right_on='CODIGO_LOCALIDAD')
                if df_rs_merged.empty:
                    st.info("No hay datos de Región Sanitaria para los filtros seleccionados.")
                else:
                    rs_agrupado = df_rs_merged.groupby("RS", as_index=False)["CANTIDAD"].sum()
                    pob_rs = poblacion_depto.merge(
                        df_rs, left_on='juri', right_on='CODIGO_LOCALIDAD'
                    ).groupby("RS", as_index=False)["poblacion"].sum()
                    result_rs = rs_agrupado.merge(pob_rs, on='RS', how='left')
                    result_rs['Tasas'] = (result_rs['CANTIDAD'] / result_rs['poblacion']) * 100000
                    result = result_rs[['RS', 'CANTIDAD', 'poblacion', 'Tasas']].copy()
                    result.columns = ['Región Sanitaria', 'Casos', 'Población', 'Tasa x100k']
                    result = result.sort_values('Tasa x100k', ascending=False)
                    st.dataframe(style_argentina(result.style), width="stretch")
                    excel_data, excel_name = download_excel(result, f"tasas_region_sanitaria_{anio}.xlsx")
                    st.download_button("📥 Descargar Excel Región Sanitaria", excel_data, excel_name)

        elif filtro_depto:
            st.subheader(f"Tasas por Departamento - {evento} ({anio})")
            agrupado_depto = filtered.groupby(["DEPARTAMENTO", "COD_DEPTO", "PROVINCIA"], as_index=False)["CANTIDAD"].sum()
            merged = pd.merge(agrupado_depto, poblacion_depto, left_on='COD_DEPTO', right_on='juri', how='left')
            merged['Tasas'] = (merged['CANTIDAD'] / merged['poblacion']) * 100000
            merged['DEPARTAMENTO'] = merged['DEPARTAMENTO'].str.title()
            result = merged[['DEPARTAMENTO', 'PROVINCIA', 'CANTIDAD', 'poblacion', 'Tasas']].copy()
            result.columns = ['Departamento', 'Provincia', 'Casos', 'Población', 'Tasa x100k']
            result = result.sort_values('Tasa x100k', ascending=False)
            st.dataframe(style_argentina(result.style), width="stretch")
            excel_data, excel_name = download_excel(result, f"tasas_departamento_{anio}.xlsx")
            st.download_button("📥 Descargar Excel Departamentos", excel_data, excel_name)

        else:
            st.subheader(f"Tasas por Provincia - {evento} ({anio})")
            agrupado_prov = filtered.groupby(["PROVINCIA", "CODIGO_PROVINCIA"], as_index=False)["CANTIDAD"].sum()
            merged = pd.merge(agrupado_prov, poblacion_prov, left_on='CODIGO_PROVINCIA', right_on='juri', how='left')
            merged['Tasas'] = (merged['CANTIDAD'] / merged['poblacion']) * 100000
            merged['PROVINCIA'] = merged['PROVINCIA'].str.title()
            result = merged[['PROVINCIA', 'CANTIDAD', 'poblacion', 'Tasas']].copy()
            result.columns = ['Provincia', 'Casos', 'Población', 'Tasa x100k']
            result = result.sort_values('Tasa x100k', ascending=False)
            st.dataframe(style_argentina(result.style), width="stretch")
            excel_data, excel_name = download_excel(result, f"tasas_provincia_{anio}.xlsx")
            st.download_button("📥 Descargar Excel Provincias", excel_data, excel_name)
