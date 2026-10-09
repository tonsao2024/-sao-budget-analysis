#!/usr/bin/env python3
"""
Backend สำหรับเว็บวิเคราะห์งบประมาณไทย 2566-2569
ใช้ข้อมูลที่ clean แล้วจาก output/ เป็นฐาน

รัน:  python3 web/server.py   (แล้วเปิด http://localhost:8000)
"""
import os
import io
import math
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
STATIC = os.path.join(BASE, "static")
DATA_MAIN = os.path.join(ROOT, "output", "budget_2566-2569_clean.csv.gz")
DATA_COMM = os.path.join(ROOT, "output", "budget_2566-2569_commitments.csv.gz")

YEARS = [2022, 2023, 2024, 2025, 2026]
CATS = ["CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3",
        "CATEGORY_LV4", "CATEGORY_LV5", "CATEGORY_LV6"]

# ---------------------------------------------------------------- load data
print("⏳ กำลังโหลดข้อมูล...")
_main = pd.read_csv(DATA_MAIN, dtype=str, keep_default_na=False)
_comm = pd.read_csv(DATA_COMM, dtype=str, keep_default_na=False)
for d in (_main, _comm):
    d["AMOUNT"] = pd.to_numeric(d["AMOUNT"]).astype("int64")
    d["FISCAL_YEAR"] = pd.to_numeric(d["FISCAL_YEAR"]).astype("int16")
    d["OBLIGED?"] = d["OBLIGED?"].map({"True": True, "1": True, "False": False, "0": False, "": False})
    d["CROSS_FUNC?"] = d["CROSS_FUNC?"].map({"True": True, "1": True, "False": False, "0": False, "": False})
_main["source"] = "main"
_comm["source"] = "commitments"
all_df = pd.concat([_main, _comm], ignore_index=True)
main_df = _main

# คอลัมน์สำหรับค้นหาแบบ full-text
SEARCHABLE = ["MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION", "BUDGET_PLAN",
              "OUTPUT", "PROJECT", "STRATEGY", "MOTHER_PLAN"] + CATS
all_df["_search"] = (
    all_df[SEARCHABLE].fillna("").agg(" ".join, axis=1).str.lower()
)
print(f"✅ โหลดเสร็จ: ไฟล์หลัก {len(_main):,} แถว + ภาระผูกพัน {len(_comm):,} แถว = {len(all_df):,} แถว")

# ---------------------------------------------------------------- helpers
_cache = {}


def cached(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def clean(v):
    """แปลงค่า NaN/NaT/Numpy type → JSON-safe"""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, (bool,)):
        return bool(v)
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def rows_out(d, cols):
    return [{c: clean(r[c]) for c in cols} for r in d[cols].to_dict("records")]


# ---------------------------------------------------------------- meta
META = {
    "years": YEARS,
    "ministries": sorted(main_df["MINISTRY"].unique().tolist()),
    "cat_lv1": sorted([c for c in main_df["CATEGORY_LV1"].unique() if c]),
    "plans": sorted([c for c in main_df["BUDGET_PLAN"].unique() if c]),
    "strategies": sorted([c for c in main_df["STRATEGY"].unique() if c]),
    "mother_plans": sorted([c for c in main_df["MOTHER_PLAN"].unique() if c]),
    "flag_types": sorted(set(
        f for flags in all_df["dq_flag"] for f in flags.split(";") if f)),
    "counts": {
        "main_rows": int(len(main_df)),
        "commitments_rows": int(len(_comm)),
        "ministries": int(main_df["MINISTRY"].nunique()),
        "units": int(main_df["BUDGETARY_UNIT"].nunique()),
        "plans": int(main_df["BUDGET_PLAN"].nunique()),
    },
    "generated": "2026-10-09",
    "source_files": ["output/budget_2566-2569_clean.csv.gz",
                     "output/budget_2566-2569_commitments.csv.gz"],
}

# ---------------------------------------------------------------- app
app = FastAPI(title="Thai Budget Analyzer 2566-2569")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/health")
def health():
    return {"ok": True, "rows": int(len(all_df))}


