# pages/25_ReporteSemanal.py — Boletín semanal descargable (PDF / HTML)
import html as html_lib
import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from utils.common import (
    get_data_corte,
    get_distinct_events,
    get_distinct_years,
    load_population_province,
    query_duckdb,
    show_data_corte,
    show_semana_actual,
)

st.set_page_config(page_title="Reporte Semanal", page_icon="📄", layout="wide")
show_semana_actual()

st.title("📄 Reporte semanal (boletín descargable)")
st.markdown(
    "Genera un **boletín semanal** listo para imprimir o compartir: resumen de la semana, "
    "eventos y provincias con más casos, serie de las últimas semanas y comparación por "
    "semana epidemiológica entre años."
)

col1, col2, col3 = st.columns(3)
with col1:
    anio = st.selectbox("Año", get_distinct_years())
with col2:
    evento = st.selectbox("Evento", ["Todos los eventos"] + get_distinct_events())
with col3:
    n_sem = st.slider("Semanas en la serie", min_value=4, max_value=26, value=12, step=1)

# ── Helpers de formato ────────────────────────────────────────────────────────
def fmt(n):
    try:
        return f"{int(round(float(n))):,}".replace(",", ".")
    except Exception:
        return "—"


def fmt1(n):
    try:
        return f"{float(n):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def color_celda(v, vmax):
    if vmax <= 0:
        return "#ffffff"
    inten = max(0.0, min(1.0, float(v) / vmax))
    r = int(255 - inten * (255 - 31))
    g = int(255 - inten * (255 - 119))
    b = int(255 - inten * (255 - 180))
    return f"rgb({r},{g},{b})"


