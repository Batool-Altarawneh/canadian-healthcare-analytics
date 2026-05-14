# Model Card : 30-Day Readmission Risk Classifier

## What This Model Does

This model predicts whether a hospital patient is likely to be readmitted within 30 days after discharge.

The model outputs:

- `0` = Not readmitted within 30 days
- `1` = Readmitted within 30 days
- A probability score representing the estimated readmission risk

This project is designed as a portfolio demonstration of a healthcare machine learning workflow, not as a clinical decision-support tool.

---

## Training Data

- **Source:** Synthetic patient admissions dataset
- **Total records:** 55,392 admissions
- **Date range:** 2019–2024
- **Target variable:** `readmitted_30d`
- **Target creation method:** Engineered from admission and discharge dates
- **Positive class:** Patient had another admission within 30 days of discharge
- **Positive class rate:** 1.0%  
- **Total readmission events:** 578

The target variable was created by sorting admissions by patient name and admission date, then checking whether the next admission occurred within 30 days after the previous discharge date.

---

## Model Selected

The selected baseline model is:

**Logistic Regression with StandardScaler using an sklearn Pipeline**

This model was selected because it achieved the highest recall for the minority class among the standard models tested.

Models compared:

- Logistic Regression
- XGBoost
- Random Forest
- XGBoost with threshold tuning
- XGBoost with SMOTE oversampling

Although XGBoost with threshold tuning achieved higher recall, it produced too many false positives to be considered a practical final model. Logistic Regression was selected as the most interpretable baseline model.

---

## Performance on Test Set

The model was evaluated on a test set of **11,079 records**.

| Metric | Not Readmitted | Readmitted |
|---|---:|---:|
| Precision | 0.99 | 0.01 |
| Recall | 0.54 | 0.49 |
| F1-score | 0.70 | 0.02 |
| AUC-ROC | 0.5179 | |
| PR-AUC | 0.0108 | |

### Interpretation

The Logistic Regression model identified approximately **49%** of actual readmission cases. However, precision for the readmitted class was very low at **0.01**, meaning the model produced many false positive alerts.

The PR-AUC score of **0.0108** is close to the baseline positive class rate of approximately **1.0%**, suggesting that the current features do not provide strong predictive signal for readmission risk.

Overall, the model is useful as a baseline experiment, but it is not reliable enough for clinical use.

---

## Top Predictive Features

SHAP was used to explain the Logistic Regression model.

| Rank | Feature | Mean Absolute SHAP |
|---:|---|---:|
| 1 | age | 0.218 |
| 2 | age_group | 0.159 |
| 3 | insurance_provider | 0.085 |
| 4 | medication | 0.084 |
| 5 | billing_amount | 0.071 |

### SHAP Interpretation

The model relied most heavily on general demographic and administrative variables, especially `age` and `age_group`.

However, because the model performance is weak, these SHAP values should be interpreted as explanations of the model’s behaviour, not as true clinical risk factors.

Categorical variables were encoded using `LabelEncoder`, so the direction of SHAP impact for features such as `insurance_provider`, `medication`, and `medical_condition` should not be interpreted as a real clinical ordering.

---

## Known Limitations

1. **Synthetic data**

   The dataset is synthetic and may not contain realistic clinical relationships between patient features and readmission outcomes. Performance on real hospital data would likely differ significantly.

2. **Limited clinical features**

   Important predictors are not available in the dataset, including:

   - Prior admission count
   - Previous readmissions
   - Comorbidity index
   - Diagnosis severity
   - Discharge disposition
   - Lab values
   - Follow-up appointment status
   - Social determinants of health

3. **Severe class imbalance**

   Only about **1.0%** of admissions were positive readmission cases. This made the prediction task difficult and caused all models to produce very low precision for the readmitted class.

4. **Categorical encoding limitation**

   `LabelEncoder` was used to convert categorical variables into numeric values. This is acceptable for a baseline model, but future versions should test one-hot encoding or target encoding.

5. **Patient identity limitation**

   The target variable was engineered using patient name as the patient identifier. In a real healthcare dataset, a unique patient ID should be used instead to avoid errors caused by duplicate names.

---

## Responsible AI and Ethical Considerations

This model should not be used for real clinical decision-making.

A readmission risk model can affect patient care, resource allocation, and follow-up planning. Because this model has low precision and was trained on synthetic data, using it in a real healthcare environment could lead to unfair or inaccurate risk classification.

Before any clinical use, a model like this would require:

- Real hospital data validation
- Bias and fairness testing
- Clinical review
- External validation
- Monitoring after deployment
- Clear human oversight

The model should support healthcare professionals, not replace clinical judgment.

---

## Intended Use
Portfolio demonstration of end-to-end ML pipeline including feature 
engineering, class imbalance handling, model comparison, and SHAP 
explainability. Not intended for clinical use.

## Not Intended For
- Clinical decision-making
- Real patient risk stratification
- Any production healthcare environment