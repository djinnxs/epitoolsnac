# 📋 epitoolsnac2 — Qué es y cómo usarlo

> **Copia de mejora de `epitoolsnac`.** El proyecto original (`epitoolsnac\`)
> quedó intacto: no se modificó nada de esa carpeta ni de su app en vivo.
> El código nuevo está en el repositorio **`djinnxs/epitoolsnac2`** (privado,
> ya subido a GitHub) y **aún no está desplegado en streamlit.io**.

---

## 🖥️ Verlo en tu computadora (ya está corriendo)

La app quedó levantada en: **http://localhost:8501**

Si algún día se cierra, para volver a abrirla:

```powershell
cd "C:\Users\djinn\OneDrive\Documentos\epitoolsnac2"
.\.venv\Scripts\streamlit run Home.py --server.port 8501
```

---

## 🚀 Publicar en streamlit.io (siguiente paso)

> ✅ **Repositorio ya creado y subido:** [`djinnxs/epitoolsnac2`](https://github.com/djinnxs/epitoolsnac2)
> (privado, branch `main`, con todos los datos). La app en vivo de tus jefes
> sigue exactamente como estaba.
>
> Lo único que queda es el deploy en streamlit.io:
1. Entrá a [share.streamlit.io](https://share.streamlit.io) con tu cuenta.
2. **Create app** → **Deploy a new app** → **From existing repo**.
3. Elegí:
   - Repository: **`djinnxs/epitoolsnac2`**
   - Branch: **`main`**
   - Main file path: **`Home.py`**
4. En **Advanced settings → Secrets** pegá (si querés usar Clima e IA):

   ```toml
   OPENWEATHER_API_KEY = "tu-clave"
   OPENAI_API_KEY = "tu-clave"
   ```
   *(Sin estas claves la app funciona igual; solo Clima e IA muestran un aviso.)*
5. **Deploy**. Listo.

> ⚠️ No hace falta tocar `requirements.txt`: se respetaron todas las versiones
> declaradas, así que instala exactamente igual que el proyecto original.
> No hay (ni hace falta) Dockerfile.

---

## 🧪 Tests (opcional)

```powershell
cd "C:\Users\djinn\OneDrive\Documentos\epitoolsnac2"
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

En GitHub, el workflow **CI** (`.github/workflows/ci.yml`) corre solo en cada
push: instala el mismo `requirements.txt` que streamlit.io, compila todo,
corre los 36 tests y verifica que el servidor arranque.

### 📄 Sobre el PDF del Reporte Semanal

streamlit.io (Linux) instala aparte de `requirements.txt` lo que ponga en
**`packages.txt`** (librerías del sistema). Ya está incluido con lo que
WeasyPrint necesita (pango, harfbuzz, fontconfig), así que el **PDF se genera
solo al desplegar**. Solo si algún día cambiara la plataforma, en Windows sin
esas librerías la misma página ofrece el **HTML imprimible** de respaldo.

---

## 🗂️ Páginas nuevas para revisar

| Página | Qué muestra |
|---|---|
| **Ranking por Semana** | Cómo cambia el puesto de cada provincia SE a SE (bump chart). |
| **Retraso de Reporte** | Qué provincias/eventos están atrasados respecto del corte y dónde hay huecos de carga. |
| **Reporte Semanal** | Boletín descargable (PDF en la nube / HTML imprimible en Windows). |

Y en las páginas de siempre: **Mapas** ahora tiene mapa bivariado y cartograma;
**Casos por Semana** tiene small multiples; **Tendencias** tiene fan chart;
**Nowcasting** se reescribió con una banda de referencia honesta.


---

## 🔄 Ciclo semanal de datos

Igual que siempre: cuando tengas el `Base_uni.csv` nuevo,

```powershell
cd "C:\Users\djinn\OneDrive\Documentos\epitoolsnac2"
$env:BASE_UNI_CSV="C:\ruta\del\csv\Base_uni.csv"
.\.venv\Scripts\python.exe etl_semanal.py
# borrar el CSV, commitear y pushear el parquet:
git add data/base_semanal.parquet
git commit -m "data: regenerar base_semanal.parquet desde Base_uni.csv (datos al YYYY-MM-DD)"
git push origin main
```

---

## 🛟 Si algo sale mal: volver al original

- **Carpeta local:** usá `C:\Users\djinn\OneDrive\Documentos\epitoolsnac`
  (no se modificó).
- **App en streamlit.io:** si ya tenés una app apuntando al repo original
  `djinnxs/epitoolsnac`, sigue funcionando sin cambios.

Ver el detalle completo de todo lo cambiado en [`CAMBIOS.md`](CAMBIOS.md).