@app.get("/api/meta")
def meta():
    return META


# ---------------------------------------------------------------- overview
def _overview(year):
    m = main_df
    my = m[m["FISCAL_YEAR"] == year]
    prev = m[m["FISCAL_YEAR"] == year - 1]
    total = int(my["AMOUNT"].sum())
    prev_total = int(prev["AMOUNT"].sum()) if len(prev) else None
    yoy = round((total - prev_total) / prev_total * 100, 2) if prev_total else None

    by_year = (m.groupby("FISCAL_YEAR")["AMOUNT"]
               .agg(["sum", "count"]).reset_index())
    yearly = [{"year": int(r["FISCAL_YEAR"]), "total": int(r["sum"]), "rows": int(r["count"])}
              for r in by_year.to_dict("records")]

    comm = _comm
    comm_yearly = (comm.groupby("FISCAL_YEAR")["AMOUNT"].sum()
                   .sort_values(ascending=False))
    comm_yearly_list = [{"year": int(y), "total": int(v)}
                        for y, v in comm_yearly.items()]

    def top_group(col, n, dfy):
        g = (dfy.groupby(col)["AMOUNT"].sum().sort_values(ascending=False).head(n))
        return [{"name": str(k) if k else "(ไม่ระบุ)", "total": int(v),
                 "share": round(v / total * 100, 2) if total else 0}
                for k, v in g.items()]

    min_rank = (my.groupby("MINISTRY")["AMOUNT"].sum()
                .sort_values(ascending=False))
    top_ministry = ({"name": str(min_rank.index[0]), "total": int(min_rank.iloc[0]),
                     "share": round(min_rank.iloc[0] / total * 100, 2)}
                    if len(min_rank) else None)
    cat_rank = (my[my["CATEGORY_LV1"] != ""].groupby("CATEGORY_LV1")["AMOUNT"]
                .sum().sort_values(ascending=False))
    top_cat = ({"name": str(cat_rank.index[0]), "total": int(cat_rank.iloc[0]),
                "share": round(cat_rank.iloc[0] / total * 100, 2)}
               if len(cat_rank) else None)

    # distribution (log10 buckets)
    pos = my[my["AMOUNT"] > 0]["AMOUNT"]
    edges = [10 ** i for i in range(0, 13)]
    labels, counts = [], []
    labels.append("0 บาท"); counts.append(int((my["AMOUNT"] == 0).sum()))
    labels.append("ติดลบ"); counts.append(int((my["AMOUNT"] < 0).sum()))
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        n = int(((pos >= lo) & (pos < hi)).sum())
        labels.append(f"{lo:,.0f}–{hi:,.0f}")
        counts.append(n)
    n = int((pos >= edges[-1]).sum())
    labels.append(f"≥ {edges[-1]:,.0f}"); counts.append(n)

    return {
        "year": year,
        "kpis": {
            "total": total,
            "prev_total": prev_total,
            "yoy_pct": yoy,
            "n_ministries": int(my["MINISTRY"].nunique()),
            "n_units": int(my["BUDGETARY_UNIT"].nunique()),
            "n_rows": int(len(my)),
            "n_plans": int(my["BUDGET_PLAN"].nunique()),
            "total_all_years": int(m["AMOUNT"].sum()),
            "comm_total": int(comm["AMOUNT"].sum()),
            "comm_rows": int(len(comm)),
            "flagged_rows": int((all_df["dq_flag"] != "").sum()),
            "top_ministry": top_ministry,
            "top_category": top_cat,
        },
        "yearly": yearly,
        "comm_yearly": comm_yearly_list,
        "top_ministries": top_group("MINISTRY", 12, my),
        "categories_lv1": top_group("CATEGORY_LV1", 10, my),
        "top_plans": top_group("BUDGET_PLAN", 12, my),
        "top_units": top_group("BUDGETARY_UNIT", 15, my),
        "distribution": {"labels": labels, "counts": counts},
    }


@app.get("/api/overview")
def overview(year: int = 2026):
    year = year if year in YEARS else 2026
    return cached(("overview", year), lambda: _overview(year))


