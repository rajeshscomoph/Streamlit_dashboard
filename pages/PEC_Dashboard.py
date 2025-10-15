import streamlit as st
import pandas as pd

from common.Chart_builder import builder
from common.helper import inject_global_dataframe_css
from common.render import render_many
from common import config
from common.dynamic_sidebar import dynamic_sidebar_filters

# ========== Setup ==========
config.setup_page(page_title="📊 Primary Eye Care", page_key="primary_eye_care")
inject_global_dataframe_css()
DATA_PATH, SHEET = config.get_data_path("PECdata.xlsx", sheet=0)

# ========== Column registry ==========
CANDIDATES = {
    "date": ["date"],
    "pec": ["pec"],                 # Team
    "cluster": ["clustercode"],     # Vision Centre
    "sex": ["sex"],
    "no": ["no", "n_o", "n/o"],
    "wear_glass": ["wearglass"],
    "diagnosis_code": ["diagnosiscode"],
    "referred": ["referred"],
    "clinic": ["clinic"],
    "vision": ["vision"],
    "hearing": ["hearing"],
    "walking": ["walking"],
    "remember": ["remember"],
    "selfcare": ["selfcare"],
    "communication": ["comcation", "communication"],
    "dry_pmt_dil": ["drypmtdil"],
    "spec_pres": ["specpres"],
    "spec_pres_type": ["specprestype"],
    "specbook": ["specbook"],       # Dispensed/Booked
    "specprice": ["specprice"],
    "agewisesexcat": ["agewisesexcat"],
    "ref_dig": ["ref_dig"],
    "betterpvacat" : ["betterpvacat"],
    "need" : ["need"],
}
df, RES = config.load_df_or_stop(DATA_PATH, SHEET, candidates=CANDIDATES, date_key="date")

# ========== Small helpers ==========
YES = {"y","yes","true","t","1","present","referred","done","given","issued","booked"}
UNIFORM_H = 260
TABLE_HEIGHT = 260

def col_ok(key: str):
    c = RES.get(key)
    return c if (c in df.columns) else None

sex_col = RES.get("sex")

def yes_like(s: pd.Series) -> pd.Series:
    if s is None: return pd.Series([], dtype=bool)
    return s.astype(str).str.strip().str.lower().isin(YES)

def normalize_sex(s: pd.Series) -> pd.Series:
    if s is None: return pd.Series([], dtype="string")
    z = s.astype("string").str.strip().str.lower().replace({
        "m":"male","male":"male","man":"male","boy":"male",
        "f":"female","female":"female","woman":"female","girl":"female",
    })
    return z.map({"male":"Male","female":"Female"})

def rm(charts, data):
    """Safe render_many: drops charts with missing/None col."""
    cleaned = [c for c in charts if c.get("col")]
    if cleaned: render_many(cleaned, data, data)

