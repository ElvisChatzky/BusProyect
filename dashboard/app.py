import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Monitor de Noticias", layout="wide")

st.title("📡 Monitor de Noticias")
st.markdown("---")

DATA_PATH = Path("data")

hoy_file = DATA_PATH / "hoy.csv"
hist_file = DATA_PATH / "historico.csv"

def render_cards(df):
    for _, row in df.iterrows():
        st.markdown(
            f"""
            <div style="
                background-color:#1e1e1e;
                padding:20px;
                border-radius:12px;
                margin-bottom:15px;
                border:1px solid #333;">
                <h4 style="margin-bottom:5px;">{row['titulo']}</h4>
                <p style="color:gray; margin:0;">
                    📰 {row['medio']} | 🕒 {row['fecha']}
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

if hoy_file.exists():
    st.header("📰 Noticias de Hoy")
    df_hoy = pd.read_csv(hoy_file)
    render_cards(df_hoy)
else:
    st.warning("No existe hoy.csv en el repo")

if hist_file.exists():
    st.header("📚 Histórico")
    df_hist = pd.read_csv(hist_file)
    render_cards(df_hist.tail(50))
else:
    st.warning("No existe historico.csv en el repo")