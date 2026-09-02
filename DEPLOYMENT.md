# Guía de Despliegue en Streamlit Cloud

## Preparación para GitHub

Este proyecto (**epitools**) está configurado para funcionar correctamente en Streamlit Cloud. Se han realizado las siguientes mejoras:

### ✅ Cambios Realizados

1. **Fix de Importaciones de Módulos Locales**
   - Todas las páginas en `/pages` ahora incluyen al inicio:
   ```python
   import sys
   from pathlib import Path
   sys.path.append(str(Path(__file__).resolve().parent.parent))
   ```
   - Esto permite que las páginas dentro de `/pages` accedan correctamente a los módulos en `/utils`

2. **Requirements.txt Actualizado**
   - Incluye todas las dependencias necesarias con versiones específicas
   - Se eliminaron paquetes innecesarios (`epilearn`, `torch`)
   - Se agregaron paquetes faltantes (`pygwalker`, `streamlit-echarts`, `Pillow`)

3. **Configuración de Streamlit**
   - Archivo `.streamlit/config.toml` para configuración personalizada
   - Tema y comportamiento optimizado para Cloud

## Pasos para Desplegar

### 1. Subirlo a GitHub

```bash
# Inicializar git (si no lo has hecho)
git init

# Agregar todos los archivos
git add .

# Commit inicial
git commit -m "Preparación para despliegue en Streamlit Cloud"

# Crear repositorio en GitHub y agregar remote
git remote add origin https://github.com/tu-usuario/epitools.git
git branch -M main
git push -u origin main
```

### 2. Desplegar en Streamlit Cloud

1. Ir a [streamlit.io](https://streamlit.io)
2. Hacer clic en "Get Started"
3. Conectar tu cuenta de GitHub
4. Seleccionar el repositorio `epitools`
5. Configurar:
   - **Main file path**: `Home.py`
   - **Branch**: `main`
6. Hacer clic en "Deploy!"

## Estructura del Proyecto

```
epitools/
├── Home.py                 # Página principal
├── requirements.txt        # Dependencias
├── .streamlit/
│   └── config.toml        # Configuración de Streamlit
├── .gitignore             # Archivos a ignorar en Git
├── pages/                 # Páginas de la aplicación
│   ├── 00_Carga_Datos.py
│   ├── 1_Dashboard.py
│   ├── 2_Corredores.py
│   ├── 3_CasosSemana.py
│   ├── 4_Mapas.py
│   ├── 5_Tasas.py
│   ├── 6_Tablas.py
│   ├── 7_Poblacion.py
│   ├── 8_Calendario.py
│   ├── 9_Mediana.py
│   ├── 10_Monitoreo.py
│   ├── 11_Rumores.py
│   ├── 12_Clima.py
│   ├── 13_IA.py
│   ├── 14_Tendencia.py
│   ├── 15_Avanzado.py
│   ├── 17_Nowcasting.py
│   ├── 18_Alertas.py
│   ├── 19_MapaAnimado.py
│   ├── 20_CorrelacionClima.py
│   ├── 21_Sindemias.py
│   ├── 22_Semaforo.py
│   └── 30_About.py
├── utils/                 # Módulos locales
│   ├── common.py
│   ├── query_builder.py
│   ├── convert_clima.py
│   └── update_clima.py
├── data/                  # Datos
│   ├── parquet/
│   ├── provincia.json
│   └── departamento.json
└── assets/               # Assets estáticos
```

## Resolución de Problemas

### Error: "ModuleNotFoundError: No module named 'utils'"

- ✅ Ya está solucionado con el import fix en todas las páginas
- Cada página tiene al inicio:
  ```python
  import sys
  from pathlib import Path
  sys.path.append(str(Path(__file__).resolve().parent.parent))
  ```

### Error: "Missing requirements"

- ✅ Verifica que `requirements.txt` esté en la raíz del proyecto
- Todas las dependencias están incluidas con versiones específicas

### Datos no cargados

- Asegúrate de que los archivos en `data/` estén en el repositorio
- Los archivos `.parquet` deben estar en `data/parquet/`

## Variables de Entorno

Si tu aplicación usa variables de entorno (ej: API keys):

1. Agrega un archivo `.env.local` (NO se sube a GitHub)
2. En Streamlit Cloud, agrega las variables en los "Secrets"

Ejemplo en tu código:
```python
import os
api_key = os.getenv('API_KEY')
```

En Streamlit Cloud (Settings → Secrets):
```
API_KEY = "tu_clave_aqui"
```

## Notas Importantes

- Todas las hojas (pages) ahora pueden importar correctamente de `utils`
- El proyecto usa `python-dotenv` para variables de entorno
- Los datos están en formato Parquet para mejor rendimiento
- La configuración de Streamlit está optimizada para Cloud
