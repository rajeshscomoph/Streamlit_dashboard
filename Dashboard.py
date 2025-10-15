# Home.py
import streamlit as st
from common.helper import inject_global_dataframe_css

# Set page first (must be the first Streamlit call)
st.set_page_config(page_title="Community Ophthalmology Dashboard", layout="wide")

# Inject shared CSS for st.dataframe toolbars/menus (defined in common.helper)
inject_global_dataframe_css()

HAS_PAGE_LINK   = hasattr(st, "page_link")
HAS_SWITCH_PAGE = hasattr(st, "switch_page")

BRAND_HEX = "#0ea5e9"  # change to your brand color (e.g., "#8b5cf6")

# ---------- Styles (compact, only what's used) ----------
st.markdown(f"""
<style>
:root {{ --brand: {BRAND_HEX}; }}

/* Fill viewport so content can push to bottom naturally */
.block-container {{
  padding-top: 1.2rem;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}}

/* Hero */
.hero {{ text-align:center; margin-bottom:.75rem; }}
.hero h1 {{
  font-size: clamp(28px, 3.6vw, 44px);
  line-height: 1.15; letter-spacing: -.01em; font-weight: 800; margin: 0;
}}
.hero p {{ margin: 6px 0 0; color:#475569; font-size: clamp(13px, 1.3vw, 16px); }}
@media (prefers-color-scheme: dark) {{ .hero p {{ color:#a3b1c6; }} }}

/* Thin brand divider under title */
.brand-divider {{
  width: clamp(140px, 22vw, 280px); height: 2px; background: var(--brand);
  margin: 10px auto 2px; border-radius: 999px; opacity: .65;
}}

/* Section headings with brand dot */
.section-title {{
  display:inline-flex; align-items:center; gap:.5rem;
  font-weight:800; letter-spacing:-.01em; margin:0 0 .25rem 0;
  font-size: clamp(20px, 2.6vw, 28px);
}}
.section-dot {{ width:12px; height:12px; border-radius:999px; background: var(--brand); opacity:.75; }}
</style>
""", unsafe_allow_html=True)

# ---------- Small helpers ----------
def hero(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class="hero">
          <h1>{title}</h1>
          <div class="brand-divider"></div>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

def section(title: str):
    st.markdown(
        f'<div class="section-title"><span class="section-dot"></span><span>{title}</span></div>',
        unsafe_allow_html=True
    )

def nav_link(page_path: str, label: str, key: str):
    """Single place to handle navigation across Streamlit versions."""
    if HAS_PAGE_LINK:
        st.page_link(page_path, label=label)
    elif HAS_SWITCH_PAGE:
        if st.button(label, key=key):
            st.switch_page(page_path)
    else:
        st.info("Please upgrade Streamlit to enable navigation links.")

# ---------- Hero ----------
hero("Community Ophthalmology Program", "Unified dashboards for Community Services")

# ---------- Sections / Navigation (one row, three columns) ----------
c1, c2, c3 = st.columns(3, gap="large")

with c1:
    section("Primary Eye Care (PEC)")
    st.caption("Coverage, referrals, WGSS indicators, refraction & spectacles.")
    nav_link("pages/PEC_Dashboard.py", "Open PEC Dashboard →", key="pec_btn")

with c2:
    section("Cataract Management")
    st.caption("Reported cases, surgeries, follow-ups, and post-op vision metrics.")
    nav_link("pages/Cataract_Dashboard.py", "Open Cataract Dashboard →", key="cataract_btn")

with c3:
    section("School Screening")
    st.caption("Attendance, myopia distribution, refraction outcomes, referrals.")
    nav_link("pages/School_Dashboard.py", "Open School Dashboard →", key="school_btn")    

# ---------- Footer ----------
st.caption("✨ Note: Select a dashboard to see the results.")
