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
    """Traduce SQL básico a operaciones pandas. Maneja WHERE con strings, ORDER BY, GROUP BY, LIMIT."""
    import re
    q = sql.strip().rstrip(';')

    # --- Extraer cláusulas SQL ---
    def extract_clause(sql, keyword):
        m = re.search(rf'\b{keyword}\b', sql, re.IGNORECASE)
        if not m:
            return None, sql
        start = m.end()
        for kw in ['ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'UNION']:
            km = re.search(rf'\b{kw}\b', sql[start:], re.IGNORECASE)
            if km:
                return sql[start:start+km.start()].strip(), sql[:start] + sql[start+km.start():]
        return sql[start:].strip(), sql[:start]

    # Extraer en orden inverso para que cada cláusula no afecte a la siguiente
    limit_clause, q2 = extract_clause(q, 'LIMIT')
    order_clause, q3 = extract_clause(q2, 'ORDER BY')
    group_clause, q4 = extract_clause(q3, 'GROUP BY')
    where_clause, q5 = extract_clause(q4, 'WHERE')
    from_match = re.search(r'\bFROM\b', q5, re.IGNORECASE)
    if from_match:
        before_from = q5[:from_match.start()].strip()
        after_from = q5[from_match.end():].strip()
    else:
        before_from = q5.strip()
        after_from = ''

    # --- Detectar DISTINCT ---
    is_distinct = 'DISTINCT' in before_from.upper()
    select_part = re.sub(r'\bSELECT\b', '', before_from, flags=re.IGNORECASE)
    select_part = re.sub(r'\bDISTINCT\b', '', select_part, flags=re.IGNORECASE).strip()
    cols = [c.strip() for c in select_part.split(',')]

    # --- Función para convertir condición WHERE a boolean mask pandas ---
    def _eval_condition(cond_str, df):
        cond_str = cond_str.strip()
        # Soportar =, !=, <>, >, <, >=, <=
        m = re.match(r"(\w+)\s*(=|!=|<>|>=|<=|>|<)\s*'([^']*)'", cond_str)
        if m:
            col, op, val = m.group(1), m.group(2), m.group(3)
            if col not in df.columns:
                return pd.Series(True, index=df.index)
            if op == '=':
                return df[col].astype(str) == val
            elif op in ('!=', '<>'):
                return df[col].astype(str) != val
            elif op == '>':
                return df[col] > pd.to_numeric(val, errors='coerce')
            elif op == '<':
                return df[col] < pd.to_numeric(val, errors='coerce')
            elif op == '>=':
                return df[col] >= pd.to_numeric(val, errors='coerce')
            elif op == '<=':
                return df[col] <= pd.to_numeric(val, errors='coerce')

        m = re.match(r"(\w+)\s*(=|!=|<>|>=|<=|>|<)\s*(\d+(?:\.\d+)?)", cond_str)
        if m:
            col, op, val = m.group(1), m.group(2), float(m.group(3))
            if col not in df.columns:
                return pd.Series(True, index=df.index)
            val_int = int(val) if val == int(val) else val
            if op == '=':
                try:
                    return df[col].astype(int) == int(val)
                except (ValueError, TypeError):
                    return df[col] == val_int
            elif op in ('!=', '<>'):
                try:
                    return df[col].astype(int) != int(val)
                except (ValueError, TypeError):
                    return df[col] != val_int
            elif op == '>':
                return df[col] > val
            elif op == '<':
                return df[col] < val
            elif op == '>=':
                return df[col] >= val
            elif op == '<=':
                return df[col] <= val

        return pd.Series(True, index=df.index)

    def _apply_where(where_str, df):
        if not where_str:
            return df
        # Separar por AND (soporte básico, sin paréntesis anidados)
        conditions = re.split(r'\bAND\b', where_str, flags=re.IGNORECASE)
        mask = pd.Series(True, index=df.index)
        for cond in conditions:
            cond = cond.strip()
            if cond:
                mask = mask & _eval_condition(cond, df)
        return df[mask]

    # --- Aplicar filtros y operaciones ---
    result = df.copy()
    result = _apply_where(where_clause, result)

    # --- GROUP BY ---
    if group_clause:
        group_cols = [c.strip() for c in group_clause.split(',')]
        # Detectar funciones de agregación y alias en SELECT
        select_items = [s.strip() for s in select_part.split(',')]
        agg_col_name = 'CANTIDAD'
        agg_src = None
        for item in select_items:
            item_upper = item.upper().strip()
            alias_match = re.match(r'.*\bAS\s+(\w+)', item, re.IGNORECASE)
            if 'SUM(' in item_upper:
                col_match = re.search(r'SUM\((\w+)\)', item, re.IGNORECASE)
                if col_match:
                    agg_src = col_match.group(1)
                    agg_col_name = alias_match.group(1) if alias_match else f'SUM({agg_src})'
            elif 'COUNT(' in item_upper:
                agg_col_name = alias_match.group(1) if alias_match else 'CANTIDAD'

        if agg_src and agg_src in result.columns:
            grouped = result.groupby(group_cols, as_index=False)[agg_src].sum()
            grouped = grouped.rename(columns={agg_src: agg_col_name})
            result = grouped
        else:
            result = result.groupby(group_cols, as_index=False).size().rename(columns={'size': agg_col_name})

    # --- SELECT ---
    if is_distinct:
        result = result[cols].drop_duplicates()
    elif cols != ['*'] and all(c in result.columns for c in cols):
        result = result[cols]

    # --- ORDER BY ---
    if order_clause:
        order_cols = [c.strip() for c in order_clause.split(',')]
        asc_list = []
        sort_cols = []
        for oc in order_cols:
            desc = 'DESC' in oc.upper()
            col_name = oc.replace('DESC', '').replace('ASC', '').strip()
            sort_cols.append(col_name)
            asc_list.append(not desc)
        if all(c in result.columns for c in sort_cols):
            result = result.sort_values(sort_cols, ascending=asc_list)

    # --- LIMIT ---
    if limit_clause:
        try:
            result = result.head(int(limit_clause.strip()))
        except ValueError:
            pass

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
