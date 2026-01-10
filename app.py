# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO
from pathlib import Path

# ----------------------------
# CONFIG
# ----------------------------
st.set_page_config(
    page_title="Dashboard Ventas | Empresa Alimentación",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard de Ventas — Cierre de Año")
st.caption("Visión global + análisis por tienda y estado")

# ----------------------------
# CARGA DE DATOS (PARQUET)
# ----------------------------
CACHE_FILE = Path("ventas_normalizadas.parquet")
@st.cache_data(ttl=24*3600, show_spinner=True)
def download_and_prepare_data() -> None:
    """
    Descarga el parquet original, normaliza los datos
    y guarda un parquet limpio en disco.
    """
    url = "https://upcomillas-my.sharepoint.com/:u:/g/personal/202408980_alu_comillas_edu/IQCa_6_CXHL6TKZs8lSa6SwWAeCY5dTnHOWTpQ7gAoQ_GCM?download=1"

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
    r = requests.get(url, headers=headers, timeout=300)
    r.raise_for_status()

    df = pd.read_parquet(BytesIO(r.content))

    # --- Normalización ---
    for col in ["sales", "onpromotion", "transactions"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32").fillna(0)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in ["year", "month", "week"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int16")

    if "store_nbr" in df.columns:
        df["store_nbr"] = pd.to_numeric(df["store_nbr"], errors="coerce").astype("Int16")

    for col in ["state", "family"]:
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("NA").astype("category")

    if "holiday_type" in df.columns:
        df["holiday_type"] = df["holiday_type"].astype("string")

    # --- Guardado ---
    df.to_parquet(DATA_FILE, index=False)
@st.cache_data(ttl=24*3600)
def load_data() -> pd.DataFrame:
    """
    Lee el parquet normalizado ya existente.
    """
    return pd.read_parquet(DATA_FILE)
def reset_store():
    st.session_state.pop("store_sel", None)
    st.session_state.pop("state_sel", None)

if not DATA_FILE.exists():
    download_and_prepare_data()

df = load_data()

# ----------------------------
# SIDEBAR (filtros globales opcionales)
# ----------------------------
with st.sidebar:
    st.header("Filtros globales")
    years = sorted(df["year"].dropna().unique()) if "year" in df.columns else []

    selected_years = st.multiselect(
        "Años",
        years,
        default=years,
        on_change=reset_store,
        key="years_sel"
    )

    if selected_years:
        df_f = df[df["year"].isin(selected_years)].copy()
    else:
        df_f = df.copy()

    st.divider()

# ----------------------------
# TABS
# ----------------------------
tab1, tab2, tab3, tab4 = st.tabs(["1) Global", "2) Por tienda", "3) Por estado", "4) Insights extra ⭐"])

# ============================================================
# TAB 1 — GLOBAL
# ============================================================
with tab1:
    st.subheader("Visión global del periodo")

    # A) Conteo general
    c1, c2, c3, c4 = st.columns(4)

    total_stores = df_f["store_nbr"].nunique() if "store_nbr" in df_f.columns else 0
    total_products = df_f["family"].nunique() if "family" in df_f.columns else 0
    total_states = df_f["state"].nunique() if "state" in df_f.columns else 0
    total_months = df_f[["year", "month"]].dropna().drop_duplicates().shape[0] if {"year","month"}.issubset(df_f.columns) else 0

    c1.metric("🏪 Tiendas", f"{total_stores:,}")
    c2.metric("🧺 Productos (families)", f"{total_products:,}")
    c3.metric("🗺️ Estados", f"{total_states:,}")
    c4.metric("🗓️ Meses con datos", f"{total_months:,}")

    st.divider()

    # B) Análisis (términos medios / rankings)
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 🔝 Top 10 productos más vendidos (ventas totales)")
        top_products = (
            df_f.groupby("family", as_index=False)["sales"]
            .sum()
            .sort_values("sales", ascending=False)
            .head(10)
        )
        fig = px.bar(top_products, x="sales", y="family", orientation="h", text_auto=".2s" )
        fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

    with col_right:
        st.markdown("#### 🏪 Distribución de ventas por tienda")
        store_sales = (
            df_f.groupby("store_nbr", as_index=False)["sales"]
            .sum()
            .sort_values("sales", ascending=False)
        )
        fig = px.box(
            store_sales,
            y="sales",
            title="Distribución de ventas por tienda"
        )
        st.plotly_chart(fig, width="stretch")

    st.markdown("#### 🔝 Top 10 tiendas con ventas en productos en promoción")
    promo_df = df_f[df_f["onpromotion"].fillna(0) > 0].copy()
    top_promo_stores = (
        promo_df.groupby("store_nbr", as_index=False)["sales"]
        .sum()
        .sort_values("sales", ascending=False)
        .head(10)
    )
    top_promo_stores["store_nbr"] = top_promo_stores["store_nbr"].astype(str)

    fig = px.bar(
        top_promo_stores,
        x="store_nbr",
        y="sales",
        title="Top 10 tiendas con ventas en productos en promoción",
        text_auto=".2s" 
    )
    fig.update_xaxes(type="category")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig, width="stretch")

    st.divider()

    # C) Estacionalidad
    cA, cB, cC = st.columns(3)

    with cA:
        st.markdown("#### 📅 Día de la semana con más ventas medias")
        dow_mean = (
            df_f.groupby("day_of_week", as_index=False)["sales"]
            .mean()
            .sort_values("sales", ascending=False)
        )
        fig = px.bar(dow_mean, x="day_of_week", y="sales", text_auto=".2s" )
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

    with cB:
        st.markdown("#### 📆 Ventas medias por semana del año")
        week_mean = (
            df_f.groupby("week", as_index=False)["sales"]
            .mean()
            .sort_values("week")
        )
        fig = px.line(week_mean, x="week", y="sales")
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

    with cC:
        st.markdown("#### 🗓️ Ventas medias por mes")
        month_mean = (
            df_f.groupby("month", as_index=False)["sales"]
            .mean()
            .sort_values("month")
        )
        fig = px.line(month_mean, x="month", y="sales", markers=True)
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")


