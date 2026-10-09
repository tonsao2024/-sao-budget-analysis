"""Round 3: remaining checks."""
import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 50)
pd.set_option("display.max_colwidth", 90)

df = pd.read_csv("budget_2566-2569.csv.gz", dtype=str, keep_default_na=False)
df["_amt"] = pd.to_numeric(df["AMOUNT"], errors="coerce")
df["_year"] = pd.to_numeric(df["FISCAL_YEAR"], errors="coerce")

print("=== MINISTRY full list ===")
print(df["MINISTRY"].value_counts().to_string())

print("\n=== STRATEGY values ===")
print(df["STRATEGY"].value_counts(dropna=False).to_string())

print("\n=== MOTHER_PLAN values ===")
print(df["MOTHER_PLAN"].value_counts(dropna=False).to_string())

print("\n=== NBSP / tab / CR check (string cols only) ===")
strcols = [c for c in df.columns if not c.startswith("_")]
for c in strcols:
    n = df[c].str.contains(" |\t|\r", regex=True).sum()
    if n:
        print(f"{c}: {n} rows with NBSP/tab/CR")
print("(done)")

print("\n=== OBLIGED? by year group ===")
df["_ygroup"] = pd.cut(df["_year"], [0, 2021, 2026, 2100],
                       labels=["<=2021", "2022-2026", ">2026"])
print(pd.crosstab(df["_ygroup"], df["OBLIGED?"]))

print("\n=== Rows with year <= 2005: what are they? ===")
old = df[df["_year"] <= 2005]
print(f"count={len(old):,}  sum={old['_amt'].sum()/1e9:,.2f}B")
print(old[["REF_DOC", "MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION", "AMOUNT",
           "FISCAL_YEAR", "OBLIGED?", "Source_Sheet"]].head(12).to_string())
print("\nREF_DOC of old rows:")
print(old["REF_DOC"].value_counts().head(10))

print("\n=== Rows with year 2006-2021: sample ===")
mid = df[(df["_year"] > 2005) & (df["_year"] <= 2021)]
print(f"count={len(mid):,}  sum={mid['_amt'].sum()/1e9:,.2f}B")
print(mid[["REF_DOC", "MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION", "AMOUNT",
           "FISCAL_YEAR", "Source_Sheet"]].head(8).to_string())
print("\nREF_DOC of mid rows (top 10):")
print(mid["REF_DOC"].value_counts().head(10))

print("\n=== Rows with year > 2026: are they ผูกพัน (OBLIGED=1)? ===")
fut = df[df["_year"] > 2026]
print(f"count={len(fut):,}  sum={fut['_amt'].sum()/1e9:,.2f}B")
print(pd.crosstab(fut["_year"], fut["OBLIGED?"]))
print("\nITEM_DESCRIPTION patterns in future-year rows:")
print(fut["ITEM_DESCRIPTION"].str.contains("ผูกพัน|สัญญา|Multi|ผูกพันตาม").value_counts())

print("\n=== CATEGORY_LV1 blank rows: what are they? ===")
blank1 = df[df["CATEGORY_LV1"].str.strip() == ""]
print(f"count={len(blank1):,}")
print(blank1[["MINISTRY", "BUDGETARY_UNIT", "BUDGET_PLAN", "ITEM_DESCRIPTION", "AMOUNT",
              "FISCAL_YEAR"]].head(8).to_string())

print("\n=== CATEGORY_LV1 = plan-name rows (misaligned?) ===")
oddcat = df[~df["CATEGORY_LV1"].isin(
    ["งบบุคลากร", "งบดำเนินงาน", "งบลงทุน", "งบเงินอุดหนุน", "งบรายจ่ายอื่น", ""])]
print(oddcat[["MINISTRY", "BUDGETARY_UNIT", "BUDGET_PLAN", "OUTPUT", "PROJECT",
              "CATEGORY_LV1", "ITEM_DESCRIPTION", "AMOUNT", "FISCAL_YEAR"]].to_string())

print("\n=== 'Total'/'total' rows in ITEM_DESCRIPTION ===")
tot = df[df["ITEM_DESCRIPTION"].str.contains("Total|total", regex=True)]
print(tot[["REF_DOC", "MINISTRY", "ITEM_DESCRIPTION", "AMOUNT", "FISCAL_YEAR"]].to_string())

print("\n=== 'ทั้งสิ้น' / 'ทั้งหมด' rows ===")
tot2 = df[df["ITEM_DESCRIPTION"].str.contains("ทั้งสิ้น|ทั้งหมด", regex=False)]
print(tot2[["MINISTRY", "ITEM_DESCRIPTION", "AMOUNT", "FISCAL_YEAR"]].head(10).to_string())

print("\n=== CROSS_FUNC? blank rows sample ===")
print(df[df["CROSS_FUNC?"].str.strip() == ""][
    ["MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION", "AMOUNT"]].head(5).to_string())

print("\n=== BUDGETARY_UNIT name consistency: อปท-related ===")
bu = df["BUDGETARY_UNIT"].value_counts()
print("units containing 'เทศบาล':", bu[bu.index.str.contains("เทศบาล")].sum())
print("units containing 'อบต':", bu[bu.index.str.contains("อบต|องค์การบริหารส่วนตำบล")].sum())
print("units containing 'อบจ':", bu[bu.index.str.contains("อบจ|องค์การบริหารส่วนจังหวัด")].sum())

print("\n=== Sanity: total AMOUNT main years vs known budget ===")
main = df[(df["_year"] >= 2023) & (df["_year"] <= 2026)]
print(main.groupby("_year")["_amt"].sum() / 1e9)
