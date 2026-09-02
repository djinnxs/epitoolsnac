# SEI - Sistema de Epidemiología Interactiva
## Manual Operativo Completo y Detallado para el Usuario Final

Bienvenido al **Sistema de Epidemiología Interactiva (SEI)**. Este manual está diseñado para explicar a profundidad el funcionamiento, las opciones y la base de los cálculos de cada una de las herramientas y hojas (pestañas) que conforman esta plataforma.

---

### 📊 SECCIÓN 1: RESUMEN

#### 1. Dashboard Principal (`1_Dashboard.py`)
**¿Qué hace?**  
Es el panel de control principal donde puedes obtener una vista macro del estado epidemiológico actual o histórico. Filtra millones de registros en segundos.

**¿Qué opciones tiene?**  
*   **Filtros:** Año, Semana, Evento (Enfermedad), Provincia, Departamento y Grupo Etario.
*   **Gráfico de Barras por Provincia:** Muestra la cantidad absoluta de casos por provincia seleccionada.
*   **Gráfico de Anillo (Donut) por Evento:** Muestra el porcentaje de distribución de patologías.
*   **Serie de Tiempo (Curva Epidemiológica):** Muestra los casos a lo largo del tiempo. Además, calcula **Tasas de Incidencia** automáticamente (Casos / Población * 100.000 habitantes) cruzando los datos con tablas poblacionales del INDEC.
*   **Treemap Jerárquico:** Un gráfico de rectángulos que permite ver la proporción de casos dividiendo primero por Provincia y luego por Departamento.
*   **Tabla Pivot Mensual:** Agrupa los datos en una tabla de doble entrada (Enfermedad vs Meses) para fácil descarga a Excel.

---

#### 2. Casos por Semana (`3_CasosSemana.py`)
**¿Qué hace?**  
A diferencia del Dashboard que agrupa por meses o totales, esta hoja se enfoca netamente en la agregación por **Semana Epidemiológica (SE)**. Es vital para detectar el inicio de un brote.

**Detalle:**  
Permite comparar las curvas de casos semanales entre diferentes años superpuestos, lo cual ayuda a visualizar si el pico de contagios actual se está adelantando o retrasando en el calendario en comparación con años anteriores.

---

#### 3. Monitoreo (`10_Monitoreo.py`)
**¿Qué hace?**  
No evalúa cuánta gente se enferma, sino **cómo están reportando los centros de salud** (hospitales, clínicas, laboratorios). Evalúa la calidad y velocidad de la carga de datos al sistema.

**¿Cómo se calculan sus indicadores?**  
*   **Regularidad (%):** Calcula en cuántas semanas del año (hasta la semana actual) el centro de salud notificó al menos 1 caso (o notificó "casos cero"). Si estamos en la semana 10, y el hospital reportó datos en 8 semanas, su regularidad es del 80%.
*   **Oportunidad:** Mide el retraso en la carga. Se calcula restando la "Semana actual menos 2" (semana esperada consolidada) a la "Última semana en la que el centro ingresó un dato". Si el número es 0, están al día; si es mayor, hay atraso administrativo.
*   **Cobertura:** Porcentaje de centros de salud en una provincia/departamento que tienen una regularidad mayor o igual al 50%.
*   **Notificación Nula (Silencio Epidemiológico):** Calcula el porcentaje de semanas en las que un centro no subió absolutamente ningún registro. En la tabla se colorea de Azul/Rojo cuando el centro no ha reportado nada, alertando al analista de una posible falla administrativa.

---

#### 4. Tendencias (`14_Tendencia.py`)
**¿Qué hace?**  
Utiliza modelos matemáticos avanzados de Machine Learning y Series Temporales para proyectar hacia el futuro (predicción de casos para el próximo año).

