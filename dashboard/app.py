import streamlit as st
import pandas as pd
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

st.title("Monitor de Noticias")

hist_path = os.path.join(DATA, "historico.csv")
hoy_path = os.path.join(DATA, "hoy.csv")

if os.path.exists(hoy_path):
    st.header("Noticias de Hoy")
    st.dataframe(pd.read_csv(hoy_path))

if os.path.exists(hist_path):
    st.header("Histórico")
    st.dataframe(pd.read_csv(hist_path))