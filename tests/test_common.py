"""Tests de utilidades del dashboard (corren sin servidor Streamlit).

Cubre:
- Semana epidemiológica (helpers centralizados desde 7 páginas).
- Corte de datos visible en el dashboard.
- _parse_sql: el motor SQL-en-pandas que usa streamlit.io (duckdb no está
  en requirements.txt). Incluye la regresión del bug "ORDER BYLIMIT".
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.common import (  # noqa: E402
    _parse_sql,
    epiweek_to_date,
    get_data_corte,
    get_epi_week,
    get_epi_week_data,
)


# ---------- Semana epidemiológica ----------

def test_se1_contiene_4_de_enero():
    """La SE 1 es la que contiene el 4 de enero."""
    assert get_epi_week(date(2026, 1, 4)) == 1
    assert get_epi_week_data(date(2026, 1, 4)) == (1, 2026)


def test_semana_actual_conocida():
    # 27/10/2026 (martes) pertenece a la SE 43 de 2026
    assert get_epi_week(date(2026, 10, 27)) == 43
    assert get_epi_week_data(date(2026, 10, 27)) == (43, 2026)


def test_cierre_de_anio_epidemiologico():
    # 28/12/2025 (domingo) cierra la SE 53 de 2025
    assert get_epi_week_data(date(2025, 12, 28)) == (53, 2025)


def test_epiweek_to_date_es_domingo():
    inicio = epiweek_to_date(2026, 39)
    assert inicio == date(2026, 9, 27)
    assert inicio.weekday() == 6  # domingo


# ---------- Corte de datos ----------

def test_get_data_corte():
    c = get_data_corte()
    if c is None:
        pytest.skip("base_semanal.parquet no disponible")
    assert set(c) == {"anio", "semana", "fecha_inicio", "fecha_fin"}
    assert 1 <= c["semana"] <= 53
    assert c["fecha_inicio"].weekday() == 6   # domingo
    assert c["fecha_fin"].weekday() == 5      # sábado
    assert (c["fecha_fin"] - c["fecha_inicio"]).days == 6


# ---------- _parse_sql (motor SQL en pandas) ----------

@pytest.fixture
def df():
    return pd.DataFrame({
        "ANIO": [2025, 2025, 2026, 2026, 2026],
        "SEMANA": [1, 2, 1, 1, 2],
        "PROVINCIA": ["A", "B", "A", "B", "A"],
        "NOMBREEVENTOAGRP": ["X", "X", "Y", "Y", "X"],
        "CANTIDAD": [10, 20, 30, 40, 50],
    })


def test_group_by_order_by_limit(df):
    """Regresión: ORDER BY + LIMIT se pegaban como 'ORDER BYLIMIT' y fallaba."""
    sql = ("SELECT ANIO, SUM(CANTIDAD) AS TOTAL FROM t "
           "GROUP BY ANIO ORDER BY TOTAL DESC LIMIT 1")
    r = _parse_sql(sql, df)
    assert list(r.columns) == ["ANIO", "TOTAL"]
    assert len(r) == 1
    assert int(r.iloc[0]["ANIO"]) == 2026
    assert int(r.iloc[0]["TOTAL"]) == 120


def test_where_con_string(df):
    sql = "SELECT * FROM t WHERE NOMBREEVENTOAGRP = 'Y'"
    r = _parse_sql(sql, df)
    assert len(r) == 2
    assert set(r["NOMBREEVENTOAGRP"]) == {"Y"}


def test_where_numerico(df):
    sql = "SELECT * FROM t WHERE ANIO = 2026"
    r = _parse_sql(sql, df)
    assert len(r) == 3


def test_distinct_con_order_by(df):
    sql = "SELECT DISTINCT PROVINCIA FROM t ORDER BY PROVINCIA"
    r = _parse_sql(sql, df)
    assert r["PROVINCIA"].tolist() == ["A", "B"]


def test_limit_simple(df):
    sql = "SELECT * FROM t LIMIT 2"
    r = _parse_sql(sql, df)
    assert len(r) == 2


def test_group_by_con_alias(df):
    sql = ("SELECT PROVINCIA, SUM(CANTIDAD) AS TOTAL FROM t "
           "WHERE ANIO = 2026 GROUP BY PROVINCIA")
    r = _parse_sql(sql, df)
    assert set(r.columns) == {"PROVINCIA", "TOTAL"}
    assert int(r[r["PROVINCIA"] == "A"]["TOTAL"].iloc[0]) == 80