**¿Cómo lo hace y en qué se basa?**  
1.  **Descomposición STL:** El sistema toma la curva histórica de una enfermedad y matemáticamente la divide en 3 partes: *Tendencia* (si la enfermedad sube o baja a lo largo de los años), *Estacionalidad* (los picos repetitivos de cada verano/invierno), y el *Ruido/Residuos* (brotes anómalos impredecibles).
2.  **Tests de Estacionaridad (ADF / KPSS):** Pruebas estadísticas para verificar si el comportamiento del virus es estable a largo plazo o si su varianza cambia (importante para saber cuán confiable será la predicción).
3.  **Modelos Predictivos (El usuario puede elegir):**
    *   **Prophet:** Algoritmo creado por Meta (Facebook). Es muy bueno manejando feriados, datos faltantes y cambios de tendencia fuertes.
    *   **SARIMA:** El estándar de oro en estadística clásica. Toma en cuenta la auto-correlación (cómo los casos de la semana pasada afectan a esta semana) y la estacionalidad (periodo de 52 semanas).
    *   **ETS (Suavizado Exponencial):** Da mayor peso a los datos más recientes.
*El resultado es una curva punteada hacia el futuro con un "Intervalo de Confianza" sombreado que indica el rango de error esperado.*

---

#### 5. Análisis Avanzado (`15_Avanzado.py`)
**¿Qué hace?**  
Permite desglosar y cruzar los datos epidemiológicos con mayor granularidad para responder preguntas complejas.

**¿Qué análisis incluye?**  
1.  **Tendencia Temporal:** Visualiza la evolución de los casos por semana para un evento específico.
2.  **Correlación por Evento:** Compara todos los eventos epidemiológicos registrados durante un año seleccionado para ver cuáles tienen mayor peso.
3.  **Distribución por Grupo Etario:** Presenta un gráfico de anillo para entender qué grupo de edad es el más afectado por una enfermedad particular.
 4.  **Comparativa por provincia:** Compara la carga de una misma enfermedad entre diferentes provincias para un año determinado.

---

#### 6. Tablas y Explorador Dinámico (`6_Tablas.py`)
**¿Qué hace?**  
Integra un motor de inteligencia artificial y exploración de datos llamado *PyGWalker*, que transforma la tabla de datos bruta en una interfaz tipo Tableau o PowerBI.

**¿Para qué sirve?**  
Permite a los usuarios avanzados "arrastrar y soltar" variables (arrastrar "Semana" al Eje X, "Casos" al Eje Y) para crear sus propios gráficos y tablas personalizadas sin necesidad de programar, explorando la base de datos a su gusto.

---

### 🗺️ SECCIÓN 2: GEOGRAFÍA

#### 7. Mapas Estáticos y Mapa Animado (`4_Mapas.py` y `19_MapaAnimado.py`)
**¿Qué hacen?**  
Georreferencian la información utilizando las coordenadas (polígonos) de provincias y departamentos de Argentina.
*   **Estáticos (Nacional):** Crean mapas de "Coropletas" a nivel de provincias, donde las zonas más oscuras indican mayor cantidad de casos o mayor tasa de incidencia. Al seleccionar una provincia, se desglosa por departamentos.
*   **Animado:** Añade una barra de tiempo en la parte inferior. Al darle "Play", el sistema dibuja el mapa semana a semana, permitiendo visualizar la dirección en la que avanza una epidemia geográficamente (por ejemplo, desde el norte hacia el sur del país).

#### 8. Semáforo de Riesgo (`22_Semaforo.py`)
**¿Qué hace?**  
Pinta automáticamente las provincias de colores (Verde, Amarillo, Rojo) basándose en umbrales de crecimiento pre-establecidos, eximiendo al analista de buscar provincia por provincia para ver dónde está el problema.

---

### 🔬 SECCIÓN 3: ANÁLISIS EPIDEMIOLÓGICO

#### 9. Corredores Endémicos (`2_Corredores.py`)
**¿Qué hace?**  
Es la herramienta más importante para saber si estamos en "brote/epidemia" o en una "situación normal".

