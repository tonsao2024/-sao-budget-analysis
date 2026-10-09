"""Scan 2: near-duplicate pairs that differ ONLY by spelling (digits/quantities excluded)."""
import re
import pandas as pd
from collections import defaultdict

df = pd.read_csv("budget_2566-2569.csv.gz", dtype=str, keep_default_na=False)


def lev(a, b, maxd=2):
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


def strip_digits(s):
    return re.sub(r"[0-9๐-๙]+", "#", s)


def scan_column(col, topn=50, maxd=2):
    vc = df[col].value_counts()
    vc = vc[vc.index.str.strip() != ""]
    groups = defaultdict(list)
    for val, cnt in vc.items():
        s = re.sub(r"\s+", "", val)
        if len(s) < 4:
            continue
        groups[(s[:5], len(s) // 2)].append((val, cnt))
    pairs = []
    for g in groups.values():
        if len(g) < 2 or len(g) > 80:
            continue
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                v1, c1 = g[i]
                v2, c2 = g[j]
                s1 = re.sub(r"\s+", "", v1)
                s2 = re.sub(r"\s+", "", v2)
                if abs(len(s1) - len(s2)) > maxd:
                    continue
                # skip pairs that are identical once digits are masked (quantity variants)
                if strip_digits(s1) == strip_digits(s2):
                    continue
                d = lev(s1, s2, maxd)
                if 1 <= d <= maxd:
                    pairs.append((min(c1, c2), max(c1, c2), v1, v2, d))
    pairs.sort(key=lambda x: -x[0])
    print(f"\n########## {col} : {len(pairs)} typo-candidate pairs, top {topn} ##########")
    for lo, hi, v1, v2, d in pairs[:topn]:
        c1, c2 = vc[v1], vc[v2]
        print(f"  [{d}] ({c1:>6,} vs {c2:>6,}) {v1!r}  <->  {v2!r}")


for c in ["BUDGETARY_UNIT", "ITEM_DESCRIPTION", "OUTPUT", "PROJECT",
          "CATEGORY_LV2", "CATEGORY_LV3", "CATEGORY_LV4", "CATEGORY_LV5", "CATEGORY_LV6"]:
    scan_column(c)
