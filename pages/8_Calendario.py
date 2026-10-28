import datetime
import calendar
import sys
from io import BytesIO
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from utils.common import (
    get_data_corte,
    get_distinct_events,
    get_epi_week_data,
    get_parquet_path,
)

try:
    from weasyprint import HTML
    HAVE_WEASYPRINT = True
except Exception:
    HAVE_WEASYPRINT = False

# Configuración de página
st.set_page_config(page_title="Calendario Epidemiológico", page_icon=":date:", layout="wide")

from utils.common import show_semana_actual
show_semana_actual()

# Establecer el primer día de la semana como Domingo
calendar.setfirstweekday(calendar.SUNDAY)

# --- FUNCIONES DE GENERACIÓN (calendario tradicional en texto) ---

def generar_calendario_mes(anio_visto, mes):
    nbsp = "\xa0"
    meses_es = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    cal = calendar.monthcalendar(anio_visto, mes)
    lineas = []
    lineas.append(f"{meses_es[mes].upper()}:")
    lineas.append("SE  D  L  M  M  J  V  S ".replace(" ", nbsp))

    for fila in cal:
        # Buscamos el primer día distinto de 0 en la fila para determinar la SE
        dia_referencia = next((d for d in fila if d != 0), None)
        if dia_referencia:
            fecha_ref = datetime.date(anio_visto, mes, dia_referencia)
            num_semana, _ = get_epi_week_data(fecha_ref)
            semana_str = f"{num_semana:2d}"
        else:
            semana_str = "  "

        dias_str = ""
        for dia in fila:
            if dia == 0:
                dias_str += nbsp * 3
            else:
                dias_str += f"{dia:2d}{nbsp}"

        lineas.append(f"{semana_str}{nbsp}{dias_str.rstrip()}")

    while len(lineas) < 8:
        lineas.append(f"{nbsp*2} {nbsp*21}")

    return "\n".join(lineas)


# --- DATOS: matriz de casos por semana epidemiológica y año ---

@st.cache_data(ttl=3600)
def cargar_matriz_semanas(evento="Todos"):
    """Casos agrupados por (año, semana epidemiológica), con filtro opcional por evento."""
    path = get_parquet_path().replace('\\', '/')
    cols = ['ANIO', 'SEMANA', 'CANTIDAD']
    if evento != "Todos":
        cols.append('NOMBREEVENTOAGRP')
    df = pd.read_parquet(path, columns=cols)
    if evento != "Todos":
        df = df[df['NOMBREEVENTOAGRP'] == evento]
    return df.groupby(['ANIO', 'SEMANA'], as_index=False)['CANTIDAD'].sum()


# --- INTERFAZ STREAMLIT ---

st.markdown("<h1 style='text-align: center; margin-bottom: 10px;'> 📅 Calendario de Semanas Epidemiológicas</h1>", unsafe_allow_html=True)

hoy = datetime.date.today()
sem_hoy, anio_hoy = get_epi_week_data(hoy)
st.markdown(f"<h3 style='text-align: center;'>Hoy es Semana Epidemiológica: <span style='color: red; font-weight:bold;'>{sem_hoy}</span> del {anio_hoy}</h3>", unsafe_allow_html=True)

tab_datos, tab_trad = st.tabs(["🗓️ Calendario con datos", "🖨️ Calendario tradicional (PDF)"])