# ============================================================
# TAB 2 — POR TIENDA
# ============================================================
with tab2:
    st.subheader("Análisis por tienda (store_nbr)")

    stores = sorted(df_f["store_nbr"].dropna().unique())
    store_sel = st.selectbox(
    "Selecciona una tienda",
    stores,
    index=0,
    key="store_sel"
)

    df_store = df_f[df_f["store_nbr"] == store_sel]

    a, b, c = st.columns(3)
    a.metric("💰 Ventas totales", f"{df_store['sales'].sum():,.2f}")
    b.metric("🧾 Transacciones totales", f"{df_store['transactions'].sum():,.0f}" if "transactions" in df_store.columns else "—")
    c.metric("🏷️ Días con promoción", f"{(df_store['onpromotion'].fillna(0) > 0).sum():,}")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("####  Ventas totales por año")
        by_year = (
            df_store.groupby("year", as_index=False)["sales"]
            .sum()
            .sort_values("year")
        )
        fig = px.bar(by_year, x="year", y="sales", text_auto=".2s" )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

    with col2:

        prod_count = df_store["family"].nunique()
        prod_promo_count = df_store[df_store["onpromotion"].fillna(0) > 0]["family"].nunique()

        st.metric("🧺 Productos distintos vendidos", f"{prod_count:,}")
        st.metric("🏷️ Productos distintos vendidos en promoción", f"{prod_promo_count:,}")

