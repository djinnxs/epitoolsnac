import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# ==============================================================================
# CONFIGURACIÓN INICIAL
# ==============================================================================
st.set_page_config(page_title="Epidemiologia - Población", page_icon=":bar_chart:", layout="wide")

# ==============================================================================
# CARGA DE DATOS Y SANITIZACIÓN
# ==============================================================================
# Resolve data directory relative to this script
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
data_dir = os.path.join(project_root, 'data')
prov_parquet = os.path.join(data_dir, 'poblacionxprovinciaindec.parquet')
dept_parquet = os.path.join(data_dir, 'proyecciones_depto_indec.parquet')

df_prov = pd.DataFrame()
df_dept = pd.DataFrame()

# Carga de datos Provinciales
if os.path.exists(prov_parquet):
    df_prov = pd.read_parquet(prov_parquet)
    df_prov.columns = df_prov.columns.str.strip()
    if 'sexo_nombre' in df_prov.columns:
        # Aseguramos que los nombres de sexo sean consistentes: 'Varones', 'Mujeres', 'Ambos Sexos'
        df_prov['sexo_nombre'] = df_prov['sexo_nombre'].str.title()
else:
    st.error('⚠️ Archivo de población provincial no encontrado. Ejecute `python etl_semanal.py` para generar los archivos Parquet.')

# Carga de datos Departamentales
if os.path.exists(dept_parquet):
    df_dept = pd.read_parquet(dept_parquet)
    df_dept.columns = df_dept.columns.str.strip()
    if 'juri_nombre' in df_dept.columns:
        df_dept['juri_nombre'] = df_dept['juri_nombre'].str.upper()
    if 'sexo_nombre' in df_dept.columns:
        # Aseguramos que los nombres de sexo sean consistentes: 'Varones', 'Mujeres', 'Ambos Sexos'
        df_dept['sexo_nombre'] = df_dept['sexo_nombre'].str.title()
else:
    st.error('⚠️ Archivo de población departamental no encontrado. Ejecute `python etl_semanal.py` para generar los archivos Parquet.')

# ==============================================================================
# INTERFAZ DE USUARIO (UI)
# ==============================================================================
st.markdown('<center><h2 style="font-weight:bold; padding:5px; border-radius:6px; width:100%;">📊 Pirámide y Gráfico Poblacional</h2></center>', unsafe_allow_html=True)

# Main selector: Nivel
nivel = st.radio("📍 Seleccione Nivel", ["Provincia", "Departamento"], horizontal=True)

# Inicializar variables de filtro
provincia_sel = None
anio = None
depto_sel = None
df_filtrado_base = pd.DataFrame()
df_data_display = pd.DataFrame()

# ==============================================================================
# LÓGICA DE FILTRADO
# ==============================================================================

if nivel == "Provincia":
    if not df_prov.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            provincias = sorted(df_prov['juri_nombre'].unique().tolist())
            if 'TOTAL DEL PAÍS' in provincias:
                provincias.remove('TOTAL DEL PAÍS')
                provincias.insert(0, "TOTAL DEL PAÍS")
            
            provincia_sel = st.selectbox("🗺️ Provincia", provincias, index=0, format_func=lambda x: 'Nacional' if x == 'TOTAL DEL PAÍS' else x)
        
        with col2:
            años = sorted(df_prov['ano'].unique())
            default_year = 2023 if 2023 in años else años[-1]
            anio = st.selectbox("📅 Año", años, index=años.index(default_year))
        
        # Filtro base: Solo Varones y Mujeres para la pirámide y el cálculo total
        df_filtrado_base = df_prov[
            (df_prov['ano'] == anio) & 
            (df_prov['sexo_nombre'].isin(['Varones', 'Mujeres']))
        ]

        if provincia_sel == "TOTAL DEL PAÍS":
            df_data_display = df_filtrado_base[df_filtrado_base['juri_nombre'] == "TOTAL DEL PAÍS"]
        else:
            df_data_display = df_filtrado_base[df_filtrado_base['juri_nombre'] == provincia_sel]
            
    else:
        st.warning("No hay datos disponibles para el nivel provincial.")

else:  # Departamento level
    if not df_dept.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            provincias_dept = sorted(df_dept['juri_nombre'].unique())
            provincia_default = provincias_dept[0]
            provincia_sel = st.selectbox("🗺️ Provincia", provincias_dept, index=provincias_dept.index(provincia_default))
        
        with col2:
            deptos = sorted(df_dept[df_dept['juri_nombre'] == provincia_sel]['departamento_nombre'].unique())
            depto_sel = st.selectbox("🏘️ Departamento", deptos)
        
        with col3:
            años = sorted(df_dept['ano'].unique())
            default_year = 2023 if 2023 in años else años[-1]
            anio = st.selectbox("📅 Año", años, index=años.index(default_year))
        
        # Filtro base: Incluye Ambos Sexos, Varones y Mujeres (ya que no hay edad)
        df_filtrado_base = df_dept[
            (df_dept['ano'] == anio) & 
            (df_dept['juri_nombre'] == provincia_sel) & 
            (df_dept['departamento_nombre'] == depto_sel)
        ]
        
        # DataFrame para visualización (puede incluir "Ambos sexos" si existe)
        df_data_display = df_filtrado_base.copy()
        

    else:
        st.warning("No hay datos disponibles para el nivel departamental.")

# ==============================================================================
# DISPLAY DE RESULTADOS
# ==============================================================================