# ============ PESTAÑA 1: HEATMAP CON DATOS REALES ============
with tab_datos:
    st.markdown("#### 📊 Casos por semana epidemiológica y año")
    st.caption("Cada celda muestra los casos reportados en esa semana. "
               "Pasa el mouse por encima para ver el valor exacto.")

    eventos = get_distinct_events()
    evento_sel = st.selectbox("Filtrar por evento", ["Todos"] + eventos, key="cal_evento")

    matriz = cargar_matriz_semanas(evento_sel)

    if matriz.empty:
        st.info("No hay datos para mostrar con el filtro seleccionado.")
    else:
        pivot = (matriz.pivot(index='SEMANA', columns='ANIO', values='CANTIDAD')
                 .fillna(0).astype(int))

        fig = px.imshow(
            pivot,
            x=[str(c) for c in pivot.columns],
            y=[int(s) for s in pivot.index],
            labels=dict(x="Año", y="Semana epidemiológica", color="Casos"),
            color_continuous_scale="YlOrRd",
            aspect="auto",
        )
        fig.update_layout(
            height=640,
            margin=dict(l=50, r=20, t=30, b=40),
            coloraxis_colorbar=dict(title="Casos"),
        )
        st.plotly_chart(fig, width="stretch")

        # Resumen rápido
        total = int(matriz['CANTIDAD'].sum())
        ult_sem = matriz.loc[matriz['CANTIDAD'].idxmax()]
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("📌 Total en el rango", f"{total:,}".replace(",", "."))
        with c2:
            st.metric("🔥 Semana más crítica",
                      f"S{int(ult_sem['SEMANA'])} · {int(ult_sem['ANIO'])}",
                      delta=f"{int(ult_sem['CANTIDAD']):,} casos".replace(",", "."),
                      delta_color="off")
        with c3:
            corte = get_data_corte()
            if corte:
                st.metric("🗓️ Último corte",
                          f"S{corte['semana']} · {corte['anio']}",
                          delta=corte['fecha_fin'].strftime("%d/%m/%Y"),
                          delta_color="off")

# ============ PESTAÑA 2: CALENDARIO TRADICIONAL (conservado) ============
with tab_trad:
    # Selector de año
    col_izq, col_der = st.columns([1, 5])
    with col_izq:
        anios_lista = list(range(2020, 2051))
        anio_seleccionado = st.selectbox(
            "Seleccione Año", anios_lista,
            index=anios_lista.index(hoy.year) if hoy.year in anios_lista else 5)

    # Generar la data de los meses
    meses_render = [generar_calendario_mes(anio_seleccionado, m) for m in range(1, 13)]

    # Mostrar en 3 columnas
    col1, col2, col3 = st.columns(3)
    for i, texto in enumerate(meses_render):
        with [col1, col2, col3][i % 3]:
            st.code(texto, language=None)

    # --- GENERACIÓN DE PDF ---
    st.markdown("---")
    st.subheader("Descargar PDF para imprimir")

    if st.button("Generar PDF", type="primary"):
        filas_pdf = [(0,1,2), (3,4,5), (6,7,8), (9,10,11)]

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{ size: A4; margin: 1.2cm; }}
                body {{ font-family: 'Courier New', monospace; font-size: 11pt; line-height: 1.4; background: white; }}
                h1 {{ text-align: center; color: #003366; font-size: 18pt; margin-bottom: 15px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                td {{ width: 33.3%; vertical-align: top; padding: 8px 5px; }}
                .mes {{ border: 1px solid #999; border-radius: 8px; padding: 5px; background: #f9f9f9; }}
                .titulo {{ font-weight: bold; color: #003366; margin-bottom: 6px; }}
                pre {{ margin: 0; white-space: pre; font-size: 10pt; }}
            </style>
        </head>
        <body>
            <h1>Calendario de Semanas Epidemiológicas {anio_seleccionado}</h1>
            <table>
        """

        for a, b, c in filas_pdf:
            html_content += "<tr>"
            for idx in (a, b, c):
                m_texto = meses_render[idx]
                titulo = m_texto.split("\n")[0]
                # Extraemos el contenido quitando el título y convirtiendo saltos de línea
                c_lineas = m_texto.split("\n")[1:]
                contenido_html = "<br>".join(c_lineas)
                html_content += f'<td><div class="mes"><div class="titulo">{titulo}</div><pre>{contenido_html}</pre></div></td>'
            html_content += "</tr>"

        html_content += "</table></body></html>"

        if HAVE_WEASYPRINT:
            buffer = BytesIO()
            HTML(string=html_content).write_pdf(buffer, presentational_hints=True)
            st.download_button(
                label="📥 Descargar PDF",
                data=buffer.getvalue(),
                file_name=f"Calendario_EPI_{anio_seleccionado}.pdf",
                mime="application/pdf"
            )
            st.success("¡PDF generado correctamente!")
        else:
            st.warning("⚠️ La descarga PDF no está disponible en Windows. Instalá GTK3 o usá la captura de pantalla.")
