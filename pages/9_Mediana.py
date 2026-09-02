# pages/9_Mediana.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
import io
import locale
from utils.common import query_duckdb, get_distinct_events, get_distinct_years, get_distinct_provinces

st.set_page_config(page_title="Mediana", page_icon=":pencil:", layout="wide")

# Configurar la configuración regional
try:
    locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
except:
    locale.setlocale(locale.LC_ALL, '')

# Función para formatear números sin decimales, usando punto para miles y coma para decimales
def format_number(number):
    try:
        return locale.format_string('%.0f', number, grouping=True)
    except:
        return str(int(number)) if pd.notnull(number) else ''

st.markdown('<center><h3 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;"> Índice epidémico 📝 </h3></center>', unsafe_allow_html=True)

# Cargar filtros
events = get_distinct_events()
years = get_distinct_years()
provincias = get_distinct_provinces()

# Filtros en columnas
col1, col2, col3 = st.columns(3)
with col1:
    evento = st.multiselect("Elije el Evento", events)
with col2:
    if not years:
        years = [2024, 2023, 2022, 2021, 2020, 2019]
    year = st.selectbox("Selecciona el Año", years)
with col3:
    semana = st.selectbox("Selecciona la Semana", range(1, 53))

prov_opciones = ["Todas"] + provincias
filtro_provincia = st.selectbox("Provincia", prov_opciones)

calcular_tabla = st.button("Calcular Tabla")

