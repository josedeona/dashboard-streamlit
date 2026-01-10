# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO
import traceback

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
# CARGA + NORMALIZACIÓN (CACHE)
# ----------------------------
@st.cache_data(ttl=24*3600, show_spinner=True)
def load_data():
    url_parquet = "https://upcomillas-my.sharepoint.com/:u:/g/personal/202408980_alu_comillas_edu/IQCa_6_CXHL6TKZs8lSa6SwWAeCY5dTnHOWTpQ7gAoQ_GCM?download=1"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}

    r = requests.get(url_parquet, headers=headers, allow_redirects=True, timeout=300)
    r.raise_for_status()

    # SharePoint a veces devuelve HTML (login/redirect)
    if r.content[:1] == b"<":
        raise ValueError("SharePoint devolvió HTML (redirect/login), no un parquet.")

    df = pd.read_parquet(BytesIO(r.content))

    # Numéricos (reduce RAM)
    for col in ["sales", "onpromotion", "transactions"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32").fillna(0)

    # Fechas
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Temporales
    for col in ["year", "month", "week", "day_of_week"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int16")

    # store_nbr
    if "store_nbr" in df.columns:
        df["store_nbr"] = pd.to_numeric(df["store_nbr"], errors="coerce").astype("Int16")

    # Categóricas que suelen ir bien como category
    for col in ["state", "family"]:
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("NA").astype("category")

    # holiday_type: mejor string (evita líos de categorías nuevas en fillna)
    if "holiday_type" in df.columns:
        df["holiday_type"] = df["holiday_type"].astype("string")

    return df


try:
    df = load_data()
except Exception:
    st.error("❌ Error cargando datos (evitamos crash).")
    st.code(traceback.format_exc())
    st.stop()

if df.empty:
    st.error("⚠️ El DataFrame está vacío tras cargar el parquet.")
    st.stop()


# ----------------------------
# SIDEBAR (filtros globales + navegación)
# ----------------------------
with st.sidebar:
    st.header("Navegación")
    page = st.radio(
        "Sección",
        ["1) Global", "2) Por tienda", "3) Por estado", "4) Insights extra ⭐"],
        index=0
    )

    st.divider()
    st.header("Filtros globales")

    years = sorted(df["year"].dropna().astype(int).unique().tolist()) if "year" in df.columns else []
    selected_years = st.multiselect("Años", years, default=years, key="years_sel")

    if selected_years and "year" in df.columns:
        # NO copy gigante: solo vista filtrada
        df_f = df.loc[df["year"].isin(selected_years)]
    else:
        df_f = df

    st.divider()
    st.caption(f"Filas con filtros: {len(df_f):,}")


# ============================================================
# 1) GLOBAL
# ============================================================
if page == "1) Global":
    st.subheader("Visión global del periodo")

    c1, c2, c3, c4 = st.columns(4)
    total_stores = int(df_f["store_nbr"].nunique()) if "store_nbr" in df_f.columns else 0
    total_products = int(df_f["family"].nunique()) if "family" in df_f.columns else 0
    total_states = int(df_f["state"].nunique()) if "state" in df_f.columns else 0
    total_months = df_f[["year", "month"]].dropna().drop_duplicates().shape[0] if {"year", "month"}.issubset(df_f.columns) else 0

    c1.metric("🏪 Tiendas", f"{total_stores:,}")
    c2.metric("🧺 Productos (families)", f"{total_products:,}")
    c3.metric("🗺️ Estados", f"{total_states:,}")
    c4.metric("🗓️ Meses con datos", f"{total_months:,}")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### 🔝 Top 10 productos más vendidos (ventas totales)")
        if {"family", "sales"}.issubset(df_f.columns) and len(df_f):
            top_products = (
                df_f.groupby("family", as_index=False)["sales"]
                .sum()
                .sort_values("sales", ascending=False)
                .head(10)
            )
            if top_products.empty:
                st.info("No hay datos para el ranking.")
            else:
                fig = px.bar(top_products, x="sales", y="family", orientation="h", text_auto=".2s")
                fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("Faltan columnas 'family' y/o 'sales'.")

    with col_right:
        st.markdown("#### 🏪 Distribución de ventas por tienda")
        if {"store_nbr", "sales"}.issubset(df_f.columns) and len(df_f):
            store_sales = (
                df_f.groupby("store_nbr", as_index=False)["sales"]
                .sum()
                .sort_values("sales", ascending=False)
            )
            if store_sales.empty:
                st.info("No hay datos para la distribución.")
            else:
                fig = px.box(store_sales, y="sales", title="Distribución de ventas por tienda")
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("Faltan columnas 'store_nbr' y/o 'sales'.")

    st.markdown("#### 🔝 Top 10 tiendas con ventas en productos en promoción")
    if {"store_nbr", "sales", "onpromotion"}.issubset(df_f.columns) and len(df_f):
        promo_df = df_f[df_f["onpromotion"].fillna(0) > 0]
        top_promo_stores = (
            promo_df.groupby("store_nbr", as_index=False)["sales"]
            .sum()
            .sort_values("sales", ascending=False)
            .head(10)
        )
        if top_promo_stores.empty:
            st.info("No hay ventas en promoción con los filtros actuales.")
        else:
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
    else:
        st.info("Faltan columnas para el análisis de promoción.")

    st.divider()

    cA, cB, cC = st.columns(3)

    with cA:
        st.markdown("#### 📅 Día de la semana con más ventas medias")
        if {"day_of_week", "sales"}.issubset(df_f.columns) and len(df_f):
            dow_mean = (
                df_f.groupby("day_of_week", as_index=False)["sales"]
                .mean()
                .sort_values("sales", ascending=False)
            )
            if dow_mean.empty:
                st.info("No hay datos.")
            else:
                fig = px.bar(dow_mean, x="day_of_week", y="sales", text_auto=".2s")
                fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("Faltan columnas 'day_of_week' y/o 'sales'.")

    with cB:
        st.markdown("#### 📆 Ventas medias por semana del año")
        if {"week", "sales"}.issubset(df_f.columns) and len(df_f):
            week_mean = (
                df_f.groupby("week", as_index=False)["sales"]
                .mean()
                .sort_values("week")
            )
            if week_mean.empty:
                st.info("No hay datos.")
            else:
                fig = px.line(week_mean, x="week", y="sales")
                fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("Faltan columnas 'week' y/o 'sales'.")

    with cC:
        st.markdown("#### 🗓️ Ventas medias por mes")
        if {"month", "sales"}.issubset(df_f.columns) and len(df_f):
            month_mean = (
                df_f.groupby("month", as_index=False)["sales"]
                .mean()
                .sort_values("month")
            )
            if month_mean.empty:
                st.info("No hay datos.")
            else:
                fig = px.line(month_mean, x="month", y="sales", markers=True)
                fig.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10))
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("Faltan columnas 'month' y/o 'sales'.")