# ---------------------------------------------------------------- search
SEARCH_COLS = ["FISCAL_YEAR", "MINISTRY", "BUDGETARY_UNIT", "ITEM_DESCRIPTION",
               "CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3", "AMOUNT",
               "OBLIGED?", "CROSS_FUNC?", "BUDGET_PLAN", "dq_flag", "source",
               "REF_DOC", "REF_PAGE_NO"]


def _apply_filters(q, years, ministry, cat1, plan, amt_min, amt_max,
                   obliged, cross, flagged, source):
    d = all_df
    if source == "main":
        d = d[d["source"] == "main"]
    elif source == "commitments":
        d = d[d["source"] == "commitments"]
    if q:
        d = d[d["_search"].str.contains(q.lower(), regex=False)]
    if years:
        d = d[d["FISCAL_YEAR"].isin(years)]
    if ministry:
        d = d[d["MINISTRY"] == ministry]
    if cat1:
        d = d[d["CATEGORY_LV1"] == cat1]
    if plan:
        d = d[d["BUDGET_PLAN"] == plan]
    if amt_min is not None:
        d = d[d["AMOUNT"] >= amt_min]
    if amt_max is not None:
        d = d[d["AMOUNT"] <= amt_max]
    if obliged is not None:
        d = d[d["OBLIGED?"] == obliged]
    if cross is not None:
        d = d[d["CROSS_FUNC?"] == cross]
    if flagged:
        d = d[d["dq_flag"] != ""]
    return d


@app.get("/api/search")
def search(q: str = "", years: str = "", ministry: str = "", cat1: str = "",
           plan: str = "", amt_min: float = None, amt_max: float = None,
           obliged: bool = None, cross: bool = None, flagged: bool = False,
           source: str = "all", sort: str = "AMOUNT", order: str = "desc",
           page: int = 1, per_page: int = 50):
    yrs = [int(y) for y in years.split(",") if y.strip().isdigit()] if years else []
    d = _apply_filters(q, yrs, ministry, cat1, plan, amt_min, amt_max,
                       obliged, cross, flagged, source)
    total = int(len(d))
    sort_col = sort if sort in ("AMOUNT", "FISCAL_YEAR", "MINISTRY",
                                "BUDGETARY_UNIT", "ITEM_DESCRIPTION") else "AMOUNT"
    d = d.sort_values(sort_col, ascending=(order == "asc"),
                      kind="mergesort", na_position="last")
    page = max(page, 1)
    per_page = min(max(per_page, 10), 200)
    start = (page - 1) * per_page
    page_rows = d.iloc[start:start + per_page]
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 1,
        "sum": int(d["AMOUNT"].sum()),
        "rows": rows_out(page_rows, SEARCH_COLS),
    }


@app.get("/api/export")
def export(q: str = "", years: str = "", ministry: str = "", cat1: str = "",
           plan: str = "", amt_min: float = None, amt_max: float = None,
           obliged: bool = None, cross: bool = None, flagged: bool = False,
           source: str = "all", sort: str = "AMOUNT", order: str = "desc"):
    yrs = [int(y) for y in years.split(",") if y.strip().isdigit()] if years else []
    d = _apply_filters(q, yrs, ministry, cat1, plan, amt_min, amt_max,
                       obliged, cross, flagged, source)
    d = d.sort_values(sort if sort in ("AMOUNT", "FISCAL_YEAR") else "AMOUNT",
                      ascending=(order == "asc"), kind="mergesort")
    d = d.head(100000)
    cols = [c for c in all_df.columns if c != "_search"]
    buf = io.StringIO()
    d[cols].to_csv(buf, index=False, encoding="utf-8-sig")
    fname = f"budget_export_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"})


