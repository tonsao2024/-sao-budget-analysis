#!/usr/bin/env python3
"""
สร้างไฟล์ข้อมูลแบบ "columnar + dictionary" สำหรับเว็บ static (docs/)

ทำไม: ไฟล์ CSV.gz 12.4 MB ต้องแกะเป็นข้อความ 93 ล้านตัวอักษร แล้วให้ PapaParse
อ่านทีละแถว → เบราว์เซอร์ใช้เวลา ~5.8 วิ และกิน RAM ~1.1 GB (มือถืออาจค้าง/แครช)

รูปแบบใหม่: เก็บเป็น "คอลัมน์" + พจนานุกรมค่าที่ซ้ำ (dictionary encoding)
  ไฟล์ .json.gz เล็กกว่า และเบราว์เซอร์ใช้ JSON.parse (โค้ดเนทีฟ เร็วมาก)
  แล้วประกอบเป็นแถวเท่าที่ต้องใช้

ผลลัพธ์: docs/data/{main,comm}.cols.json.gz
"""
import gzip
import json
import os
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
DOCS_DATA = os.path.join(ROOT, "docs", "data")

# คอลัมน์ตัวเลข/บูลีน เก็บเป็นค่าตรง ๆ ไม่ต้องทำพจนานุกรม
NUM_COLS = {"AMOUNT", "FISCAL_YEAR"}
BOOL_COLS = {"OBLIGED?", "CROSS_FUNC?"}


def encode_column(series, name):
    """แปลง 1 คอลัมน์เป็นโครงสร้างแบบกะทัดรัด"""
    vals = series.tolist()
    if name in NUM_COLS:
        return {"t": "num", "v": vals}
    if name in BOOL_COLS:
        return {"t": "bool", "v": [1 if v in ("True", "1", True) else 0 for v in vals]}
    # dictionary: ค่าที่ไม่ซ้ำ + ดัชนี
    uniq = {}
    idx = []
    for v in vals:
        i = uniq.get(v)
        if i is None:
            i = len(uniq)
            uniq[v] = i
        idx.append(i)
    return {"t": "dict", "v": list(uniq.keys()), "i": idx}


def build(src_csv, dst_file, label):
    t0 = time.time()
    df = pd.read_csv(src_csv, dtype=str, keep_default_na=False)
    cols = list(df.columns)
    payload = {"cols": cols, "rows": len(df), "data": {}}
    for c in cols:
        payload["data"][c] = encode_column(df[c], c)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with gzip.open(dst_file, "wb", compresslevel=6) as f:
        f.write(raw)
    print(f"  {label}: {len(df):,} แถว | JSON {len(raw)/1e6:,.1f} MB "
          f"→ gz {os.path.getsize(dst_file)/1e6:,.2f} MB | {time.time()-t0:.1f} วิ")
    return os.path.getsize(dst_file)


def main():
    os.makedirs(DOCS_DATA, exist_ok=True)
    print("⏳ สร้างไฟล์ columnar สำหรับเว็บ static ...")
    s1 = build(os.path.join(OUT, "budget_2566-2569_clean.csv.gz"),
               os.path.join(DOCS_DATA, "main.cols.json.gz"), "ไฟล์หลัก")
    s2 = build(os.path.join(OUT, "budget_2566-2569_commitments.csv.gz"),
               os.path.join(DOCS_DATA, "comm.cols.json.gz"), "ภาระผูกพัน")
    old = (os.path.getsize(os.path.join(DOCS_DATA, "budget_2566-2569_clean.csv.gz")) +
           os.path.getsize(os.path.join(DOCS_DATA, "budget_2566-2569_commitments.csv.gz")))
    print(f"\n🎉 เสร็จ: CSV.gz เดิม {old/1e6:,.2f} MB → columnar {(s1+s2)/1e6:,.2f} MB "
          f"(ลดลง {(1-(s1+s2)/old)*100:.0f}%)")


if __name__ == "__main__":
    main()
