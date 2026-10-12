#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_water_budget.py — วิเคราะห์งบประมาณด้านการบริหารจัดการน้ำ
จากข้อมูลงบประมาณรายจ่าย ร่าง พ.ร.บ. ปีงบประมาณ 2566–2569 (2023–2026)

อ่านข้อมูลจาก:
    output/budget_2566-2569_clean.csv.gz        (ไฟล์หลัก — แถวงบประมาณรายปี + แถวภาระผูกพันในปี 2022–2026)
    output/budget_2566-2569_commitments.csv.gz  (ภาระผูกพันปีนอกช่วง 2022–2026)

เขียนผลลัพธ์ไปที่ output/water/ :
    water_budget_detail_2566-2569.csv.gz     รายละเอียดทุกรายการ (ระดับไอเทม) งบประมาณรายปี
    water_commitments_2566-2569.csv.gz       รายละเอียดภาระผูกพัน (OBLIGED?=True)
    summary_plan_year.csv                    ยอดตามแผนงาน × ปีงบประมาณ
    summary_scope_year.csv                   ยอดตามขอบเขต (A/B1/B2/B3) × ปีงบประมาณ
    summary_ministry_year.csv                ยอดตามกระทรวง × ปีงบประมาณ
    summary_unit_year.csv                    ยอดตามหน่วยงาน × ปีงบประมาณ
    summary_project_year.csv                 ยอดตามโครงการ × ปีงบประมาณ
    summary_category_year.csv                ยอดตามหมวดงบ (CATEGORY_LV1) × ปีงบประมาณ
    water_budget_2566-2569.xlsx              สมุดงาน Excel (ถ้ามี openpyxl)
    tables_for_report.md                     ตารางพร้อมใช้ในรายงาน
    (และคัดลอกไฟล์ detail ไป docs/data/ เพื่อใช้กับหน้าเว็บ)

นิยามขอบเขต "งานด้านการบริหารจัดการน้ำ"
    A  = แผนงานที่มีคำว่า "ทรัพยากรน้ำ" ในชื่อแผน (3 แผนงาน) — นับทั้งแผน
    B1 = รายการในแผนงานอื่นที่ "ชื่อโครงการ/ผลผลิต" เป็นงานด้านน้ำ (ผ่านกฎคำค้น + รายการยกเว้น)
    B2 = งบของ "หน่วยงานด้านน้ำ" (กรมชลประทาน กรมทรัพยากรน้ำ ฯลฯ) ที่ไปอยู่ในแผนงานอื่น
    B3 = รายการในแผนงานอื่นที่ "ชื่อไอเทม" เป็นงานด้านน้ำชัดเจน (เช่น เงินอุดหนุนประปาหมู่บ้านของ อปท.)
    นอกนั้น = ไม่นับเป็นงานด้านน้ำ (เช่น กรมเจ้าท่า/การเดินเรือ, ท่องเที่ยวทางน้ำ, ชื่อสถานที่)
