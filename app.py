import os
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# -----------------------------
# Configuración general (estética y layout)
# -----------------------------
st.set_page_config(
    page_title="Dashboard Ventas | Empresa Alimentación",
    page_icon="📊",
    layout="wide",
)

# CSS ligero para mejorar estética (sin “abusar”)
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2.5rem; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      .small-note { color: rgba(0,0,0,0.6); font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Carga + preparación de datos (optimizada para memoria)
# -----------------------------
DATA_COLS = [
    "date","store_nbr","family","sales","onpromotion","holiday_type","dcoilwtico",
    "city","state","store_type","cluster","transactions","year","month","week","quarter","day_of_week"
]
CAT_COLS = ["family","holiday_type","city","state","store_type","day_of_week"]
DOW_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

# >>>>>> CAMBIO MÍNIMO: IDs de Google Drive (los enlaces que pasaste)
GDRIVE_ID_P1 = "1DOuw_bO4ERQL0XfGqdafwNSnGGF2J8F9"
GDRIVE_ID_P2 = "1c1pq4pGi6yieuv_0kffKbTiVhvkQZO54"

@st.cache_data(ttl=60*60, show_spinner="Cargando datos...")
def load_data() -> pd.DataFrame:
    """Lee parte_1.csv y parte_2.csv (si existen) y concatena. Si no existen, los descarga desde Google Drive."""
    base_dir = Path(__file__).parent
    p1 = base_dir / "parte_1.csv"
    p2 = base_dir / "parte_2.csv"

    if (not p1.exists()) or (not p2.exists()):
        try:
            import gdown  # necesitas añadir "gdown" a requirements.txt
        except ImportError:
            return pd.DataFrame()

        url1 = f"https://drive.google.com/uc?id={GDRIVE_ID_P1}"
        url2 = f"https://drive.google.com/uc?id={GDRIVE_ID_P2}"
        gdown.download(url1, str(p1), quiet=True)
        gdown.download(url2, str(p2), quiet=True)

        # si por permisos/no público no se descarga, devolvemos vacío para mostrar el error existente
        if (not p1.exists()) or (not p2.exists()) or p1.stat().st_size == 0 or p2.stat().st_size == 0:
            return pd.DataFrame()

    # Leemos solo columnas necesarias para el dashboard (ahorra memoria)
    df1 = pd.read_csv(p1, usecols=DATA_COLS, low_memory=False)
    df2 = pd.read_csv(p2, usecols=DATA_COLS, low_memory=False)

    df = pd.concat([df1, df2], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Optimización de tipos (muy importante para Streamlit Cloud)
    for c in CAT_COLS:
        if c in df.columns:
            df[c] = df[c].astype("category")

    df["store_nbr"] = df["store_nbr"].astype("int16")
    df["onpromotion"] = df["onpromotion"].astype("int16")
    df["cluster"] = df["cluster"].astype("int16")
    df["year"] = df["year"].astype("int16")
    df["month"] = df["month"].astype("int8")
    df["week"] = df["week"].astype("int16")
    df["quarter"] = df["quarter"].astype("int8")

    # Asegurar orden del día de semana
    if "day_of_week" in df.columns:
        df["day_of_week"] = df["day_of_week"].cat.set_categories(DOW_ORDER, ordered=True)

    return df

@st.cache_data(ttl=60*60, show_spinner=False)
def build_store_day(df: pd.DataFrame) -> pd.DataFrame:
    """
    DF a nivel tienda-día para evitar doble conteo de 'transactions'
    (en el dataset viene repetido por familia).
    """
    if df.empty:
        return df
    cols = [
        "date","store_nbr","state","city","store_type","cluster","transactions",
        "year","month","week","quarter","day_of_week","dcoilwtico","holiday_type"
    ]
    return df[cols].drop_duplicates(subset=["date","store_nbr"]).copy()

def apply_global_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Filtros globales (sidebar) aplicables a todas las pestañas."""
    if df.empty:
        return df

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()

    st.sidebar.subheader("Filtros globales")
    date_range = st.sidebar.date_input(
        "Años",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    else:
        start, end = pd.to_datetime(min_date), pd.to_datetime(max_date)

    out = df[(df["date"] >= start) & (df["date"] <= end)].copy()

    return out

def empty_state():
    # >>>>>> CAMBIO MÍNIMO: mensaje actualizado para Drive + requirements
    st.error("No se han podido cargar los datos (ni localmente ni desde Google Drive).")
    st.info(
        "Comprueba que en requirements.txt has añadido 'gdown' y que los archivos en Drive tienen acceso "
        "'Cualquier persona con el enlace (lector)'."
    )
    st.stop()

# -----------------------------
# App
# -----------------------------
st.title("📊 Dashboard de Ventas — Cierre de Año")
st.markdown(
    '<div class="small-note">Visión global + análisis por tienda y estado</div>',
    unsafe_allow_html=True,
)

df = load_data()
if df.empty:
    empty_state()

df = apply_global_filters(df)
df_store_day = build_store_day(df)

tabs = st.tabs(["1) Visión global", "2) Tienda", "3) Estado", "4) Insights extra"])

# ==========================================================
# TAB 1 — VISIÓN GLOBAL
# ==========================================================
with tabs[0]:
    st.header("Visión global del periodo")

    # ---- A) Conteo general
    st.subheader("A) Conteo general")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🏪 Tiendas", int(df["store_nbr"].nunique()))
    with c2:
        st.metric("🧺 Productos (families)", int(df["family"].nunique()))
    with c3:
        st.metric("🗺️ Estados", int(df["state"].nunique()))
    with c4:
        st.metric("🗓️ Meses con datos", int(df[["year","month"]].drop_duplicates().shape[0]))

    st.caption(
        f"Periodo: {df['date'].min().date()} → {df['date'].max().date()} | "
        f"Registros: {len(df):,}".replace(",", ".")
    )

    st.divider()

    # ---- B) Análisis en términos medios
    st.subheader("B) Análisis (ranking y distribución)")
    left, right = st.columns([1.1, 0.9])

    # i. Top 10 productos más vendidos (por ventas totales)
    top_prod = (
        df.groupby("family", observed=True)["sales"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
        .rename(columns={"sales":"total_sales"})
    )
    fig_top_prod = px.bar(
        top_prod,
        x="total_sales",
        y="family",
        orientation="h",
        title="🔝 Top 10 productos más vendidos (ventas totales)",
        labels={"total_sales":"Ventas totales", "family":"Familia"},
        text_auto=".2s",
    )
    fig_top_prod.update_layout(yaxis={"categoryorder":"total ascending"})
    left.plotly_chart(fig_top_prod, use_container_width=True)

    # ii. Distribución de ventas por tiendas
    store_sales = (
        df.groupby("store_nbr", observed=True)["sales"]
        .sum()
        .reset_index()
        .rename(columns={"sales":"total_sales"})
    )
    fig_dist_store = px.box(
        store_sales,
        y="total_sales",
        title="🏪 Distribución de ventas por tienda",
        labels={"total_sales":"Ventas totales por tienda"},
    )
    right.plotly_chart(fig_dist_store, use_container_width=True)

    # iii. Top 10 tiendas con ventas en productos en promoción
    promo_store = (
        df[df["onpromotion"] > 0]
        .groupby("store_nbr", observed=True)["sales"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
        .rename(columns={"sales":"promo_sales"})
    )
    fig_promo_store = px.bar(
        promo_store,
        x="store_nbr",
        y="promo_sales",
        title="🔝 Top 10 tiendas con ventas en productos en promoción",
        labels={"store_nbr":"Tienda", "promo_sales":"Ventas en promoción"},
        text_auto=".2s",
    )
    fig_promo_store.update_xaxes(type="category")
    st.plotly_chart(fig_promo_store, use_container_width=True)

    st.divider()

    # ---- C) Estacionalidad
    st.subheader("C) Estacionalidad")
    colA, colB = st.columns(2)

    # i. Día de la semana con más ventas promedio
    dow_avg = (
        df.groupby("day_of_week", observed=True)["sales"]
        .mean()
        .reset_index()
        .rename(columns={"sales":"avg_sales"})
    )
    fig_dow = px.bar(
        dow_avg,
        x="day_of_week",
        y="avg_sales",
        title="📅 Día de la semana con más ventas medias",
        labels={"day_of_week":"Día", "avg_sales":"Ventas promedio"},
        text_auto=".2s",
    )
    colA.plotly_chart(fig_dow, use_container_width=True)

    # ii. Ventas promedio por semana del año (promedio entre años)
    week_avg = (
        df.groupby("week", observed=True)["sales"]
        .mean()
        .reset_index()
        .rename(columns={"sales":"avg_sales"})
        .sort_values("week")
    )
    fig_week = px.line(
        week_avg, x="week", y="avg_sales",
        title="📆 Ventas medias por semana del año",
        labels={"week":"Semana", "avg_sales":"Ventas promedio"},
    )
    colB.plotly_chart(fig_week, use_container_width=True)

    # iii. Ventas promedio por mes (promedio entre años)
    month_avg = (
        df.groupby("month", observed=True)["sales"]
        .mean()
        .reset_index()
        .rename(columns={"sales":"avg_sales"})
        .sort_values("month")
    )
    fig_month = px.line(
        month_avg, x="month", y="avg_sales",
        title="🗓️ Ventas medias por mes",
        labels={"month":"Mes", "avg_sales":"Ventas promedio"},
        markers=True,
    )
    st.plotly_chart(fig_month, use_container_width=True)

# ==========================================================
# TAB 2 — TIENDA
# ==========================================================
with tabs[1]:
    st.header("Análisis por tienda")

    stores = sorted(df["store_nbr"].unique().tolist())
    store_sel = st.selectbox("Selecciona una tienda (store_nbr)", options=stores, index=0)

    d = df[df["store_nbr"] == store_sel].copy()

    # KPIs
    total_sales = float(d["sales"].sum())
    total_units_promo = float(d.loc[d["onpromotion"] > 0, "sales"].sum())
    prod_sold = int((d.groupby("family", observed=True)["sales"].sum() > 0).sum())

    k1, k2, k3 = st.columns(3)
    k1.metric("💰 Ventas totales", f"{total_sales:,.0f}".replace(",", "."))
    k2.metric("🧾 Transacciones totales", prod_sold)
    k3.metric("🏷️ Días con promoción", f"{total_units_promo:,.0f}".replace(",", "."))

    st.divider()

    col1, col2 = st.columns([1.1, 0.9])

    # a) Ventas por año
    by_year = (
        d.groupby("year", observed=True)["sales"]
        .sum()
        .reset_index()
        .sort_values("year")
        .rename(columns={"sales":"total_sales"})
    )
    fig_year = px.bar(
        by_year, x="year", y="total_sales",
        title="Ventas totales por año",
        labels={"year":"Año", "total_sales":"Ventas totales"},
        text_auto=".2s",
    )
    col1.plotly_chart(fig_year, use_container_width=True)

    prod_count = d["family"].nunique()
    prod_promo_count = d.loc[d["onpromotion"] > 0, "family"].nunique()
    col2.metric("🧺 Productos distintos vendidos", f"{prod_count:,}")
    col2.metric("🏷️ Productos distintos en promoción", f"{prod_promo_count:,}")

# ==========================================================
# TAB 3 — ESTADO
# ==========================================================
with tabs[2]:
    st.header("Análisis por estado (state)")

    states = sorted(df["state"].dropna().unique().tolist())
    state_sel = st.selectbox("Selecciona un estado", options=states, index=0)

    ds = df[df["state"] == state_sel].copy()
    dsd = df_store_day[df_store_day["state"] == state_sel].copy()

    # a) Total transacciones por año
    trx_year = (
        dsd.groupby("year", observed=True)["transactions"]
        .sum()
        .reset_index()
        .sort_values("year")
        .rename(columns={"transactions":"total_transactions"})
    )
    fig_trx = px.line(
        trx_year, x="year", y="total_transactions",
        title="Nº total de transacciones por año",
        labels={"year":"Año", "total_transactions":"Transacciones"},
        markers=True,
    )

    # b) Ranking tiendas con más ventas
    top_stores_state = (
        ds.groupby("store_nbr", observed=True)["sales"]
        .sum()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
        .rename(columns={"sales":"total_sales"})
    )
    fig_top_stores = px.bar(
        top_stores_state, x="store_nbr", y="total_sales",
        title="Ranking de tiendas con más ventas (en este estado)",
        labels={"store_nbr":"Tienda", "total_sales":"Ventas totales"},
        text_auto=".2s",
    )

    c1, c2 = st.columns(2)
    c1.plotly_chart(fig_trx, use_container_width=True)
    c2.plotly_chart(fig_top_stores, use_container_width=True)

    st.divider()

    # c) Producto más vendido por tienda (tabla)
    st.subheader("Producto más vendido por tienda (en el estado)")
    sf = (
        ds.groupby(["store_nbr","family"], observed=True)["sales"]
        .sum()
        .reset_index()
    )
    idx = sf.groupby("store_nbr")["sales"].idxmax()
    best_prod = sf.loc[idx].sort_values("sales", ascending=False)
    best_prod = best_prod.rename(columns={"family":"best_family","sales":"best_family_sales"})
    best_prod["best_family_sales"] = best_prod["best_family_sales"].round(2)
    st.dataframe(best_prod, use_container_width=True, height=420)

# ==========================================================
# TAB 4 — INSIGHTS EXTRA
# ==========================================================
with tabs[3]:
    st.header("Insights extra para decisiones rápidas ⭐")

    st.markdown(
        """
        - Impacto de promociones: ventas con promoción vs sin promoción.
        - Top 10 productos: ¿qué % de ventas concentran?
        - Impacto de festivos en ventas.
        """
    )

    if df.empty:
        st.warning("No hay datos para los filtros seleccionados.")
        st.stop()

    # ----------------------------------------------------------
    # 1) Impacto de promociones: ventas con vs sin promoción
    # ----------------------------------------------------------
    st.subheader("1) Impacto de promociones")

    tmp_promo = df[["sales", "onpromotion"]].copy()
    tmp_promo["onpromotion"] = pd.to_numeric(tmp_promo["onpromotion"], errors="coerce").fillna(0)

    tmp_promo["promo_flag"] = tmp_promo["onpromotion"].gt(0).map(
        {True: "En promoción", False: "Sin promoción"}
    )

    promo_compare = (
        tmp_promo.groupby("promo_flag", observed=True)["sales"]
        .sum()
        .reset_index()
        .rename(columns={"sales": "total_sales"})
    )

    fig_promo = px.bar(
        promo_compare,
        x="promo_flag",
        y="total_sales",
        title="Ventas totales: promoción vs no promoción",
        labels={"promo_flag": "Tipo de venta", "total_sales": "Ventas totales"},
        text_auto=".2s",
    )
    st.plotly_chart(fig_promo, use_container_width=True)

    st.divider()

    # ----------------------------------------------------------
    # 2) Top 10 productos: % de ventas que concentran
    # ----------------------------------------------------------
    st.subheader("2) Concentración de ventas en Top 10 productos")

    prod_all = (
        df.groupby("family", observed=True)["sales"]
        .sum()
        .reset_index()
        .rename(columns={"sales": "total_sales"})
        .sort_values("total_sales", ascending=False)
    )

    top10 = prod_all.head(10).copy()
    top10_sum = float(top10["total_sales"].sum())
    total_sum = float(prod_all["total_sales"].sum())
    share = (top10_sum / total_sum) * 100 if total_sum > 0 else 0.0

    c1, c2 = st.columns(2)
    c1.metric("Ventas Top 10 productos", f"{top10_sum:,.2f}")
    c2.metric("% sobre ventas totales", f"{share:,.2f}%")

    fig_top10 = px.bar(
        top10.sort_values("total_sales"),
        x="total_sales",
        y="family",
        orientation="h",
        title="Top 10 familias por ventas",
        labels={"family": "Familia", "total_sales": "Ventas totales"},
        text_auto=".2s",
    )
    fig_top10.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_top10, use_container_width=True)

    st.divider()

    # ----------------------------------------------------------
    # 3) Impacto de festivos: ventas medias (festivo vs no festivo)
    # ----------------------------------------------------------
    st.subheader("3) Impacto de festivos en ventas")
    
    hol = (
    df["holiday_type"]
    .astype("string")              # <-- clave: salir de category
    .fillna("No holiday")
    .str.strip()
    .str.lower()
)

    tmp_holiday = df[["sales", "holiday_type"]].copy()

    tmp_holiday["tipo_dia"] = hol.apply(
        lambda x: "No festivo" if x in {"no holiday", "none", "no festivo"} else "Festivo"
    )

    holiday_summary = (
        tmp_holiday.groupby("tipo_dia", observed=True)["sales"]
        .mean()
        .reset_index()
        .rename(columns={"sales": "avg_sales"})
    )

    fig_holiday = px.bar(
        holiday_summary,
        x="tipo_dia",
        y="avg_sales",
        title="Ventas medias diarias: festivo vs no festivo",
        labels={"tipo_dia": "Tipo de día", "avg_sales": "Ventas medias"},
        text_auto=".2s",
    )
    st.plotly_chart(fig_holiday, use_container_width=True)

    with st.expander("Notas de interpretación"):
        st.write("""
        - **Promociones**: las ventas se concentran principalmente en productos en promoción.
        - **Top 10 productos**: una parte significativa de las ventas proviene de pocas familias.
        - **Festivos**: las ventas medias aumentan en días festivos.
        """)






















