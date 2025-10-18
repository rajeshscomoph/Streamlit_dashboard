import streamlit as st
import pandas as pd
from common.Chart_builder import builder
from common.helper import is_done, metric_card, inject_global_dataframe_css, render_metric_cards
from common.render import render_many
from common import config
from common.dynamic_sidebar import dynamic_sidebar_filters

# Page setup
config.setup_page(page_title="📊 Cataract Management", page_key="cataract_management")
inject_global_dataframe_css()
DATA_PATH, SHEET = config.get_data_path("CataractData.xlsx", sheet=0)

# Column registry
CANDIDATES = {
    "date": ["Date", "date"],
    "pec": ["pec", "PEC"],
    "cluster": ["ClusterCode", "clustercode", "cluster"],
    "cataractsx": ["CataractSx", "cataractsx"],
    "followdone": ["followdone", "FollowDone"],
    "bcvaf618": ["bcvaf618"],
    "sex": ["sex"],
    "surgery_tech": ["sxTech","sxtech"],
    "iol": ["iol"],
    "bilateral": ["bilateral"],
}
df, RES = config.load_df_or_stop(DATA_PATH, SHEET, candidates=CANDIDATES, date_key="date")

# Sidebar filters
filters = [
    {"col": "date", "label": "📅 Date", "type": "date"},
    {"col": "pec", "label": "🏥 Team", "type": "multiselect"},
    {"col": "cluster", "label": "🧩 Vision Centre", "type": "multiselect"},
    {"col": "sex", "label": "Sex", "type": "multiselect"},
]
f, selected_filters = dynamic_sidebar_filters(df, RES, filters)
if f.empty:
    st.warning("No data available with current filters.")
    st.stop()

# Header
config.render_page_header(
    title="📊 Cataract Management",
    data_path=DATA_PATH,
    df=f,
    active_filters=selected_filters,
    show_filters_heading=True,
)

def count_done(col):
    return f[col].apply(is_done).sum() if col in f.columns else 0

def mf_table(col_name: str) -> pd.DataFrame:
    cluster, sex = RES.get("cluster"), RES.get("sex")
    if col_name not in f.columns or not cluster or not sex or cluster not in f.columns or sex not in f.columns:
        return pd.DataFrame()
    d = f.copy()
    d[cluster] = d[cluster].fillna("Unknown").astype(str).str.strip()
    d[sex] = d[sex].fillna("Unknown").astype(str).str.strip()
    d = d[d[col_name].apply(is_done)]
    if d.empty: return pd.DataFrame()
    t = pd.crosstab(d[cluster], d[sex])
    t["Total"] = t.sum(axis=1)
    for s in t.columns[:-1]:
        t[s] = t[s].astype(str) + " (" + (t[s] / t["Total"] * 100).round(1).astype(str) + "%)"
    return t.reset_index().rename(columns={cluster: "Vision Centre"})

metrics = {
    "🩺 Surgery Done": ("cataractsx", None),
    "🕶️ Bilateral Blind Operated": ("bilateral", "cataractsx"),
    "🔁 Follow-up Done": ("followdone", "cataractsx"),
    "👁️ Visual Acuity in Operated Eye ≥ 6/18": ("bcvaf618", "followdone"),
}

st.markdown("---")
st.subheader("📌 Key Metrics")
render_metric_cards(metrics, df=f, res=RES)  # optional: columns=st.columns(len(metrics))


# Monthly Surgery Trend (vbar via render_many)
st.markdown("---")
st.subheader("📊 Monthly Surgery Trend")

def _monthly_surgery_counts(df_all: pd.DataFrame, df_present: pd.DataFrame, date_col: str):
    sx_col = RES.get("cataractsx")
    if df_present.empty or not date_col or date_col not in df_present.columns or not sx_col or sx_col not in df_present.columns:
        return pd.Series(dtype="int64")
    d = df_present[df_present[sx_col].apply(is_done)].copy()
    if d.empty:
        return pd.Series(dtype="int64")
    m = pd.to_datetime(d[date_col], errors="coerce").dt.to_period("M")
    grp = m.value_counts().sort_index()
    grp.index = grp.index.astype(str)  # 'YYYY-MM'
    return grp

trend_col = st.columns(1)[0]
render_many([{
    "container": trend_col,
    "col": RES.get("date"),
    "title": "Monthly Surgery Trend",
    "chart_func": builder.vbar,
    "kind": "vbar",
    "bar_with_labels": True,
    "custom_counts": _monthly_surgery_counts,
    "warn_text": "No monthly surgery data.",
    "info_text": "Surgery trend unavailable (missing date or surgery columns).",
}], df_all=f, df_present=f)

# Surgery Technique & IOL
st.markdown("---")
st.subheader("📋 Surgery Technique & IOL Distribution")

c1, c2 = st.columns(2)
render_many([
    {"container": c1, "col": RES.get("surgery_tech"), "title": "Surgery Technique Distribution",
     "chart_func": builder.pie, "drop_values": {"", "nan", "none", None, " "}},
    {"container": c2, "col": RES.get("iol"), "title": "IOL Distribution",
     "chart_func": builder.pie, "drop_values": {"", "nan", "none", None, " "}},
], f, f)

# Tables
c1, c2 = st.columns(2)
surgery_df = mf_table("cataractsx")
follow_df = mf_table("followdone")

with c1:
    st.markdown("### 🛠️ Surgeries Done (M/F)")
    st.dataframe(
        surgery_df if not surgery_df.empty else pd.DataFrame({"Info": ["No surgery data found"]}),
        use_container_width=True, hide_index=True
    )

with c2:
    st.markdown("### 🔁 Follow-up Done (M/F)")
    st.dataframe(
        follow_df if not follow_df.empty else pd.DataFrame({"Info": ["No follow-up data found"]}),
        use_container_width=True, hide_index=True
    )

# Footer
st.markdown(
    "<div class='caption'>✨ Use the <b>Clear</b> button in the sidebar to reset filters.</div>",
    unsafe_allow_html=True
)
