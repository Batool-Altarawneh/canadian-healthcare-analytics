"""
app.py
------
Canadian Healthcare Analytics Platform
Readmission Risk Prediction App

Run with: streamlit run streamlit_app/app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib.pyplot as plt
from pathlib import Path

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Canadian Healthcare Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 1rem !important;
}
#root > div:first-child { margin-top: 0 !important; }
div[data-testid="stAppViewContainer"] > div:first-child {
    padding-top: 0 !important;
}
* { cursor: default !important; }
button, select, input, .stSelectbox, .stSlider,
[role="tab"], [role="button"], a,
div[data-testid="stSidebar"] select,
div[data-testid="stSidebar"] input { cursor: pointer !important; }
input[type="range"] { cursor: grab !important; }
input[type="range"]:active { cursor: grabbing !important; }
label, p, span { user-select: none; }
.metric-card {
    background: #F8F9FB;
    border: 0.5px solid #E0E4EA;
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
    margin-bottom: 8px;
}
.metric-val { font-size: 24px; font-weight: 600; color: #1A3A5C; }
.metric-label { font-size: 11px; color: #888; margin-top: 3px; }
.notice-box {
    background: #EFF6FF;
    border-left: 3px solid #185FA5;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    font-size: 11px;
    color: #555;
    margin-top: 12px;
}
.section-header {
    font-size: 14px;
    font-weight: 600;
    color: #1A3A5C;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #E0E4EA;
}
section[data-testid="stSidebar"] { background: #F2F4F7; }
section[data-testid="stSidebar"] label {
    font-size: 12px !important;
    color: #555 !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 13px;
    padding: 8px 20px;
    cursor: pointer !important;
}
.stTabs [aria-selected="true"] {
    color: #1A3A5C !important;
    border-bottom-color: #1A3A5C !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────
st.markdown("""
<div style="background:#1A3A5C;color:white;padding:14px 24px;
     border-radius:10px;margin-bottom:20px;margin-top:40px;
     display:flex;align-items:center;justify-content:space-between;">
    <div>
        <div style="font-size:20px;font-weight:600;color:white;">
            🏥 Canadian Healthcare Analytics Platform
        </div>
        <div style="font-size:11px;color:rgba(255,255,255,0.65);margin-top:3px;">
            Python · SQL Server · Power BI · XGBoost · Prophet
            &nbsp;·&nbsp; Portfolio project · Synthetic data only
        </div>
    </div>
    <div style="text-align:right;">
        <div style="font-size:11px;color:rgba(255,255,255,0.6);">
            Active model
        </div>
        <div style="font-size:13px;color:white;font-weight:500;">
            Logistic Regression
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
PROCESSED  = BASE_DIR / "data" / "processed"

# ── Load model ─────────────────────────────────────────────────
@st.cache_resource
def load_model():
    m = joblib.load(MODELS_DIR / "lr_readmission_model.pkl")
    e = joblib.load(MODELS_DIR / "lr_encoders.pkl")
    f = joblib.load(MODELS_DIR / "feature_columns.pkl")
    return m, e, f

model, encoders, feature_cols = load_model()