# ---------------------------------------------------------------- ministries
def _ministries(year):
    m = main_df
    my = m[m["FISCAL_YEAR"] == year]
    pivot = m.pivot_table(index="MINISTRY", columns="FISCAL_YEAR",
                          values="AMOUNT", aggfunc="sum", fill_value=0)
    totals = my.groupby("MINISTRY")["AMOUNT"].sum().sort_values(ascending=False)
    grand = int(totals.sum())
    out = []
    for name, total in totals.items():
        row = {"name": name, "total": int(total),
               "share": round(total / grand * 100, 2) if grand else 0,
               "by_year": {int(y): int(pivot.loc[name, y]) if name in pivot.index and y in pivot.columns else 0
                           for y in YEARS},
               "n_units": int(my[my["MINISTRY"] == name]["BUDGETARY_UNIT"].nunique()),
               "n_rows": int((my["MINISTRY"] == name).sum())}
        out.append(row)
    return {"year": year, "grand_total": grand, "ministries": out}


@app.get("/api/ministries")
def ministries(year: int = 2026):
    year = year if year in YEARS else 2026
    return cached(("ministries", year), lambda: _ministries(year))


@app.get("/api/ministry")
def ministry_detail(name: str, year: int = 2026):
    year = year if year in YEARS else 2026
    key = ("ministry_detail", name, year)

    def build():
        m = main_df[main_df["MINISTRY"] == name]
        my = m[m["FISCAL_YEAR"] == year]
        by_year = {int(y): int(v) for y, v in
                   m.groupby("FISCAL_YEAR")["AMOUNT"].sum().items()}
        total = int(my["AMOUNT"].sum())
        grand_year = int(main_df[main_df["FISCAL_YEAR"] == year]["AMOUNT"].sum())
        top_units = (my.groupby("BUDGETARY_UNIT")["AMOUNT"].sum()
                     .sort_values(ascending=False).head(15))
        by_cat = (my[my["CATEGORY_LV1"] != ""].groupby("CATEGORY_LV1")["AMOUNT"]
                  .sum().sort_values(ascending=False))
        top_items = (my.sort_values("AMOUNT", ascending=False).head(20))
        rank = (main_df[main_df["FISCAL_YEAR"] == year]
                .groupby("MINISTRY")["AMOUNT"].sum()
                .sort_values(ascending=False))
        rank_pos = list(rank.index).index(name) + 1 if name in rank.index else None
        return {
            "name": name, "year": year,
            "total": total, "share": round(total / grand_year * 100, 2) if grand_year else 0,
            "rank": rank_pos, "n_ranked": int(len(rank)),
            "by_year": by_year,
            "n_rows": int(len(my)), "n_units": int(my["BUDGETARY_UNIT"].nunique()),
            "top_units": [{"name": str(k), "total": int(v)} for k, v in top_units.items()],
            "by_category": [{"name": str(k), "total": int(v)} for k, v in by_cat.items()],
            "top_items": rows_out(top_items, ["FISCAL_YEAR", "BUDGETARY_UNIT",
                                              "ITEM_DESCRIPTION", "CATEGORY_LV1",
                                              "AMOUNT", "OBLIGED?", "dq_flag"]),
        }
    return cached(key, build)


@app.get("/api/compare")
def compare(names: str, year: int = 2026):
    out = []
    for name in [n.strip() for n in names.split(",") if n.strip()][:4]:
        m = main_df[main_df["MINISTRY"] == name]
        by_year = {int(y): int(v) for y, v in
                   m.groupby("FISCAL_YEAR")["AMOUNT"].sum().items()}
        out.append({"name": name,
                    "by_year": by_year,
                    "total": int(sum(by_year.values()))})
    return {"series": out, "years": YEARS}


# ---------------------------------------------------------------- categories
def _cat_nodes(year, path):
    m = main_df[main_df["FISCAL_YEAR"] == year]
    path = [p for p in path.split("/") if p]
    level = len(path) + 1
    if level > 6:
        level = 6
    # filter by prefix
    d = m
    for i, p in enumerate(path):
        d = d[d[CATS[i]] == p]
    col = CATS[level - 1]
    g = (d[d[col] != ""].groupby(col)["AMOUNT"]
         .agg(["sum", "count"]).sort_values("sum", ascending=False))
    # check has_children: any deeper level non-empty among this node's rows
    nodes = []
    for name, r in g.iterrows():
        sub = d[d[col] == name]
        has_children = any((sub[CATS[j]] != "").any() for j in range(level, 6))
        nodes.append({"name": str(name), "total": int(r["sum"]),
                      "rows": int(r["count"]), "has_children": bool(has_children)})
    total = int(d["AMOUNT"].sum())
    return {
        "year": year, "level": level, "path": path,
        "nodes": nodes, "total": total, "rows": int(len(d)),
        "grand_total": int(main_df[main_df["FISCAL_YEAR"] == year]["AMOUNT"].sum()),
    }


