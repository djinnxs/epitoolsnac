# 📋 epitoolsnac2 — Qué es y cómo usarlo

> **Copia de mejora de `epitoolsnac`, SOLO LOCAL.** El proyecto original
> (`epitoolsnac\`) y **todo lo que está en GitHub quedaron intactos**: no se
> subió ni se modificó nada remoto. Esto es para que lo pruebes en tu
> computadora y, cuando vos (y tus jefes) lo aprueben, recién ahí se decida
> publicarlo.

---

## 🖥️ Verlo en tu computadora (ya está corriendo)

La app quedó levantada en: **http://localhost:8501**

Si algún día se cierra, para volver a abrirla:

```powershell
cd "C:\Users\djinn\OneDrive\Documentos\epitoolsnac2"
.\.venv\Scripts\streamlit run Home.py --server.port 8501
```

---

## 🚀 Publicar en streamlit.io (SOLO cuando lo apruebes — NO se hizo)

> ⛔ **Estado actual: 100% local.** No hay repositorio remoto configurado y
> **no se subió nada a GitHub**. La app en vivo de tus jefes sigue exactamente
> como estaba.
>
> Cuando quieras publicar (después de tu revisión y la aprobación de tus
> jefes), el paso a paso es:

1. Crear un repositorio **nuevo** en GitHub (por ejemplo `epitoolsnac2`).
   No usar el repo original.
2. En esta carpeta:

   ```powershell
   cd "C:\Users\djinn\OneDrive\Documentos\epitoolsnac2"
   git remote add origin https://github.com/djinnxs/epitoolsnac2.git
   git push -u origin main
   ```

3. Entrá a [share.streamlit.io](https://share.streamlit.io) con tu cuenta.
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
corre los 34 tests y verifica que el servidor arranque.

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