if not df_data_display.empty:
    
    # 1. CÁLCULO DE POBLACIÓN TOTAL (CORREGIDO: SUMA SOLO VARONES + MUJERES)
    df_poblacion_total = df_data_display[df_data_display['sexo_nombre'].isin(['Varones', 'Mujeres'])]
    total_poblacion = df_poblacion_total['poblacion'].sum()
    
    # Formato de título
    location_display = provincia_sel if nivel == "Provincia" else f"{provincia_sel} - {depto_sel}"
    location_display = 'Nacional' if location_display == "TOTAL DEL PAÍS" else location_display
    total_poblacion_fmt = f"{total_poblacion:,.0f}".replace(",", ".")
    
    st.markdown(f"""
        <h3 style='text-align: center; color: #1f77b4;'>
            {location_display} - Año {anio}: Población Total: {total_poblacion_fmt}
        </h3>
    """, unsafe_allow_html=True)
    
    
    # 2. LÓGICA DE GRÁFICOS MUTUAMENTE EXCLUYENTES
    
    if nivel == "Provincia":
        # 2.1. PIRÁMIDE POBLACIONAL (SOLO PARA PROVINCIA)
        
        # Reutilizamos el DataFrame filtrado df_data_display (ya solo tiene Varones/Mujeres)
        df_pyramid = df_data_display.copy()
        
        if 'edad' in df_pyramid.columns and not df_pyramid.empty:
            
            fig_pyramid = go.Figure()

            # Varones (Eje negativo)
            fig_pyramid.add_trace(go.Bar(
                x=-df_pyramid[df_pyramid["sexo_nombre"] == "Varones"]["poblacion"],
                y=df_pyramid[df_pyramid["sexo_nombre"] == "Varones"]["edad"],
                orientation="h",
                name="Varones",
                marker=dict(color="#4682b4"),
                hovertemplate='<b>Varones</b><br>Edad: %{y}<br>Población: %{customdata:,.0f}<extra></extra>',
                customdata=df_pyramid[df_pyramid["sexo_nombre"] == "Varones"]["poblacion"]
            ))

            # Mujeres
            fig_pyramid.add_trace(go.Bar(
                x=df_pyramid[df_pyramid["sexo_nombre"] == "Mujeres"]["poblacion"],
                y=df_pyramid[df_pyramid["sexo_nombre"] == "Mujeres"]["edad"],
                orientation="h",
                name="Mujeres",
                marker=dict(color="#ee7a87"),
                hovertemplate='<b>Mujeres</b><br>Edad: %{y}<br>Población: %{customdata:,.0f}<extra></extra>',
                customdata=df_pyramid[df_pyramid["sexo_nombre"] == "Mujeres"]["poblacion"]
            ))

            # Configuración
            max_pop = df_pyramid['poblacion'].max() * 1.1 
            
            fig_pyramid.update_layout(
                barmode='overlay',
                title=f"Pirámide Poblacional - {location_display} ({anio})",
                xaxis=dict(
                    title="Población",
                    tickvals=[-max_pop/2, 0, max_pop/2], 
                    ticktext=[f'{int(abs(-max_pop/2)):,}', '0', f'{int(abs(max_pop/2)):,}'],
                    range=[-max_pop, max_pop]
                ),
                yaxis_title="Grupo etario",
                template='plotly_white',
                height=650,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            st.plotly_chart(fig_pyramid, width="stretch")
                
        else:
            st.info("No se encontraron datos de grupo etario ('edad') para mostrar la pirámide poblacional.")

    elif nivel == "Departamento":
        # 2.2. GRÁFICO DE BARRAS POR SEXO (SOLO PARA DEPARTAMENTO)
        
        # Usamos df_poblacion_total (solo Varones y Mujeres) para el gráfico de barras
        pob_sexo = df_poblacion_total.groupby('sexo_nombre')['poblacion'].sum().reset_index()

        if not pob_sexo.empty:
            fig_bar = go.Figure()
            
            sexos = ['Varones', 'Mujeres']
            colors = {'Varones': '#4682b4', 'Mujeres': '#ee7a87'}
            
            for sexo in sexos:
                df_sexo = pob_sexo[pob_sexo['sexo_nombre'] == sexo]
                if not df_sexo.empty:
                    poblacion = df_sexo['poblacion'].iloc[0]
                    # Formato con separador de puntos
                    hover_text = f'<b>{sexo}</b><br>Población: {poblacion:,.0f}<extra></extra>'.replace(",", ".")
                    fig_bar.add_trace(go.Bar(
                        x=[sexo],
                        y=[poblacion],
                        name=sexo,
                        marker_color=colors[sexo],
                        hovertemplate=hover_text
                    ))

            fig_bar.update_layout(
                title=f"Población por Sexo - {location_display} ({anio})",
                xaxis_title="Sexo",
                yaxis_title="Población Total",
                template='plotly_white',
                showlegend=True,
                # Altura ajustada para ocupar un buen espacio visual
                height=650
            )
            
            st.plotly_chart(fig_bar, width="stretch")
        else:
            st.warning("No hay datos de 'Varones' o 'Mujeres' para el gráfico por sexo a nivel departamental.")

    # 3. TABLA Y DESCARGA
    
    st.markdown("---")
    st.subheader(f"📋 Datos de Población - Año {anio}")
    st.dataframe(df_data_display, width="stretch")
    
    with st.expander("📥 Descargar Datos"):
        csv = df_data_display.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar CSV",
            data=csv,
            file_name=f"poblacion_{nivel}_{anio}.csv",
            mime="text/csv"
        )
else:
    if df_prov.empty and df_dept.empty:
        st.info("🔄 Ejecute el script de conversión ETL para generar los archivos de población en formato Parquet.")
    else:
        st.warning('⚠️ No hay datos para los filtros seleccionados.')