**¿Cómo se calcula?**  
1. El sistema filtra los últimos **5 años históricos** (descartando la semana 53 si la hubiera) para el evento y provincia/departamento seleccionado.
2. Agrupa los casos semana a semana y calcula **Cuartiles Matemáticos**:
   *   **Zona de Éxito (Verde):** Por debajo del Cuartil 25% (Q25). Indica que hay menos casos que en el 75% de los años históricos.
   *   **Zona de Seguridad (Azul):** Entre Q25 y Q50 (Mediana).
   *   **Zona de Alerta (Amarillo):** Entre Q50 y Q75.
   *   **Zona Epidémica (Arriba del Amarillo):** Supera el Q75 histórico.
3. Finalmente, grafica una línea de color distintivo con **los datos del año actual** superponiéndola sobre las bandas de colores calculadas, permitiendo ver de inmediato si la curva actual cruzó hacia la zona de epidemia.

#### 10. Tasas y Medianas (`5_Tasas.py` y `9_Mediana.py`)
*   **Tasas:** Relaciona los casos brutos con el censo. Un departamento chico con 100 casos puede estar mucho peor que uno grande con 500. El cálculo es `(Casos / Población) * 100.000`.
*   **Medianas:** Compara la curva de este año contra la Mediana de años anteriores (en lugar del promedio). La mediana es más confiable porque no se deja "ensuciar" por un año pasado que haya tenido un brote extraordinariamente gigante.

#### 11. Población Demográfica (`7_Poblacion.py`)
**¿Qué hace?**  
Es el módulo base que provee los denominadores poblacionales utilizados para calcular las tasas en todo el sistema.

**Detalle:**  
Permite explorar la distribución poblacional proyectada por el INDEC (2010-2026). Presenta pirámides poblacionales, densidad por provincia/departamento e indicadores de crecimiento, asegurando que el analista entienda la composición de la comunidad que está estudiando.

#### 12. Calendario Epidemiológico (`8_Calendario.py`)
**¿Qué hace?**  
Provee la estructura de tiempo estandarizada internacionalmente.

**¿Cómo lo hace?**  
Calcula automáticamente a qué Semana Epidemiológica (SE) corresponde una fecha calendario específica. Se basa en la regla estándar: "La Semana Epidemiológica 1 es aquella que contiene el primer jueves del año". Esto asegura que todos los datos se alineen correctamente sin importar en qué día de la semana caiga el 1 de enero.

---

### 🤖 SECCIÓN 4: INTELIGENCIA Y ALERTAS

#### 13. Nowcasting (`17_Nowcasting.py`)
**¿Qué hace?**  
Soluciona el problema universal de la vigilancia: los datos de las últimas 2 o 3 semanas siempre caen artificialmente porque los hospitales aún están procesando planillas (retraso en la notificación). El Nowcasting "adivina" cuántos casos reales hubo hoy, sin esperar a que carguen los datos.

**¿Cómo calcula la "estimación en tiempo real"?**  
1. Toma los últimos 4 años y analiza qué porcentaje del total final se solía reportar en la semana 1, en la 2, etc. (Calcula un **Factor de Completitud Histórico**).
2. Si históricamente en la semana 40 los hospitales solo llegan a cargar el 60% de los datos (Factor 0.60), y hoy tenemos reportados 100 casos, el sistema asume matemáticamente que el valor real final será `100 / 0.60 = 166 casos`.
3. Corrige la curva del gráfico levantando la "cola final" para mostrar la realidad estimada, e incluye una banda de error del ±15%.

#### 14. Sistema de Alertas Automáticas (EWS) (`18_Alertas.py`)
**¿Qué hace?**  
En lugar de que el usuario busque enfermedades jurisdicción por jurisdicción, el EWS (Early Warning System) **escanea toda la base de datos completa de un solo clic**.

**¿Cómo funciona?**  
1. Itera por cada evento y por cada provincia/departamento a la vez.
2. Calcula la Mediana y el Cuartil 75 (o el umbral que decidas en la barra superior) de los últimos 5 años para esa misma semana.
3. Evalúa la cantidad de casos actuales:
   *   **Si Actual > Q75:** Genera Alerta ROJA (Brote inminente).
   *   **Si Actual > Mediana:** Genera Alerta AMARILLA (Precaución).
   *   **Si Actual < Mediana:** Declara situación VERDE (Normal).
