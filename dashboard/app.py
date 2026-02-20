import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Monitor de Noticias", layout="wide")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

st.title("📡 Monitor de Noticias")
st.markdown("---")

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

hist_path = os.path.join(DATA, "historico.csv")
hoy_path = os.path.join(DATA, "hoy.csv")

if os.path.exists(hoy_path):
    st.header("📰 Noticias de Hoy")
    df_hoy = pd.read_csv(hoy_path)
    render_cards(df_hoy)

if os.path.exists(hist_path):
    st.header("📚 Histórico")
    df_hist = pd.read_csv(hist_path)
    render_cards(df_hist.tail(50))