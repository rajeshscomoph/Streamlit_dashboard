import streamlit as st
from common.Chart_builder import builder
from common.helper import metric_card, inject_global_dataframe_css
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
    "cutoff_uva": ["cutoffuva"],
    "refer_to_optho": ["refer_to_optho"],
    "refraction_attend": ["refractionattend"],
    "refraction_type": ["refractiontype"],
    "spec_pres": ["specpres"],
    "myopia_p": ["myopiap"],
    "myopia_cat_p": ["myopiacatp"],
    "ref_eye_spec": ["ref_eye_spec"],
    "refer_reason": ["referreason"],
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
    title="📊 School Screening Program",
    data_path=DATA_PATH,
    df=f,
    active_filters=selected_filters,
    show_filters_heading=True,
)

# -------------------- Key Metrics --------------------
st.subheader("📌 Key Metrics")

school_col = next((c for c in [RES.get("school_name"), RES.get("school"), RES.get("schoolcode")] if c in f.columns), None)
n_schools = f[school_col].dropna().nunique() if school_col else 0

att_col = RES.get("screen_attend")
ref_col = RES.get("ref_eye_spec")

if att_col in f.columns:
    sa = f[att_col].astype(str).str.strip().str.lower()
    n_screened = (sa != "").sum()
    mask_present = sa.eq("present")
    mask_absent = sa.eq("absent")
    n_present = mask_present.sum()
    n_absent = mask_absent.sum()

    referred = f.loc[mask_present, ref_col].astype(str).str.strip().str.lower().isin({"yes", "y", "1", "true"}).sum() if ref_col in f.columns else 0

    def pct(a, b): return (a / max(b, 1)) * 100.0

    c1, c2, c3, c4, c5 = st.columns(5)
    metric_card("Schools Covered", f"{n_schools:,}", icon="🏫", color="#6366f1", container=c1)
    metric_card("Total Children Screened", f"{n_screened:,}", icon="🩺", color="#22c55e", container=c2)
    metric_card("Children Examined", f"{n_present:,} ({pct(n_present, n_screened):.1f}%)", icon="✅", color="#0ea5e9", container=c3)
    metric_card("Absent", f"{n_absent:,} ({pct(n_absent, n_screened):.1f}%)", icon="🚫", color="#ef4444", container=c4)
    metric_card("Referred", f"{referred:,} ({pct(referred, n_present):.1f}%)", icon="➡️", color="#14b8a6", container=c5)

    attended = f.loc[mask_present]
else:
    st.info("Column 'screen_attend' not found.")
    attended = f.iloc[0:0]

# -------------------- Demographics --------------------
st.markdown("---")
st.subheader("👨‍👩‍👧 Demographics Screening")
if not attended.empty:
    cols = st.columns(4)
    render_many([
        dict(container=cols[0], col=RES.get("sex"), title="Gender Distribution", chart_func=builder.pie, drop_values={"", "nan"}),
        dict(container=cols[1], col=RES.get("age1"), title="Age Distribution", chart_func=builder.pie, drop_values={"", "nan"}),
        dict(container=cols[2], col=RES.get("wearspec"), title="Wearing Glasses or Contact Lens", chart_func=builder.pie, drop_values={"", "nan"}),
        dict(container=cols[3], col=RES.get("refer_to_optho"), title="Referral to Optometrist", chart_func=builder.pie, drop_values={"", "nan"}),
    ], f, attended)
else:
    st.info("No data to display with the current filters.")

# -------------------- Clinical --------------------
st.markdown("---")
st.subheader("🧑‍⚕️ Clinical Screening")
if not attended.empty:
    c = st.columns(3)
    render_many([
        dict(container=c[0], col=RES.get("refraction_attend"), title="Refraction Attendance", chart_func=builder.pie, drop_values={"", "nan", "not screened"}),
        dict(container=c[1], col=RES.get("refraction_type"), title="Refraction Type", chart_func=builder.bar, kind="bar", drop_values={"", "nan"}, bar_with_labels=True),
        dict(container=c[2], col=RES.get("spec_pres"), title="Spectacle Prescription", chart_func=builder.pie, drop_values={"", "nan"}),
    ], f, attended)
else:
    st.info("No data to display with the current filters.")

# -------------------- Myopia --------------------
st.markdown("---")
st.subheader("👁️ Myopia & Referred to Eye Specialist")
if not attended.empty:
    m_cols = st.columns(3)
    render_many([
        dict(container=m_cols[0], col=RES.get("myopia_p"), title="Myopia Presence", chart_func=builder.pie, drop_values={"", "nan"}),
        dict(container=m_cols[1], col=RES.get("myopia_cat_p"), title="Myopia Category", chart_func=builder.pie, drop_values={"", "nan"}),
        dict(container=m_cols[2], col=RES.get("ref_eye_spec"), title="Referred to Eye Specialist", chart_func=builder.pie, drop_values={"", "nan"}),
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
    "<div class='caption'>✨ Note: Use the <b>Clear</b> button in the sidebar to reset filters.</div>",
    unsafe_allow_html=True,
)
