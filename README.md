# Dashboard de Análisis Epidemiológico Nacional (Argentina)

Este proyecto es una herramienta integral de visualización y análisis epidemiológico desarrollada con **Streamlit**. Está diseñada para monitorear, analizar y predecir eventos de salud pública a nivel nacional (Argentina).

**Repositorio:** https://github.com/djinnxs/epitoolsnac

## Características Principales

- **Dashboards Interactivos**: Visualización dinámica de casos filtrables por Año, Evento, Provincia y Grupo Etario.
- **Mapas Geoespaciales**:
  - **Nivel Nacional**: Mapa de calor por provincias.
  - **Nivel Departamental**: Desglose por departamentos dentro de cada provincia.
- **Análisis Temporal**:
  - **Corredores Endémicos**: Visualización de zonas de seguridad, éxito, alarma y brote.
  - **Tendencias y Predicciones**: Modelos avanzados (Prophet, SARIMA) para proyectar casos futuros.
  - **Nowcasting**: Estimación de casos en tiempo real corrigiendo el retraso de notificación.
- **Sistema de Alertas Tempranas (EWS)**: Escaneo automático de toda la base para detectar brotes.
- **Información Contextual**:
  - **Clima**: Integración con datos climáticos históricos y actuales.
  - **Rumores**: Web scraping de noticias de salud para detección temprana de alertas.
  - **Epidemiología IA**: Consultas en lenguaje natural sobre la base de datos.
- **Reportes**: Generación automática de calendarios epidemiológicos en PDF y exportación de datos a Excel.

## Requisitos del Sistema

- **Python 3.12** o superior.
- **Git** (para clonar el repositorio).
- Acceso a internet (para mapas, clima y descargas de datos).

> **Nota**: Este proyecto **no requiere SQL Server**. Los datos se leen de un archivo Parquet local (`data/base_semanal.parquet`) generado a partir de un CSV de eventos mediante el script ETL.

## Instalación

1.  **Clonar el repositorio**:

    ```bash
    git clone https://github.com/djinnxs/epitoolsnac.git
    cd epitoolsnac
    ```

2.  **Crear un entorno virtual**:

    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate  # Windows
    source .venv/bin/activate  # Linux/Mac
    ```

3.  **Instalar dependencias**:

    ```bash
    pip install -r requirements.txt
    ```

    > **Nota**: `weasyprint` puede requerir librerías adicionales del sistema (GTK) en Windows.

## Configuración

Crea un archivo `.env` en la raíz del proyecto (opcional; solo lo necesitan las funcionalidades de clima):

```env
# Clave para la funcionalidad de clima (12_Clima.py)
OPENWEATHER_API_KEY=tu_clave_clima
```

## Generar los datos (ETL)

El dashboard lee los casos desde `data/base_semanal.parquet`. Para generarlo (o regenerarlo) a partir del CSV de la fuente de datos original:

```bash
python etl_semanal.py --csv "ruta\a\Base_uni.csv"
```

Esto escribe `data/base_semanal.parquet`, compatible con todas las páginas del dashboard.

## Uso

```bash
streamlit run Home.py
```

## Estructura del Proyecto

- `Home.py`: Página principal y punto de entrada.
- `etl_semanal.py`: Script ETL que convierte el CSV de eventos en `data/base_semanal.parquet`.
- `pages/`: Contiene los módulos individuales del dashboard.
- `data/`: Almacena los archivos de datos (Parquet, JSON, CSV) y el `base_semanal.parquet`.
- `utils/`: Funciones auxiliares y lógica compartida.
- `requirements.txt`: Lista de dependencias de Python.

## Contacto

Email: djinnxs@gmail.com
