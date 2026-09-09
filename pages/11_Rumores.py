import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import re
import streamlit as st
import pandas as pd
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
from scrapling.fetchers import Fetcher

# Configuración de la página
st.set_page_config(page_title="Epirumores - Noticias de Salud", page_icon=":newspaper:", layout="wide")

# Lista de palabras clave (Keywords)
KEYWORDS = [
    'epidemia', 'enfermedad', 'virus', 'vacuna', 'Rabia', 'Lepidópteros', 'Lonomía', 'Alacranismo', 'Amebiasis', 
    'Araneísmo', 'Latrodectismo', 'Loxoscelismo', 'Foneutrismo', 'Aspergilosis', 'Bartonelosis', 'Botulismo', 
    'Bronquiolitis', 'Brucelosis', 'Candidemias', 'Candidiasis', 'Carbunco', 'Miositis', 'Celiaquía', 'Chagas', 
    'Cisticercosis', 'Citomegalovirus', 'Clamidiasis', 'Coccidioidomicosis', 'Cólera', 'Coqueluche', 
    'Coriomeningitis', 'COVID-19', 'Influenza', 'Cromoblastomicosis', 'Biotinidasa', 'Dengue', 'Dermatofitosis', 
    'Diabetes', 'Diarrea', 'Difteria', 'Encefalitis de San Luis', 'Encefalitis equina del Oeste', 
    'Encefalopatía espongiforme', 'Enfermedad Febril Exantemática-EFE', 'Sarampión', 'Rubéola', 'Virus del Zika', 
    'Esporotricosis', 'Fenilcetonuria', 'Feohifomicosis', 'Fibrosis Quística', 'Fiebre Amarilla', 'Chikungunya', 
    'Oropouche', 'Fiebre del Nilo Occidental', 'Fiebre Hemorrágica Argentina', 'Fiebre Q', 'Borreliosis', 
    'Fiebre tifoidea', 'Filariosis', 'Galactosemia', 'Gonorrea', 'Hantavirosis', 'paratifoidea', 'Hepatitis', 
    'Hialohifomicosis', 'Hidatidosis', 'Hidroarsenicismo', 'Hiperplasia Suprarrenal Congénita', 
    'Hipotiroidismo congénito', 'Histoplasmosis', 'HTLV', 'Infección respiratoria aguda bacteriana', 
    'Infecciones genitales', 'Infecciones por Candida auris', 'Cryptococcus', 'hongos miceliales', 
    'Influenza Aviar', 'Intoxicación medicamentosa', 'Intoxicación por Moluscos', 'Intoxicación por ARSÉNICO', 
    'Intoxicación por Cromo', 'Intoxicación por hidrocarburos', 'Intoxicación por Mercurio', 
    'Intoxicación por plaguicidas', 'Intoxicación por Plomo', 'Intoxicación por Monóxido de Carbono', 
    'Legionelosis', 'Leishmaniasis', 'Lepra', 'Leptospirosis', 'Linfogranuloma Venéreo', 'Listeriosis', 
    'Meningoencefalitis', 'Metahemoglobinemia del lactante', 'Micetomas actinomicóticos', 'Mucormicosis', 
    'Neumonía', 'Ofidismo', 'infecciones bacterianas', 'Paludismo', 'Pandrogo resistencia', 
    'Paracoccidioidomicosis', 'Parotiditis', 'Poliomielitis', 'Psitacosis', 'Rickettsiosis', 'Sífilis', 
    'brote de ETA', 'virus emergente', 'Streptococcus agalactiae', 'Sindrome Urémico Hemolítico', 'Tétanos', 
    'Toxocariasis', 'Toxoplasmosis', 'Triquinelosis', 'Tuberculosis', 'Triquinosis', 'VIH', 'Viruela', 'Antrax'
]

