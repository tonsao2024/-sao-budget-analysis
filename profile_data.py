"""Profile the budget CSV for data-quality issues (assessment only, no modification)."""
import pandas as pd
import numpy as np

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)

df = pd.read_csv("budget_2566-2569.csv.gz", dtype=str, keep_default_na=False)
# keep raw strings; also derive typed columns for checks
print("=== SHAPE ===")
print(f"rows={len(df):,}  cols={df.shape[1]}")
print("\n=== COLUMNS ===")
print(list(df.columns))

print("\n=== MISSING / EMPTY per column ===")
for c in df.columns:
    n_blank = (df[c].str.strip() == "").sum()
    print(f"{c:20s} blank={n_blank:8,} ({n_blank/len(df)*100:5.1f}%)")

print("\n=== WHITESPACE ISSUES (leading/trailing) per column ===")
for c in df.columns:
    s = df[c]
    n_ws = ((s != s.str.strip())).sum()
    n_dbl = (s.str.contains("  ", regex=False)).sum()
    if n_ws or n_dbl:
        print(f"{c:20s} lead/trail_ws={n_ws:8,}  double_space={n_dbl:8,}")

print("\n=== AMOUNT column checks ===")
amt_raw = df["AMOUNT"]
print("unique raw sample:", amt_raw.unique()[:10])
amt = pd.to_numeric(amt_raw.str.replace(",", "", regex=False).str.strip(), errors="coerce")
print(f"non-numeric AMOUNT: {amt.isna().sum():,}")
print(amt.describe())
print(f"negative: {(amt < 0).sum():,}   zero: {(amt == 0).sum():,}")
print("top amounts:", amt.sort_values(ascending=False).head(5).tolist())

print("\n=== FISCAL_YEAR values ===")
print(df["FISCAL_YEAR"].value_counts(dropna=False))

print("\n=== OBLIGED? values ===")
print(df["OBLIGED?"].value_counts(dropna=False))

print("\n=== CROSS_FUNC? values ===")
print(df["CROSS_FUNC?"].value_counts(dropna=False))

print("\n=== Duplicates ===")
print(f"fully duplicated rows: {df.duplicated().sum():,}")
key_cols = ["REF_DOC", "REF_PAGE_NO", "MINISTRY", "BUDGETARY_UNIT", "BUDGET_PLAN",
            "OUTPUT", "PROJECT", "CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3",
            "CATEGORY_LV4", "CATEGORY_LV5", "CATEGORY_LV6", "ITEM_DESCRIPTION",
            "AMOUNT", "FISCAL_YEAR"]
print(f"duplicated on business key {key_cols}: {df.duplicated(subset=key_cols).sum():,}")

print("\n=== Cardinality of key categorical columns ===")
for c in ["MINISTRY", "BUDGETARY_UNIT", "BUDGET_PLAN", "CATEGORY_LV1", "Source_Sheet",
          "STRATEGY", "MOTHER_PLAN", "REF_DOC"]:
    print(f"{c:20s} nunique={df[c].nunique():6,}")

print("\n=== Top 15 MINISTRY ===")
print(df["MINISTRY"].value_counts().head(15))

print("\n=== Top 15 BUDGET_PLAN ===")
print(df["BUDGET_PLAN"].value_counts().head(15))

print("\n=== CATEGORY_LV1 values ===")
print(df["CATEGORY_LV1"].value_counts(dropna=False))

print("\n=== REF_PAGE_NO sample / non-numeric ===")
pg = pd.to_numeric(df["REF_PAGE_NO"], errors="coerce")
print(f"non-numeric REF_PAGE_NO: {pg.isna().sum():,}")

print("\n=== AMOUNT by FISCAL_YEAR (sum, in 100M THB) ===")
df["_amt"] = amt
print((df.groupby("FISCAL_YEAR")["_amt"].agg(["sum", "count", "mean"]) / 1e8).round(2))

print("\n=== ITEM_DESCRIPTION top 20 ===")
print(df["ITEM_DESCRIPTION"].value_counts().head(20))

print("\n=== Check category hierarchy consistency (LV1 non-empty but LV2 empty etc.) ===")
cat = ["CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3", "CATEGORY_LV4", "CATEGORY_LV5", "CATEGORY_LV6"]
for i in range(len(cat) - 1):
    hi, lo = cat[i], cat[i + 1]
    bad = ((df[hi].str.strip() == "") & (df[lo].str.strip() != "")).sum()
    print(f"{lo} filled but {hi} empty: {bad:,}")

print("\n=== Rows where ALL category levels empty ===")
all_empty = (df[cat].apply(lambda r: (r.str.strip() == "").all(), axis=1)).sum()
print(f"{all_empty:,}")

print("\n=== OUTPUT / PROJECT fill rates ===")
print(f"OUTPUT blank: {(df['OUTPUT'].str.strip()=='').sum():,}   PROJECT blank: {(df['PROJECT'].str.strip()=='').sum():,}")
