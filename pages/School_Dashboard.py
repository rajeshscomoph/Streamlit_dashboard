import streamlit as st

from common.Chart_builder import builder
from common.helper import metric_card,inject_global_dataframe_css
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

# -------------------- Load + Resolve (via common.config) --------------------
df, RES = config.load_df_or_stop(DATA_PATH, SHEET, candidates=CANDIDATES, date_key="date")

# -------------------- Dynamic Sidebar --------------------
filter_order = [
    {"col": "date", "label": "📅 Date", "type": "date"},
    {"col": "school_type", "label": "🏫 School Type", "type": "multiselect"},
    {"col": "school_name", "label": "🏫 School Name", "type": "multiselect"},
    {"col": "sex", "label": "👦👧 Sex", "type": "multiselect"},
]
f, selected_filters = dynamic_sidebar_filters(df, RES, filter_order)

# -------------------- Header & Active Filters --------------------
config.render_page_header(
    title="📊 School Screening Program",
    data_path=DATA_PATH,
    df=f,
    active_filters=selected_filters,
    show_filters_heading=True,
)

# -------------------- Metrics --------------------
st.subheader("📌 Key Metrics")

# --- find a plausible school column (first match wins)
_school_candidates = [
    RES.get("school"),
    RES.get("school_name"),
    RES.get("schoolcode"),
    "school", "school_name", "schoolname", "sch_name",
    "school_code", "schoolcode", "school_id", "schoolid",
    "name_of_school",
]
school_col = next((c for c in _school_candidates if c in f.columns), None)

# unique schools in current filter (ignore blanks/na)
n_schools = 0
if school_col:
    schools_series = f[school_col].astype("string").str.strip()
    n_schools = int(schools_series.replace({"": None, "nan": None}).dropna().nunique())

attended = f.iloc[0:0]  # default empty

att_col = RES.get("screen_attend")
ref_col = RES.get("ref_eye_spec")

if att_col in f.columns:
    norm = lambda s: s.astype("string").fillna("").str.strip().str.lower()
    pct  = lambda a, b: (a / max(b, 1)) * 100.0

    sa = norm(f[att_col])

    n_screened   = int((sa != "").sum())
    mask_present = sa.eq("present")
    mask_absent  = sa.eq("absent")

    n_present = int(mask_present.sum())
    n_absent  = int(mask_absent.sum())

    referred = 0
    if ref_col in f.columns and n_present > 0:
        referred = int(
            norm(f.loc[mask_present, ref_col]).isin({"yes", "y", "1", "true"}).sum()
        )

    # 5 cards now (added Schools Covered)
    c1, c2, c3, c4, c5 = st.columns(5)
    metric_card("Schools Covered",         f"{n_schools:,}",                           icon="🏫", color="#6366f1", container=c1)
    metric_card("Total Children Screened",    f"{n_screened:,}",                          icon="🩺", color="#22c55e", container=c2)
    metric_card("Children Examined",          f"{n_present:,} ({pct(n_present, n_screened):.1f}%)", icon="✅", color="#0ea5e9", container=c3)
    metric_card("Absent",                     f"{n_absent:,} ({pct(n_absent, n_screened):.1f}%)",  icon="🚫", color="#ef4444", container=c4)
    metric_card("Referred", f"{referred:,} ({pct(referred, n_present):.1f}%)",   icon="➡️", color="#14b8a6", container=c5)

    attended = f.loc[mask_present].copy()
else:
    st.info("Column 'screen_attend' not found.")


# -------------------- Demographics --------------------
st.markdown("---")
st.subheader("👨‍👩‍👧 Demographics Screening")
if not attended.empty:
    d1, d2, d3, d4, d5 = st.columns(5)
    render_many(
        [
            dict(container=d1, col=RES.get("sex"),            title="Gender Distribution",                   chart_func=builder.pie, drop_values={"", "nan"}),
            dict(container=d2, col=RES.get("age1"),           title="Age Distribution",                      chart_func=builder.pie, drop_values={"", "nan"}),
            dict(container=d3, col=RES.get("wearspec"),       title="Wearing Glasses or Contact Lens",       chart_func=builder.pie, drop_values={"", "nan"}),
            dict(container=d4, col=RES.get("cutoff_uva"),     title="Cut-off Vision",                        chart_func=builder.pie, drop_values={"", "nan"}),
            dict(container=d5, col=RES.get("refer_to_optho"), title="Referral to Optometrist",               chart_func=builder.pie, drop_values={"", "nan"}),
        ],
        f,
        attended,
    )
else:
    st.info("No data to display with the current filters.")

# -------------------- Clinical --------------------
st.markdown("---")
st.subheader("🧑‍⚕️ Clinical Screening")
if not attended.empty:
    c1, c2, c3 = st.columns(3)
    render_many(
        [
            dict(container=c1, col=RES.get("refraction_attend"), title="Refraction Attendance", chart_func=builder.pie, drop_values={"", "nan", "not screened"}),
            dict(container=c2, col=RES.get("refraction_type"),   title="Refraction Type",       chart_func=builder.bar, kind="bar", drop_values={"", "nan"}, bar_with_labels=True),
            dict(container=c3, col=RES.get("spec_pres"),         title="Spectacle Prescription",chart_func=builder.pie, drop_values={"", "nan"}),
        ],
        f,
        attended,
    )
else:
    st.info("No data to display with the current filters.")

# -------------------- Myopia --------------------
st.markdown("---")
st.subheader("👁️ Myopia & Referred to eye specialist")
m1, m2, m3 = st.columns(3)
render_many(
    [
        dict(container=m1, col=RES.get("myopia_p"),     title="Myopia Presence",            chart_func=builder.pie, drop_values={"", "nan"}),
        dict(container=m2, col=RES.get("myopia_cat_p"), title="Myopia Category",            chart_func=builder.pie, drop_values={"", "nan"}),
        dict(container=m3, col=RES.get("ref_eye_spec"), title="Referred to eye specialist", chart_func=builder.pie, drop_values={"", "nan"}),
    ],
    f,
    attended,
)

# -------------------- Referral --------------------
st.markdown("---")
st.subheader("📑 Referral Reasons")
(b1,) = st.columns(1)
render_many(
    [dict(container=b1, col=RES.get("refer_reason"), title="", chart_func=builder.bar, kind="bar", bar_with_labels=True, drop_values={"", "nan"})],
    f,
    attended,
)

# -------------------- Footer --------------------
st.markdown(
    "<div class='caption'>✨ Note: Use the <b>Clear</b> button in the sidebar to reset filters.</div>",
    unsafe_allow_html=True,
)