@app.get("/api/categories")
def categories(year: int = 2026, path: str = ""):
    year = year if year in YEARS else 2026
    return cached(("cat", year, path), lambda: _cat_nodes(year, path))


@app.get("/api/category_rows")
def category_rows(year: int = 2026, path: str = "", n: int = 100):
    m = main_df[main_df["FISCAL_YEAR"] == year]
    path = [p for p in path.split("/") if p]
    d = m
    for i, p in enumerate(path):
        d = d[d[CATS[i]] == p]
    d = d.sort_values("AMOUNT", ascending=False).head(min(n, 500))
    return {"rows": rows_out(d, ["FISCAL_YEAR", "MINISTRY", "BUDGETARY_UNIT",
                                 "ITEM_DESCRIPTION", "AMOUNT", "OBLIGED?", "dq_flag"]),
            "total": int(d["AMOUNT"].sum()), "count": int(len(d))}


# ---------------------------------------------------------------- plans
def _plans(year, q):
    m = main_df
    my = m[m["FISCAL_YEAR"] == year]
    g = (my[my["BUDGET_PLAN"] != ""].groupby("BUDGET_PLAN")["AMOUNT"]
         .agg(["sum", "count"]).sort_values("sum", ascending=False))
    grand = int(my["AMOUNT"].sum())
    out = []
    for name, r in g.iterrows():
        if q and q.lower() not in name.lower():
            continue
        allp = m[m["BUDGET_PLAN"] == name]
        out.append({
            "name": name, "total": int(r["sum"]), "rows": int(r["count"]),
            "share": round(r["sum"] / grand * 100, 2) if grand else 0,
            "by_year": {int(y): int(v) for y, v in
                        allp.groupby("FISCAL_YEAR")["AMOUNT"].sum().items()},
        })
    return {"year": year, "grand_total": grand, "plans": out}


@app.get("/api/plans")
def plans(year: int = 2026, q: str = ""):
    year = year if year in YEARS else 2026
    return cached(("plans", year, q), lambda: _plans(year, q))


@app.get("/api/plan")
def plan_detail(name: str, year: int = 2026):
    year = year if year in YEARS else 2026
    key = ("plan_detail", name, year)

    def build():
        m = main_df[main_df["BUDGET_PLAN"] == name]
        my = m[m["FISCAL_YEAR"] == year]
        by_year = {int(y): int(v) for y, v in
                   m.groupby("FISCAL_YEAR")["AMOUNT"].sum().items()}
        total = int(my["AMOUNT"].sum())
        grand_year = int(main_df[main_df["FISCAL_YEAR"] == year]["AMOUNT"].sum())

        def topn(col, n, dfy, extra=None):
            g = (dfy[dfy[col] != ""].groupby(col)["AMOUNT"]
                 .sum().sort_values(ascending=False).head(n))
            return [{"name": str(k), "total": int(v)} for k, v in g.items()]

        top_items = my.sort_values("AMOUNT", ascending=False).head(15)
        return {
            "name": name, "year": year, "total": total,
            "share": round(total / grand_year * 100, 2) if grand_year else 0,
            "by_year": by_year, "n_rows": int(len(my)),
            "n_ministries": int(my["MINISTRY"].nunique()),
            "by_ministry": topn("MINISTRY", 10, my),
            "by_unit": topn("BUDGETARY_UNIT", 10, my),
            "by_strategy": topn("STRATEGY", 10, my),
            "by_mother_plan": topn("MOTHER_PLAN", 10, my),
            "top_items": rows_out(top_items, ["FISCAL_YEAR", "MINISTRY",
                                              "BUDGETARY_UNIT", "ITEM_DESCRIPTION",
                                              "AMOUNT", "dq_flag"]),
        }
    return cached(key, build)


