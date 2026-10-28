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
3. **Casos por Semana (3_CasosSemana.py)** — pestaña nueva **Small multiples**:
   una mini-curva por año (SE 1 a 52), con los años elegidos resaltados y su
   pico marcado. Permite comparar la *forma* de la temporada año a año.
4. **Mapas (4_Mapas.py)** — reorganizado en **3 pestañas**:
   - Provincia / Departamento (lo de siempre, con tasas y descargas).
   - **Mapa bivariado**: color = incidencia de las últimas 4 SE × tendencia
     (3×3), con leyenda explicativa y tabla descargable.
   - **Cartograma de burbujas**: tamaño = casos, color = tasa x100k (útil para
     comparar provincias grandes y despobladas con las chicas y densas).
5. **Tendencias (14_Tendencia.py)** — **fan chart** de verdad: banda del 50%
   (intensa) y del 80% (clara) por bootstrap de residuos + **pico estimado**
   anotado en el gráfico.
6. **Nowcasting (17_Nowcasting.py)** — reescrito:
   - Antes usaba la **semana de hoy** como referencia (con datos al corte, la
     estimación salía vacía o en cero). Ahora usa la **última SE con datos**.
   - La corrección anterior (factor acumulado mal aplicado) producía
     estimaciones absurdas (570 observados → 30.978 estimados). Se reemplazó
     por una **banda de referencia histórica**: mediana y p10–p90 de las mismas
     SE en los 5 años previos, ajustadas por el nivel del año actual.
   - Tabla de las últimas semanas con observado / esperado / banda y % de
     cumplimiento, más explicación del método en un expander.
7. **Ranking por Semana (23_Ranking.py — NUEVA)** — **bump chart**: cómo cambia
   el puesto de las provincias semana a semana (top 12 por volumen), con KPIs
   de líder, mayor suba y mayor caída, y tabla/CSV descargable.
8. **Retraso de Reporte (24_RetrasoReporte.py — NUEVA)** — control de calidad
   semanal: qué provincias y eventos dejaron de reportar (semanas de atraso
   respecto del corte), con mapa de calor provincia × SE para ver los huecos.
9. **Reporte Semanal (25_ReporteSemanal.py — NUEVA)** — boletín descargable en
   **PDF** (en streamlit.io) o **HTML imprimible** (en Windows sin GTK):
   KPIs, top eventos, top provincias con tasa, serie de las últimas semanas y
   mapa de calor SE × año. Generado con WeasyPrint (ya estaba en
   `requirements.txt`, sin agregar dependencias).
10. **Home** — menú actualizado (Ranking, Retraso de Reporte, Reporte Semanal)
    + pie con el corte de datos.

## 🗓️ Semana epidemiológica visible en todas las páginas

- Banner uniforme **"📅 Semana Epidemiológica Actual: N del AAAA"** en las
  24 páginas + Home (antes solo estaba en 7 páginas y con estilos distintos).
- Se eliminaron los banners duplicados de esas 7 páginas: ahora el banner es
  uno solo, centralizado en `utils/common.py` (`show_semana_actual()`).
- El año que se muestra es el **año epidemiológico** (correcto en el cambio de
  año), no el año calendario.

## 🎨 Identidad visual común

- `PALETA` y `style_fig()` en `utils/common.py`: todos los gráficos nuevos usan
  el mismo tema claro, tipografía, márgenes y escala de colores.
- Escala **bivariada 3×3** (`BIVAR_COLORS`) compartida y documentada en el mapa.


## 🧹 Deprecaciones

- 5 usos de `use_container_width` → `width="stretch"` (API actual de
  streamlit 1.59): `4_Mapas.py` (4) y `14_Tendencia.py` (1).

## 🧪 Tests y CI (sin Docker)

- `tests/test_common.py` — 11 tests: semana epidemiológica, corte de datos y
  **regresión del bug `ORDER BY LIMIT`**.
- `tests/test_app.py` — smoke test con `streamlit.testing.v1.AppTest`:
  ejecuta **Home + las 24 páginas** y falla si alguna lanza excepción.
- `requirements-dev.txt` — solo `pytest` (NO afecta el deploy).
- `.github/workflows/ci.yml` — instala el **mismo `requirements.txt`** que
  streamlit.io (Python 3.12 en Ubuntu), compila todo, corre los 36 tests y
  verifica que el servidor arranque.

## ⚠️ Limitaciones conocidas (y cómo se resolvieron)

- **No existe fecha del evento** en la base: solo `FECHAREGISTROCLINICA`, que
  además define la semana epidemiológica. Por eso **no se puede** reconstruir
  el triángulo clásico de *backfill* (casos por semana de ocurrencia vs. semana
  de notificación). En su lugar:
  - Nowcasting usa **banda de referencia histórica** (explicado en la página).
  - Retraso de Reporte mide **atraso por fuente** (última SE con datos vs.
    corte nacional), que sí es medible.
- **WeasyPrint en Windows** necesita GTK y no está instalado: el Reporte
  Semanal ofrece automáticamente la versión **HTML imprimible** (se abre en el
  navegador y se guarda como PDF). En streamlit.io (Linux) el PDF funciona.
- **Sin coordenadas de localidad/establecimiento** (`LOCALIDAD` viene
  "SIN ESPECIFICAR"): no se pueden hacer polígonos de Voronoi. Se optó por
  mapa bivariado + cartograma de burbujas sobre los polígonos reales.

## 🔄 Cambios respecto de la primera versión de esta copia

- Se **eliminó `23_SerieCronologica.py`**: para el equipo la unidad de análisis
  es la **semana epidemiológica**, no la fecha; la página no aportaba y su
  nombre ("diaria") era engañoso. En su lugar se agregaron Ranking por Semana,
  Retraso de Reporte y Reporte Semanal.


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