# ============================================================
# 2) POR TIENDA
# ============================================================
elif page == "2) Por tienda":
    st.subheader("Análisis por tienda (store_nbr)")

    if df_f.empty or "store_nbr" not in df_f.columns:
        st.warning("No hay tiendas con los filtros actuales.")
    else:
        stores = sorted(df_f["store_nbr"].dropna().astype(int).unique().tolist())
        store_sel = st.selectbox("Selecciona una tienda", stores, key="store_sel")

        df_store = df_f[df_f["store_nbr"] == int(store_sel)]
        if df_store.empty:
            st.info("Esta tienda no tiene datos con los filtros actuales.")
        else:
            a, b, c = st.columns(3)
            a.metric("💰 Ventas totales", f"{df_store['sales'].sum():,.2f}" if "sales" in df_store.columns else "—")
            b.metric("🧾 Transacciones totales", f"{df_store['transactions'].sum():,.0f}" if "transactions" in df_store.columns else "—")
            c.metric("🏷️ Días con promoción", f"{(df_store['onpromotion'].fillna(0) > 0).sum():,}" if "onpromotion" in df_store.columns else "—")

            st.divider()
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Ventas totales por año")
                if {"year", "sales"}.issubset(df_store.columns):
                    by_year = (
                        df_store.dropna(subset=["year"])
                        .groupby("year", as_index=False)["sales"]
                        .sum()
                        .sort_values("year")
                    )
                    if by_year.empty:
                        st.info("No hay datos suficientes para el gráfico.")
                    else:
                        fig = px.bar(by_year, x="year", y="sales", text_auto=".2s")
                        fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
                        st.plotly_chart(fig, width="stretch")
                else:
                    st.info("Faltan columnas 'year' y/o 'sales'.")

            with col2:
                prod_count = df_store["family"].nunique() if "family" in df_store.columns else 0
                prod_promo_count = (
                    df_store[df_store["onpromotion"].fillna(0) > 0]["family"].nunique()
                    if {"family", "onpromotion"}.issubset(df_store.columns)
                    else 0
                )
                st.metric("🧺 Productos distintos vendidos", f"{prod_count:,}")
                st.metric("🏷️ Productos distintos vendidos en promoción", f"{prod_promo_count:,}")


