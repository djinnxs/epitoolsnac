# utils/common.py
import os
import streamlit as st
import pandas as pd
import io
try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
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

def _read_parquet(filename='base_semanal.parquet'):
    path = check_parquet_exists(filename)
    return pd.read_parquet(path)

def _parse_sql(sql, df):
    """Traduce SQL básico a operaciones pandas."""
    q = sql.strip().rstrip(';')
    q_upper = q.upper()

    # SELECT ... DISTINCT
    if 'DISTINCT' in q_upper:
        # Extraer columnas: SELECT DISTINCT col1, col2
        after_select = q_upper.split('DISTINCT')[1]
        cols_part = after_select.split('FROM')[0].strip()
        cols = [c.strip() for c in cols_part.split(',')]

        # WHERE
        if 'WHERE' in q_upper:
            where_part = q.split('WHERE')[1]
            if 'ORDER BY' in where_part:
                where_part = where_part.split('ORDER BY')[0]
            df = df.query(where_part.strip())

        result = df[cols].drop_duplicates()
        # ORDER BY
        if 'ORDER BY' in q_upper:
            order_part = q.split('ORDER BY')[1].strip()
            desc = 'DESC' in order_part.upper()
            order_col = order_part.replace('DESC', '').replace('ASC', '').strip()
            result = result.sort_values(order_col, ascending=not desc)
        return result

    # SELECT ... GROUP BY
    if 'GROUP BY' in q_upper:
        after_select = q_upper.split('FROM')[0].replace('SELECT', '').strip()
        cols = [c.strip() for c in after_select.split(',')]

        # WHERE
        if 'WHERE' in q_upper:
            where_part = q.split('WHERE')[1]
            for keyword in ['GROUP BY', 'ORDER BY', 'HAVING']:
                if keyword in where_part.upper():
                    where_part = where_part.split(keyword)[0]
            df = df.query(where_part.strip())

        result = df.groupby(cols, as_index=False).size().rename(columns={'size': 'CANTIDAD'})

        # ORDER BY
        if 'ORDER BY' in q_upper:
            order_part = q.split('ORDER BY')[1].strip()
            desc = 'DESC' in order_part.upper()
            order_col = order_part.replace('DESC', '').replace('ASC', '').strip()
            result = result.sort_values(order_col, ascending=not desc)
        return result

    # SELECT simples
    after_select = q_upper.split('FROM')[0].replace('SELECT', '').strip()
    cols = [c.strip() for c in after_select.split(',')]

    # WHERE
    if 'WHERE' in q_upper:
        where_part = q.split('WHERE')[1]
        for keyword in ['ORDER BY', 'LIMIT', 'GROUP BY']:
            if keyword in where_part.upper():
                where_part = where_part.split(keyword)[0]
        df = df.query(where_part.strip())

    result = df[cols] if cols != ['*'] else df

    # ORDER BY
    if 'ORDER BY' in q_upper:
        order_part = q.split('ORDER BY')[1].strip()
        desc = 'DESC' in order_part.upper()
        order_col = order_part.replace('DESC', '').replace('ASC', '').strip()
        result = result.sort_values(order_col, ascending=not desc)

    # LIMIT
    if 'LIMIT' in q_upper:
        limit_val = int(q.split('LIMIT')[1].strip())
        result = result.head(limit_val)

    return result

def query_duckdb(query, filename='base_semanal.parquet'):
    path = check_parquet_exists(filename)
    path = path.replace('\\', '/')
    formatted_query = query.replace('{parquet}', f"'{path}'")
    try:
        if HAS_DUCKDB:
            with duckdb.connect() as con:
                return con.execute(formatted_query).df()
        else:
            df = pd.read_parquet(path)
            return _parse_sql(formatted_query, df)
    except Exception as e:
        st.error(f"Error consultando datos: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_distinct_years():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            df = pd.read_parquet(path)
            return sorted(df['ANIO'].dropna().astype(int).unique().tolist(), reverse=True)
    except Exception:
        pass
    return []

@st.cache_data(ttl=3600)
def get_distinct_events():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            df = pd.read_parquet(path)
            return sorted(df['NOMBREEVENTOAGRP'].dropna().unique().tolist())
    except Exception:
        pass
    return []

@st.cache_data(ttl=3600)
def get_distinct_provinces():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            df = pd.read_parquet(path)
            return sorted(df['PROVINCIA'].dropna().unique().tolist())
    except Exception:
        pass
    return []

@st.cache_data(ttl=3600)
def get_distinct_departments():
    try:
        path = get_parquet_path().replace('\\', '/')
        if os.path.exists(path):
            df = pd.read_parquet(path)
            return sorted(df['DEPARTAMENTO'].dropna().unique().tolist())
    except Exception:
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
