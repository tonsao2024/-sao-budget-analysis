"""Round 2: dig into the anomalies found in round 1."""
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 50)
pd.set_option("display.max_colwidth", 80)

df = pd.read_csv("budget_2566-2569.csv.gz", dtype=str, keep_default_na=False)
df["_amt"] = pd.to_numeric(df["AMOUNT"], errors="coerce")
df["_year"] = pd.to_numeric(df["FISCAL_YEAR"], errors="coerce")

print("=== FISCAL_YEAR full distribution ===")
vc = df["FISCAL_YEAR"].value_counts()
print(vc.to_string())

print("\n=== Rows with year outside 2022-2026: sample ===")
odd = df[(df["_year"] < 2022) | (df["_year"] > 2026)]
print(f"odd-year rows: {len(odd):,}")
print(odd[["REF_DOC", "MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION", "AMOUNT",
           "FISCAL_YEAR", "Source_Sheet"]].head(15).to_string())

print("\n=== Odd-year rows: sum of AMOUNT (billion) ===")
print(f"{odd['_amt'].sum()/1e9:,.1f} B THB across {len(odd):,} rows")
print(f"main-year rows: {df[(df['_year']>=2022)&(df['_year']<=2026)]['_amt'].sum()/1e9:,.1f} B THB")

print("\n=== Are odd-year rows concentrated in specific Source_Sheet / REF_DOC? ===")
print(odd["Source_Sheet"].value_counts())
print(odd["REF_DOC"].str.split("/").str[-1].value_counts().head(10))

print("\n=== AMOUNT extremes ===")
print("\nTop 10 rows by AMOUNT:")
print(df.nlargest(10, "_amt")[["MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION", "AMOUNT",
                                "FISCAL_YEAR", "CATEGORY_LV1"]].to_string())
print("\nThe single negative row:")
print(df[df["_amt"] < 0][["REF_DOC", "MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION",
                           "AMOUNT", "FISCAL_YEAR", "CATEGORY_LV1"]].to_string())
print("\nZero-amount rows sample:")
print(df[df["_amt"] == 0][["MINISTRY", "ITEM_DESCRIPTION", "FISCAL_YEAR"]].head(5).to_string())

print("\n=== Possible TOTAL/AGGREGATE rows in ITEM_DESCRIPTION ===")
for pat in ["รวม", "Total", "total", "ทั้งสิ้น", "ทั้งหมด"]:
    n = df["ITEM_DESCRIPTION"].str.contains(pat, regex=False).sum()
    print(f"  contains '{pat}': {n:,}")

print("\n=== MINISTRY: suspicious similar names ===")
mins = df["MINISTRY"].value_counts()
print(mins.to_string())

print("\n=== STRATEGY values ===")
print(df["STRATEGY"].value_counts(dropna=False).to_string())

print("\n=== MOTHER_PLAN values (top 30) ===")
print(df["MOTHER_PLAN"].value_counts(dropna=False).head(30).to_string())

print("\n=== Source_Sheet values ===")
print(df["Source_Sheet"].value_counts().to_string())

print("\n=== The non-numeric REF_PAGE_NO row ===")
pg = pd.to_numeric(df["REF_PAGE_NO"], errors="coerce")
print(df[pg.isna()][["REF_DOC", "REF_PAGE_NO", "MINISTRY", "ITEM_DESCRIPTION"]].to_string())

print("\n=== CATEGORY_LV1 odd values (plan names) rows ===")
oddcat = df[~df["CATEGORY_LV1"].isin(
    ["งบบุคลากร", "งบดำเนินงาน", "งบลงทุน", "งบเงินอุดหนุน", "งบรายจ่ายอื่น", ""])]
print(oddcat[["MINISTRY", "BUDGETARY_UNIT", "BUDGET_PLAN", "OUTPUT", "PROJECT",
              "CATEGORY_LV1", "CATEGORY_LV2", "ITEM_DESCRIPTION", "AMOUNT"]].to_string())

print("\n=== LV3-filled-but-LV2-empty: sample ===")
mask = (df["CATEGORY_LV2"].str.strip() == "") & (df["CATEGORY_LV3"].str.strip() != "")
print(f"count={mask.sum():,}")
print(df[mask][["CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3", "CATEGORY_LV4", "ITEM_DESCRIPTION"]].head(10).to_string())

print("\n=== LV5-filled-but-LV4-empty rows ===")
mask5 = (df["CATEGORY_LV4"].str.strip() == "") & (df["CATEGORY_LV5"].str.strip() != "")
print(df[mask5][["MINISTRY", "CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3", "CATEGORY_LV4",
                 "CATEGORY_LV5", "CATEGORY_LV6", "ITEM_DESCRIPTION", "AMOUNT"]].to_string())

print("\n=== Duplicated rows: sample ===")
dup_mask = df.duplicated(keep=False)
print(f"rows involved in duplication: {dup_mask.sum():,}")
print(df[dup_mask].sort_values(["REF_DOC", "ITEM_DESCRIPTION"]).head(8)[
    ["REF_DOC", "REF_PAGE_NO", "MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION",
     "AMOUNT", "FISCAL_YEAR"]].to_string())

print("\n=== BUDGET_PLAN blank rows sample ===")
print(df[df["BUDGET_PLAN"].str.strip() == ""][
    ["MINISTRY", "BUDGETARY_UNIT", "CATEGORY_LV1", "ITEM_DESCRIPTION", "AMOUNT"]].head(5).to_string())

print("\n=== ITEM_DESCRIPTION blank rows ===")
print(df[df["ITEM_DESCRIPTION"].str.strip() == ""][
    ["MINISTRY", "BUDGETARY_UNIT", "CATEGORY_LV1", "AMOUNT", "FISCAL_YEAR"]].to_string())

print("\n=== Check for mixed Thai/English whitespace or NBSP ===")
for c in df.columns:
    n = df[c].str.contains("\\u00a0|\\t|\\r", regex=True).sum()
    if n:
        print(f"{c}: {n} rows with NBSP/tab/CR")