# ============================================================
# 3) POR ESTADO
# ============================================================
elif page == "3) Por estado":
    st.subheader("Análisis por estado (state)")

    if df_f.empty or "state" not in df_f.columns:
        st.warning("No hay estados con los filtros actuales.")
    else:
        states = sorted([s for s in df_f["state"].astype(str).unique().tolist() if s and s.lower() != "nan"])
        state_sel = st.selectbox("Selecciona un estado", states, key="state_sel")

        df_state = df_f[df_f["state"].astype(str) == str(state_sel)]
        if df_state.empty:
            st.info("Este estado no tiene datos con los filtros actuales.")
        else:
            st.divider()
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Nº total de transacciones por año")
                if {"transactions", "year"}.issubset(df_state.columns):
                    tx_year = (
                        df_state.dropna(subset=["year"])
                        .groupby("year", as_index=False)["transactions"]
                        .sum()
                        .sort_values("year")
                    )
                    if tx_year.empty:
                        st.info("No hay datos suficientes para el gráfico.")
                    else:
                        fig = px.bar(tx_year, x="year", y="transactions", text_auto=".2s")
                        fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
                        st.plotly_chart(fig, width="stretch")
                else:
                    st.info("No existe 'transactions' y/o 'year'.")

            with col2:
                st.markdown("#### Ranking de tiendas con más ventas (en este estado)")
                if {"store_nbr", "sales"}.issubset(df_state.columns):
                    n_stores = int(df_state["store_nbr"].nunique())
                    st.caption(f"Este estado tiene {n_stores} tienda(s) en el dataset.")

                    rank_stores = (
                        df_state.groupby("store_nbr", as_index=False)["sales"]
                        .sum()
                        .sort_values("sales", ascending=True)
                    )

                    if rank_stores.empty:
                        st.info("No hay datos suficientes para el ranking.")
                    else:
                        rank_stores["store_cat"] = rank_stores["store_nbr"].astype(int).astype(str)
                        fig = px.bar(rank_stores, x="sales", y="store_cat", orientation="h", text_auto=".2s")
                        fig.update_yaxes(type="category", title="Tienda")
                        fig.update_xaxes(title="Ventas")
                        st.plotly_chart(fig, width="stretch")
                else:
                    st.info("Faltan columnas 'store_nbr' y/o 'sales'.")

            st.markdown("#### Producto más vendido (en este estado)")
            if {"family", "sales"}.issubset(df_state.columns):
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
            else:
                st.info("Faltan columnas 'family' y/o 'sales'.")


# ============================================================
# 4) INSIGHTS EXTRA
# ============================================================
else:
    st.subheader("Insights extra para decisiones rápidas ⭐")

    st.markdown("##### Impacto de promociones: ventas con promoción vs sin promoción")
    if {"sales", "onpromotion"}.issubset(df_f.columns) and len(df_f):
        tmp_promo = df_f[["sales", "onpromotion"]]
        tmp_promo = tmp_promo.assign(
            promo_flag=tmp_promo["onpromotion"].gt(0).map({True: "En promoción", False: "Sin promoción"})
        )
        promo_compare = tmp_promo.groupby("promo_flag", as_index=False)["sales"].sum()

        if promo_compare.empty:
            st.info("No hay datos para comparar.")
        else:
            fig = px.bar(promo_compare, x="promo_flag", y="sales", text_auto=".2s",
                         title="Impacto de promociones: ventas con vs sin promoción")
            st.plotly_chart(fig, width="stretch")
    else:
        st.info("Faltan columnas para el análisis de promociones.")

    st.divider()

    st.markdown("##### Top 10 productos: ¿qué % de ventas concentran?")
    if {"family", "sales"}.issubset(df_f.columns) and len(df_f):
        prod_all = df_f.groupby("family", as_index=False)["sales"].sum().sort_values("sales", ascending=False)
        top10_sum = float(prod_all.head(10)["sales"].sum())
        total_sum = float(prod_all["sales"].sum())
        share = (top10_sum / total_sum) * 100 if total_sum else 0

        c1, c2 = st.columns(2)
        c1.metric("Ventas Top 10 productos", f"{top10_sum:,.2f}")
        c2.metric("% sobre ventas totales", f"{share:,.2f}%")
    else:
        st.info("Faltan columnas para el análisis de top productos.")

    st.divider()

    st.markdown("### 📅 Impacto de festivos en ventas")
    if {"sales", "holiday_type"}.issubset(df_f.columns) and len(df_f):
        tmp_holiday = df_f[["sales", "holiday_type"]].copy()
        tmp_holiday["holiday_type"] = tmp_holiday["holiday_type"].astype("string").fillna("No festivo")

        tmp_holiday["tipo_dia"] = tmp_holiday["holiday_type"].apply(
            lambda x: "Festivo" if str(x).lower() not in ["no holiday", "no festivo", "none", "na"] else "No festivo"
        )

        holiday_summary = tmp_holiday.groupby("tipo_dia", as_index=False)["sales"].mean()

        if holiday_summary.empty:
            st.info("No hay datos para comparar festivos.")
        else:
            fig = px.bar(
                holiday_summary,
                x="tipo_dia",
                y="sales",
                title="Ventas medias diarias: festivo vs no festivo",
                text_auto=".2s"
            )
            st.plotly_chart(fig, width="stretch")
    else:
        st.info("Faltan columnas para el análisis de festivos.")






