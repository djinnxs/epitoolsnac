# pages/6_Tablas.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from utils.common import query_duckdb, get_distinct_years, get_distinct_events, download_excel, style_argentina

st.set_page_config(page_title="Epidemiologia - Tablas", page_icon=":bar_chart:", layout="wide")

# Título
st.title('📚 Explorador de Datos')
st.subheader('Filtre, ordene y descargue los datos epidemiológicos')

# --- FILTROS ---
col1, col2, col3 = st.columns(3)
with col1:
    years = get_distinct_years()
    anios = st.multiselect("Año(s)", years, default=[years[0]] if years else [])
with col2:
    events = get_distinct_events()
    eventos = st.multiselect("Evento(s)", events, default=[events[0]] if events else [])
with col3:
    agrupar_por = st.multiselect(
        "Agrupar por",
        ["PROVINCIA", "DEPARTAMENTO", "ANIO", "SEMANA", "NOMBREEVENTOAGRP", "GRUPO"],
        default=["DEPARTAMENTO", "ANIO", "NOMBREEVENTOAGRP"]
    )

# Construir filtros SQL dinámicos
where_clauses = []
if anios:
    anios_str = ", ".join(str(a) for a in anios)
    where_clauses.append(f"ANIO IN ({anios_str})")
if eventos:
    eventos_str = ", ".join(f"'{e}'" for e in eventos)
    where_clauses.append(f"NOMBREEVENTOAGRP IN ({eventos_str})")

where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

if agrupar_por:
    cols = ", ".join(agrupar_por)
    query = f"""
    SELECT {cols}, SUM(CANTIDAD) AS CANTIDAD
    FROM {{parquet}}
    {where_sql}
    GROUP BY {cols}
    ORDER BY CANTIDAD DESC
    """
else:
    query = f"""
    SELECT PROVINCIA, DEPARTAMENTO, ANIO, SEMANA, NOMBREEVENTOAGRP, GRUPO, CANTIDAD
    FROM {{parquet}}
    {where_sql}
    ORDER BY CANTIDAD DESC
    LIMIT 5000
    """

df = query_duckdb(query)

if not df.empty:
    st.metric("Total de registros", f"{len(df):,}".replace(",", "."))
    st.dataframe(style_argentina(df.style), width="stretch", height=600)

    # Descarga
    excel_data, excel_name = download_excel(df, "tabla_explorador.xlsx")
    st.download_button("📥 Descargar Excel", excel_data, excel_name)
else:
    st.warning("No hay datos disponibles para los filtros seleccionados.")