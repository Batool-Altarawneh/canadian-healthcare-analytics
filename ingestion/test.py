# import pandas as pd
# from pathlib import Path

# df = pd.read_csv(Path("data/processed/admissions_clean.csv"))

# print("Negative billing amounts:")
# print(df[df["billing_amount"] < 0]["billing_amount"])

# print(f"\nMin billing amount: {df['billing_amount'].min()}")
# print(f"Zero billing amounts: {(df['billing_amount'] == 0).sum()}")
# print(f"Near-zero (<0.01): {(df['billing_amount'] < 0.01).sum()}")

# import pandas as pd
# from pathlib import Path

# df_er = pd.read_csv(Path("data/processed/er_visits_clean.csv"))
# df_admissions = pd.read_csv(Path("data/processed/admissions_clean.csv"))

# # Check what hospital names look like in each dataset
# print("ER hospital sample:")
# print(df_er["hospital_name"].head(5).tolist())

# print("\nAdmissions hospital sample:")
# print(df_admissions["hospital"].head(5).tolist())

# print("\nER hospital count:", df_er["hospital_name"].nunique())
# print("Admissions hospital count:", df_admissions["hospital"].nunique())

# # Check for overlap
# er_hospitals = set(df_er["hospital_name"].unique())
# adm_hospitals = set(df_admissions["hospital"].unique())
# overlap = er_hospitals.intersection(adm_hospitals)
# print(f"\nOverlapping hospital names: {len(overlap)}")

# import pandas as pd
# from pathlib import Path

# df_er = pd.read_csv(Path("data/processed/er_visits_clean.csv"))

# print("ER hospital names from fact CSV:")
# for name in df_er["hospital_name"].unique():
#     print(repr(name))

import pandas as pd
from pathlib import Path
import numpy as np

df_er = pd.read_csv(Path("data/processed/er_visits_clean.csv"))

# Build a minimal dim_hospital exactly as the loading script does
hosp_er = (
    df_er[["hospital_name", "region", "facility_beds"]]
    .dropna(subset=["hospital_name"])
    .drop_duplicates(subset=["hospital_name"])
    .copy()
)
hosp_er["source"] = "er"
hosp_er.insert(0, "hospital_id", range(1, len(hosp_er) + 1))

print("dim_hospital (er only):")
print(hosp_er[["hospital_id", "hospital_name"]])

# Attempt the merge
merged = df_er.merge(
    hosp_er[["hospital_id", "hospital_name"]],
    on="hospital_name",
    how="left"
)

print(f"\nColumns after merge: {merged.columns.tolist()}")
print(f"hospital_id nulls: {merged['hospital_id'].isna().sum()}")
print(f"Total rows: {len(merged)}")