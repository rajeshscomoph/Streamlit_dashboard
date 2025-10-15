import streamlit as st
import pandas as pd
from common.helper import metric_card, inject_global_dataframe_css
from common import config
from common.dynamic_sidebar import dynamic_sidebar_filters

# -------------------- Page Setup --------------------
config.setup_page(page_title="📊 Cataract Management", page_key="cataract_management")
inject_global_dataframe_css()
DATA_PATH, SHEET = config.get_data_path("CataractData.xlsx", sheet=0)

# -------------------- Column registry --------------------
CANDIDATES = {
    "date": ["Date", "date"],
    "pec": ["pec", "PEC"],
    "cluster": ["ClusterCode", "clustercode", "cluster"],
    "cataractsx": ["CataractSx", "cataractsx"],
    "followdone": ["followdone", "FollowDone"],
    "bcvaf618": ["bcvaf618"],
    "sex": ["sex"],
}
df, RES = config.load_df_or_stop(DATA_PATH, SHEET, candidates=CANDIDATES, date_key="date")

# -------------------- Sidebar Filters --------------------
filters = [
    {"col": "date", "label": "📅 Date", "type": "date"},
    {"col": "pec", "label": "🏥 Team", "type": "multiselect"},
    {"col": "cluster", "label": "🧩 Vision Centre", "type": "multiselect"},
    {"col": "sex", "label": "Sex", "type": "multiselect"}
]
f, selected_filters = dynamic_sidebar_filters(df, RES, filters)
if f.empty: st.warning("No data available with current filters."); st.stop()

# -------------------- Header --------------------
config.render_page_header(
    title="📊 Cataract Management",
    data_path=DATA_PATH,
    df=f,
    active_filters=selected_filters,
    show_filters_heading=True,
)

# -------------------- Helper Functions --------------------
def is_done(val):
    if pd.isna(val): return False
    if isinstance(val, (int, float)) and val == 1: return True
    if isinstance(val, bool) and val: return True
    return str(val).strip().lower() in ["yes", "y", "true", "1"]

def count_done(col): return f[col].apply(is_done).sum() if col in f.columns else 0

def mf_table(col_name):
    """Return M/F counts + row-wise percentages per Vision Centre"""
    cluster, sex = RES.get("cluster"), RES.get("sex")
    if col_name not in f.columns or not cluster or not sex or cluster not in f.columns or sex not in f.columns:
        return pd.DataFrame()
    df_tmp = f.copy()
    df_tmp[cluster] = df_tmp[cluster].astype(str).str.strip().replace("", "Unknown")
    df_tmp[sex] = df_tmp[sex].astype(str).str.strip().replace("", "Unknown")
    df_done = df_tmp[df_tmp[col_name].apply(is_done)]
    if df_done.empty: return pd.DataFrame()
    table = pd.crosstab(df_done[cluster], df_done[sex])
    table["Total"] = table.sum(axis=1)
    for s in table.columns[:-1]:
        table[s] = table[s].astype(str) + " (" + (table[s]/table["Total"]*100).round(1).astype(str) + "%)"
    return table.reset_index().rename(columns={cluster: "Vision Centre"})

# -------------------- Metrics --------------------
st.markdown("---")
st.subheader("📌 Key Metrics")

metrics = {
    "🩺 Surgery Done": ("cataractsx", None),
    "🔁 Follow-up Done": ("followdone", "cataractsx"),
    "👁️ BCVA ≥ 6/18": ("bcvaf618", "followdone")
}

cols = st.columns(3)
for col_block, (title, (col_name, base_col)) in zip(cols, metrics.items()):
    with col_block:
        val = count_done(col_name)
        if base_col:
            base = count_done(base_col)
            val = f"{val} ({(val/base*100 if base else 0):.1f}%)"
        metric_card(title, val)

# -------------------- Tables Side by Side --------------------
c1, c2 = st.columns(2)

with c1:
    st.markdown("### 🛠️ Surgeries Done (M/F)")
    st.dataframe(mf_table("cataractsx") if not mf_table("cataractsx").empty else pd.DataFrame({"Info": ["No surgery data found"]}), use_container_width=True, hide_index=True)

with c2:
    st.markdown("### 🔁 Follow-up Done (M/F)")
    st.dataframe(mf_table("followdone") if not mf_table("followdone").empty else pd.DataFrame({"Info": ["No follow-up data found"]}), use_container_width=True, hide_index=True)
# ========== Footer ==========
st.markdown("<div class='caption'>✨ Use the <b>Clear</b> button in the sidebar to reset filters.</div>", unsafe_allow_html=True)
