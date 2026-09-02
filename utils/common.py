# utils/common.py
import os
import streamlit as st
import pandas as pd
import io
import duckdb
from dotenv import load_dotenv
import locale

load_dotenv()

# Configurar locale para números con punto de miles
# En la nube (Linux), es más seguro usar 'en_US.UTF-8' o manejarlo manualmente si falla
try:
    locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        pass

def format_number(number, decimals=0):
    try:
        if pd.notnull(number) and isinstance(number, (int, float)):
            if decimals == 0:
                return f"{int(number):,}".replace(",", ".")
            else:
                # Formateo para decimales: 1.234,56
                formatted = f"{float(number):,.{decimals}f}"
                # Intercambiar comas y puntos
                # Usamos un placeholder temporal
                return formatted.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")
        return ''
    except (ValueError, TypeError):
        return str(number) if number is not None else ''

def style_argentina(styler, numeric_cols=None):
    """Aplica formato argentino (punto para miles, coma para decimales) a un Pandas Styler."""
    if numeric_cols is None:
        numeric_cols = styler.data.select_dtypes(include=['number']).columns.tolist()
    
    formats = {}
    for col in numeric_cols:
        # Si la columna es float y tiene valores decimales, usamos 2 decimales
        if styler.data[col].dtype == 'float64' and (styler.data[col] % 1 != 0).any():
             formats[col] = "{:,.2f}"
        else:
             formats[col] = "{:,.0f}"
             
    return styler.format(formats, thousands='.', decimal=',')

# --- DUCKDB / PARQUET HELPERS ---

def get_parquet_path(filename='base_semanal.parquet'):
    """
    Obtiene la ruta absoluta al archivo parquet dentro de la carpeta 'data'.
    Funciona correctamente en despliegues de Streamlit Cloud.
    """
    # Detecta la raíz del proyecto (un nivel arriba de /utils)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'data', filename)

def check_parquet_exists(filename='base_semanal.parquet'):
    path = get_parquet_path(filename)
    if not os.path.exists(path):
        st.error(f"⚠️ No se encontró el archivo de datos (`data/{filename}`).")
        st.info("Asegúrate de que el archivo esté en el repositorio de GitHub dentro de la carpeta 'data'.")
        st.stop()
    return path

def query_duckdb(query, filename='base_semanal.parquet'):
    """
    Ejecuta consulta SQL sobre Parquet usando DuckDB.
    """
    path = check_parquet_exists(filename)
    # Sanitizar ruta para DuckDB (Linux/Cloud usa forward slashes)
    path = path.replace('\\', '/')
    try:
        formatted_query = query.replace('{parquet}', f"'{path}'")
        with duckdb.connect() as con:
            return con.execute(formatted_query).df()
    except Exception as e:
        st.error(f"Error consultando DuckDB: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_distinct_years():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            query = f"SELECT DISTINCT ANIO FROM '{path}' WHERE ANIO IS NOT NULL ORDER BY ANIO DESC"
            with duckdb.connect() as con:
                df = con.execute(query).df()
            return df['ANIO'].astype(int).tolist()
    except Exception as e:
        st.warning(f"No se pudieron cargar años del archivo local.")
    return []

@st.cache_data(ttl=3600)
def get_distinct_events():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            query = f"SELECT DISTINCT NOMBREEVENTOAGRP FROM '{path}' WHERE NOMBREEVENTOAGRP IS NOT NULL ORDER BY NOMBREEVENTOAGRP"
            with duckdb.connect() as con:
                df = con.execute(query).df()
            return df['NOMBREEVENTOAGRP'].tolist()
    except Exception as e:
        st.warning("No se pudieron cargar eventos del archivo local.")
    return []

@st.cache_data(ttl=3600)
def get_distinct_provinces():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            query = f"SELECT DISTINCT PROVINCIA FROM '{path}' WHERE PROVINCIA IS NOT NULL ORDER BY PROVINCIA"
            with duckdb.connect() as con:
                df = con.execute(query).df()
            return df['PROVINCIA'].tolist()
    except Exception as e:
        pass
    return []

@st.cache_data(ttl=3600)
def get_distinct_departments():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            query = f"SELECT DISTINCT DEPARTAMENTO FROM '{path}' WHERE DEPARTAMENTO IS NOT NULL ORDER BY DEPARTAMENTO"
            with duckdb.connect() as con:
                df = con.execute(query).df()
            return df['DEPARTAMENTO'].tolist()
    except Exception as e:
        pass
    return []

@st.cache_data(ttl=3600)
def load_population_province(year: int | None = None):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    candidates = [
        os.path.join(data_dir, 'poblacionxprovinciaindec.parquet'),
        os.path.join(data_dir, 'parquet', 'poblacionxprovinciaindec.parquet')
    ]
    
    for p in candidates:
        if os.path.exists(p):
            try:
                df = pd.read_parquet(p)
                # Normalización básica
                if 'ano' in df.columns:
                    df['ano'] = df['ano'].astype(int)
                    if year:
                        df = df[df['ano'] == int(year)]
                return df
            except:
                continue
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_population_department(year: int | None = None):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    p = os.path.join(data_dir, 'proyecciones_depto_indec.parquet')
    
    if os.path.exists(p):
        try:
            df = pd.read_parquet(p)
            if year and 'ano' in df.columns:
                df = df[df['ano'] == int(year)]
            return df
        except:
            pass
    return pd.DataFrame()

def style_table(df, cmap="Blues"):
    return df.style.background_gradient(cmap=cmap)

def download_csv(df, filename):
    csv = df.to_csv(index=False).encode('utf-8')
    return csv, filename

def download_excel(df, filename):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue(), filename
