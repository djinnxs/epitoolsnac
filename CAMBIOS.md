# 📝 CAMBIOS — epitoolsnac2 vs. epitoolsnac

Lista completa de lo que se modificó/agregó (el original queda sin tocar).
Fecha: 27/10/2026.

---

## 🐛 Corrección de bug de producción

- **`utils/common.py` → `_parse_sql`**: el traductor SQL-a-pandas (que es lo
  que corre en **streamlit.io**, porque `duckdb` no está en `requirements.txt`)
  pegaba mal las cláusulas: `ORDER BY` + `LIMIT` quedaban como `ORDER BYLIMIT`
  y **cualquier consulta con ambas cláusulas fallaba** (gráfico vacío + error).
  Corregido con espacio de unión + **tests de regresión**.

## ⚡ Rendimiento

- **`query_duckdb` ahora es caché** (`@st.cache_data`, 1 h): la misma consulta
  se ejecuta una sola vez por sesión en **todas** las páginas (antes cada
  rerun releía el parquet completo de 226.580 filas).
- **`get_distinct_*`** ahora leen solo la columna necesaria del parquet
  (`columns=[...]`) en vez de las 13.

## 🧹 Código duplicado eliminado

- **`get_epi_week` estaba copiada en 7 páginas** (2_Corredores, 17_Nowcasting,
  18_Alertas, 19_MapaAnimado, 20_CorrelacionClima, 21_Sindemias, 22_Semaforo).
  Ahora vive una sola vez en `utils/common.py` y todas importan de ahí.
- `8_Calendario` también importa `get_epi_week_data` desde `common`.

## ✨ Funciones nuevas en `utils/common.py`

- `get_epi_week` / `get_epi_week_data` — semana epidemiológica.
- `epiweek_to_date` — fecha de inicio (domingo) de una SE.
- `get_data_corte()` — último corte disponible (año, semana, fechas).
- `show_data_corte()` — pie "📊 Datos hasta dd/mm/aaaa · SE n de aaaa"
  reutilizable en cualquier página.

## 📊 Visualizaciones nuevas / mejoradas

1. **Dashboard (1_Dashboard.py)** — 4 **tarjetas KPI** arriba de todo:
   - 📌 Casos en el rango
   - 📈 Última semana con datos + **variación vs. semana anterior** (▲ verde /
     ▼ rojo — invertido a propósito: más casos = rojo)
   - 🗺️ Provincia líder (+ % del total)
   - 🦠 Evento líder (+ % del total)
   - Pie con **corte de datos** visible.
2. **Calendario (8_Calendario.py)** — ahora tiene **dos pestañas**:
   - 🗓️ **Calendario con datos**: heatmap (semana × año) de casos reales con
     filtro por evento + 3 métricas (total, semana más crítica, último corte).
   - 🖨️ **Tradicional**: el calendario en texto y el PDF de siempre,
     conservados tal cual.
3. **Página nueva `23_SerieCronologica.py`** — serie cronológica
   2018 → actualidad (barras por fecha de registro + media móvil de 4 semanas),
   con filtros de evento/provincia, rango de fechas, KPIs y descarga CSV.
   *(Nota: los datos se fechan en domingos —inicio de SE—, por eso la serie
   es semanal y no diaria; se eligió el nombre honesto.)*
4. **Home** — enlace a la página nueva en el menú + pie con el corte de datos.

## 🌐 UX

- Filtros y URLs con el patrón nativo de Streamlit (`/SerieCronologica`, etc.).
- Corte de datos visible en Home y Dashboard (evita interpretar datos viejos
  como actuales).

## 🧹 Deprecaciones

- 5 usos de `use_container_width` → `width="stretch"` (API actual de
  streamlit 1.59): `4_Mapas.py` (4) y `14_Tendencia.py` (1).

## 🧪 Tests y CI (sin Docker)

- `tests/test_common.py` — 11 tests: semana epidemiológica, corte de datos y
  **regresión del bug `ORDER BY LIMIT`**.
- `tests/test_app.py` — smoke test con `streamlit.testing.v1.AppTest`:
  ejecuta **Home + las 22 páginas** y falla si alguna lanza excepción.
- `requirements-dev.txt` — solo `pytest` (NO afecta el deploy).
- `.github/workflows/ci.yml` — instala el **mismo `requirements.txt`** que
  streamlit.io (Python 3.12 en Ubuntu), compila todo, corre los 34 tests y
  verifica que el servidor arranque.

## 📦 Infraestructura

- `.venv` propio con Python 3.12 y **las versiones exactas de
  `requirements.txt` (sin modificar un solo pin)**.
- **Sin remote configurado**: el repositorio es solo local, es imposible que
  un push accidental toque GitHub (el original y el repo en vivo quedan
  intactos).
- `INSTRUCCIONES_DEPLOY.md` con el paso a paso para publicar en streamlit.io
  **cuando se apruebe** (no se ejecutó).

## ❌ Lo que NO se tocó

- `requirements.txt` — idéntico al original.
- `Dockerfile` — heredado del original, **sin usar ni modificar**.
- ETL (`etl_semanal.py`) — sin cambios funcionales.
- Datos (`data/*.parquet`) — sin regenerar.
- `11_Rumores.backup` — se conservó como estaba.
- Proyecto original `epitoolsnac\` — **intacto**.
