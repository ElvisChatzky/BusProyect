import feedparser
import requests
from bs4 import BeautifulSoup
import sqlite3
import os
from datetime import datetime, timedelta
import unicodedata
import pandas as pd
import re
from urllib.parse import urljoin

# ======================
# CONFIGURACION
# ======================

KEYWORD = "petri"  # <<< CAMBIAR ACA
MAX_DIAS_HISTORICO = 30  # limpiar noticias más viejas que esto

# Si es True, en cada ejecución se limpia la base/CSVs y se
# reconstruye todo con el criterio actual. Así evitamos que
# se sigan mostrando noticias viejas agregadas con lógica
# anterior que ya no coincide con la palabra clave.
RESETEAR_TODO_EN_CADA_EJECUCION = True

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "noticias.db")
CSV_HOY = os.path.join(DATA_DIR, "hoy.csv")
CSV_HIST = os.path.join(DATA_DIR, "historico.csv")

os.makedirs(DATA_DIR, exist_ok=True)

RSS_FEEDS = {
    "Infobae": "https://www.infobae.com/arc/outboundfeeds/rss/",
    "Clarín": "https://www.clarin.com/rss/lo-ultimo/",
    "La Nación": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/",
    "Ámbito": "https://www.ambito.com/rss/pages/home.xml",
    "Página12": "https://www.pagina12.com.ar/rss/ultimas-noticias",
    "El Cronista": "https://www.cronista.com/files/rss/ultimas_noticias.xml",
    "TN": "https://tn.com.ar/rss/",
    "MDZ": "https://www.mdzol.com/rss/",
    "Los Andes": "https://www.losandes.com.ar/arc/outboundfeeds/rss/",
    "Diario Uno": "https://www.diariouno.com.ar/rss.xml",
    "Sitio Andino": "https://www.sitioandino.com.ar/rss",
    "El Intransigente": "https://www.elintransigente.com/rss/",
    "Mendoza Post": "https://www.mendozapost.com/rss/",
    "La Política Online": "https://www.lapoliticaonline.com/rss.xml",
}

# ======================
# UTILIDADES
# ======================

def normalize(text):
    text = text.lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def contains_exact_word(text):
    text = normalize(text)
    keyword_normalized = normalize(KEYWORD)
    pattern = rf"\b{re.escape(keyword_normalized)}\b"
    return re.search(pattern, text) is not None


def extraer_texto_visible(html: str) -> str:
    """Extrae solo el texto visible típico de una nota (títulos y párrafos).

    Esto reduce falsos positivos que antes venían de metadatos, scripts,
    comentarios o secciones ocultas de la página.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Eliminar elementos que seguro no aportan contenido de la nota
    for tag in ["script", "style", "noscript", "header", "footer", "nav", "aside", "form"]:
        for elem in soup.find_all(tag):
            elem.decompose()

    textos = []
    for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        txt = elem.get_text(separator=" ", strip=True)
        if txt:
            textos.append(txt)

    return " ".join(textos)

# ======================
# BASE DE DATOS
# ======================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS noticias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            medio TEXT,
            titulo TEXT,
            url TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()

def limpiar_historico():
    limite = datetime.now() - timedelta(days=MAX_DIAS_HISTORICO)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM noticias WHERE fecha < ?", (limite.isoformat(),))
    conn.commit()
    conn.close()


def resetear_datos_completos():
    """Elimina la base y los CSV para empezar de cero."""
    try:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        if os.path.exists(CSV_HOY):
            os.remove(CSV_HOY)
        if os.path.exists(CSV_HIST):
            os.remove(CSV_HIST)
    except Exception:
        # Si por algún motivo no se puede borrar, seguimos igual.
        pass

def noticia_existe(url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM noticias WHERE url=?", (url,))
    existe = c.fetchone()
    conn.close()
    return existe is not None

def guardar_noticia(fecha, medio, titulo, url):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO noticias (fecha, medio, titulo, url)
        VALUES (?, ?, ?, ?)
    """, (fecha, medio, titulo, url))
    conn.commit()
    conn.close()

# ======================
# EXPORTAR CSV
# ======================

def exportar_csv():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM noticias ORDER BY fecha DESC", conn)
    conn.close()

    if df.empty:
        return

    df.to_csv(CSV_HIST, index=False)

    hoy = datetime.now().date().isoformat()
    df_hoy = df[df["fecha"].str.startswith(hoy)]
    df_hoy.to_csv(CSV_HOY, index=False)

# ======================
# SCRAPER
# ======================

def ejecutar():
    if RESETEAR_TODO_EN_CADA_EJECUCION:
        resetear_datos_completos()

    init_db()

    for medio, feed_url in RSS_FEEDS.items():
        print(f"Revisando {medio}...")
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            url = entry.link

            if noticia_existe(url):
                continue

            try:
                # Descargamos la nota y buscamos la palabra en el texto visible
                # (títulos y párrafos), no en todo el HTML crudo.
                resp = requests.get(
                    url,
                    timeout=10,
                    headers={
                        "User-Agent": "Mozilla/5.0 (compatible; BusProyect/1.0)"
                    },
                )
                resp.raise_for_status()

                texto_visible = extraer_texto_visible(resp.text)

                if contains_exact_word(texto_visible):
                    guardar_noticia(
                        datetime.now().isoformat(),
                        medio,
                        getattr(entry, "title", "(sin título)"),
                        url,
                    )
                    print("Nueva coincidencia:", getattr(entry, "title", "(sin título)"))

            except Exception as e:
                print("Error en:", url, "-", e)
                continue

    limpiar_historico()
    exportar_csv()
    print("Proceso finalizado")

if __name__ == "__main__":
    ejecutar()