import datetime
import calendar
import streamlit as st
from io import BytesIO
import sys
from pathlib import Path

try:
    from weasyprint import HTML
    HAVE_WEASYPRINT = True
except Exception:
    HAVE_WEASYPRINT = False

# Configuración de página
st.set_page_config(page_title="Calendario Epidemiológico", page_icon=":date:", layout="wide")

# Establecer el primer día de la semana como Domingo
calendar.setfirstweekday(calendar.SUNDAY)

# --- LÓGICA DE CÁLCULO EPIDEMIOLÓGICO ---

def get_epi_week_data(fecha):
    """
    Calcula el número de SE y el año epidemiológico.
    Regla: La SE 1 es la que contiene el primer jueves del año.
    Las semanas comienzan en DOMINGO.
    """
    anio = fecha.year
    
    def inicio_se_1(year):
        # El 4 de enero siempre está en la SE 1
        cuatro_enero = datetime.date(year, 1, 4)
        # weekday() de Python: 0=Lun... 6=Dom. 
        # Para que el domingo sea el inicio (retroceso 0):
        retroceso = (cuatro_enero.weekday() + 1) % 7 
        return cuatro_enero - datetime.timedelta(days=retroceso)

    inicio_actual = inicio_se_1(anio)
    
    # Si la fecha es anterior al inicio de la SE 1 del año actual, pertenece al anterior
    if fecha < inicio_actual:
        inicio_anterior = inicio_se_1(anio - 1)
        dias = (fecha - inicio_anterior).days
        return (dias // 7) + 1, anio - 1
    
    # Si la fecha es posterior o igual al inicio de la SE 1 del año siguiente
    inicio_proximo = inicio_se_1(anio + 1)
    if fecha >= inicio_proximo:
        return 1, anio + 1
    
    # Caso normal dentro del año
    dias = (fecha - inicio_actual).days
    return (dias // 7) + 1, anio

# --- FUNCIONES DE GENERACIÓN ---

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

# --- INTERFAZ STREAMLIT ---

st.markdown("<h1 style='text-align: center; margin-bottom: 10px;'> 📅 Calendario de Semanas Epidemiológicas</h1>", unsafe_allow_html=True)

hoy = datetime.date.today()
sem_hoy, anio_hoy = get_epi_week_data(hoy)
st.markdown(f"<h3 style='text-align: center;'>Hoy es Semana Epidemiológica: <span style='color: red; font-weight:bold;'>{sem_hoy}</span> del {anio_hoy}</h3>", unsafe_allow_html=True)

# Selector de año
col_izq, col_der = st.columns([1, 5])
with col_izq:
    anios_lista = list(range(2020, 2051))
    anio_seleccionado = st.selectbox("Seleccione Año", anios_lista, index=anios_lista.index(hoy.year) if hoy.year in anios_lista else 5)

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
