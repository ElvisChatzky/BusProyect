import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Monitor de Noticias", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        color: #e5e7eb;
        font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stSidebar {
        background-color: #111827 !important;
    }
    h1, h2, h3, h4 {
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📡 Monitor de Noticias")
st.caption("Panel de seguimiento automático de noticias filtradas por palabra clave.")
st.markdown("---")

DATA_PATH = Path("data")

hoy_file = DATA_PATH / "hoy.csv"
hist_file = DATA_PATH / "historico.csv"

# Lista completa de medios que queremos mostrar siempre en el filtro,
# aunque todavía no tengan noticias cargadas.
ALL_MEDIOS = [
    "El Cronista",
    "Infobae",
    "DolarHoy",
    "Clarín",
    "La Nación",
    "MDZ",
    "Los Andes",
    "Página12",
    "Ámbito",
    "Diario Uno",
    "Sitio Andino",
    "TN",
    "El Intransigente",
    "Mendoza Post",
    "La Política Online",
]


@st.cache_data(show_spinner=False)
def load_csv(path: Path):
    df = pd.read_csv(path)
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df


def build_filter_controls(df: pd.DataFrame):
    """Dibuja los filtros una sola vez en la sidebar y devuelve sus valores."""
    st.sidebar.header("Filtros")

    # Buscar por título siempre visible
    search_text = st.sidebar.text_input("Buscar en título", "", key="global_search").strip()

    st.sidebar.markdown("")  # pequeño espacio visual

    medios_en_datos = (
        sorted(df["medio"].dropna().unique())
        if (not df.empty and "medio" in df.columns)
        else []
    )
    # Unimos los medios que realmente existen en datos con la lista
    # completa de medios deseados, para que siempre aparezcan todos
    # en el filtro aunque todavía no tengan coincidencias.
    medios = sorted(set(ALL_MEDIOS) | set(medios_en_datos))
    if medios:
        medios_sel = st.sidebar.multiselect(
            "Medios", medios, default=medios, key="global_medios"
        )
        # Si el usuario des-selecciona todo, interpretamos como "todos los medios"
        if not medios_sel:
            medios_sel = medios
    else:
        medios_sel = None

    st.sidebar.markdown("")

    fecha_rango = None
    if "fecha" in df.columns and pd.api.types.is_datetime64_any_dtype(df["fecha"]):
        fechas_validas = df["fecha"].dropna()
        if not fechas_validas.empty:
            min_date = fechas_validas.min().date()
            max_date = fechas_validas.max().date()
            fecha_rango = st.sidebar.date_input(
                "Rango de fechas",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="global_fecha",
            )

    return search_text, medios_sel, fecha_rango


def apply_filters(df: pd.DataFrame, search_text: str, medios_sel, fecha_rango) -> pd.DataFrame:
    if df.empty:
        return df

    if search_text and "titulo" in df.columns:
        df = df[df["titulo"].str.contains(search_text, case=False, na=False)]

    if medios_sel and "medio" in df.columns:
        df = df[df["medio"].isin(medios_sel)]

    if (
        fecha_rango
        and "fecha" in df.columns
        and pd.api.types.is_datetime64_any_dtype(df["fecha"])
    ):
        fechas_validas = df["fecha"].dropna()
        if not fechas_validas.empty and isinstance(fecha_rango, tuple) and len(fecha_rango) == 2:
            desde, hasta = fecha_rango
            mask = (df["fecha"].dt.date >= desde) & (df["fecha"].dt.date <= hasta)
            df = df[mask]

    return df


def render_cards(df: pd.DataFrame):
    if df.empty:
        st.info("No hay noticias para los filtros seleccionados.")
        return

    for _, row in df.iterrows():
        titulo = row.get("titulo", "(Sin título)")
        medio = row.get("medio", "")
        fecha = row.get("fecha", "")
        url = row.get("url", None)

        fecha_str = (
            fecha.strftime("%Y-%m-%d %H:%M")
            if hasattr(fecha, "strftime")
            else str(fecha)
        )

        if url and isinstance(url, str):
            titulo_html = f'<a href="{url}" target="_blank" style="color:#ffffff;text-decoration:none;">{titulo}</a>'
            link_html = f'<a href="{url}" target="_blank" style="color:#4da3ff;">Ver nota completa ↗</a>'
        else:
            titulo_html = titulo
            link_html = ""

        st.markdown(
            f"""
            <div style="
                background-color:#1e1e1e;
                padding:20px;
                border-radius:12px;
                margin-bottom:15px;
                border:1px solid #333;">
                <h4 style="margin-bottom:5px;">{titulo_html}</h4>
                <p style="color:gray; margin:0 0 8px 0;">
                    📰 {medio} | 🕒 {fecha_str}
                </p>
                {link_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

# Cargar datos una sola vez
df_hoy = load_csv(hoy_file) if hoy_file.exists() else pd.DataFrame()
df_hist = load_csv(hist_file) if hist_file.exists() else pd.DataFrame()

# Armar un dataframe combinado para configurar los filtros (medios/fechas)
df_base_filtros_list = [d for d in [df_hoy, df_hist] if not d.empty]
df_base_filtros = pd.concat(df_base_filtros_list, ignore_index=True) if df_base_filtros_list else pd.DataFrame()

search_text, medios_sel, fecha_rango = build_filter_controls(df_base_filtros)

# Métricas rápidas
col1, col2 = st.columns(2)
with col1:
    if not df_hoy.empty:
        st.metric("Noticias de hoy", len(df_hoy))
with col2:
    if not df_hist.empty:
        st.metric("Noticias histórico", len(df_hist))

st.markdown("---")

tab_hoy, tab_hist = st.tabs(["📰 Hoy", "📚 Histórico"])

with tab_hoy:
    if not df_hoy.empty:
        df_hoy_filtrado = apply_filters(df_hoy, search_text, medios_sel, fecha_rango)
        render_cards(df_hoy_filtrado)
    else:
        st.warning("No existe hoy.csv en el repo")

with tab_hist:
    if not df_hist.empty:
        df_hist_filtrado = apply_filters(df_hist, search_text, medios_sel, fecha_rango)
        render_cards(df_hist_filtrado)
    else:
        st.warning("No existe historico.csv en el repo")