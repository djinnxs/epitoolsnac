# pages/13_IA.py
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.common import get_parquet_path, check_parquet_exists, format_number, style_argentina
from utils.query_builder import NaturalLanguageQueryBuilder
import os

st.set_page_config(page_title="Consultas IA", page_icon="🤖", layout="wide")

# Estilo personalizado para que se vea lindo
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #1f77b4;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .example-box {
        background-color: #f0f8ff;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 1.5rem;
    }
    .result-box {
        background-color: #f9f9f9;
        padding: 1rem;
        border-radius: 8px;
        margin-top: 1rem;
    }
    .success-message {
        color: #28a745;
        font-weight: bold;
    }
    .detected-params {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ffc107;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown('<div class="main-title">🤖 Consultas Inteligentes a Datos Epidemiológicos</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Pregunta en lenguaje natural y obtén resultados al instante</div>', unsafe_allow_html=True)

# Separador
st.markdown("---")

# Crear dos columnas: izquierda para entrada, derecha para ayuda
col_input, col_help = st.columns([2, 1])

with col_help:
    with st.expander("💡 Ejemplos de Consultas", expanded=False):
        st.markdown("""
    <div class="example-box">
        <ul>
            <li>Dame casos de <b>diarrea</b> en <b>Buenos Aires</b> entre <b>2020</b> y <b>2022</b></li>
            <li>Muestra <b>bronquiolitis</b> en <b>Córdoba</b> del <b>2023</b></li>
            <li><b>Influenza</b> en <b>Santa Fe</b> en <b>2021</b></li>
            <li>Casos de <b>IRAG</b> en <b>Tandil</b> en <b>2022</b></li>
            <li>Total de <b>neumonía</b> en <b>Salta</b> <b>2019</b></li>
            <li><b>ETI</b> en <b>Resistencia</b> desde <b>2018</b> hasta <b>2020</b></li>
        </ul>
        <hr style="margin: 0.8rem 0; border: none; border-top: 1px solid #ddd;">
        <small style="color: #666;">
            💬 <b>Tip:</b> Escribe de forma natural. El sistema tolera errores ortográficos 
            (ej: "bronquilitis", "diarreas", "neumonia") y detecta variaciones automáticamente.
        </small>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("💡 **Eventos disponibles:** Bronquiolitis, Diarreas, Influenza (ETI), IRAG, Neumonía, y más.")

with col_input:
    st.markdown("### 🗣️ Tu Consulta")
    
    # Área de texto para la consulta
    query_text = st.text_area(
        "Escribe tu pregunta aquí:",
        height=120,
        placeholder="Ejemplo: dame casos de diarrea en tandil del año 2023",
        help="Escribe tu consulta en lenguaje natural. El sistema detectará automáticamente departamentos, eventos y años."
    )
    
    # Botón de consultar
    consultar_btn = st.button("🔍 Consultar", type="primary", width="stretch")

# Inicializar el query builder
query_builder = NaturalLanguageQueryBuilder()

# Inicializar estado de sesión
if 'query_result' not in st.session_state:
    st.session_state.query_result = None
if 'query_params' not in st.session_state:
    st.session_state.query_params = None

# Verificar que existe el archivo parquet
parquet_path = check_parquet_exists('base_semanal.parquet')

# Procesar la consulta cuando se presiona el botón
if consultar_btn and query_text.strip():
    with st.spinner('🔄 Procesando tu consulta...'):
        parquet_path_clean = parquet_path.replace('\\', '/')
        df_result, params = query_builder.execute_query(query_text, parquet_path_clean)
        st.session_state.query_result = df_result
        st.session_state.query_params = params

# Mostrar resultados desde el estado
if st.session_state.query_result is not None and st.session_state.query_params is not None:
    df_result = st.session_state.query_result
    params = st.session_state.query_params
    
    if params['success']:
        st.markdown("---")
        st.markdown("### 🎯 Parámetros Detectados")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if params.get('provincias'):
                st.markdown(f"**📍 Provincia/s:** {', '.join(params['provincias'])}")
            elif params.get('departamentos'):
                st.markdown(f"**📍 Departamento/s:** {', '.join(params['departamentos'])}")
            else:
                st.markdown("**📍 Provincia/s:** Todas")
        
        with col2:
            if params.get('eventos'):
                st.markdown(f"**🦠 Eventos:** {', '.join(params['eventos'])}")
            else:
                st.markdown("**🦠 Eventos:** Todos")
        
        with col3:
            if params.get('años'):
                años_str = ', '.join(map(str, params['años']))
                st.markdown(f"**📅 Años:** {años_str}")
            else:
                st.markdown("**📅 Años:** Todos")
        
        st.success(params['message'])

        # Mostrar resultados
        if not df_result.empty:
            st.markdown("---")
            st.markdown("### 📊 Resultados")

            # Métricas rápidas
            total_casos = df_result['CANTIDAD'].sum()
            num_provincias = df_result['PROVINCIA'].nunique()
            num_eventos = df_result['NOMBREEVENTOAGRP'].nunique()

            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("Total de Casos", format_number(total_casos))
            with metric_col2:
                st.metric("Provincias", num_provincias)
            with metric_col3:
                st.metric("Eventos", num_eventos)

            st.markdown("---")

            # Mostrar primeras 10 filas
            st.markdown("#### 📋 Primeras 10 Filas")
            df_display = df_result.sort_values('PROVINCIA').head(10).copy()
            df_display = df_display.rename(columns={'PROVINCIA': 'Provincia', 'DEPARTAMENTO': 'Departamento', 'SEMANA': 'Semana'})
            num_cols = ['CANTIDAD']
            st.dataframe(
                style_argentina(df_display.style.background_gradient(cmap="Blues", subset=['CANTIDAD']), num_cols),
                width="stretch",
                height=400
            )

            # Información adicional
            if len(df_result) > 10:
                st.info(f"ℹ️ Mostrando las primeras 10 filas de {len(df_result)} resultados totales. Descarga el CSV completo para ver todos los datos.")

            # Botón de descarga
            st.markdown("---")
            csv = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Resultados Completos (CSV)",
                data=csv,
                file_name=f"consulta_epidemiologia_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                help="Descarga todos los resultados en formato CSV",
                width="stretch"
            )

            # Opción de visualización
            st.markdown("---")
            st.markdown("### 📈 Visualización")

            viz_type = st.radio(
                "Selecciona el tipo de gráfico:",
                ["Barras por Provincia", "Barras por Evento", "Línea de Tiempo", "No mostrar gráfico"],
                horizontal=True
            )

            has_depto = 'DEPARTAMENTO' in df_result.columns
            geo_col = 'DEPARTAMENTO' if has_depto else 'PROVINCIA'
            geo_label = 'Departamento' if has_depto else 'Provincia'

            if viz_type == "Barras por Provincia":
                df_geo = df_result.groupby(geo_col, as_index=False)['CANTIDAD'].sum()
                df_geo = df_geo.rename(columns={geo_col: geo_label})
                fig = px.bar(
                    df_geo.sort_values('CANTIDAD', ascending=False),
                    x=geo_label,
                    y='CANTIDAD',
                    title=f'Casos por {geo_label}',
                    color='CANTIDAD',
                    color_continuous_scale='Blues'
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, width="stretch")

            elif viz_type == "Barras por Evento":
                df_evento = df_result.groupby('NOMBREEVENTOAGRP', as_index=False)['CANTIDAD'].sum()
                fig = px.bar(
                    df_evento.sort_values('CANTIDAD', ascending=False),
                    x='NOMBREEVENTOAGRP',
                    y='CANTIDAD',
                    title='Casos por Evento',
                    color='CANTIDAD',
                    color_continuous_scale='Oranges'
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, width="stretch")

            elif viz_type == "Línea de Tiempo":
                if 'SEMANA' not in df_result.columns:
                    st.info("Volvé a presionar 'Consultar' para generar la línea de tiempo con semana epidemiológica.")
                else:
                    df_tiempo = df_result.groupby(['ANIO', 'SEMANA'], as_index=False)['CANTIDAD'].sum()
                    df_tiempo = df_tiempo.sort_values(['ANIO', 'SEMANA'])
                    df_tiempo['semana_label'] = df_tiempo['ANIO'].astype(str) + '-S' + df_tiempo['SEMANA'].astype(int).astype(str).str.zfill(2)
                    fig = px.line(
                        df_tiempo,
                        x='semana_label',
                        y='CANTIDAD',
                        title='Evolución Temporal por Semana Epidemiológica',
                        markers=True
                    )
                    fig.update_xaxes(tickangle=-90, tickmode='auto', nticks=30)
                    st.plotly_chart(fig, width="stretch")

        else:
            st.warning("⚠️ No se encontraron resultados para tu consulta. Intenta con otros parámetros.")

    else:
        st.error(params['message'])
        st.info("💡 Intenta reformular tu pregunta incluyendo al menos una provincia, evento o año.")

if consultar_btn and not query_text.strip():
    st.warning("⚠️ Por favor, escribe una consulta antes de presionar el botón.")

# Footer con información adicional
st.markdown("---")
st.markdown("### ℹ️ ¿Cómo funciona?")

with st.expander("Ver detalles técnicos"):
    st.markdown("""
    **Sistema de Consultas Basado en Reglas**
    
    Este sistema utiliza técnicas de procesamiento de texto para detectar:
    
    1. **Provincias:** Detecta nombres de provincias
    2. **Departamentos:** Detecta nombres de departamentos
    3. **Eventos de Salud:** Identifica enfermedades y eventos epidemiológicos
    4. **Años y Rangos:** Extrae años específicos o rangos (ej: "entre 2020 y 2022")
    
    **Ventajas:**
    - ⚡ Respuesta instantánea (sin APIs externas)
    - 🚀 Sin consumo adicional de recursos
    - 🎯 Preciso para consultas bien estructuradas
    - 📊 Agrupa y suma datos automáticamente
    
    **Datos:**
    La base de datos se actualiza semanalmente.
    """)