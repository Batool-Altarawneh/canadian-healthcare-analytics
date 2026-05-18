# 🏥 Canadian Healthcare Analytics Platform

An end-to-end healthcare analytics portfolio project built to demonstrate data engineering, SQL, machine learning, and business intelligence skills in a Canadian healthcare context.

**Live demo:** https://canadian-healthcare-analytics.streamlit.app/

---

## What This Project Does

This project ingests, cleans, models, and visualises three healthcare datasets including real Canadian government data through a complete analytics pipeline from raw CSV files to a deployed machine learning app.

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| Ingestion & cleaning | Python, pandas, pathlib |
| Data quality | Custom DataQualityChecker (50 checks) |
| Storage | SQL Server (star schema, 9 tables) |
| Analysis | Jupyter, scipy, statsmodels |
| Machine learning | scikit-learn, XGBoost, SHAP, Prophet |
| Dashboard | Power BI (5 pages, DAX measures) |
| App deployment | Streamlit Community Cloud |

---

---

## Key Findings

**Patient Admissions (synthetic)**
- Billing is uniformly distributed (~$25,590 avg) characteristic of synthetic data while real billing shows right-skewed distributions.
- Monthly admissions stable at 850-1,000/month with no seasonal pattern.
- 2024 data is a partial year only 3,846 admissions vs ~11,000 in full years.

**ER Performance (synthetic)**
- Only 11.5% of visits meet CTAS benchmarks.
- Low urgency patients wait an average of 174 minutes which is nearly 3× the 60-minute CTAS IV benchmark.
- Urban vs rural wait time difference of 0.2 minutes was not statistically significant (t-test p=0.94).
- Evening weekdays (Mon–Wed) show the highest average wait times, exceeding 100 minutes.

**Provincial Wait Times (real CIHI data)**
- COVID-19 caused a universal spike in 2020 across all provinces.
  Saskatchewan knee replacement reached 466 days in 2022.
- Nova Scotia improved most: hip wait times fell from 201 days (2008) to 124 days (2024), a reduction of 38%.
- Quebec deteriorated most: hip wait times rose from 69 days (2008) to 188 days (2024), an increase of 172%.
- Pre-COVID national trend: +2.6 days/year (hip), +2.8 days/year (knee).
- Post-COVID recovery: −5.9 days/year (hip), −6.1 days/year (knee).
- Prophet forecast predicts wait times will increase again by 2027 tension with the post-COVID improving slope reflects uncertainty in long-term trend direction.

**Machine Learning**
- Readmission prediction: all 5 models performed near-random (AUC ~0.51) due to synthetic data lacking real clinical relationships.
-  Logistic Regression achieved the best recall (49.1%).
- ER wait time prediction: XGBoost R²=0.934, MAE=12 minutes. Urgency level was the dominant SHAP feature (47.3 mean abs SHAP).
- CIHI forecast: Prophet predicts hip replacement P50 will reach
  160 days by 2027 (95% CI: 128–190 days).

---

## Machine Learning Models

| Model | Task | Algorithm | Key Metric |
|-------|------|-----------|------------|
| Readmission risk | Classification | Logistic Regression | Recall: 49.1% |
| ER wait time | Regression | XGBoost | R²: 0.934 |
| CIHI forecast | Time series | Prophet | 15 years of data |

---

## SQL Star Schema

9 tables across 3 fact tables and 6 dimension tables:

**Facts:** `fact_admissions`, `fact_er_visits`, `fact_provincial_wait_times`

**Dimensions:** `dim_date`, `dim_patient`, `dim_hospital`, `dim_condition`, `dim_region`, `dim_procedure`

---

## Power BI Dashboard

5-page interactive dashboard:
1. **Home** — Navigation landing page with pipeline diagram
2. **Executive Summary** — KPIs, admissions trend, billing analysis
3. **ER Performance** — CTAS benchmark analysis, wait time heatmap
4. **Provincial Wait Times** — 16 years of real CIHI data by province
5. **ML Insights** — SHAP feature importance, model comparison,  Prophet forecast

---

## How to Run Locally

```bash
# Clone the repo
git clone https://github.com/Batool-Altarawneh/canadian-healthcare-analytics.git
cd canadian-healthcare-analytics

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Run the Streamlit app
streamlit run streamlit_app/app.py
```

---


## Data Sources

| Dataset | Rows | Type | Source |
|---------|------|------|--------|
| Patient admissions | 55,392 | Synthetic | Kaggle |
| ER wait times | 5,000 | Synthetic | Kaggle |
| CIHI wait times 2025 | 9,020 | **Real government data** | cihi.ca |

---