# Lista de diarios
DIARIOS = [
    {'nombre': 'TN', 'url': 'https://tn.com.ar/'},
    {'nombre': 'Clarín', 'url': 'https://www.clarin.com/'},
    {'nombre': 'La Nación', 'url': 'https://www.lanacion.com.ar/'},
    {'nombre': 'Página/12', 'url': 'https://www.pagina12.com.ar/'},
    {'nombre': 'El Ancasti', 'url': 'https://www.elancasti.com/'},
    {'nombre': 'Norte', 'url': 'https://www.diarioelnorte.com/'},
    {'nombre': 'El Chubut', 'url': 'https://www.elchubut.com.ar/'},
    {'nombre': 'La Voz del Interior', 'url': 'https://www.lavoz.com.ar/'},
    {'nombre': 'El Litoral', 'url': 'https://www.ellitoral.com/'},
    {'nombre': 'Uno Entre Ríos', 'url': 'https://www.unoentrerios.com.ar/'},
    {'nombre': 'El Comercial', 'url': 'https://www.elcomercial.com.ar/'},
    {'nombre': 'El Tribuno', 'url': 'https://www.eltribuno.com/'},
    {'nombre': 'Jujuy al Día', 'url': 'https://www.jujuyaldia.com.ar/'},
    {'nombre': 'La Arena', 'url': 'https://www.laarena.com.ar/'},
    {'nombre': 'El Diario de la Pampa', 'url': 'https://www.eldiariodelapampa.com.ar/'},
    {'nombre': 'Los Andes', 'url': 'https://www.losandes.com.ar/'},
    {'nombre': 'El Sol', 'url': 'https://www.elsol.com.ar/'},
    {'nombre': 'El Territorio', 'url': 'https://www.elterritorio.com.ar/'},
    {'nombre': 'La Mañana de Neuquén', 'url': 'https://www.lmneuquen.com/'},
    {'nombre': 'Río Negro', 'url': 'https://www.rionegro.com.ar/'},
    {'nombre': 'Diario de Cuyo', 'url': 'https://www.diariodecuyo.com.ar/'},
    {'nombre': 'La Gaceta', 'url': 'https://www.lagaceta.com.ar/'},
]

def _limpiar(texto):
    return re.sub(r'\s+', ' ', texto or '').strip()

def _enlace_valido(a_tag, base_url):
    href = (a_tag.attrib.get('href') or '').strip()
    if not href or href.startswith('#') or href.lower().startswith('javascript:'):
        return ''
    return urljoin(base_url, href)

def scrape_diario(diario, keywords):
    url = diario['url']
    nombre = diario['nombre']
    try:
        page = Fetcher.get(url, timeout=15, retries=2, retry_delay=0.5)
        if getattr(page, 'status', None) != 200:
            return [], f"{nombre}: HTTP {getattr(page, 'status', '?')}"

        noticias = []
        kws = [k.lower() for k in keywords]
        for tag in page.css('article, h2, h3'):
            titulo = _limpiar(tag.get_all_text())
            if not titulo:
                continue

            if tag.tag == 'article':
                enlaces = tag.css('a')
                enlace_tag = enlaces[0] if enlaces else None
            else:
                enlace_tag = tag.find_ancestor(lambda e: getattr(e, 'tag', '') == 'a')
            enlace = _enlace_valido(enlace_tag, url) if enlace_tag else ""

            tl = titulo.lower()
            if any(kw in tl for kw in kws):
                noticias.append({'diario': nombre, 'titulo': titulo, 'enlace': enlace})

        return noticias, None
    except Exception as e:
        return [], f"{nombre}: {type(e).__name__}: {e}"

@st.cache_data(ttl=1800) # El cache dura 30 minutos
def fetch_all_data(diarios_list, keywords_list):
    all_news = []
    errors = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape_diario, d, keywords_list): d for d in diarios_list}
        for future in futures:
            nombre = futures[future]['nombre']
            noticias, error = future.result()
            all_news.extend(noticias)
            if error:
                errors.append(error)

    return pd.DataFrame(all_news), errors

def main():
    st.title("📰 Noticias de Salud en Argentina (Epirumores)")
    st.write("Monitoreo en tiempo real de medios nacionales y provinciales.")

    if st.button('🔄 Actualizar Noticias'):
        st.cache_data.clear()

    with st.spinner('Escaneando diarios en paralelo...'):
        df_noticias, lista_errores = fetch_all_data(DIARIOS, KEYWORDS)

    if not df_noticias.empty:
        # Mostrar tabla
        st.subheader(f"📍 Se encontraron {len(df_noticias)} noticias relevantes")
        
        # Botón de Descarga CSV (Inspirado en mejores prácticas de Whale Alert)
        csv = df_noticias.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar tabla en CSV",
            data=csv,
            file_name='reporte_epirumores.csv',
            mime='text/csv',
        )
        
        # Mostrar DataFrame interactivo
        st.dataframe(df_noticias, width="stretch", height=500)
    else:
        st.info("No se detectaron noticias con las palabras clave en este momento.")

    # Sección de diagnóstico
    with st.expander("🛠️ Estado de la conexión por sitio"):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"✅ Sitios procesados: {len(DIARIOS)}")
        with col2:
            if lista_errores:
                st.error(f"❌ Errores detectados: {len(lista_errores)}")
                for err in lista_errores:
                    st.caption(err)
            else:
                st.success("Sin errores de conexión.")

if __name__ == "__main__":
    main()