# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO

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
# CARGA DE DATOS
# ----------------------------

def read_csv_from_sharepoint(url, usecols=None):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,application/octet-stream,*/*",
    }
    r = requests.get(url, headers=headers, allow_redirects=True, timeout=180)
    r.raise_for_status()
    return pd.read_csv(
        BytesIO(r.content),
        low_memory=False,
        usecols=usecols,
        dtype_backend="pyarrow"  # 👈 reduce RAM
    )
@st.cache_data
def load_data():
    # 👉 Si ya lo tienes cargado en tu notebook/script, puedes ignorar esto y asignar df directamente.
    url_1 = "https://upcomillas-my.sharepoint.com/:x:/g/personal/202408980_alu_comillas_edu/IQC_RUnSNtBtSoLag-Jbmd2WAVN5uSQZHRk6AYVXyWlkPiM?download=1"
    url_2 = "https://upcomillas-my.sharepoint.com/:x:/g/personal/202408980_alu_comillas_edu/IQCyEV6FfDZ2S4JM0exAF6GfAXHjciOC5aZ-wFoZzAhaEbw?download=1"
    df1 = read_csv_from_sharepoint(url_1)
    df2 = read_csv_from_sharepoint(url_2)

    df = pd.concat([df1, df2], ignore_index=True)
    df["holiday_type"] = df["holiday_type"].astype(str)
    return df

df = load_data()

# Si tú ya tienes df cargado, puedes comentar lo de arriba y hacer:
# df = TU_DATAFRAME

if df.empty:
    st.warning("⚠️ Tu DataFrame está vacío en este script. Reemplaza load_data() por tu carga real o asigna df.")
    st.stop()

# Asegurar tipos esperados
if "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

# ----------------------------
# SIDEBAR (filtros globales opcionales)
# ----------------------------
with st.sidebar:
    st.header("Filtros globales")
    years = sorted(df["year"].dropna().unique()) if "year" in df.columns else []
    selected_years = st.multiselect("Años", years, default=years)

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
    store_sel = st.selectbox("Selecciona una tienda", stores, index=0)

    df_store = df_f[df_f["store_nbr"] == store_sel].copy()

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
    state_sel = st.selectbox("Selecciona un estado", states, index=0)

    df_state = df_f[df_f["state"] == state_sel].copy()

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
    df_f["promo_flag"] = (df_f["onpromotion"].fillna(0) > 0).map({True: "En promoción", False: "Sin promoción"})
    promo_compare = (
    df_f.assign(
        promo_flag=df_f["onpromotion"].fillna(0).gt(0)
            .map({True: "En promoción", False: "Sin promoción"})
    )
    .groupby("promo_flag", as_index=False)["sales"]
    .sum()
)

    fig = px.bar(
        promo_compare,
        x="promo_flag",
        y="sales",
        title="Impacto de promociones: ventas con vs sin promoción",
        text_auto=".2s"
    )

    fig.update_layout(
        xaxis_title="Tipo de venta",
        yaxis_title="Unidades vendidas",
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

    # 1) Creamos bandera festivo / no festivo
    tmp = df_f.copy()
    tmp["is_holiday"] = tmp["holiday_type"].fillna("No holiday").ne("No holiday")

    holiday_summary = (
        tmp.groupby("is_holiday", as_index=False)["sales"]
        .mean()
        .replace({"is_holiday": {True: "Festivo", False: "No festivo"}})
    )

    # 2) Gráfico
    fig = px.bar(
        holiday_summary,
        x="is_holiday",
        y="sales",
        title="Ventas medias diarias: festivo vs no festivo",
        text_auto=".2s"
    )

    fig.update_layout(
        xaxis_title="Tipo de día",
        yaxis_title="Media diaria (sales)"
    )

    st.plotly_chart(fig, width="stretch")



