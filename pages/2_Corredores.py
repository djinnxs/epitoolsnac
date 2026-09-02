import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts
import numpy as np
from datetime import date, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

# Lógica de Semana Epidemiológica (como en Calendario)
def get_epi_week(fecha):
    """Semana epidemiologica (semanas inician en domingo, SE1 contiene el 4 de enero)."""
    anio = fecha.year
    def inicio_se_1(year):
        cuatro_enero = date(year, 1, 4)
        retroceso = (cuatro_enero.weekday() + 1) % 7
        return cuatro_enero - timedelta(days=retroceso)
    inicio_actual = inicio_se_1(anio)
    if fecha < inicio_actual:
        inicio_anterior = inicio_se_1(anio - 1)
        return ((fecha - inicio_anterior).days // 7) + 1
    inicio_proximo = inicio_se_1(anio + 1)
    if fecha >= inicio_proximo:
        return 1
    return ((fecha - inicio_actual).days // 7) + 1

hoy = date.today()
semana_actual = get_epi_week(hoy)

st.set_page_config(page_title="Epidemiologia", page_icon=":bar_chart:", layout="wide")

# Esto descarga la librería de iconos para que los iconos de área funcionen
st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">', unsafe_allow_html=True)

# Título con Semana Actual resaltada
st.markdown(f'''<center>
    <h3 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;"><i class="fa-solid fa-chart-area"></i> SNVS Corredores endémicos</h3>
    <div style="background-color: #1e2130; color: #ffeb3b; padding: 10px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #4a6fa5;">
        📅 Semana Epidemiológica Actual: <b>{semana_actual}</b> del {hoy.year}
    </div>
</center>''', unsafe_allow_html=True)
# Solo el título sin logo
#st.markdown('<center><h3 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;">&#x1F4C8; SNVS Corredores endémicos</h3></center>', unsafe_allow_html=True)

from utils.common import query_duckdb, get_distinct_events, get_distinct_departments, get_distinct_years, get_distinct_provinces, get_parquet_path

# Cargar filtros
events = get_distinct_events()
provincias = get_distinct_provinces()

@st.cache_data(ttl=3600)
def get_departments_by_province(provincia):
    path = get_parquet_path().replace('\\', '/')
    query = f"SELECT DISTINCT DEPARTAMENTO FROM '{path}' WHERE PROVINCIA = '{provincia}' AND DEPARTAMENTO IS NOT NULL ORDER BY DEPARTAMENTO"
    df = query_duckdb(query)
    return df['DEPARTAMENTO'].tolist() if not df.empty else []

# --- Sección de filtros ---
col1, col2 = st.columns(2)

with col1:
    filtro_evento = st.multiselect("Elije el Evento", events)

with col2:
    filtro_anio = st.selectbox("Año", get_distinct_years())

col_prov, col_depto = st.columns(2)

with col_prov:
    provincias_opciones = ["Todas"] + provincias
    filtro_provincia = st.selectbox("Provincia", provincias_opciones)

with col_depto:
    if filtro_provincia and filtro_provincia != "Todas":
        deptos_disponibles = get_departments_by_province(filtro_provincia)
    else:
        deptos_disponibles = get_distinct_departments()
    filtro_partido = st.multiselect("Departamento", deptos_disponibles)

col4 = st.columns(1)[0]
with col4:
    filtro_semana = st.selectbox("Semana", list(range(1, 53)), index=semana_actual - 1 if 1 <= semana_actual <= 52 else 0)

# Si no se selecciona departamento, se incluyen todos los departamentos nacionales
partidos_filtro_final = filtro_partido if filtro_partido else []

# Botón para generar el gráfico
if st.button("Generar Gráfico"):
    # Construir query dinámica para DuckDB
    
    where_clauses = [
        f"ANIO >= {filtro_anio - 5}",
        f"ANIO <= {filtro_anio}",
        "SEMANA != 53"
    ]
    
    if filtro_evento:
        eventos_str = ", ".join([f"'{e}'" for e in filtro_evento])
        where_clauses.append(f"NOMBREEVENTOAGRP IN ({eventos_str})")

    if filtro_provincia and filtro_provincia != "Todas":
        where_clauses.append(f"PROVINCIA = '{filtro_provincia}'")

    if partidos_filtro_final:
        partido_str = ", ".join([f"'{p}'" for p in partidos_filtro_final])
        where_clauses.append(f"DEPARTAMENTO IN ({partido_str})")

    where_str = " AND ".join(where_clauses)
    
    query = f"""
    SELECT CODIGO_PROVINCIA, PROVINCIA, DEPARTAMENTO, ANIO, SEMANA, ID_SNVS_EVENTO_AGRP,
           NOMBREEVENTOAGRP, IDEDAD, GRUPO, CANTIDAD, FECHAREGISTROCLINICA
    FROM {{parquet}}
    WHERE {where_str}
    """
        
    clinica = query_duckdb(query)
    
    if clinica.empty:
        st.warning("No hay datos para los filtros seleccionados.")
    else:
        # Procesamiento
        # Ordenar las columnas alfabéticamente
        clinica.sort_values(['NOMBREEVENTOAGRP', 'DEPARTAMENTO'], inplace=True)
        clinica.reset_index(drop=True, inplace=True)
        
        datos_filtrados = clinica.copy()
        
        # Generar cuartiles y crear matriz
        datos_filtrados.sort_values(by=['ANIO', 'SEMANA'], inplace=True)
        matriz = datos_filtrados.pivot_table(index='ANIO', columns='SEMANA', values='CANTIDAD', aggfunc='sum', fill_value=0)

        # Calcular los cuartiles para los 5 años anteriores al seleccionado
        anos_anteriores = matriz.index[
            (matriz.index >= filtro_anio - 5) & (matriz.index < filtro_anio)
        ]
        if not anos_anteriores.empty:
            cuartiles = matriz.loc[anos_anteriores].apply(lambda x: pd.Series(x).quantile([0.25, 0.5, 0.75])).T
            cuartiles.columns = ['Exito', 'Seguridad', 'Alerta']
            
            # Obtener los datos del año seleccionado
            if filtro_anio in matriz.index:
                matriz_anio = matriz.loc[filtro_anio].reset_index()
                datos_anio_actual = matriz.loc[filtro_anio].tolist()
            else:
                datos_anio_actual = [0] * 52 # O manejar como vacío

            # Subtítulo dinámico
            subtitulo_parts = []
            if filtro_provincia and filtro_provincia != "Todas":
                subtitulo_parts.append(f"Provincia: {filtro_provincia}")
            if filtro_partido:
                subtitulo_parts.append(f"Departamentos: {', '.join(filtro_partido)}")
            subtitulo = " | ".join(subtitulo_parts) if subtitulo_parts else "Nacional"

            # Crear la configuración del gráfico de ECharts
            options = {
                "title": {
                    "text": f"Corredor de {', '.join(filtro_evento) if filtro_evento else 'Todos'}",
                    "subtext": subtitulo,
                    "textStyle": {"fontSize": 20},
                },
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
                "toolbox": {
                    "feature": {
                        "dataZoom": {"yAxisIndex": "none"},
                        "saveAsImage": {"type": "png"},
                        "magicType": {"type": ["line", "bar"]},
                    }
                },
                "dataZoom": [
                    {"type": "inside", "startValue": 0, "endValue": 52},
                    {"type": "slider", "startValue": 0, "endValue": 52},
                ],
                "legend": {"data": ["Exito", "Seguridad", "Alerta", f"Año {filtro_anio}"]},
                "grid": {"backgroundColor": "rgba(255, 0, 0, 0.1)"},
                "xAxis": {"type": "category", "data": list(range(1, 53))},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "name": "Exito",
                        "type": "line",
                        "stack": "Total",
                        "areaStyle": {"color": "rgba(144, 238, 144, 1)"},
                        "emphasis": {"focus": "series"},
                        "data": cuartiles['Exito'].tolist(),
                    },
                    {
                        "name": "Seguridad",
                        "type": "line",
                        "stack": "Total",
                        "areaStyle": {"color": "rgba(100, 149, 237, 1)"},
                        "emphasis": {"focus": "series"},
                        "data": cuartiles['Seguridad'].tolist(),
                    },
                    {
                        "name": "Alerta",
                        "type": "line",
                        "stack": "Total",
                        "areaStyle": {"color": "rgba(255, 255, 0, 1)"},
                        "emphasis": {"focus": "series"},
                        "data": cuartiles['Alerta'].tolist(),
                    },
                    {
                        "name": f"Año {filtro_anio}",
                        "type": "line",
                        "data": datos_anio_actual,
                        "lineStyle": {"color": "black", "width": 2},
                        "symbol": "circle",
                        "symbolSize": 4,
                        "itemStyle": {
                            "color": "white",
                            "borderColor": "red",
                            "borderWidth": 2
                        },
                    },
                ],
                "backgroundColor": "#ffffff",
            }

            # Cortar la línea negra en la semana seleccionada
            if len(options['series'][-1]['data']) >= filtro_semana:
                 options['series'][-1]['data'] = options['series'][-1]['data'][:filtro_semana] + [None] * (52 - filtro_semana)

            # Mostrar el gráfico de ECharts
            st_echarts(options=options, height="600px")
            
            # Sección para la fecha de última actualización
            if 'FECHAREGISTROCLINICA' in clinica.columns:
                last_update_date = clinica['FECHAREGISTROCLINICA'].max()
                st.markdown('<style>div.block-container{padding-top:1rem;}</style>', unsafe_allow_html=True)
                st.write(f"Última actualización: {last_update_date}")
        else:
             st.warning("No hay datos históricos suficientes para calcular el corredor (se necesitan 5 años previos).")
