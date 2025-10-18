import streamlit as st
from common.Chart_builder import builder
from common.helper import inject_global_dataframe_css, render_metric_cards
from common.render import render_many
from common import config
from common.dynamic_sidebar import dynamic_sidebar_filters

# -------------------- Page Setup --------------------
config.setup_page(page_title="📊 School Program", page_key="school_program")
inject_global_dataframe_css()

# -------------------- Data Config --------------------
DATA_PATH, SHEET = config.get_data_path("School_Program.xlsx", sheet=0)

# -------------------- Column Registry --------------------
CANDIDATES = {
    "date": ["screendate", "date"],
    "school_type": ["schooltype"],
    "school_name": ["schoolcode", "school name", "school"],
    "screen_attend": ["screenattend", "screenattended"],
    "sex": ["sex"],
    "age1": ["age1"],
    "wearspec": ["wearspec"],
    "refer_to_optho": ["refer_to_optho"],
    "refraction_attend": ["refractionattend"],
    "refraction_type": ["refractiontype"],
    "spec_pres": ["specpres"],
    "myopia_p": ["myopiap"],
    "myopia_cat_p": ["myopiacatp"],
    "ref_eye_spec": ["ref_eye_spec"],
    "refer_reason": ["referreason"],
    "examined": ["examined"],
    "absent": ["absent"],
}

# -------------------- Load Data --------------------
df, RES = config.load_df_or_stop(DATA_PATH, SHEET, candidates=CANDIDATES, date_key="date")

# -------------------- Filters --------------------
filter_order = [
    {"col": "date", "label": "📅 Date", "type": "date"},
    {"col": "school_type", "label": "🏫 School Type", "type": "multiselect"},
    {"col": "school_name", "label": "🏫 School Name", "type": "multiselect"},
    {"col": "sex", "label": "👦👧 Sex", "type": "multiselect"},
]
f, selected_filters = dynamic_sidebar_filters(df, RES, filter_order)

# -------------------- Header --------------------
config.render_page_header(
    title="📊 School Screening Program", data_path=DATA_PATH, df=f, active_filters=selected_filters, show_filters_heading=True,
)

# -------------------- Metric Card with Subcaption --------------------
def metric_card_with_subcaption(
    title: str,
    value: str,
    subcaption: str,
    icon: str = "🏫",
    color: str = "#2563eb",
    container=None,
):
    """Render metric card visually matching metric_card(), with a subcaption line and blue accent."""
    target = container if container is not None else st
    html = f"""
<div style="
    border:1px solid rgba(2,6,23,0.08);
    border-radius:14px;
    padding:12px 14px;
    background:#fff;
    box-shadow:0 1px 1.5px rgba(2,6,23,.06),0 8px 18px rgba(2,6,23,.04);
">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <span style="font-size:1.05rem;color:{color};">{icon}</span>
    <span style="font-weight:700;color:#334155;">{title}</span>
  </div>
  <div style="font-size:1.25rem;font-weight:800;color:{color};">{value}</div>
  <div style="margin-top:4px;font-size:.9rem;color:#64748b;">{subcaption}</div>
</div>
"""
    target.markdown(html, unsafe_allow_html=True)


# -------------------- Key Metrics --------------------
st.markdown("---")
st.subheader("📌 Key Metrics")

school_col = next((c for c in [RES.get("school_name"), RES.get("schoolcode")] if c in f.columns), None)
stype_col = RES.get("school_type")
n_schools = f[school_col].dropna().nunique() if school_col else 0

type_breakdown = "—"
if school_col and stype_col and stype_col in f.columns:
    tmp = (
        f.dropna(subset=[stype_col, school_col])
         .astype({stype_col: str, school_col: str})
         .drop_duplicates(subset=[stype_col, school_col])
         .groupby(stype_col)[school_col]
         .nunique()
         .sort_values(ascending=False)
    )
    if not tmp.empty:
        type_breakdown = " | ".join([f"{k}: {v}" for k, v in tmp.items()])

metrics = {
    "🩺 Total Children Screened": ("screendate", None),
    "✅ Children Examined":       ("examined", "screendate"),
    "🚫 Absent":                  ("absent",   "screendate"),
    "➡️ Referred":                ("ref_eye_spec", "examined"),
}

cols = st.columns(1 + len(metrics))

# Schools covered card
metric_card_with_subcaption(
    title="Schools Covered",
    value=f"{n_schools:,}",
    subcaption=type_breakdown,
    icon="🏫",
    color="#2563eb",
    container=cols[0],
)

# Other metrics
render_metric_cards(metrics, df=f, res=RES, columns=cols[1:])

# -------------------- Attendance Filter --------------------
att_col = RES.get("screen_attend")
mask_present = f[att_col].astype(str).str.strip().str.lower().eq("present") if att_col in f.columns else []
attended = f.loc[mask_present] if not f.empty else f

# -------------------- Demographics --------------------
st.markdown("---")
st.subheader("👨‍👩‍👧 Demographics Screening")
if not attended.empty:
    cols = st.columns(4)
    render_many([
        dict(container=cols[0], col=RES.get("sex"),              title="Gender Distribution",             chart_func=builder.pie, kind="pie"),
        dict(container=cols[1], col=RES.get("age1"),             title="Age Distribution",                chart_func=builder.pie, kind="pie"),
        dict(container=cols[2], col=RES.get("wearspec"),         title="Wearing Glasses or Contact Lens", chart_func=builder.pie, kind="pie"),
        dict(container=cols[3], col=RES.get("refer_to_optho"),   title="Referral to Optometrist",         chart_func=builder.pie, kind="pie"),
    ], f, attended)
else:
    st.info("No data to display with the current filters.")

# -------------------- Clinical --------------------
st.markdown("---")
st.subheader("🧑‍⚕️ Clinical Screening")
if not attended.empty:
    c = st.columns(3)
    render_many([
        dict(container=c[0], col=RES.get("refraction_attend"), title="Refraction Attendance", chart_func=builder.pie, kind="pie"),
        dict(container=c[1], col=RES.get("refraction_type"),   title="Refraction Type",       chart_func=builder.bar, kind="bar", bar_with_labels=True),
        dict(container=c[2], col=RES.get("spec_pres"),         title="Spectacle Prescription",chart_func=builder.pie, kind="pie"),
    ], f, attended)
else:
    st.info("No data to display with the current filters.")

# -------------------- Myopia --------------------
st.markdown("---")
st.subheader("👁️ Myopia & Eye Specialist Referrals")
if not attended.empty:
    m_cols = st.columns(3)
    render_many([
        dict(container=m_cols[0], col=RES.get("myopia_p"),      title="Myopia Presence",            chart_func=builder.pie, kind="pie"),
        dict(container=m_cols[1], col=RES.get("myopia_cat_p"),  title="Myopia Category",            chart_func=builder.pie, kind="pie"),
        dict(container=m_cols[2], col=RES.get("ref_eye_spec"),  title="Referred to Eye Specialist", chart_func=builder.pie, kind="pie"),
    ], f, attended)

# -------------------- Referral --------------------
st.markdown("---")
st.subheader("📑 Referral Reasons")
if not attended.empty:
    b1, = st.columns(1)
    render_many([
        dict(container=b1, col=RES.get("refer_reason"), title="Referral Reasons", chart_func=builder.bar, kind="bar", bar_with_labels=True, drop_values={"", "nan"})
    ], f, attended)


# -------------------- Footer --------------------
st.markdown(
    "<div class='caption'>✨ Use the <b>Clear</b> button in the sidebar to reset filters.</div>",
    unsafe_allow_html=True,
)