"""

import csv
import io
import gzip
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(ROOT, "output", "budget_2566-2569_clean.csv.gz")
COMM = os.path.join(ROOT, "output", "budget_2566-2569_commitments.csv.gz")
OUTDIR = os.path.join(ROOT, "output", "water")
DOCSDATA = os.path.join(ROOT, "docs", "data")

YEARS = ["2022", "2023", "2024", "2025", "2026"]

# ---------------------------------------------------------------- Thai helpers
NAAM = "\u0e19\u0e49\u0e33"          # น้ำ (sara-am + mai-tho)
NAAM_OPT = "\u0e19\u0e49?\u0e33"     # น้ำ หรือ นำ (ตกไม้โท)
NAAM_BAD3 = "\u0e19\u0e4d\u0e49\u0e32"  # นํ้า (นิคหิต)


def self_norm(s: str) -> str:
    """ปรับคำไทยที่ 'เรา' พิมพ์ ให้เป็นรูปแบบเดียวกัน (ไม้โท + สระอำ)"""
    return (s.replace("\u0e19\u0e33\u0e49", NAAM)      # นำ้
             .replace(NAAM_BAD3, NAAM)                  # นํ้า
             .replace("\u0e19\u0e33", NAAM))            # นำ (ตกไม้โท) ในคำที่เราตั้งใจว่า น้ำ


def kw2re(kw: str) -> str:
    """แปลงคำค้นเป็น regex ที่ยอมให้ 'น้ำ' ตกไม้โทได้ (ข้อมูลต้นทางมีทั้ง น้ำ และ นำ)"""
    k = self_norm(kw).replace(NAAM, NAAM_OPT)
    return k


def data_norm(s: str) -> str:
    """คืนข้อความสำหรับแสดงผล/จัดกลุ่ม: แก้ น้ำ ที่ตกไม้โท/เรียงผิด เฉพาะคำที่ตรวจพบ"""
    s = s.replace("\u0e19\u0e33\u0e49", NAAM).replace(NAAM_BAD3, NAAM)
    for bad, good in DATA_FIX:
        s = s.replace(bad, good)
    return s


# คำที่ข้อมูลต้นทางตกไม้โท (ตรวจสอบด้วย eye แล้วว่าเป็น defect จริง ไม่ใช่คำว่า "นำ")
_P = "\u0e19\u0e33"      # นำ (ไม่มีไม้โท)
DATA_FIX = [
    # "น้ำ" ตกไม้โท (พบในชื่อหน่วยงานด้านน้ำ)
    ("\u0e17\u0e23\u0e31\u0e1e\u0e22\u0e32\u0e01\u0e23" + _P, "\u0e17\u0e23\u0e31\u0e1e\u0e22\u0e32\u0e01\u0e23" + NAAM),      # ทรัพยากรนำ -> ทรัพยากรน้ำ
    ("\u0e2d\u0e49\u0e2d\u0e22\u0e41\u0e25\u0e30" + _P + "\u0e15\u0e32\u0e25", "\u0e2d\u0e49\u0e2d\u0e22\u0e41\u0e25\u0e30" + NAAM + "\u0e15\u0e32\u0e25"),  # อ้อยและนำตาล -> น้ำตาล
    # รูปสะกดอื่นที่กระทบการจัดกลุ่มหน่วยงานในขอบเขตน้ำ (ตรวจแล้ว)
    ("\u0e01\u0e23\u0e21\u0e2a\u0e48\u0e07\u0e40\u0e2a\u0e23\u0e34\u0e21\u0e01\u0e32\u0e23\u0e1b\u0e01\u0e04\u0e23\u0e2d\u0e07\u0e17\u0e2d\u0e07\u0e16\u0e34\u0e48\u0e19",
     "\u0e01\u0e23\u0e21\u0e2a\u0e48\u0e07\u0e40\u0e2a\u0e23\u0e34\u0e21\u0e01\u0e32\u0e23\u0e1b\u0e01\u0e04\u0e23\u0e2d\u0e07\u0e17\u0e49\u0e2d\u0e07\u0e16\u0e34\u0e48\u0e19"),   # ทองถิ่น -> ท้องถิ่น
    ("\u0e01\u0e23\u0e21\u0e1b\u0e23\u0e30\u0e1b\u0e32\u0e19\u0e04\u0e23\u0e2b\u0e25\u0e27\u0e07",
     "\u0e01\u0e32\u0e23\u0e1b\u0e23\u0e30\u0e1b\u0e32\u0e19\u0e04\u0e23\u0e2b\u0e25\u0e27\u0e07"),                       # กรมประปานครหลวง -> การประปานครหลวง
    ("\u0e2a\u0e33\u0e19\u0e31\u0e01\u0e07\u0e32\u0e19\u0e1b\u0e0f\u0e34\u0e23\u0e39\u0e1b\u0e17\u0e35\u0e48\u0e14\u0e34\u0e19\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e40\u0e01\u0e29\u0e15\u0e23\u0e01\u0e23\u0e23\u0e21",
     "\u0e2a\u0e33\u0e19\u0e31\u0e01\u0e07\u0e32\u0e19\u0e01\u0e32\u0e23\u0e1b\u0e0f\u0e34\u0e23\u0e39\u0e1b\u0e17\u0e35\u0e48\u0e14\u0e34\u0e19\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e40\u0e01\u0e29\u0e15\u0e23\u0e01\u0e23\u0e23\u0e21"),  # สำนักงานปฏิรูปที่ดิน -> สำนักงานการปฏิรูปที่ดิน
    ("\u0e2a\u0e33\u0e19\u0e31\u0e01\u0e07\u0e32\u0e19\u0e2a\u0e20\u0e32\u0e19\u0e42\u0e22\u0e1a\u0e32\u0e22\u0e01\u0e32\u0e23\u0e2d\u0e38\u0e14\u0e21\u0e28\u0e36\u0e01\u0e29\u0e32 \u0e27\u0e34\u0e17\u0e22\u0e32\u0e28\u0e32\u0e2a\u0e15\u0e23\u0e4c \u0e27\u0e34\u0e08\u0e31\u0e22\u0e41\u0e25\u0e30\u0e19\u0e27\u0e31\u0e15\u0e01\u0e23\u0e23\u0e21",
     "\u0e2a\u0e33\u0e19\u0e31\u0e01\u0e07\u0e32\u0e19\u0e2a\u0e20\u0e32\u0e19\u0e42\u0e22\u0e1a\u0e32\u0e22\u0e01\u0e32\u0e23\u0e2d\u0e38\u0e14\u0e21\u0e28\u0e36\u0e01\u0e29\u0e32 \u0e27\u0e34\u0e17\u0e22\u0e32\u0e28\u0e32\u0e2a\u0e15\u0e23\u0e4c \u0e27\u0e34\u0e08\u0e31\u0e22\u0e41\u0e25\u0e30\u0e19\u0e27\u0e31\u0e15\u0e01\u0e23\u0e23\u0e21\u0e41\u0e2b\u0e48\u0e07\u0e0a\u0e32\u0e15\u0e34"),
     # สอวช. (รูปย่อ -> รูปเต็ม)
    ("\u0e08\u0e31\u0e07\u0e2b\u0e27\u0e31\u0e14\u0e19\u0e04\u0e23\u0e2a\u0e27\u0e23\u0e23\u0e04",
     "\u0e08\u0e31\u0e07\u0e2b\u0e27\u0e31\u0e14\u0e19\u0e04\u0e23\u0e2a\u0e27\u0e23\u0e23\u0e04\u0e4c"),                      # จังหวัดนครสวรรค -> นครสวรรค์
    ("\u0e01\u0e25\u0e48\u0e21\u0e08\u0e31\u0e07\u0e2b\u0e27\u0e31\u0e14", "\u0e01\u0e25\u0e38\u0e48\u0e21\u0e08\u0e31\u0e07\u0e2b\u0e27\u0e31\u0e14"),                  # กล่มจังหวัด -> กลุ่มจังหวัด
]

# ---------------------------------------------------------------- scope rules
CORE_PLAN_RE = re.compile(kw2re("ทรัพยากรน้ำ"))

# หน่วยงานด้านน้ำ (B2) — เรียงจากเฉพาะเจาะจงมากไปน้อย
WATER_UNIT_RE = [
    re.compile(kw2re("กรมชลประทาน")),
    re.compile(kw2re("กรมทรัพยากรน้ำบาดาล")),
    re.compile(kw2re("กรมทรัพยากรน้ำ")),
    re.compile(kw2re("สำนักงานทรัพยากรน้ำแห่งชาติ")),
    re.compile(kw2re("สถาบันสารสนเทศทรัพยากรน้ำ")),
    re.compile(kw2re("องค์การจัดการน้ำเสีย")),
    re.compile(kw2re("กรมฝนหลวงและการบินเกษตร")),
    re.compile(kw2re("การประปานครหลวง")),
    re.compile(kw2re("การประปาส่วนภูมิภาค")),
]

# ---- B1: ชื่อโครงการ/ผลผลิตที่เป็นงานด้านน้ำ
B1_INCLUDE = [
    "ชลประทาน", "อ่างเก็บน้ำ", "เขื่อน", "ฝาย", "ประตูระบายน้ำ", "คันกั้นน้ำ", "พนังกั้นน้ำ",
    "น้ำบาดาล", "น้ำใต้ดิน", "ลุ่มน้ำ", "แม่น้ำ", "คลอง", "น้ำท่วม", "อุทกภัย", "อุทก", "ภัยแล้ง",
    "น้ำเสีย", "บำบัดน้ำ", "คุณภาพน้ำ", "ประปา", "ทรัพยากรน้ำ", "แหล่งน้ำ", "บริหารจัดการน้ำ",
    "จัดการน้ำ", "ระบายน้ำ", "กักเก็บน้ำ", "ส่งน้ำ", "น้ำดิบ", "น้ำอุปโภค", "ฝนหลวง", "ชุ่มน้ำ",
    "เติมน้ำ", "ชะลอน้ำ", "น้ำชุมชน", "ข้อมูลน้ำ", "น้ำฝน", "น้ำและ", "ระบบน้ำ",
]
# รายการยกเว้น (false positive ที่ตรวจด้วยตาแล้ว)
B1_EXCLUDE = [
    "น้ำตาล", "น้ำมัน", "น้ำหนัก", "สีน้ำเงิน", "ปากน้ำ", "สัตว์น้ำ", "น้ำเชื้อ", "ลุ่มแม่น้ำโขง",
    "ปัญญานันทภิกขุชลประทาน",          # ชื่อสถานที่ (ศูนย์การแพทย์)
    "ท่องเที่ยวสำราญทางน้ำ",           # การท่องเที่ยว
    "ศึกษาธรรมชาติ",                   # ทางเดินศึกษาธรรมชาติ
    "ขนส่งทางน้ำ", "เดินเรือ", "ร่องน้ำ", "ท่าเทียบเรือ", "ท่าเรือ",   # คมนาคมทางน้ำ (กรมเจ้าท่า)
    "รับจำนำ", "รุกล้ำ",
    "ชำระหนี้เงินกู้",                  # หนี้เงินกู้รถไฟ (ชื่อเส้นทางมีคำว่า "คลองสิบเก้า")
]

# ---- B3: ชื่อไอเทมที่เป็นงานด้านน้ำชัดเจน (ใช้เฉพาะรายการที่ไม่อยู่ใน A/B1/B2 แล้ว)
B3_INCLUDE = [
    "แหล่งกักเก็บน้ำ", "กักเก็บน้ำ", "ขาดแคลนน้ำอุปโภคบริโภค", "สถานีสูบน้ำด้วยไฟฟ้า",
    "ประปาหมู่บ้าน", "ระบบประปาบาดาล", "แหล่งน้ำบาดาล", "บ่อบาดาล", "ชุดเจาะสำรวจแหล่งน้ำบาดาล",
    "ขุดลอกแหล่งน้ำ", "ขุดลอกคลอง", "ขุดลอกคูคลอง", "ขุดลอกหนอง", "ขุดลอกอ่างเก็บน้ำ",
    "ประตูระบายน้ำ", "อ่างเก็บน้ำ", "คันกั้นน้ำ", "พนังกั้นน้ำ", "ทำนบ",
    "ระบบบำบัดน้ำเสีย",
]
B3_EXCLUDE = [
    "หนองน้ำใส", "บึงกาฬ", "ร่องน้ำ", "สะพาน", "ทางหลวง", "เครื่องสูบน้ำ", "รถปฏิบัติการ",
    "รถบรรเทา", "ค่าประปา", "ค่าน้ำประปา", "สัมภาระ", "ตรวจสอบสิ่งของ",
    "ถนน", "ลาดยาง", "ทางเท้า", "จราจร", "รถบรรทุก",        # งานถนนที่อ้างชื่อแหล่งน้ำ
]


def is_water_unit(unit: str) -> bool:
    return any(r.search(unit) for r in WATER_UNIT_RE)


def classify(row):
    """คืน (scope, เหตุผล) — 'A'|'B1'|'B2'|'B3'|'' """
    plan = row["BUDGET_PLAN"]
    if CORE_PLAN_RE.search(plan):
        return "A", "แผนงานด้านทรัพยากรน้ำ"
    pr = row["PROJECT"]
    if pr and any(k in pr for k in B1_INCLUDE) and not any(k in pr for k in B1_EXCLUDE):
        return "B1", "ชื่อโครงการเป็นงานด้านน้ำ (แผนงานอื่น)"
    if is_water_unit(row["BUDGETARY_UNIT"]):
        return "B2", "งบของหน่วยงานด้านน้ำในแผนงานอื่น"
    item = row["ITEM_DESCRIPTION"]
    if any(k in item for k in B3_INCLUDE) and not any(k in item for k in B3_EXCLUDE):
        return "B3", "รายการด้านน้ำในแผนงานอื่น (ระดับไอเทม)"
    return "", ""


SCOPE_LABEL = {
    "A": "A · แผนงานด้านทรัพยากรน้ำ",
    "B1": "B1 · โครงการด้านน้ำในแผนงานอื่น",
    "B2": "B2 · งบหน่วยงานด้านน้ำในแผนงานอื่น",
    "B3": "B3 · รายการด้านน้ำระดับไอเทมในแผนงานอื่น",
}

DETAIL_COLS = [
    "water_scope", "scope_reason", "FISCAL_YEAR", "BUDGET_PLAN", "MINISTRY", "BUDGETARY_UNIT",
    "PROJECT", "OUTPUT", "CATEGORY_LV1", "CATEGORY_LV2", "CATEGORY_LV3", "CATEGORY_LV4",
    "CATEGORY_LV5", "CATEGORY_LV6", "ITEM_DESCRIPTION", "AMOUNT", "CROSS_FUNC?", "OBLIGED?",
    "REF_DOC", "REF_PAGE_NO", "Source_Sheet", "dq_flag",
]


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield row


def amount_of(row):
    try:
        return float(row["AMOUNT"] or 0)
    except ValueError:
        return 0.0


def write_csv(path, cols, rows):
    # mtime=0 + ไม่ฝังชื่อไฟล์ -> ไฟล์ .gz คงที่แบบไบต์ต่อไบต์ รันซ้ำไม่เกิด diff ปลอม
    with open(path, "wb") as raw, \
         gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz, \
         io.TextIOWrapper(gz, encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_plain_csv(path, cols, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(r)


def thb(v):
    """รูปแบบเงินไทยแบบย่อ"""
    a = abs(v)
    if a >= 1e12:
        return f"{v/1e12:,.3f} ล้านล้านบาท"
    if a >= 1e9:
        return f"{v/1e9:,.3f} พันล้านบาท"
    if a >= 1e6:
        return f"{v/1e6:,.2f} ล้านบาท"
    return f"{v:,.0f} บาท"


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    os.makedirs(DOCSDATA, exist_ok=True)

    detail_annual, detail_obliged = [], []
    scope_plan = defaultdict(float)        # (scope, plan, year) -> amount
    scope_year = defaultdict(float)
    plan_year = defaultdict(float)         # (plan, year) - เฉพาะ scope A
    min_year = defaultdict(float)          # (ministry, year) - scope A+B
    min_scope = defaultdict(float)
    unit_year = defaultdict(float)
    proj_year = defaultdict(float)
    cat_year = defaultdict(float)
    n_rows = Counter()
    matched_plans = Counter()

    for row in read_rows(MAIN):
        scope, reason = classify(row)
        if not scope:
            continue
        y = row["FISCAL_YEAR"]
        amt = amount_of(row)
        out = dict(row)
        out["BUDGET_PLAN"] = data_norm(row["BUDGET_PLAN"])
        out["BUDGETARY_UNIT"] = data_norm(row["BUDGETARY_UNIT"])
        out["MINISTRY"] = data_norm(row["MINISTRY"])
        out["water_scope"] = scope
        out["scope_reason"] = reason
        out["OBLIGED?"] = row["OBLIGED?"]

        if row["OBLIGED?"] == "True":
            detail_obliged.append(out)
            continue

        detail_annual.append(out)
        n_rows[scope] += 1
        scope_year[(scope, y)] += amt
        scope_plan[(scope, out["BUDGET_PLAN"], y)] += amt
        min_year[(out["MINISTRY"], y)] += amt
        min_scope[(out["MINISTRY"], scope)] += amt
        unit_year[(out["BUDGETARY_UNIT"], y)] += amt
        proj_year[(out["PROJECT"] or "(ไม่ระบุโครงการ)", y)] += amt
        cat_year[(out["CATEGORY_LV1"] or "(ไม่ระบุ)", y)] += amt
        if scope == "A":
            plan_year[(out["BUDGET_PLAN"], y)] += amt
            matched_plans[out["BUDGET_PLAN"]] += 1

    # ภาระผูกพันปีนอกช่วง (ไฟล์ commitments) ในขอบเขตน้ำ
    for row in read_rows(COMM):
        scope, reason = classify(row)
        if not scope:
            continue
        out = dict(row)
        out["BUDGET_PLAN"] = data_norm(row["BUDGET_PLAN"])
        out["BUDGETARY_UNIT"] = data_norm(row["BUDGETARY_UNIT"])
        out["MINISTRY"] = data_norm(row["MINISTRY"])
        out["water_scope"] = scope
        out["scope_reason"] = reason
        detail_obliged.append(out)

    # ---------------- เขียนไฟล์
    detail_annual.sort(key=lambda r: (r["FISCAL_YEAR"], r["water_scope"], r["BUDGET_PLAN"],
                                      r["MINISTRY"], r["BUDGETARY_UNIT"], -amount_of(r)))
    write_csv(os.path.join(OUTDIR, "water_budget_detail_2566-2569.csv.gz"), DETAIL_COLS, detail_annual)
    write_csv(os.path.join(OUTDIR, "water_commitments_2566-2569.csv.gz"), DETAIL_COLS, detail_obliged)
    # สำเนาสำหรับหน้าเว็บ (สถิติ static) — ไฟล์งบรายปี ภาระผูกพัน และไฟล์ Excel ให้ดาวน์โหลด
    for fname in ("water_budget_detail_2566-2569.csv.gz",
                  "water_commitments_2566-2569.csv.gz"):
        try:
            with open(os.path.join(OUTDIR, fname), "rb") as src, \
                 open(os.path.join(DOCSDATA, fname), "wb") as dst:
                dst.write(src.read())
        except OSError as exc:  # pragma: no cover
            print("  ! คัดลอกไฟล์ไป docs/data ไม่ได้:", exc)

    # ---------------- สรุปตาราง
    plans = sorted({p for (s, p, y) in scope_plan if s == "A"})
    scopes = ["A", "B1", "B2", "B3"]

    def row_of(getter, keys):
        return [getter(k) for k in keys]

    # 1) แผนงาน × ปี (scope A) — เรียงจากยอดรวมมากไปน้อย
    order = sorted(plans, key=lambda p: -sum(plan_year[(p, y)] for y in YEARS))
    rows = []
    for p in order:
        r = [p, sum(a for (pp, y), a in plan_year.items() if pp == p)]
        r += [plan_year.get((p, y), 0) for y in YEARS]
        rows.append(r)
    write_plain_csv(os.path.join(OUTDIR, "summary_plan_year.csv"),
                    ["แผนงาน"] + [f"ปี {y} (บาท)" for y in YEARS] + ["รวม (บาท)"], rows)

    # 2) ขอบเขต × ปี
    rows = []
    for s in scopes:
        r = [SCOPE_LABEL[s]]
        r += [scope_year.get((s, y), 0) for y in YEARS]
        r.append(sum(scope_year.get((s, y), 0) for y in YEARS))
        rows.append(r)
    r = ["รวมทั้งขอบเขตน้ำ"]
    r += [sum(scope_year.get((s, y), 0) for s in scopes) for y in YEARS]
    r.append(sum(scope_year.values()))
    rows.append(r)
    write_plain_csv(os.path.join(OUTDIR, "summary_scope_year.csv"),
                    ["ขอบเขต"] + [f"ปี {y} (บาท)" for y in YEARS] + ["รวม (บาท)"], rows)

    # 3) กระทรวง × ปี
    mins = sorted({m for (m, y) in min_year}, key=lambda m: -sum(
        a for (mm, y), a in min_year.items() if mm == m))
    rows = []
    for m in mins:
        r = [m] + [min_year.get((m, y), 0) for y in YEARS]
        r.append(sum(min_year.get((m, y), 0) for y in YEARS))
        rows.append(r)
    write_plain_csv(os.path.join(OUTDIR, "summary_ministry_year.csv"),
                    ["กระทรวง"] + [f"ปี {y} (บาท)" for y in YEARS] + ["รวม (บาท)"], rows)

    # 4) หน่วยงาน × ปี
    units = sorted({u for (u, y) in unit_year}, key=lambda u: -sum(
        a for (uu, y), a in unit_year.items() if uu == u))
    rows = []
    for u in units:
        r = [u] + [unit_year.get((u, y), 0) for y in YEARS]
        r.append(sum(unit_year.get((u, y), 0) for y in YEARS))
        rows.append(r)
    write_plain_csv(os.path.join(OUTDIR, "summary_unit_year.csv"),
                    ["หน่วยงาน"] + [f"ปี {y} (บาท)" for y in YEARS] + ["รวม (บาท)"], rows)

    # 5) โครงการ × ปี (เฉพาะโครงการที่มียอดรวม >= 100 ลบ.)
    projs = sorted({p for (p, y) in proj_year}, key=lambda p: -sum(
        a for (pp, y), a in proj_year.items() if pp == p))
    rows = []
    for p in projs:
        tot = sum(a for (pp, y), a in proj_year.items() if pp == p)
        if tot < 100e6:
            continue
        r = [p] + [proj_year.get((p, y), 0) for y in YEARS]
        r.append(tot)
        rows.append(r)
    write_plain_csv(os.path.join(OUTDIR, "summary_project_year.csv"),
                    ["โครงการ"] + [f"ปี {y} (บาท)" for y in YEARS] + ["รวม (บาท)"], rows)

    # 6) หมวดงบ × ปี
    cats = sorted({c for (c, y) in cat_year}, key=lambda c: -sum(
        a for (cc, y), a in cat_year.items() if cc == c))
    rows = []
    for c in cats:
        r = [c] + [cat_year.get((c, y), 0) for y in YEARS]
        r.append(sum(cat_year.get((c, y), 0) for y in YEARS))
        rows.append(r)
    write_plain_csv(os.path.join(OUTDIR, "summary_category_year.csv"),
                    ["หมวดงบ (CATEGORY_LV1)"] + [f"ปี {y} (บาท)" for y in YEARS] + ["รวม (บาท)"], rows)

    # ---------------- Excel
    write_xlsx(os.path.join(OUTDIR, "water_budget_2566-2569.xlsx"),
               detail_annual, detail_obliged, plan_year, scope_year, min_year, unit_year,
               proj_year, cat_year, YEARS)
    # คัดลอกไฟล์ Excel (สร้างเสร็จแล้ว) ไปให้หน้าเว็บดาวน์โหลด
    try:
        with open(os.path.join(OUTDIR, "water_budget_2566-2569.xlsx"), "rb") as src, \
             open(os.path.join(DOCSDATA, "water_budget_2566-2569.xlsx"), "wb") as dst:
            dst.write(src.read())
    except OSError as exc:  # pragma: no cover
        print("  ! คัดลอกไฟล์ Excel ไป docs/data ไม่ได้:", exc)

    # ---------------- ตาราง markdown สำหรับรายงาน
    write_md_tables(os.path.join(OUTDIR, "tables_for_report.md"),
                    detail_annual, detail_obliged, plan_year, scope_year, min_year, unit_year,
                    proj_year, cat_year, YEARS)

    # ---------------- สรุปออกหน้าจอ
    print("=" * 78)
    print("สรุปงบประมาณด้านการบริหารจัดการน้ำ (งบรายปี OBLIGED?=0)")
    print("=" * 78)
    total = sum(scope_year.values())
    print(f"รวมทั้งสิ้น {thb(total)}  ({len(detail_annual):,} รายการ)")
    for s in scopes:
        v = sum(scope_year.get((s, y), 0) for y in YEARS)
        print(f"  {SCOPE_LABEL[s]:<46} {thb(v):>22}  {n_rows[s]:>6,} รายการ")
    print("\nรายปี:")
    for y in YEARS:
        v = sum(scope_year.get((s, y), 0) for s in scopes)
        print(f"  ปี {y} (พ.ศ. {int(y)+543}): {thb(v):>22}")
    print("\nไฟล์ผลลัพธ์อยู่ใน output/water/:")
    for f in sorted(os.listdir(OUTDIR)):
        print("  -", f)


def write_xlsx(path, detail_annual, detail_obliged, plan_year, scope_year, min_year, unit_year,
               proj_year, cat_year, years):
    """สร้างสมุดงาน Excel สำหรับส่งมอบ (หัวตารางภาษาไทย + ชีตแยกขอบเขต + ตัวกรอง + แผนภูมิ)"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        from openpyxl.formatting.rule import DataBarRule
        from openpyxl.chart import BarChart, Reference
    except ImportError:
        print("  ! ไม่มี openpyxl — ข้ามการสร้างไฟล์ xlsx (ติดตั้งด้วย pip install openpyxl)")
        return

    SCOPES = ["A", "B1", "B2", "B3"]
    SNAME = {"A": "A · แผนงานด้านทรัพยากรน้ำ",
             "B1": "B1 · โครงการด้านน้ำในแผนงานอื่น",
             "B2": "B2 · งบหน่วยงานด้านน้ำในแผนงานอื่น",
             "B3": "B3 · รายการด้านน้ำระดับไอเทม"}
    SHORT = {"A": "A แผนงานน้ำ", "B1": "B1 โครงการนอกแผน",
             "B2": "B2 หน่วยงานนอกแผน", "B3": "B3 ไอเทมในแผนอื่น"}
    # ปีที่มีข้อมูลจริง (ตัดปีที่ไม่มีงบรายปีออก เช่น 2565)
    years = [y for y in years if any(scope_year.get((s, y), 0) for s in SCOPES)]
    ylabel = {y: f"ปี {int(y) + 543}" for y in years}

    HEAD_FILL = PatternFill("solid", fgColor="1F4E79")
    HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)
    TITLE_FONT = Font(bold=True, size=14, color="1F4E79")
    NOTE_FONT = Font(italic=True, size=10, color="555555")
    TOTAL_FILL = PatternFill("solid", fgColor="DDEBF7")
    BOLD = Font(bold=True)
    YEARFMT = "0"
    MONEYFMT = "#,##0"

    def thai_year(cy):
        try:
            return int(cy) + 543
        except (TypeError, ValueError):
            return cy

    def to_num(v):
        try:
            f = float(v or 0)
        except (TypeError, ValueError):
            return 0
        return int(f) if f == int(f) else f

    def add_sheet(title, cols, rows, widths=None, money_cols=(), year_cols=(),
                  autofilter=True, total_row=None, data_bar_cols=(), ncols=None):
        ws = wb.create_sheet(title)
        ws.append(cols)
        for c in range(1, len(cols) + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = HEAD_FONT
            cell.fill = HEAD_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for r in rows:
            ws.append(r)
        ws.row_dimensions[1].height = 30
        if total_row is not None:
            ws.append(total_row)
            for c in range(1, len(cols) + 1):
                ws.cell(row=ws.max_row, column=c).font = BOLD
                ws.cell(row=ws.max_row, column=c).fill = TOTAL_FILL
        for i, w in enumerate(widths or [], start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        last_data = ws.max_row - (1 if total_row is not None else 0)
        for col in money_cols:
            for r in range(2, last_data + 1):
                ws.cell(row=r, column=col).number_format = MONEYFMT
        for col in year_cols:
            for r in range(2, last_data + 1):
                ws.cell(row=r, column=col).number_format = YEARFMT
        if total_row is not None:
            # แถวรวมเป็นจำนวนเงินทุกคอลัมน์ตัวเลข (เว้นคอลัมน์แรกที่เป็นชื่อ)
            for col in range(2, len(cols) + 1):
                if isinstance(ws.cell(row=ws.max_row, column=col).value, (int, float)):
                    ws.cell(row=ws.max_row, column=col).number_format = MONEYFMT
        if autofilter and ws.max_row >= 2:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{last_data}"
        for col in data_bar_cols:
            letter = get_column_letter(col)
            ws.conditional_formatting.add(f"{letter}2:{letter}{last_data}",
                                          DataBarRule(start_type="num", start_value=0,
                                                      end_type="max", color="5B9BD5"))
        ws.freeze_panes = "A2"
        return ws

    wb = Workbook()
    grants = sum(scope_year.values())
    by_year = {y: sum(scope_year.get((s, y), 0) for s in SCOPES) for y in years}

    # ---------------- 1) ชีตคำอธิบาย ----------------
    ws = wb.active
    ws.title = "อ่านก่อน"
    ws.column_dimensions["A"].width = 118
    lines = [
        ("T", "งบประมาณด้านการบริหารจัดการน้ำ พ.ศ. 2566–2569"),
        ("", ""),
        ("B", "ที่มาของข้อมูล"),
        ("", "ข้อมูลงบประมาณรายจ่ายของหน่วยรับงบประมาณทุกกระทรวง จากเอกสาร “ร่างพระราชบัญญัติงบประมาณรายจ่าย "
             "ประจำปีงบประมาณ พ.ศ. 2566–2569 (ฉบับที่ 3–4)” ซึ่งผ่านการ clean และตรวจคุณภาพแล้ว "
             "(ไฟล์ต้นทาง: output/budget_2566-2569_clean.csv.gz)"),
        ("", "ข้อมูลนี้เป็น “ร่าง พ.ร.บ.” ไม่ใช่ฉบับประกาศใช้ และครอบคลุมประมาณ 94% ของวงเงินงบประมาณที่ประกาศ "
             "จึงใช้เปรียบเทียบแนวโน้มได้ แต่ไม่ใช่ยอดงบประมาณทั้งประเทศ"),
        ("", "ในไฟล์นี้แสดงเฉพาะ “งบประมาณรายจ่ายรายปี” (OBLIGED?=False) เท่านั้น — ตารางภาระผูกพันข้ามปี "
             "(สัญญาที่ผูกพันไว้แล้ว) แยกอยู่ชีต “ภาระผูกพัน” และห้ามนำมารวมกับงบรายปี"),
        ("", "หมายเหตุ: ไม่มีข้อมูลงบรายปี 2565 ในชุดข้อมูล (มีแต่แถวภาระผูกพัน) จึงเริ่มที่ พ.ศ. 2566"),
        ("", ""),
        ("B", "นิยามขอบเขต (ดูคอลัมน์ “ขอบเขต” และ “เหตุผลขอบเขต” ในชีตรายละเอียด)"),
        ("", "A  = แผนงานที่มีชื่อว่า “ทรัพยากรน้ำ” ทั้งแผนงาน (3 แผนงาน) — งบของแผนงานน้ำโดยตรง"),
        ("", "B1 = โครงการที่ชื่อบ่งชี้งานน้ำ (ชลประทาน/อ่างเก็บน้ำ/เขื่อน/ฝาย/บาดาล/ลุ่มน้ำ/แม่น้ำ/คลอง/น้ำท่วม/"
             "อุทกภัย/ภัยแล้ง/น้ำเสีย/ประปา/แหล่งน้ำ/ระบบกระจายน้ำ ฯลฯ) แต่ถูกตั้งงบในแผนงานอื่น"),
        ("", "B2 = งบของหน่วยงานด้านน้ำ (กรมชลประทาน กรมทรัพยากรน้ำ กรมทรัพยากรน้ำบาดาล สทนช. สสน. "
             "องค์การจัดการน้ำเสีย กรมฝนหลวง การประปา ฯลฯ) ที่ไปอยู่ในแผนงานอื่น เช่น เงินเดือนในแผนงานบุคลากรภาครัฐ"),
        ("", "B3 = รายการระดับไอเทมที่เป็นงานน้ำชัดเจน (เช่น เงินอุดหนุนประปาหมู่บ้าน/สถานีสูบน้ำด้วยไฟฟ้า/"
             "แหล่งกักเก็บน้ำให้ อปท. ขุดลอก ระบบบำบัดน้ำเสีย) ในแผนงานอื่น"),
        ("", "ไม่นับ: งานเดินเรือ/ขนส่งทางน้ำ/ท่องเที่ยวทางน้ำ, ถนนที่ชื่ออ้างอิงแหล่งน้ำ, รถดับเพลิงพร้อมเครื่องสูบน้ำ, "
             "โครงการชำระหนี้เงินกู้ และรายการที่ชื่อมีคำว่า “น้ำ” แต่ไม่ใช่งานน้ำ (น้ำตาล น้ำมัน น้ำหนัก)"),
        ("", ""),
        ("B", f"ยอดรวมในไฟล์นี้ — งานด้านน้ำ {grants / 1e9:,.3f} พันล้านบาท ({len(detail_annual):,} รายการ)"),
        ("", " · ".join(f"พ.ศ. {int(y) + 543} = {by_year[y] / 1e9:,.2f} พันล้านบาท" for y in years)),
        ("", "แยกขอบเขต: " + " · ".join(
            f"{s} = {sum(scope_year.get((s, y), 0) for y in years) / 1e9:,.3f} พันล้านบาท "
            f"({sum(1 for r in detail_annual if r['water_scope'] == s):,} รายการ)" for s in SCOPES)),
        ("", ""),
        ("B", "สารบัญชีต"),
        ("", "1. อ่านก่อน — คำอธิบาย นิยาม และข้อควรระวัง (ชีตนี้)"),
        ("", "2. สรุปขอบเขต-ปี — งบงานน้ำรายปี แยกขอบเขต A/B1/B2/B3 + สัดส่วน + แผนภูมิ"),
        ("", "3. แผนงาน-ปี — เฉพาะ 3 แผนงานด้านทรัพยากรน้ำ (ขอบเขต A)"),
        ("", "4. กระทรวง-ปี — งานน้ำทั้งระบบแยกตามกระทรวง (A+B)"),
        ("", "5. หน่วยงาน-ปี — งานน้ำทั้งระบบแยกตามหน่วยงาน (A+B) + แผนภูมิ 15 อันดับ"),
        ("", "6. โครงการ-ปี — ทุกโครงการที่มีงานน้ำ (A+B)"),
        ("", "7. หมวดงบ-ปี — CATEGORY_LV1 ของงานน้ำทั้งระบบ"),
        ("", "8. รายละเอียดงบรายปี — ทุกรายการถึงระดับไอเทม (ใช้ตัวกรองของ Excel ได้ทุกคอลัมน์)"),
        ("", "9–12. A / B1 / B2 / B3 — รายละเอียดแยกตามขอบเขต (คอลัมน์เหมือนชีตที่ 8)"),
        ("", "13. ภาระผูกพัน — ตารางผูกพันข้ามปี (ห้ามบวกกับงบรายปี)"),
        ("", ""),
        ("B", "การอ่านตัวเลข"),
        ("", "คอลัมน์จำนวนเงินเป็น “บาท” ทุกชีต (รูปแบบ #,##0) · คอลัมน์ปี พ.ศ. = ค.ศ. + 543 · "
             "เลขหน้า (REF_PAGE_NO) และเอกสารอ้างอิง (REF_DOC) อ้างอิงกลับไปยังเอกสารต้นฉบับได้"),
        ("", "สร้างโดยสคริปต์ analyze_water_budget.py — รันซ้ำได้เพื่ออัปเดตตัวเลขทั้งไฟล์"),
    ]
    for kind, text in lines:
        ws.append([text])
        c = ws.cell(row=ws.max_row, column=1)
        if kind == "T":
            c.font = TITLE_FONT
        elif kind == "B":
            c.font = Font(bold=True, color="1F4E79")
        elif text:
            c.font = NOTE_FONT
        c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---------------- 2) ชีตสรุปขอบเขต ----------------
    ws = add_sheet(
        "สรุปขอบเขต-ปี",
        ["ขอบเขต"] + [ylabel[y] for y in years] + ["รวม 4 ปี (บาท)", "สัดส่วนของงานน้ำทั้งระบบ"],
        [[SNAME[s]] + [to_num(scope_year.get((s, y), 0)) for y in years]
         + [to_num(sum(scope_year.get((s, y), 0) for y in years)),
            (sum(scope_year.get((s, y), 0) for y in years) / grants if grants else 0)]
         for s in SCOPES],
        widths=[40] + [17] * len(years) + [20, 22],
        money_cols=list(range(2, len(years) + 3)),
        year_cols=list(range(2, len(years) + 2)),
        total_row=["รวมงานด้านน้ำทั้งระบบ"] + [to_num(by_year[y]) for y in years]
                  + [to_num(grants), 1.0])
    for r in range(2, len(SCOPES) + 3):
        ws.cell(row=r, column=len(years) + 3).number_format = "0.0%"

    ch = BarChart()
    ch.type = "col"
    ch.title = "งบประมาณด้านการบริหารจัดการน้ำรายปี (บาท) แยกตามขอบเขต"
    ch.y_axis.title = "บาท"
    ch.x_axis.title = "ปีงบประมาณ"
    data = Reference(ws, min_col=1, max_col=1 + len(years), min_row=2, max_row=1 + len(SCOPES))
    ch.add_data(data, titles_from_data=True, from_rows=True)
    ch.set_categories(Reference(ws, min_col=2, max_col=1 + len(years), min_row=1, max_row=1))
    ch.height, ch.width = 9.5, 24
    ws.add_chart(ch, f"A{len(SCOPES) + 6}")

    def sum_sheet(title, key, label, width, chart_top=0):
        keys = sorted({k for (k, y) in key}, key=lambda k: -sum(key.get((k, y), 0) for y in years))
        ws_x = add_sheet(title, [label] + [ylabel[y] for y in years] + ["รวม 4 ปี (บาท)"],
                         [[k] + [to_num(key.get((k, y), 0)) for y in years]
                          + [to_num(sum(key.get((k, y), 0) for y in years))] for k in keys],
                         widths=[width] + [17] * len(years) + [20],
                         money_cols=list(range(2, len(years) + 3)),
                         year_cols=list(range(2, len(years) + 2)),
                         data_bar_cols=[len(years) + 2],
                         total_row=[f"รวม {len(keys)} รายการ"]
                                   + [to_num(sum(key.get((k, y), 0) for k in keys)) for y in years]
                                   + [to_num(sum(key.values()))])
        if chart_top:
            n = min(chart_top, len(keys))
            c2 = BarChart()
            c2.type = "bar"
            c2.title = f"{label} — {n} อันดับแรก (รวม 4 ปี, บาท)"
            c2.add_data(Reference(ws_x, min_col=len(years) + 2, min_row=1, max_row=1 + n),
                        titles_from_data=True)
            c2.set_categories(Reference(ws_x, min_col=1, min_row=2, max_row=1 + n))
            c2.height, c2.width = max(7, 0.45 * n + 4), 18
            c2.legend = None
            ws_x.add_chart(c2, f"A{len(keys) + 4}")
        return ws_x

    sum_sheet("แผนงาน-ปี", plan_year, "แผนงาน (ขอบเขต A)", 62)
    sum_sheet("กระทรวง-ปี", min_year, "กระทรวง", 40)
    sum_sheet("หน่วยงาน-ปี", unit_year, "หน่วยงาน", 44, chart_top=15)
    sum_sheet("โครงการ-ปี", proj_year, "โครงการ", 74, chart_top=15)
    sum_sheet("หมวดงบ-ปี", cat_year, "หมวดงบ (CATEGORY_LV1)", 34)

    # ---------------- 3) ชีตรายละเอียด ----------------
    cols = ["ปีงบประมาณ (พ.ศ.)", "ปี (ค.ศ.)", "ขอบเขต", "เหตุผลขอบเขต", "แผนงาน", "กระทรวง",
            "หน่วยงาน", "โครงการ", "รายการ (ไอเทม)", "หมวดงบ LV1", "หมวดงบ LV2", "หมวดงบ LV3",
            "หมวดงบ LV4", "หมวดงบ LV5", "หมวดงบ LV6", "จำนวนเงิน (บาท)",
            "ข้ามฟังก์ชัน", "ผูกพันข้ามปี", "เอกสารอ้างอิง", "เลขหน้า", "ชีตต้นฉบับ", "DQ flag"]
    widths = [12, 9, 8, 26, 44, 26, 30, 50, 62, 16, 22, 22, 18, 18, 18, 16, 10, 10, 44, 8, 18, 26]

    def drow(r):
        return [thai_year(r.get("FISCAL_YEAR")), to_num(r.get("FISCAL_YEAR")), r.get("water_scope", ""),
                r.get("scope_reason", ""), r.get("BUDGET_PLAN", ""), r.get("MINISTRY", ""),
                r.get("BUDGETARY_UNIT", ""), r.get("PROJECT", ""), r.get("ITEM_DESCRIPTION", ""),
                r.get("CATEGORY_LV1", ""), r.get("CATEGORY_LV2", ""), r.get("CATEGORY_LV3", ""),
                r.get("CATEGORY_LV4", ""), r.get("CATEGORY_LV5", ""), r.get("CATEGORY_LV6", ""),
                to_num(r.get("AMOUNT")), r.get("CROSS_FUNC?", ""), r.get("OBLIGED?", ""),
                r.get("REF_DOC", ""), r.get("REF_PAGE_NO", ""), r.get("Source_Sheet", ""),
                r.get("dq_flag", "")]

    add_sheet("รายละเอียดงบรายปี", cols, [drow(r) for r in detail_annual],
              widths=widths, money_cols=[16], year_cols=[1, 2])
    for s in SCOPES:
        ws_s = add_sheet(SHORT[s], cols, [drow(r) for r in detail_annual if r["water_scope"] == s],
                         widths=widths, money_cols=[16], year_cols=[1, 2])
        ws_s.freeze_panes = "D2"

    # ---------------- 4) ชีตภาระผูกพัน ----------------
    cols2 = ["ปีที่ผูกพัน (พ.ศ.)", "ปี (ค.ศ.)", "ขอบเขต", "แผนงาน", "กระทรวง", "หน่วยงาน",
             "โครงการ", "รายการ (ไอเทม)", "จำนวนเงิน (บาท)",
             "เอกสารอ้างอิง", "เลขหน้า", "ชีตต้นฉบับ"]
    widths2 = [14, 9, 8, 44, 26, 30, 50, 62, 16, 44, 8, 18]
    rows2 = [[thai_year(r.get("FISCAL_YEAR")), to_num(r.get("FISCAL_YEAR")), r.get("water_scope", ""),
              r.get("BUDGET_PLAN", ""), r.get("MINISTRY", ""), r.get("BUDGETARY_UNIT", ""),
              r.get("PROJECT", ""), r.get("ITEM_DESCRIPTION", ""), to_num(r.get("AMOUNT")),
              r.get("REF_DOC", ""), r.get("REF_PAGE_NO", ""), r.get("Source_Sheet", "")]
             for r in detail_obliged]
    ws = add_sheet("ภาระผูกพัน", cols2, rows2, widths=widths2, money_cols=[9], year_cols=[1, 2])
    r0 = ws.max_row + 2
    ws.cell(row=r0, column=1, value="คำเตือน: ตารางนี้คือ “ภาระผูกพันข้ามปี” ที่แนบมากับเอกสารแต่ละฉบับ "
                                    "(สัญญาที่ผูกพันไว้แล้ว) — สัญญาเดียวกันปรากฏซ้ำในหลายฉบับ "
                                    "ห้ามนำยอดนี้ไปรวมกับงบประมาณรายจ่ายรายปี").font = Font(
        bold=True, color="C00000", size=11)

    wb.save(path)
    print(f"  → {os.path.relpath(path, ROOT)} ({len(wb.sheetnames)} ชีต: {', '.join(wb.sheetnames)})")


def write_md_tables(path, detail_annual, detail_obliged, plan_year, scope_year, min_year,
                    unit_year, proj_year, cat_year, years):
    L = []
    A = L.append

    def table(cols, rows):
        A("| " + " | ".join(cols) + " |")
        A("|" + "|".join(["---"] * len(cols)) + "|")
        for r in rows:
            A("| " + " | ".join(str(x) for x in r) + " |")

    A("# ตารางงบประมาณด้านการบริหารจัดการน้ำ (สร้างอัตโนมัติ)\n")

    A("## 1) ขอบเขต × ปีงบประมาณ (บาท)\n")
    rows = []
    for s in ["A", "B1", "B2", "B3"]:
        rows.append([SCOPE_LABEL[s]] + [f"{scope_year.get((s, y), 0):,.0f}" for y in years]
                    + [f"{sum(scope_year.get((s, y), 0) for y in years):,.0f}"])
    tot = [sum(scope_year.get((s, y), 0) for s in ["A", "B1", "B2", "B3"]) for y in years]
    rows.append(["**รวม**"] + [f"**{v:,.0f}**" for v in tot] + [f"**{sum(tot):,.0f}**"])
    table(["ขอบเขต"] + [f"ปี {y}" for y in years] + ["รวม"], rows)

    A("\n## 2) แผนงานด้านทรัพยากรน้ำ × ปีงบประมาณ (บาท)\n")
    plans = sorted({p for (p, y) in plan_year},
                   key=lambda p: -sum(plan_year.get((p, y), 0) for y in years))
    rows = []
    for p in plans:
        rows.append([p] + [f"{plan_year.get((p, y), 0):,.0f}" for y in years]
                    + [f"{sum(plan_year.get((p, y), 0) for y in years):,.0f}"])
    table(["แผนงาน"] + [f"ปี {y}" for y in years] + ["รวม"], rows)

    A("\n## 3) กระทรวง × ปีงบประมาณ (บาท)\n")
    mins = sorted({m for (m, y) in min_year},
                  key=lambda m: -sum(a for (mm, y), a in min_year.items() if mm == m))
    rows = [[m] + [f"{min_year.get((m, y), 0):,.0f}" for y in years]
            + [f"{sum(min_year.get((m, y), 0) for y in years):,.0f}"] for m in mins]
    table(["กระทรวง"] + [f"ปี {y}" for y in years] + ["รวม"], rows)

    A("\n## 4) หน่วยงาน × ปีงบประมาณ (บาท)\n")
    units = sorted({u for (u, y) in unit_year},
                   key=lambda u: -sum(a for (uu, y), a in unit_year.items() if uu == u))
    rows = [[u] + [f"{unit_year.get((u, y), 0):,.0f}" for y in years]
            + [f"{sum(unit_year.get((u, y), 0) for y in years):,.0f}"] for u in units]
    table(["หน่วยงาน"] + [f"ปี {y}" for y in years] + ["รวม"], rows)

    A("\n## 5) โครงการ (ยอดรวม ≥ 100 ล้านบาท) × ปีงบประมาณ (บาท)\n")
    projs = sorted({p for (p, y) in proj_year},
                   key=lambda p: -sum(a for (pp, y), a in proj_year.items() if pp == p))
    rows = []
    for p in projs:
        tot = sum(a for (pp, y), a in proj_year.items() if pp == p)
        if tot < 100e6:
            continue
        rows.append([p] + [f"{proj_year.get((p, y), 0):,.0f}" for y in years] + [f"{tot:,.0f}"])
    table(["โครงการ"] + [f"ปี {y}" for y in years] + ["รวม"], rows)

    A("\n## 6) หมวดงบ (CATEGORY_LV1) × ปีงบประมาณ (บาท)\n")
    cats = sorted({c for (c, y) in cat_year},
                  key=lambda c: -sum(a for (cc, y), a in cat_year.items() if cc == c))
    rows = [[c] + [f"{cat_year.get((c, y), 0):,.0f}" for y in years]
            + [f"{sum(cat_year.get((c, y), 0) for y in years):,.0f}"] for c in cats]
    table(["หมวดงบ"] + [f"ปี {y}" for y in years] + ["รวม"], rows)

    A(f"\n> หมายเหตุ: ตารางทั้งหมดคำนวณจากแถวงบประมาณรายปี (OBLIGED?=False) "
      f"จำนวน {len(detail_annual):,} รายการ\n> แถวภาระผูกพัน (OBLIGED?=True) "
      f"จำนวน {len(detail_obliged):,} รายการ แยกไว้ในไฟล์ water_commitments_2566-2569.csv.gz\n")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    main()
