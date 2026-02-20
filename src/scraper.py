import feedparser
import requests
from bs4 import BeautifulSoup
import sqlite3
import os
from datetime import datetime
import unicodedata
import pandas as pd
import re

# ======================
# CONFIGURACION
# ======================

KEYWORD = "argentina"  # <<< CAMBIAR ACA

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
    df = pd.read_sql_query("SELECT * FROM noticias", conn)
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
    init_db()

    for medio, feed_url in RSS_FEEDS.items():
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            url = entry.link

            if noticia_existe(url):
                continue

            try:
                r = requests.get(url, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                texto = soup.get_text()

                if contains_exact_word(texto):
                    guardar_noticia(
                        datetime.now().isoformat(),
                        medio,
                        entry.title,
                        url
                    )
                    print("Nueva coincidencia:", entry.title)

            except:
                continue

    exportar_csv()

if __name__ == "__main__":
    ejecutar()