def construir_reporte(anio, evento, n_sem):
    filtro = "" if evento == "Todos los eventos" else f"AND NOMBREEVENTOAGRP = '{evento.replace(chr(39), chr(39) * 2)}'"
    query = f"""
    SELECT ANIO, SEMANA, NOMBREEVENTOAGRP, PROVINCIA, CODIGO_PROVINCIA, CANTIDAD
    FROM {{parquet}}
    WHERE ANIO >= {anio - 9} AND ANIO <= {anio}
      {filtro}
      AND SEMANA != 53
    """
    df_todos = query_duckdb(query)
    if df_todos.empty:
        return None, None, None

    corte = get_data_corte()
    corte_se = corte["semana"] if (corte and corte["anio"] == anio) else int(df_todos.loc[df_todos["ANIO"] == anio, "SEMANA"].max())
    df = df_todos[(df_todos["ANIO"] == anio) & (df_todos["SEMANA"] <= corte_se)].copy()
    df["CODIGO_PROVINCIA"] = df["CODIGO_PROVINCIA"].astype(str).str.zfill(2)

    total = df["CANTIDAD"].sum()
    casos_ult = df.loc[df["SEMANA"] == corte_se, "CANTIDAD"].sum()
    casos_prev = df.loc[df["SEMANA"] == corte_se - 1, "CANTIDAD"].sum()
    var = ((casos_ult - casos_prev) / casos_prev * 100) if casos_prev > 0 else None

    # Eventos
    ev = (
        df.groupby("NOMBREEVENTOAGRP")["CANTIDAD"].sum()
        .sort_values(ascending=False).head(10)
    )
    filas_ev = "".join(
        f"<tr><td>{html_lib.escape(str(e))}</td><td style='text-align:right'>{fmt(v)}</td>"
        f"<td style='text-align:right'>{fmt1(v / total * 100)}%</td></tr>"
        for e, v in ev.items()
    )

    # Provincias (con tasa)
    prov = df.groupby("PROVINCIA")["CANTIDAD"].sum().sort_values(ascending=False).head(10)
    pob = load_population_province(anio)
    tasas = {}
    if not pob.empty:
        pob = pob[pob["sexo_nombre"] == "Ambos sexos"].copy()
        pob = pob.groupby("juri", as_index=False)["poblacion"].sum()
        pob["juri"] = pob["juri"].astype(str).str.zfill(2)
        mapa_pob = dict(zip(pob["juri"], pob["poblacion"]))
        codigos = df.drop_duplicates("PROVINCIA").set_index("PROVINCIA")["CODIGO_PROVINCIA"]
        for p in prov.index:
            cod = codigos.get(p)
            poblacion = mapa_pob.get(cod)
            if poblacion:
                tasas[p] = prov[p] / poblacion * 100000

    filas_prov = "".join(
        f"<tr><td>{html_lib.escape(str(p).title())}</td><td style='text-align:right'>{fmt(v)}</td>"
        f"<td style='text-align:right'>{fmt1(tasas.get(p, float('nan')))}</td></tr>"
        for p, v in prov.items()
    )

    # Serie de las últimas N semanas
    semanas = list(range(max(1, corte_se - n_sem + 1), corte_se + 1))
    serie = df[df["SEMANA"].isin(semanas)].groupby("SEMANA")["CANTIDAD"].sum().reindex(semanas, fill_value=0)
    vmax = serie.max() if len(serie) else 0
    barras = "".join(
        f"<div class='bar' style='height:{max(2, (v / vmax * 100) if vmax else 2):.1f}%'>"
        f"<span>{fmt(v)}</span></div>"
        for v in serie.values
    )
    etiquetas = "".join(f"<div class='lbl'>{s}</div>" for s in serie.index)

    # Comparación por SE entre años (mapa de calor) — usa todos los años consultados
    piv = df_todos.pivot_table(index="ANIO", columns="SEMANA", values="CANTIDAD", aggfunc="sum", fill_value=0)
    piv = piv.reindex(columns=range(1, 53), fill_value=0).fillna(0)
    vmax_h = piv.values.max() if piv.size else 0
    filas_heat = ""
    for year, row in piv.iterrows():
        celdas = "".join(
            f"<td style='background:{color_celda(v, vmax_h)}' title='SE{s}: {fmt(v)}'></td>"
            for s, v in row.items()
        )
        filas_heat += f"<tr><th class='yh'>{int(year)}</th>{celdas}</tr>"
    cabecera_heat = "".join(f"<th class='xh'>{s}</th>" for s in range(1, 53))

    flecha = ""
    if var is not None:
        flecha = ("▲ " if var > 0 else "▼ " if var < 0 else "= ") + fmt1(abs(var)) + "%"

    fecha_gen = date.today().strftime("%d/%m/%Y")
    fecha_fin = ""
    if corte:
        fecha_fin = corte["fecha_fin"].strftime("%d/%m/%Y")

    titulo_evento = "Todos los eventos" if evento == "Todos los eventos" else evento

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<style>
  @page {{ size: A4 landscape; margin: 1.1cm; }}
  body {{ font-family: "Segoe UI", Arial, sans-serif; color: #222; font-size: 11px; }}
  h1 {{ color: #1f77b4; margin: 0; font-size: 22px; }}
  .sub {{ color: #555; font-size: 11px; margin-bottom: 8px; }}
  h2 {{ color: #1f77b4; border-bottom: 2px solid #1f77b4; padding-bottom: 2px;
        margin: 14px 0 6px; font-size: 14px; }}
  .kpis {{ display: flex; gap: 8px; margin-top: 8px; }}
  .kpi {{ flex: 1; border: 1px solid #d0d7e2; border-radius: 6px; padding: 8px;
          text-align: center; background: #f7f9fc; }}
  .kpi .v {{ font-size: 19px; font-weight: 700; color: #1f77b4; }}
  .kpi .l {{ font-size: 10px; color: #555; }}
  .kpi .d {{ font-size: 10px; color: #777; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 10px; }}
  th {{ background: #1f77b4; color: #fff; text-align: left; padding: 3px 5px; }}
  td {{ border-bottom: 1px solid #e3e3e3; padding: 3px 5px; }}
  .bars {{ display: flex; align-items: flex-end; gap: 3px; height: 120px;
           border-bottom: 1px solid #999; margin-top: 18px; }}
  .bar {{ flex: 1; background: #1f77b4; position: relative; min-height: 2px; }}
  .bar span {{ position: absolute; top: -14px; left: 0; right: 0; text-align: center; font-size: 8px; }}
  .lbls {{ display: flex; gap: 3px; margin-top: 2px; }}
  .lbl {{ flex: 1; text-align: center; font-size: 8px; color: #555; }}
  .heat {{ table-layout: fixed; }}
  .heat td {{ padding: 0; height: 13px; border: 1px solid #fff; }}
  .heat th.xh {{ font-size: 7px; padding: 0; text-align: center; background: #eef2f7; color: #333;
                 overflow: hidden; }}
  .heat th.yh {{ width: 36px; font-size: 9px; padding: 0 4px; text-align: right;
                 background: #eef2f7; color: #333; }}
  .footer {{ margin-top: 14px; font-size: 9px; color: #777; border-top: 1px solid #ccc; padding-top: 4px; }}
</style></head>
<body>
  <h1>Reporte Epidemiológico Semanal</h1>
  <div class="sub">
    <b>{html_lib.escape(titulo_evento)}</b> · Semana epidemiológica <b>{corte_se}</b> de <b>{anio}</b>
    · datos al {fecha_fin} · generado el {fecha_gen}
  </div>

  <div class="kpis">
    <div class="kpi"><div class="v">{fmt(total)}</div><div class="l">Casos en el año (hasta SE {corte_se})</div></div>
    <div class="kpi"><div class="v">{fmt(casos_ult)}</div><div class="l">Casos en la SE {corte_se}</div>
      <div class="d">{flecha if flecha else "sin semana previa"}</div></div>
    <div class="kpi"><div class="v">{fmt(casos_prev)}</div><div class="l">Casos en la SE {corte_se - 1}</div></div>
    <div class="kpi"><div class="v">{html_lib.escape(str(prov.index[0]).title()) if len(prov) else "—"}</div>
      <div class="l">Provincia con más casos</div></div>
  </div>

  <h2>Eventos con más casos</h2>
  <table>
    <tr><th>Evento</th><th style="text-align:right">Casos</th><th style="text-align:right">% del total</th></tr>
    {filas_ev}
  </table>

  <h2>Provincias con más casos</h2>
  <table>
    <tr><th>Provincia</th><th style="text-align:right">Casos</th><th style="text-align:right">Tasa x100k</th></tr>
    {filas_prov}
  </table>

  <h2>Últimas {len(semanas)} semanas epidemiológicas</h2>
  <div class="bars">{barras}</div>
  <div class="lbls">{etiquetas}</div>

  <h2>Comparación por semana epidemiológica entre años</h2>
  <table class="heat">
    <tr><th class="yh"></th>{cabecera_heat}</tr>
    {filas_heat}
  </table>

  <div class="footer">
    Fuente: base semanal SNVS-SISA. Cada celda del mapa de calor es una semana epidemiológica
    (1 a 52) y su color representa el volumen de casos de ese año.
    Reporte generado automáticamente por SEI — Sistema de Epidemiología Interactiva.
  </div>
</body></html>"""

    nombre = f"reporte_semanal_{anio}_SE{corte_se}"
    return html, nombre, corte_se


if st.button("📄 Generar reporte", type="primary"):
    with st.spinner("Armando el reporte..."):
        html_reporte, nombre_archivo, corte_se = construir_reporte(anio, evento, n_sem)
    if html_reporte is None:
        st.warning("No hay datos para los filtros seleccionados.")
        st.session_state.pop("reporte_html", None)
    else:
        st.session_state["reporte_html"] = html_reporte
        st.session_state["reporte_nombre"] = nombre_archivo
        st.session_state["reporte_se"] = corte_se
        # El PDF se intenta una sola vez, al generar el reporte:
        # en streamlit.io funciona; en Windows sin las librerías queda None.
        st.session_state["reporte_pdf"] = None
        try:
            from weasyprint import HTML

            st.session_state["reporte_pdf"] = HTML(string=html_reporte).write_pdf()
        except Exception:
            pass

if st.session_state.get("reporte_html"):
    html_reporte = st.session_state["reporte_html"]
    nombre_archivo = st.session_state["reporte_nombre"]

    st.success(f"Reporte listo: {nombre_archivo} (SE {st.session_state['reporte_se']})")
    st.html(html_reporte)

    col_pdf, col_html = st.columns(2)
    with col_pdf:
        pdf_bytes = st.session_state.get("reporte_pdf")
        if pdf_bytes:
            st.download_button(
                "⬇️ Descargar PDF",
                pdf_bytes,
                f"{nombre_archivo}.pdf",
                "application/pdf",
                type="primary",
            )
        else:
            st.caption(
                "🖨️ Al desplegar en **streamlit.io** acá aparece el botón "
                "**Descargar PDF**. En este equipo no está la librería correspondiente: "
                "usá el HTML de la derecha (se abre en el navegador y se puede "
                "imprimir o guardar como PDF)."
            )
    with col_html:
        st.download_button(
            "⬇️ Descargar HTML (imprimible)",
            html_reporte.encode("utf-8"),
            f"{nombre_archivo}.html",
            "text/html",
        )

show_data_corte()