# ============================================================
# TAB 3 — POR ESTADO
# ============================================================
with tab3:
    st.subheader("Análisis por estado (state)")

    states = sorted(df_f["state"].dropna().unique())
    state_sel = st.selectbox(
    "Selecciona un estado",
    states,
    index=0,
    key="state_sel"
)

    df_state = df_f[df_f["state"] == state_sel]

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Nº total de transacciones por año")
        if "transactions" in df_state.columns:
            tx_year = (
                df_state.groupby("year", as_index=False)["transactions"]
                .sum()
                .sort_values("year")
            )
            fig = px.bar(tx_year, x="year", y="transactions", text_auto=".2s" )
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No existe la columna 'transactions' en el dataset.")

    with col2:
        st.markdown("#### Ranking de tiendas con más ventas (en este estado)")
        n_stores = df_state["store_nbr"].nunique()

        rank_stores = (
            df_state.groupby("store_nbr", as_index=False)["sales"]
            .sum()
            .sort_values("sales", ascending=False)
            .head(n_stores)
        )

        rank_stores["store_cat"] = rank_stores["store_nbr"].astype(str)
        rank_stores = rank_stores.sort_values("sales")

        st.caption(f"Este estado tiene {n_stores} tienda(s) en el dataset.")

        fig = px.bar(rank_stores, x="sales", y="store_cat", orientation="h", text_auto=".2s" )
        fig.update_yaxes(type="category", title="Tienda")
        fig.update_xaxes(title="Ventas")
        st.plotly_chart(fig, width="stretch")

    st.markdown("#### Producto más vendido (en este estado)")
    top_product_state = (
        df_state.groupby("family", as_index=False)["sales"]
        .sum()
        .sort_values("sales", ascending=False)
        .head(1)
    )
    if len(top_product_state) == 1:
        st.success(f"🏆 **{top_product_state.iloc[0]['family']}** — Ventas: {top_product_state.iloc[0]['sales']:,.2f}")
    else:
        st.info("No hay datos suficientes para calcular el producto más vendido.")


# ============================================================
# TAB 4 — INSIGHTS EXTRA (para sorprender)
# ============================================================
with tab4:
    st.subheader("Insights extra para decisiones rápidas ⭐")

    st.markdown("##### Impacto de promociones: ventas con promoción vs sin promoción")

    # 1) Creamos una copia "limpia" solo para este análisis (NO tocamos df_f)
    tmp_promo = df_f[["sales", "onpromotion"]].copy()

    # 2) Aseguramos que onpromotion sea numérico (por si viene como texto)
    tmp_promo["onpromotion"] = pd.to_numeric(tmp_promo["onpromotion"], errors="coerce").fillna(0)

    # 3) Etiquetamos promo / no promo
    tmp_promo["promo_flag"] = tmp_promo["onpromotion"].gt(0).map(
        {True: "En promoción", False: "Sin promoción"}
    )

    # 4) Agregamos
    promo_compare = (
        tmp_promo.groupby("promo_flag", as_index=False)["sales"]
        .sum()
    )

    # 5) Gráfico
    fig = px.bar(
        promo_compare,
        x="promo_flag",
        y="sales",
        title="Impacto de promociones: ventas con vs sin promoción",
        text_auto=".2s"
    )

    fig.update_layout(
        xaxis_title="Tipo de venta",
        yaxis_title="Ventas (sales)"
    )

    st.plotly_chart(fig, width="stretch")

    st.divider()

    st.markdown("##### Top 10 productos: ¿qué % de ventas concentran?")
    prod_all = df_f.groupby("family", as_index=False)["sales"].sum().sort_values("sales", ascending=False)
    top10_sum = prod_all.head(10)["sales"].sum()
    total_sum = prod_all["sales"].sum()
    share = (top10_sum / total_sum) * 100 if total_sum else 0

    c1, c2 = st.columns(2)
    c1.metric("Ventas Top 10 productos", f"{top10_sum:,.2f}")
    c2.metric("% sobre ventas totales", f"{share:,.2f}%")

    st.divider()

    st.markdown("### 📅 Impacto de festivos en ventas")

    # 1) Copia mínima (no tocamos df_f)
    tmp_holiday = df_f[["sales", "holiday_type"]].copy()

    # 2) Aseguramos string limpio
    tmp_holiday["holiday_type"] = (
        tmp_holiday["holiday_type"]
        .fillna("No festivo")
        .astype(str)
    )

    # 3) Creamos etiqueta FINAL (solo strings, nunca boolean)
    tmp_holiday["tipo_dia"] = tmp_holiday["holiday_type"].apply(
        lambda x: "Festivo" if x.lower() not in ["no holiday", "no festivo", "none"] else "No festivo"
    )

    # 4) Agregamos
    holiday_summary = (
        tmp_holiday.groupby("tipo_dia", as_index=False)["sales"]
        .mean()
    )

    # 5) Gráfico
    fig = px.bar(
        holiday_summary,
        x="tipo_dia",
        y="sales",
        title="Ventas medias diarias: festivo vs no festivo",
        text_auto=".2s"
    )

    fig.update_layout(
        xaxis_title="Tipo de día",
        yaxis_title="Ventas medias (sales)"
    )

    st.plotly_chart(fig, width="stretch")

