if calcular_tabla:
    if not evento:
        st.warning("Por favor selecciona al menos un evento.")
        st.stop()

    # Construir lista de años para la query (año seleccionado y 4 anteriores)
    years_filter = [year, year - 1, year - 2, year - 3, year - 4]
    years_str = ",".join(map(str, years_filter))
    
    # Formatear eventos para SQL
    events_str = "', '".join(evento)
    
    # DuckDB query
    query = f"""
    SELECT PROVINCIA, DEPARTAMENTO, ANIO, SEMANA, ID_SNVS_EVENTO_AGRP,
           NOMBREEVENTOAGRP, IDEDAD, GRUPO, CANTIDAD, FECHAREGISTROCLINICA
    FROM {{parquet}}
    WHERE ANIO IN ({years_str})
      AND NOMBREEVENTOAGRP IN ('{events_str}')
      AND SEMANA != 53
    """

    if filtro_provincia and filtro_provincia != "Todas":
        query += f" AND PROVINCIA = '{filtro_provincia}'"
    
    clinica = query_duckdb(query)
    
    if clinica.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        es_provincial = not filtro_provincia or filtro_provincia == "Todas"

        if es_provincial:
            nivel_col = 'PROVINCIA'
            nombre_col = 'Provincia'
        else:
            nivel_col = 'DEPARTAMENTO'
            nombre_col = 'Departamento'

        clinica.sort_values([nivel_col], inplace=True)
        clinica.reset_index(drop=True, inplace=True)

        df_agrupado = clinica.groupby([nivel_col, 'ANIO', 'SEMANA', 'NOMBREEVENTOAGRP'], as_index=False).agg({
            'IDEDAD': 'first',
            'GRUPO': 'first',
            'CANTIDAD': 'sum'
        })

        df_agrupado = df_agrupado.sort_values(by=[nivel_col, 'ANIO']).reset_index(drop=True)

        df_semana = df_agrupado[df_agrupado['SEMANA'] == semana]
        df_acumulado = df_agrupado[df_agrupado['SEMANA'] <= semana]

        df_semana = df_semana.groupby([nivel_col, 'ANIO'], as_index=False)['CANTIDAD'].sum()
        df_acumulado = df_acumulado.groupby([nivel_col, 'ANIO'], as_index=False)['CANTIDAD'].sum()

        df_declarados = df_semana.pivot(index=nivel_col, columns='ANIO', values='CANTIDAD')
        df_acumulados = df_acumulado.pivot(index=nivel_col, columns='ANIO', values='CANTIDAD')

        df_mediana_sem = df_semana.groupby(nivel_col)['CANTIDAD'].median()
        df_mediana_acum = df_acumulado.groupby(nivel_col)['CANTIDAD'].sum() / df_acumulado.groupby(nivel_col).size()

        df_indice_epidemico_sem = df_semana.set_index(nivel_col)['CANTIDAD'] / df_mediana_sem
        df_indice_epidemico_acum = df_acumulado.groupby(nivel_col)['CANTIDAD'].sum() / df_mediana_acum

        all_indices = pd.Index(df_declarados.index.union(df_acumulados.index).union(df_mediana_sem.index).union(df_mediana_acum.index)).drop_duplicates()

        df_mediana_sem = df_mediana_sem.loc[~df_mediana_sem.index.duplicated(keep='first')].reindex(all_indices)
        df_mediana_acum = df_mediana_acum.loc[~df_mediana_acum.index.duplicated(keep='first')].reindex(all_indices)
        df_indice_epidemico_sem = df_indice_epidemico_sem.loc[~df_indice_epidemico_sem.index.duplicated(keep='first')].reindex(all_indices)
        df_indice_epidemico_acum = df_indice_epidemico_acum.loc[~df_indice_epidemico_acum.index.duplicated(keep='first')].reindex(all_indices)

        def _reindex_series(series, index):
            return series.loc[~series.index.duplicated(keep='first')].reindex(index)

        if year in df_declarados.columns:
            col_year = _reindex_series(df_declarados[year], all_indices)
        else:
            col_year = pd.Series(0, index=all_indices)

        if (year-1) in df_declarados.columns:
            col_year_prev = _reindex_series(df_declarados[year-1], all_indices)
        else:
            col_year_prev = pd.Series(0, index=all_indices)

        if year in df_acumulados.columns:
            col_acum_year = _reindex_series(df_acumulados[year], all_indices)
        else:
            col_acum_year = pd.Series(0, index=all_indices)

        if (year-1) in df_acumulados.columns:
            col_acum_year_prev = _reindex_series(df_acumulados[year-1], all_indices)
        else:
            col_acum_year_prev = pd.Series(0, index=all_indices)

        df_final = pd.DataFrame({
            nombre_col: all_indices,
            f'Casos declarados Sem {semana} {year-1}': col_year_prev.values,
            f'Casos declarados Sem {semana} {year}': col_year.values,
            f'Acumulados {year-1}': col_acum_year_prev.values,
            f'Acumulados {year}': col_acum_year.values,
            f'Mediana Sem {semana}': df_mediana_sem.values,
            'Mediana Acum.': df_mediana_acum.values,
            f'Índice epidémico Sem {semana}': df_indice_epidemico_sem.values,
            'Índice epidémico Acum.': df_indice_epidemico_acum.values,
        })

        if not es_provincial:
            provincia_map = clinica[['DEPARTAMENTO', 'PROVINCIA']].drop_duplicates(subset='DEPARTAMENTO', keep='first').set_index('DEPARTAMENTO')['PROVINCIA']
            df_final.insert(0, 'Provincia', df_final['Departamento'].map(provincia_map).fillna(''))
            cols = ['Provincia', 'Departamento'] + [c for c in df_final.columns if c not in ['Provincia', 'Departamento']]
            df_final = df_final[cols]

        df_final = df_final.sort_values(nombre_col).reset_index(drop=True)

        for col in df_final.columns:
            if col in ('Provincia', 'Departamento'):
                continue
            df_final[col] = df_final[col].apply(lambda x: format_number(x) if pd.notnull(x) else x)

        st.dataframe(df_final.style.background_gradient(cmap="Blues"))

        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        df_final.to_excel(writer, sheet_name='Sheet1', index=False)
        writer.close()

        st.download_button(
            label="Descargar Tabla en Excel",
            data=output.getvalue(),
            file_name='indice_epidemico.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )