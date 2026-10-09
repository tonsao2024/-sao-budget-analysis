"""Scan text columns for near-duplicate spelling/spacing variants (candidates for a fix mapping)."""
import re
import pandas as pd
from collections import defaultdict

df = pd.read_csv("budget_2566-2569.csv.gz", dtype=str, keep_default_na=False)


def lev(a, b, maxd=2):
    """Levenshtein with early exit."""
    if abs(len(a) - len(b)) > maxd:
        return maxd + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > maxd:
            return maxd + 1
        prev = cur
    return prev[-1]


def scan_column(col, topn=40):
    vc = df[col].value_counts()
    vc = vc[vc.index.str.strip() != ""]
    # group by (first 5 chars of space-stripped form, length bucket) to limit pairs
    groups = defaultdict(list)
    for val, cnt in vc.items():
        s = re.sub(r"\s+", "", val)
        if len(s) < 4:
            continue
        groups[(s[:5], len(s) // 2)].append((val, cnt))
    pairs = []
    for g in groups.values():
        if len(g) < 2 or len(g) > 60:
            continue
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                v1, c1 = g[i]
                v2, c2 = g[j]
                s1 = re.sub(r"\s+", "", v1)
                s2 = re.sub(r"\s+", "", v2)
                if abs(len(s1) - len(s2)) > 2:
                    continue
                d = lev(s1, s2, 2)
                if 1 <= d <= 2:
                    pairs.append((min(c1, c2), max(c1, c2), v1, v2, d))
    pairs.sort(key=lambda x: -x[0])
    print(f"\n########## {col} : {len(pairs)} candidate pairs, top {topn} ##########")
    for lo, hi, v1, v2, d in pairs[:topn]:
        c1, c2 = vc[v1], vc[v2]
        print(f"  [{d}] ({c1:>6,} vs {c2:>6,}) {v1!r}  <->  {v2!r}")


for c in ["MINISTRY", "BUDGET_PLAN", "STRATEGY", "MOTHER_PLAN",
          "CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3", "CATEGORY_LV4",
          "CATEGORY_LV5", "CATEGORY_LV6"]:
    scan_column(c, topn=25)

scan_column("BUDGETARY_UNIT", topn=40)
scan_column("ITEM_DESCRIPTION", topn=60)
