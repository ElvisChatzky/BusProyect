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

# Frase exacta a buscar en las noticias.
# Usamos "luis petri" para enfocarnos solo en notas sobre
# la persona y evitar falsos positivos con otros usos de "petri".
KEYWORD = "luis petri"

# Cantidad de días hacia atrás que se mantienen en la base.
# Cualquier noticia con fecha anterior se borra.
MAX_DIAS_HISTORICO = 15

# Si es True, en cada ejecución se limpia la base/CSVs y se
# reconstruye todo con el criterio actual. Esto garantiza que
# no queden noticias viejas mal filtradas. Una vez que todo
# funcione como querés, podés ponerlo en False para conservar
# el histórico entre corridas.
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
    # Como KEYWORD es una frase ("luis petri"), usamos una
    # búsqueda de frase completa, respetando límites de palabra
    # al inicio y al final para evitar partes de palabras.
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

    # Aseguramos que existan siempre los CSV, aunque no haya coincidencias.
    if df.empty:
        columnas = ["fecha", "medio", "titulo", "url"]
        df = pd.DataFrame(columns=columnas)

    df.to_csv(CSV_HIST, index=False)

    hoy = datetime.now().date().isoformat()
    if not df.empty and "fecha" in df.columns:
        df_hoy = df[df["fecha"].astype(str).str.startswith(hoy)]
    else:
        df_hoy = pd.DataFrame(columns=df.columns)

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
                # Usamos el título y el resumen/descripción del feed, que es
                # lo que ve el usuario en el listado. Esto evita falsos
                # positivos que venían de texto oculto o técnico en el HTML.
                titulo = getattr(entry, "title", "") or ""
                resumen = getattr(entry, "summary", "") or ""
                descripcion = getattr(entry, "description", "") or ""

                texto = f"{titulo} {resumen} {descripcion}"

                if contains_exact_word(texto):
                    guardar_noticia(
                        datetime.now().isoformat(),
                        medio,
                        titulo or "(sin título)",
                        url,
                    )
                    print("Nueva coincidencia:", titulo or "(sin título)")

            except Exception as e:
                print("Error en:", url, "-", e)
                continue

    limpiar_historico()
    exportar_csv()
    print("Proceso finalizado")

if __name__ == "__main__":
    ejecutar()