# ── Sidebar ─────────────────────────────────────────────────────
st.sidebar.markdown("""
<div style="background:#1A3A5C;color:white;padding:12px 16px;
     border-radius:8px;margin-bottom:16px;">
    <div style="font-size:14px;font-weight:600;color:white;">
        Patient Profile
    </div>
    <div style="font-size:10px;color:rgba(255,255,255,0.65);margin-top:2px;">
        Adjust inputs to generate prediction
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("**Demographics**")
age    = st.sidebar.slider("Age", 0, 100, 67)
gender = st.sidebar.selectbox("Gender", ["Female", "Male"])

st.sidebar.markdown("**Clinical**")
medical_condition = st.sidebar.selectbox("Medical Condition", [
    "Arthritis", "Asthma", "Cancer",
    "Diabetes", "Hypertension", "Obesity"
])
admission_type = st.sidebar.selectbox("Admission Type", [
    "Elective", "Emergency", "Urgent"
])
length_of_stay = st.sidebar.slider("Length of Stay (days)", 0, 60, 18)
test_results   = st.sidebar.selectbox("Test Results", [
    "Abnormal", "Inconclusive", "Normal"
])
medication = st.sidebar.selectbox("Medication", [
    "Aspirin", "Ibuprofen", "Lipitor", "Paracetamol", "Penicillin"
])

st.sidebar.markdown("**Administrative**")
insurance_provider = st.sidebar.selectbox("Insurance Provider", [
    "Aetna", "Blue Cross", "Cigna", "Medicare", "Unitedhealthcare"
])
billing_amount = st.sidebar.slider(
    "Billing Amount (CAD)", 0, 52000, 34000, step=500)
blood_type = st.sidebar.selectbox("Blood Type", [
    "A+", "A-", "AB+", "AB-", "B+", "B-", "O+", "O-"
])

st.sidebar.divider()
st.sidebar.caption(
    "Not intended for clinical use. "
    "Built for portfolio demonstration purposes only."
)

# ── Helpers ─────────────────────────────────────────────────────
def assign_age_group(age):
    if age < 18:   return "0-17"
    elif age < 35: return "18-34"
    elif age < 55: return "35-54"
    elif age < 75: return "55-74"
    else:          return "75+"

def build_input():
    raw = {
        "age"                : age,
        "age_group"          : assign_age_group(age),
        "gender"             : gender,
        "blood_type"         : blood_type,
        "medical_condition"  : medical_condition,
        "admission_type"     : admission_type,
        "insurance_provider" : insurance_provider,
        "length_of_stay_days": length_of_stay,
        "billing_amount"     : billing_amount,
        "test_results"       : test_results,
        "medication"         : medication,
    }
    df = pd.DataFrame([raw])
    cat_cols = [
        "age_group", "gender", "blood_type", "medical_condition",
        "admission_type", "insurance_provider", "test_results", "medication"
    ]
    for col in cat_cols:
        le  = encoders[col]
        val = df[col].iloc[0]
        df[col] = le.transform([val])[0] if val in le.classes_ else 0
    return df[feature_cols]

# ── Tabs ────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🔮  Prediction",
    "📊  Model Summary",
    "🗺️  CIHI Forecast",
    "ℹ️  About"
])

# ════════════════════════════════════════════════════════════════
# TAB 1 — PREDICTION
# ════════════════════════════════════════════════════════════════
with tab1:
    input_df = build_input()
    prob     = model.predict_proba(input_df)[0][1]

    if prob >= 0.30:
        tier       = "High Risk"
        tile_color = "#FCEBEB"
        text_color = "#A32D2D"
        bar_color  = "#E24B4A"
    elif prob >= 0.15:
        tier       = "Medium Risk"
        tile_color = "#FAEEDA"
        text_color = "#854F0B"
        bar_color  = "#EF9F27"
    else:
        tier       = "Low Risk"
        tile_color = "#E1F5EE"
        text_color = "#085041"
        bar_color  = "#1D9E75"

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown(
            '<div class="section-header">Risk Score</div>',
            unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:{tile_color};border:1px solid {bar_color}44;
             border-radius:12px;padding:20px 24px;margin-bottom:16px;">
            <div style="font-size:11px;color:{text_color};margin-bottom:4px;">
                30-day readmission probability
            </div>
            <div style="font-size:52px;font-weight:700;color:{text_color};
                 line-height:1.1;">
                {prob*100:.1f}%
            </div>
            <div style="height:8px;background:#ddd;border-radius:4px;
                 margin:14px 0 12px;">
                <div style="width:{prob*100:.0f}%;height:100%;
                     background:{bar_color};border-radius:4px;"></div>
            </div>
            <span style="background:{bar_color};color:white;padding:4px 14px;
                  border-radius:10px;font-size:12px;font-weight:600;">
                {tier}
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="notice-box">
            <b>Thresholds:</b><br>
            🔴 &gt;30% = High risk<br>
            🟡 15–30% = Medium risk<br>
            🟢 &lt;15% = Low risk<br><br>
            <b>Model:</b> Logistic Regression<br>
            <b>Recall:</b> 49.1% &nbsp;·&nbsp;
            <b>AUC:</b> 0.518<br><br>
            ⚠️ Synthetic data only. Not for clinical use.
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(
            '<div class="section-header">Why this prediction? (SHAP)</div>',
            unsafe_allow_html=True)

        scaler   = model.named_steps["scaler"]
        lr       = model.named_steps["model"]
        X_scaled = scaler.transform(input_df)

        explainer   = shap.LinearExplainer(
            lr, shap.maskers.Independent(X_scaled))
        shap_values = explainer.shap_values(X_scaled)

        shap_df = pd.DataFrame({
            "feature": feature_cols,
            "shap"   : shap_values[0]
        }).sort_values("shap", key=abs, ascending=False).head(8)

        fig, ax = plt.subplots(figsize=(7, 4))
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#FFFFFF")
        colors = ["#E24B4A" if v > 0 else "#1D9E75"
                  for v in shap_df["shap"]]
        ax.barh(shap_df["feature"], shap_df["shap"],
                color=colors, height=0.55)
        ax.axvline(0, color="#AAAAAA", linewidth=0.8)
        max_shap = max(abs(shap_df["shap"].max()), abs(shap_df["shap"].min()))
        if max_shap < 0.01:
            ax.set_xlim(-0.05, 0.05)
        else:
                ax.set_xlim(-max_shap * 1.3, max_shap * 1.3)
        ax.set_xlabel(
            "SHAP value  (red = increases risk · green = decreases risk)",
            fontsize=10)
        ax.set_title(
            "Feature contributions for this patient",
            fontsize=12, color="#1A3A5C", fontweight="bold")
        ax.invert_yaxis()
        ax.tick_params(labelsize=10)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close()

        st.caption(
            "SHAP (SHapley Additive exPlanations) shows how each feature "
            "pushed the prediction higher (red) or lower (green) for this "
            "specific patient. Values near zero indicate weak influence."
        )

# ════════════════════════════════════════════════════════════════
# TAB 2 — MODEL SUMMARY
# ════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(
        '<div class="section-header">Model Performance at a Glance</div>',
        unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    for col, val, label in zip(
        [m1, m2, m3, m4],
        ["1.0%", "49.1%", "0.518", "0.011"],
        ["30-day readmission rate", "Best model recall (LR)",
         "Best AUC-ROC", "Best PR-AUC"]
    ):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        '<div class="section-header" style="margin-top:20px;">'
        'Model Comparison</div>',
        unsafe_allow_html=True)

    summary = pd.DataFrame({
        "Model"    : ["Logistic Regression", "XGB Threshold",
                      "XGBoost", "Random Forest", "XGB + SMOTE"],
        "Precision": [0.011, 0.010, 0.010, 0.007, 0.011],
        "Recall"   : [0.491, 0.879, 0.181, 0.069, 0.129],
        "F1"       : [0.022, 0.020, 0.019, 0.013, 0.020],
        "AUC-ROC"  : [0.518, 0.488, 0.488, 0.494, 0.507],
        "Verdict"  : ["✅ Best recall", "🟡 Broad screen",
                      "❌ Weak", "❌ Weak", "❌ Weak"]
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.markdown(
        '<div class="section-header" style="margin-top:20px;">'
        'Key Limitations</div>',
        unsafe_allow_html=True)
    st.markdown("""
    - **Synthetic data** : No real clinical relationships between
      features and readmission. All models perform near-random (AUC ~0.51).
    - **Limited features** : Real hospital data would include prior
      admission count, comorbidity index, discharge disposition, lab values.
    - **Class imbalance** : Only 1.0% positive rate. PR-AUC of 0.011
      barely exceeds the baseline readmission rate.
    - **LabelEncoder** : Categorical SHAP direction should not be
      over-interpreted as encoding order is arbitrary.
    """)

# ════════════════════════════════════════════════════════════════
# TAB 3 — CIHI FORECAST
# ════════════════════════════════════════════════════════════════
with tab3:
    st.markdown(
        '<div class="section-header">'
        'CIHI Prophet Forecast — National P50 Wait Days</div>',
        unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, val, label in zip(
        [c1, c2, c3],
        ["125 days", "151 days", "182 days"],
        ["Hip P50 national (2024)",
         "Knee P50 national (2024)",
         "CIHI benchmark target"]
    ):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    procedure = st.selectbox("Select procedure",
        ["Hip Replacement", "Knee Replacement"])

    try:
        forecast   = pd.read_csv(PROCESSED / "cihi_forecast.csv")
        df_plot    = forecast[forecast["procedure"] == procedure]
        historical = df_plot[~df_plot["is_forecast"]]
        future     = df_plot[df_plot["is_forecast"]]

        fig2, ax2 = plt.subplots(figsize=(10, 4.5))
        fig2.patch.set_facecolor("#FFFFFF")
        ax2.set_facecolor("#FFFFFF")

        ax2.plot(historical["year"], historical["yhat"],
                 color="#185FA5", linewidth=2.5, marker="o",
                 markersize=5, label="Historical (CIHI)", zorder=3)
        ax2.plot(future["year"], future["yhat"],
                 color="#E24B4A", linewidth=2.5, linestyle="--",
                 marker="o", markersize=5,
                 label="Forecast (Prophet)", zorder=3)
        ax2.fill_between(future["year"],
                         future["yhat_lower"], future["yhat_upper"],
                         alpha=0.12, color="#E24B4A", label="95% CI")
        ax2.axvline(2024.5, color="#AAAAAA", linewidth=1,
                    linestyle=":", label="Forecast start")
        ax2.axhline(182, color="#EF9F27", linewidth=1.5,
                    linestyle="--", label="182-day CIHI benchmark")
        ax2.set_xlabel("Year", fontsize=11)
        ax2.set_ylabel("Wait Days (50th Percentile)", fontsize=11)
        ax2.set_title(
            f"{procedure}: National Median Wait Days 2010–2027",
            fontsize=13, color="#1A3A5C", fontweight="bold")
        ax2.legend(fontsize=9, loc="upper left")
        ax2.tick_params(labelsize=10)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        fig2.tight_layout()
        st.pyplot(fig2)
        plt.close()

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("""
            **Key findings from trend analysis:**
            - Pre-COVID trend: **+2.6 days/year** (hip),
              **+2.8 days/year** (knee)
            - Post-COVID recovery: **-5.9 days/year** (hip),
              **-6.1 days/year** (knee)
            - Prophet predicts continued increase , tension with the
              post-COVID improving slope
            """)
        with col_b:
            st.markdown(f"""
            **Forecast details:**
            - Training data: **{len(historical)} years** (2010–2024)
            - Forecast horizon: **2025–2027**
            - Model: **Facebook Prophet** (annual, no seasonality)
            - Confidence interval: **95%**
            """)

    except FileNotFoundError:
        st.warning(
            "cihi_forecast.csv not found. "
            "Run the Prophet notebook first.")

# ════════════════════════════════════════════════════════════════
# TAB 4 — ABOUT
# ════════════════════════════════════════════════════════════════
with tab4:
    st.markdown(
        '<div class="section-header">About This Project</div>',
        unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Project overview**

        An end-to-end healthcare analytics portfolio project built to
        demonstrate data engineering, analytics, and machine learning
        skills in a Canadian healthcare context.

        **What was built:**
        - Python ETL pipeline: 3 ingestion scripts, 50 data quality checks
        - SQL Server star schema: 9 tables, 64,000+ records
        - Power BI dashboard: 5 pages, DAX measures, heatmaps
        - 3 ML models with SHAP explainability
        - This Streamlit prediction app
        """)

    with col2:
        st.markdown("""
        **Data sources:**
        - `healthcare_dataset.csv`: 55,392 synthetic patient admissions
        - `ER_Wait_Time_Dataset.csv`: 5,000 synthetic ER visits
        - `CIHI Wait Times 2025`: 9,020 rows of real Canadian government
          data from cihi.ca (2008-2024)

        **Tech stack:**

        Python · pandas · scikit-learn · XGBoost · SHAP · Prophet ·
        SQL Server · Power BI · Streamlit
        """)

    st.divider()

    st.markdown("""
    <div style="font-size:11px;color:#888;text-align:center;padding:8px 0;">
        Built for portfolio demonstration &nbsp;·&nbsp;
        Data: CIHI (cihi.ca) and synthetic datasets &nbsp;·&nbsp;
        Not intended for clinical use
    </div>
    """, unsafe_allow_html=True)