# ---------------------------------------------------------------- commitments
@app.get("/api/commitments")
def commitments_summary():
    def build():
        c = _comm
        by_year = (c.groupby("FISCAL_YEAR")["AMOUNT"]
                   .agg(["sum", "count"]).sort_values("sum", ascending=False))
        by_min = (c.groupby("MINISTRY")["AMOUNT"].sum()
                  .sort_values(ascending=False).head(15))
        susp = c[c["FISCAL_YEAR"] <= 2021]
        imposs = c[c["FISCAL_YEAR"] <= 2005]
        return {
            "total": int(c["AMOUNT"].sum()),
            "rows": int(len(c)),
            "n_ministries": int(c["MINISTRY"].nunique()),
            "year_min": int(c["FISCAL_YEAR"].min()),
            "year_max": int(c["FISCAL_YEAR"].max()),
            "by_year": [{"year": int(y), "total": int(r["sum"]), "rows": int(r["count"])}
                        for y, r in by_year.iterrows()],
            "by_ministry": [{"name": str(k), "total": int(v)} for k, v in by_min.items()],
            "suspicious": {"rows": int(len(susp)), "total": int(susp["AMOUNT"].sum()),
                           "note": "ปี ≤ 2021 — น่าจะเป็น artifact จากการแปลงไฟล์ (ดู quarantine_review.csv.gz)"},
            "impossible": {"rows": int(len(imposs)), "total": int(imposs["AMOUNT"].sum()),
                           "note": "ปี 1967–2005 — เป็นไปไม่ได้ในเอกสารงบประมาณปี 2566–2569"},
        }
    return cached(("comm",), build)


@app.get("/api/commitments_rows")
def commitments_rows(q: str = "", year: int = None, ministry: str = "",
                     page: int = 1, per_page: int = 50):
    d = _comm
    if q:
        d = d[d["_search"].str.contains(q.lower(), regex=False)]
    if year is not None:
        d = d[d["FISCAL_YEAR"] == year]
    if ministry:
        d = d[d["MINISTRY"] == ministry]
    d = d.sort_values("AMOUNT", ascending=False, kind="mergesort")
    total = int(len(d))
    page = max(page, 1)
    per_page = min(max(per_page, 10), 200)
    start = (page - 1) * per_page
    rows = d.iloc[start:start + per_page]
    return {
        "total": total, "page": page, "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 1,
        "sum": int(d["AMOUNT"].sum()),
        "rows": rows_out(rows, SEARCH_COLS),
    }


# ---------------------------------------------------------------- quality
@app.get("/api/flags")
def flags(page: int = 1, per_page: int = 50, type: str = "", source: str = "all"):
    d = all_df[all_df["dq_flag"] != ""]
    if type:
        d = d[d["dq_flag"].str.contains(type, regex=False)]
    if source == "main":
        d = d[d["source"] == "main"]
    elif source == "commitments":
        d = d[d["source"] == "commitments"]
    counts = {}
    for flags in all_df["dq_flag"]:
        for f in flags.split(";"):
            if f:
                counts[f] = counts.get(f, 0) + 1
    d = d.sort_values("AMOUNT", ascending=False, kind="mergesort")
    total = int(len(d))
    page = max(page, 1)
    per_page = min(max(per_page, 10), 200)
    start = (page - 1) * per_page
    rows = d.iloc[start:start + per_page]
    return {
        "counts": dict(sorted(counts.items(), key=lambda x: -x[1])),
        "total": total, "page": page, "per_page": per_page,
        "pages": math.ceil(total / per_page) if per_page else 1,
        "rows": rows_out(rows, SEARCH_COLS),
    }


if __name__ == "__main__":
    print("🚀 เปิดเว็บวิเคราะห์งบประมาณที่ http://0.0.0.0:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