4. El sistema presenta tarjetas visuales y una tabla Excel descargable indicando qué jurisdicción y para qué enfermedad se disparó la alarma, mostrando además cuánto % crecieron los casos respecto a la semana anterior.

#### 15. Asistente IA (`13_IA.py`)
Permite hacer preguntas escritas como si hablaras con una persona (Ej: *"¿Cuántos casos de Dengue hubo en Buenos Aires en marzo de 2024?"*). Por detrás, el sistema de IA traduce tu texto en consultas a DuckDB, interroga la base de datos Parquet y te devuelve la respuesta redactada junto con el dato numérico exacto, mostrando también gráficos como barras por provincia o línea de tiempo semanal.

#### 16. Epirumores - Vigilancia Basada en Eventos (`11_Rumores.py`)
**¿Qué hace?**  
Realiza vigilancia epidemiológica no estructurada escaneando portales de noticias y medios de comunicación en tiempo real.

**¿Cómo funciona?**  
Conecta simultáneamente con más de 20 diarios nacionales y provinciales (Clarín, La Nación, diarios locales de todo el país, etc.) y busca palabras clave de salud (ej. "Dengue", "Brote", "Sarampión"). Devuelve una tabla con las noticias encontradas y sus links, facilitando la detección de brotes que aún no han sido notificados oficialmente al sistema de salud.

---

### 🌡️ SECCIÓN 5: AMBIENTE Y SINERGIA DE ENFERMEDADES

#### 17. Clima en Tiempo Real e Histórico (`12_Clima.py`)
**¿Qué hace?**  
Permite obtener datos climáticos actuales y acceder a un repositorio de datos meteorológicos históricos por provincia y estación.

**Detalle:**  
Se conecta a la API de OpenWeather para dar datos en tiempo real (Temperatura, Humedad, Viento). Además, permite descargar y visualizar mapas de calor con las temperaturas mínimas y máximas históricas en formato Excel, fundamentales para analizar vectores como mosquitos.

#### 18. Correlación Clima-Epidemia (`20_CorrelacionClima.py`)
**¿Qué hace?**  
Encuentra matemáticamente la relación entre los factores climáticos y el aumento de casos de una enfermedad.

**¿Cómo lo calcula (Modelo de Lag/Desfase)?**  
No compara el clima de hoy con los casos de hoy. Calcula la **Correlación de Pearson (r)** desplazando la curva del clima *N* semanas hacia atrás (Lag). Por ejemplo, descubre que el aumento de temperatura hoy tiene su impacto máximo en los casos de Dengue exactamente 3 semanas después, permitiendo predecir cuándo subirán los casos basándose en el clima actual.

#### 19. Rastreador de Sindemias (`21_Sindemias.py`)
**¿Qué hace?**  
Analiza la superposición simultánea de múltiples epidemias para medir el riesgo de colapso del sistema de salud.

**¿Cómo funciona?**  
1. Permite seleccionar un "preset" (ej. "Respiratorio Invierno": Influenza + Bronquiolitis + Neumonía) o combinar enfermedades a gusto.
2. Suma la carga de todos los pacientes semana a semana.
3. Si la curva combinada supera un umbral de capacidad (configurado por el usuario), emite una **Alerta de Colapso**. Esto es vital porque el hospital no solo recibe pacientes de Dengue o solo de Gripe; los recibe todos al mismo tiempo.

---

### ⚙️ SECCIÓN 6: CONFIGURACIÓN Y SISTEMA

#### 20. Carga de Datos (ETL) (`00_Carga_Datos.py`)
**¿Qué hace?**  
Es el motor administrativo del sistema. Convierte los archivos en crudo de las bases de datos (Excel, CSV) a un formato hiperoptimizado llamado *Parquet*. Esto es lo que permite que la aplicación cargue en milisegundos en lugar de minutos. Es usado principalmente por el administrador para actualizar la información.

#### 21. Acerca de (`30_About.py`)
**¿Qué hace?**  
Muestra la información general de la versión del sistema, los créditos del desarrollador e información de contacto técnico en caso de soporte.