def card(container, title, main, sub, icon="ℹ️", color="#111827"):
    container.markdown(
        f"""
        <div style="border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;background:#fff">
          <div style="font-size:13px;color:#6b7280">{icon} {title}</div>
          <div style="font-size:22px;font-weight:700;color:{color}">{main}</div>
          <div style="margin-top:4px;font-size:13px;color:#374151">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def mf_table(df_in: pd.DataFrame, by: str, label: str, order=None, mask=None) -> pd.DataFrame:
    """Male/Female table for a category."""
    cols = [label, "Male", "Female", "Total"]
    if df_in.empty or not by or by not in df_in.columns or sex_col not in df_in.columns:
        return pd.DataFrame(columns=cols)
    d = (df_in.loc[mask] if mask is not None else df_in).copy()
    if d.empty: return pd.DataFrame(columns=cols)
    d["_sex"] = normalize_sex(d[sex_col]).dropna()
    if d["_sex"].empty:
        base = order or sorted(d[by].dropna().unique())
        return pd.DataFrame({label: base, "Male": 0, "Female": 0, "Total": 0})
    row_order = order or sorted(d[by].dropna().unique())
    ct = pd.crosstab(d[by], d["_sex"]).reindex(columns=["Male","Female"], fill_value=0)
    ct = ct.reindex(pd.Index(row_order, name=by), fill_value=0)
    ct["Total"] = ct.sum(axis=1)
    return ct.reset_index().rename(columns={by: label})

def add_row_pct_compact(df_tbl: pd.DataFrame, label_col: str) -> pd.DataFrame:
    """Overwrite Male/Female with 'count (row%)'. Keep Total numeric."""
    need = {label_col, "Male", "Female", "Total"}
    if df_tbl.empty or not need.issubset(df_tbl.columns):
        return df_tbl
    out = df_tbl.copy()
    denom = out["Total"].replace(0, pd.NA)
    male_pct   = (out["Male"]   / denom * 100).round(1).fillna(0)
    female_pct = (out["Female"] / denom * 100).round(1).fillna(0)
    male_cnt_str   = out["Male"].astype("Int64").map(lambda v: f"{v:,}" if pd.notna(v) else "0")
    female_cnt_str = out["Female"].astype("Int64").map(lambda v: f"{v:,}" if pd.notna(v) else "0")
    out["Male"]   = male_cnt_str   + " (" + male_pct.map(lambda x: f"{x:.1f}%") + ")"
    out["Female"] = female_cnt_str + " (" + female_pct.map(lambda x: f"{x:.1f}%") + ")"
    return out[[c for c in [label_col, "Male", "Female", "Total"] if c in out.columns]]

def clean_label_rows(df_tbl: pd.DataFrame, label_col: str) -> pd.DataFrame:
    """Drop blank/'nan'/'none' rows by label."""
    if df_tbl.empty or label_col not in df_tbl.columns:
        return df_tbl
    bad = df_tbl[label_col].astype(str).str.strip().str.lower().isin(("", "nan", "none"))
    return df_tbl.loc[~bad].copy()

def is_tail_label(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip().str.lower()
    return t.isin(("", "nan", "none", "other"))

# ========== Filters & Header ==========
F, selected = dynamic_sidebar_filters(
    df, RES,
    [
        {"col": "date", "label": "📅 Date", "type": "date"},
        {"col": "pec", "label": "🏥 Team", "type": "multiselect"},
        {"col": "cluster", "label": "🧩 Vision Centre", "type": "multiselect"},
        {"col": "sex", "label": "👦👧 Sex", "type": "multiselect"},
    ],
)
config.render_page_header(
    title="📊 Primary Eye Care Program",
    data_path=DATA_PATH,
    df=F,
    active_filters=selected,
    show_filters_heading=True,
)

# ========== Key Metrics ==========
st.markdown("---")
st.subheader("📌 Key Metrics")

N = len(F)
ref_c   = col_ok("referred")
pres_c  = col_ok("spec_pres")
book_c  = col_ok("specbook")

sex_norm = normalize_sex(F[sex_col]) if (sex_col in F.columns) else pd.Series("", index=F.index)
m_mask, f_mask = sex_norm.eq("Male"), sex_norm.eq("Female")
total_m, total_f = int(m_mask.sum()), int(f_mask.sum())

pres_mask = yes_like(F[pres_c]) if pres_c else pd.Series(False, index=F.index)
book_mask = yes_like(F[book_c]) if book_c else pd.Series(False, index=F.index)
ref_mask  = yes_like(F[ref_c])  if ref_c  else pd.Series(False, index=F.index)

spec_prescribed = int(pres_mask.sum())
spec_booked     = int(book_mask.sum())
ref_n           = int(ref_mask.sum())

c1, c2, c3, c4 = st.columns(4)
card(c1, "Total Screened", f"{N:,}", f"M:{total_m:,} | F:{total_f:,}", icon="🩺", color="#22c55e")
card(c2, "Spectacles Prescribed",
     f"{spec_prescribed:,} ({spec_prescribed/max(N,1)*100:.1f}%)",
     f"M:{int((pres_mask & m_mask).sum()):,} | F:{int((pres_mask & f_mask).sum()):,}",
     icon="👓", color="#3b82f6")
card(c3, "Spectacles Dispensed",
     f"{spec_booked:,} ({spec_booked/max(N,1)*100:.1f}%)",
     f"M:{int((book_mask & m_mask).sum()):,} | F:{int((book_mask & f_mask).sum()):,}",
     icon="📘", color="#8b5cf6")
card(c4, "Referred Patients",
     f"{ref_n:,} ({ref_n/max(N,1)*100:.1f}%)",
     f"M:{int((ref_mask & m_mask).sum()):,} | F:{int((ref_mask & f_mask).sum()):,}",
     icon="➡️", color="#14b8a6")

# ========== Demographics ==========
st.markdown("---")
st.subheader("👨‍👩‍👧 Demographics Screening")

if F.empty:
    st.info("No data to display with the current filters.")
else:
    # First row: Gender, Age & Gender, Better PVA, Need
    d1, d2, d3, d4 = st.columns(4)

    # Pies with explicit height to match bars
    rm([
        dict(container=d1, col=col_ok("sex"),           title="Gender Distribution",       chart_func=builder.pie, drop_values={"","nan"}, height=UNIFORM_H),
        dict(container=d2, col=col_ok("agewisesexcat"), title="Age & Gender Distribution", chart_func=builder.pie, drop_values={"","nan"}, height=UNIFORM_H),
        dict(container=d3, col=col_ok("betterpvacat"),  title="Vision Assessment",       chart_func=builder.pie, drop_values={"","nan"}, height=UNIFORM_H),
        dict(container=d4, col=col_ok("need"),          title="Spectacle Need",             chart_func=builder.pie, drop_values={"","nan"}, height=UNIFORM_H),
    ], F)

    # Second row: New/Old × Sex and Wear Glass × Sex
    d5, d6 = st.columns(2)

    # New/Old × Sex (counts)
    try:
        fig_no = builder.grouped_new_old_by_sex(
            F,
            new_old_col=RES.get("no"),
            sex_col=RES.get("sex"),
            title="New / Old by Gender",
            height=UNIFORM_H,
        )
        d5.plotly_chart(fig_no, use_container_width=True, theme=None)
    except Exception:
        d5.info("New/Old by Gender not available.")

    # Wear Glass × Sex (reusable generic)
    try:
        fig_wg = builder.grouped_by_category_and_sex(
            F,
            category_col=RES.get("wear_glass"),
            sex_col=RES.get("sex"),
            normalize_category=lambda s: s.astype("string").str.strip().str.title(),
            title="Wear Glass by Gender",
            height=UNIFORM_H,
            category_order=None,
            sex_order=("Male","Female"),
        )
        d6.plotly_chart(fig_wg, use_container_width=True, theme=None)
    except Exception:
        d6.info("Wear Glass by Gender not available.")


# ========== Refraction & Spectacles ==========
st.markdown("---")
st.subheader("👓 Refraction & Spectacles Detail")

if F.empty:
    st.info("No data to display with the current filters.")
else:
    c1, c2, c3, c4 = st.columns(4)
    rm([
        dict(container=c1, col=col_ok("dry_pmt_dil"),    title="Refraction Type",            chart_func=builder.pie, drop_values={"","nan"}),
        dict(container=c2, col=col_ok("spec_pres"),      title="Spectacles Prescribed",      chart_func=builder.pie, drop_values={"","nan"}),
        dict(container=c3, col=col_ok("spec_pres_type"), title="Prescribed Spectacles Type", chart_func=builder.pie, drop_values={"","nan"}),
        dict(container=c4, col=col_ok("specprice"),      title="Dispensed Spectacles",       chart_func=builder.pie, drop_values={"","nan"}),
    ], F)

# ========== WGSS ==========
st.markdown("---")
st.subheader("🧍 Washington Group Short Set (WGSS)")

if F.empty:
    st.info("No data to display with the current filters.")
else:
    r1c1, r1c2, r1c3 = st.columns(3)
    rm([
        dict(container=r1c1, col=col_ok("vision"),  title="Vision",      chart_func=builder.pie, drop_values={"","nan"}),
        dict(container=r1c2, col=col_ok("hearing"), title="Hearing",     chart_func=builder.pie, drop_values={"","nan"}),
        dict(container=r1c3, col=col_ok("walking"), title="Walking",     chart_func=builder.pie, drop_values={"","nan"}),
    ], F)
    r2c1, r2c2, r2c3 = st.columns(3)
    rm([
        dict(container=r2c1, col=col_ok("remember"),      title="Remembering",   chart_func=builder.pie, drop_values={"","nan"}),
        dict(container=r2c2, col=col_ok("selfcare"),      title="Self Care",     chart_func=builder.pie, drop_values={"","nan"}),
        dict(container=r2c3, col=col_ok("communication"), title="Communication", chart_func=builder.pie, drop_values={"","nan"}),
    ], F)

# ========== Clinical ==========
st.markdown("---")
st.subheader("🩺 Clinical Examination")

if F.empty:
    st.info("No data to display with the current filters.")
else:
    a, b = st.columns([3, 1])
    rm([
        dict(container=a, col=col_ok("diagnosis_code"), title="Screen Patients Diagnosis",
             chart_func=builder.bar, kind="bar", bar_with_labels=True, drop_values={"","nan"}),
        dict(container=b, col=col_ok("referred"),       title="Referred Patients",
             chart_func=builder.pie, drop_values={"","nan"}),
    ], F)
    c, d = st.columns(2)
    rm([
        dict(container=c, col=col_ok("ref_dig"), title="Referred Patients Diagnosis",
             chart_func=builder.bar, kind="bar", bar_with_labels=True, drop_values={"","nan"}),
        dict(container=d, col=col_ok("clinic"),  title="Referred Clinic",
             chart_func=builder.bar, kind="bar", bar_with_labels=True, drop_values={"","nan"}),
    ], F)

# ========== Sex-wise Tables (compact) ==========
st.markdown("---")
st.subheader("📋 Sex-wise Tables")

# --- Team / Vision Centre / Referred
pec_c, clus_c, ref_c = col_ok("pec"), col_ok("cluster"), col_ok("referred")
team_order    = sorted(F[pec_c].dropna().unique())  if (pec_c and not F.empty)  else []
vcentre_order = sorted(F[clus_c].dropna().unique()) if (clus_c and not F.empty) else []

team_df = mf_table(F, pec_c, "Team", order=team_order) if (pec_c and sex_col in F.columns) else pd.DataFrame(columns=["Team","Male","Female","Total"])
vc_df   = mf_table(F, clus_c, "Vision Centre", order=vcentre_order) if (clus_c and sex_col in F.columns) else pd.DataFrame(columns=["Vision Centre","Male","Female","Total"])
ref_df  = mf_table(F, clus_c, "Vision Centre", mask=yes_like(F[ref_c]) if ref_c else None, order=vcentre_order) if (clus_c and sex_col in F.columns and ref_c) else pd.DataFrame(columns=["Vision Centre","Male","Female","Total"])

team_df_viz = add_row_pct_compact(team_df, "Team")
vc_df_viz   = add_row_pct_compact(vc_df, "Vision Centre")
ref_df_viz  = add_row_pct_compact(ref_df, "Vision Centre")

# --- Diagnosis / Referred Diagnosis / Clinic
diag_c   = col_ok("diagnosis_code")
refdig_c = col_ok("ref_dig")
clinic_c = col_ok("clinic")

diag_df   = mf_table(F, diag_c, "Diagnosis", order=None) if (diag_c and sex_col in F.columns) else pd.DataFrame(columns=["Diagnosis","Male","Female","Total"])
refdig_df = mf_table(F, refdig_c, "Referred Diagnosis", order=None) if (refdig_c and sex_col in F.columns) else pd.DataFrame(columns=["Referred Diagnosis","Male","Female","Total"])
clinic_df = mf_table(F, clinic_c, "Clinic", order=None) if (clinic_c and sex_col in F.columns) else pd.DataFrame(columns=["Clinic","Male","Female","Total"])

# Sort Diagnosis by Total desc, with tail labels bottom
if not diag_df.empty and {"Diagnosis","Total"}.issubset(diag_df.columns):
    diag_df = (
        diag_df.assign(_tail=is_tail_label(diag_df["Diagnosis"]))
               .sort_values(by=["_tail", "Total", "Diagnosis"], ascending=[True, False, True], kind="mergesort")
               .drop(columns=["_tail"])
               .reset_index(drop=True)
    )

refdig_df_clean = clean_label_rows(refdig_df, "Referred Diagnosis")
clinic_df_clean = clean_label_rows(clinic_df, "Clinic")

diag_df_compact   = add_row_pct_compact(diag_df, "Diagnosis")
refdig_df_compact = add_row_pct_compact(refdig_df_clean, "Referred Diagnosis")
clinic_df_compact = add_row_pct_compact(clinic_df_clean, "Clinic")

# ----- Layout: 3 rows × 2 columns
# Row 1
r1c1, r1c2 = st.columns(2)
# with r1c1:
#     st.markdown("#### 🏥 Team")
#     st.dataframe(team_df_viz, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)
# with r1c2:
#     st.markdown("#### 🗂️ Vision Centre")
#     st.dataframe(vc_df_viz, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)

# Row 2

with r1c1:
    st.markdown("#### 🧾 Diagnosis (All)")
    st.dataframe(diag_df_compact, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)
with r1c2:
    st.markdown("#### 🧾 Referred Diagnosis")
    st.dataframe(refdig_df_compact, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)

# with r2c2:
#     st.markdown("#### ➡️ Referred")
#     st.dataframe(ref_df_viz, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)
r2c1, = st.columns(1)
with r2c1:
    st.markdown("#### 🏥 Referred Clinic")
    st.dataframe(clinic_df_compact, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)
# Row 3
# r3c1, r3c2 = st.columns(2)
# ========== Footer ==========
st.markdown("<div class='caption'>✨ Use the <b>Clear</b> button in the sidebar to reset filters.</div>", unsafe_allow_html=True)
