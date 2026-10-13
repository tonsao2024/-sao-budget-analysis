#!/usr/bin/env python3
"""
สร้างไฟล์ Excel ฉบับสมบูรณ์ (พร้อมใช้) จากข้อมูลที่ clean แล้วใน output/

ผลลัพธ์: output/budget_2566-2569_clean.xlsx  — 7 ชีต
  1. วิธีใช้            คำอธิบายชุดข้อมูล + สรุปการ clean + ข้อควรระวัง
  2. งบประมาณ_2566-2569 ข้อมูลหลัก 210,894 แถว (ปี 2566-2569 / ค.ศ. 2022-2026)
  3. ภาระผูกพัน_ปีอื่น   ภาระผูกพัน 20,325 แถว (ปีงบประมาณนอกช่วง)
  4. รายการรอตรวจ       240 แถวที่ flag ไว้ให้ตรวจย้อนหลัง
  5. สรุปการแก้ไข        ทุก rule ที่แก้ พร้อมจำนวนแถว (audit trail)
  6. สถิติรายคอลัมน์     จำนวนค่าที่ไม่ซ้ำ ก่อน/หลัง clean
  7. คู่ที่ยังไม่รวม      คู่ค่าที่ใกล้กันแต่จงใจไม่รวม ให้ผู้ใช้ตัดสิน

รัน:  python3 make_excel.py
"""
import csv
import gc
import gzip
import os
from collections import Counter

import pandas as pd
import xlsxwriter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
MAIN_CSV = os.path.join(OUT, "budget_2566-2569_clean.csv.gz")
COMM_CSV = os.path.join(OUT, "budget_2566-2569_commitments.csv.gz")
QUAR_CSV = os.path.join(OUT, "quarantine_review.csv.gz")
VARMAP_CSV = os.path.join(OUT, "variant_map.csv")
CHECKLIST_MD = os.path.join(OUT, "variant_review_checklist.md")
RAW_CSV = os.path.join(ROOT, "budget_2566-2569.csv.gz")
XLSX = os.path.join(OUT, "budget_2566-2569_clean.xlsx")

# ---------------------------------------------------------------- formats
FMT = {}


def make_formats(wb):
    FMT["title"] = wb.add_format({"bold": True, "font_size": 15, "font_color": "#1F4E79"})
    FMT["h2"] = wb.add_format({"bold": True, "font_size": 11, "bg_color": "#DDEBF7",
                                "border": 1, "border_color": "#9DC3E6", "valign": "vcenter"})
    FMT["body"] = wb.add_format({"valign": "top", "text_wrap": False})
    FMT["body_wrap"] = wb.add_format({"valign": "top", "text_wrap": True})
    FMT["num_key"] = wb.add_format({"bold": True})
    FMT["head"] = wb.add_format({"bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E79",
                                 "border": 1, "border_color": "#FFFFFF", "valign": "vcenter",
                                 "text_wrap": True})
    FMT["text"] = wb.add_format({"valign": "top"})
    FMT["amount"] = wb.add_format({"num_format": "#,##0", "valign": "top"})
    FMT["year"] = wb.add_format({"num_format": "0", "align": "center", "valign": "top"})
    FMT["center"] = wb.add_format({"align": "center", "valign": "top"})


def write_table_sheet(wb, name, header, rows, widths, col_kinds, freeze="A2"):
    """เขียนชีตตาราง: header + autofilter + ตรึงแถวแรก + ความกว้างคอลัมน์

    col_kinds: list ของ 'text' | 'amount' | 'year' | 'center'
    """
    ws = wb.add_worksheet(name)
    # set_column ต้องเรียกก่อนเขียนข้อมูล (ข้อกำหนดของ constant_memory)
    for i, (h, w) in enumerate(zip(header, widths)):
        ws.set_column(i, i, w, FMT["text"])
    for i, h in enumerate(header):
        ws.write_string(0, i, h, FMT["head"])
    ws.freeze_panes(*([1, 0] if freeze == "A2" else [0, 0]))

    r = 1
    for row in rows:
        for c, (v, kind) in enumerate(zip(row, col_kinds)):
            if v == "" or v is None:
                continue
            if kind == "amount":
                ws.write_number(r, c, int(float(v)), FMT["amount"])
            elif kind == "year":
                ws.write_number(r, c, int(float(v)), FMT["year"])
            elif kind == "center":
                ws.write_string(r, c, v, FMT["center"])
            else:
                ws.write_string(r, c, v, FMT["text"])
        r += 1
    ws.autofilter(0, 0, max(r - 1, 1), len(header) - 1)
    return r - 1


def read_gz_rows(path):
    """อ่าน CSV.gz เป็น list ของ list[str] (ค่าทุกช่องเป็นข้อความ)"""
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f)
        head = next(rd)
        rows = [r for r in rd]
    return head, rows


def read_gz_sorted(path, sort_cols, dtypes=None):
    """อ่านด้วย pandas แล้วเรียงลำดับ เพื่อให้ไฟล์ Excel ใช้งานง่าย (ปี -> กระทรวง -> หน่วยงาน)"""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df.sort_values(sort_cols, kind="stable")
    return list(df.columns), [list(t) for t in df.itertuples(index=False, name=None)]


def widths_for(header, rows, sample=3000):
    """คำนวณความกว้างคอลัมน์จากข้อมูลตัวอย่าง (จำกัดเพดานไม่ให้กว้างเกิน)"""
    caps = {"ITEM_DESCRIPTION": 60, "PROJECT": 50, "OUTPUT": 45, "MOTHER_PLAN": 32,
            "BUDGET_PLAN": 34, "MINISTRY": 30, "BUDGETARY_UNIT": 34, "REF_DOC": 26,
            "STRATEGY": 30, "CATEGORY_LV5": 30, "CATEGORY_LV6": 30,
            "AMOUNT": 18, "AMOUNT_num": 18, "FISCAL_YEAR": 13, "YEAR_num": 13,
            "REF_PAGE_NO": 12, "Source_Sheet": 26, "dq_flag": 30}
    w = []
    for i, h in enumerate(header):
        longest = len(h) + 2
        for row in rows[:sample]:
            if i < len(row):
                longest = max(longest, len(str(row[i])) + 2)
        w.append(min(max(longest, 8), caps.get(h, 26)))
    return w


def col_kinds(header):
    """กำหนดชนิดข้อมูลต่อคอลัมน์ เพื่อเขียนเป็นตัวเลข/ข้อความให้ถูกต้องใน Excel"""
    kinds = []
    for h in header:
        if h in ("AMOUNT", "AMOUNT_num"):
            kinds.append("amount")
        elif h in ("FISCAL_YEAR", "YEAR_num"):
            kinds.append("year")
        elif h in ("CROSS_FUNC?", "OBLIGED?"):
            kinds.append("center")
        else:
            kinds.append("text")
    return kinds


# ---------------------------------------------------------------- main
def main():
    wb = xlsxwriter.Workbook(XLSX, {"constant_memory": True, "strings_to_numbers": False,
                                    "default_date_format": "dd/mm/yyyy"})
    make_formats(wb)

    # ---------- อ่านข้อมูล ----------
    print("⏳ อ่านไฟล์ clean ...")
    main_head, main_rows = read_gz_sorted(MAIN_CSV, ["FISCAL_YEAR", "MINISTRY", "BUDGETARY_UNIT"])
    n_main = len(main_rows)
    total_main = sum(int(r[main_head.index("AMOUNT")]) for r in main_rows)
    print(f"   ไฟล์หลัก {n_main:,} แถว")

    print("⏳ อ่านไฟล์ภาระผูกพัน ...")
    comm_head, comm_rows = read_gz_sorted(COMM_CSV, ["FISCAL_YEAR", "MINISTRY", "BUDGETARY_UNIT"])
    n_comm = len(comm_rows)
    total_comm = sum(int(r[comm_head.index("AMOUNT")]) for r in comm_rows)
    print(f"   ภาระผูกพัน {n_comm:,} แถว")

    print("⏳ อ่านไฟล์รายการรอตรวจ ...")
    quar_head, quar_rows = read_gz_rows(QUAR_CSV)
    n_quar = len(quar_rows)

    # ---------- ชีต 1: วิธีใช้ ----------
    print("⏳ เขียนชีต วิธีใช้ ...")
    ws = wb.add_worksheet("วิธีใช้")
    ws.set_column(0, 0, 34)
    ws.set_column(1, 1, 104)
    guide = [
        ("title", "ชุดข้อมูลงบประมาณรายจ่ายภาครัฐ พ.ศ. 2566–2569 (ฉบับ clean แล้ว)"),
        ("b", ""),
        ("h2", "ข้อมูลนี้คืออะไร"),
        ("kv", ("ที่มา", "budget_2566-2569.csv.gz (ไฟล์ต้นฉบับ 231,334 แถว — ไม่ถูกแก้ไข)")),
        ("kv", ("ไฟล์นี้", "budget_2566-2569_clean.xlsx — ข้อมูลหลัง clean ครบทุกคอลัมน์ (รอบ 1–3)")),
        ("kv", ("สร้างด้วย", "make_excel.py (อ่านจาก output/*.csv.gz ที่ผ่าน clean_budget.py)")),
        ("kv", ("แถวรวม", f"{n_main + n_comm:,} แถว = ไฟล์หลัก {n_main:,} + ภาระผูกพัน {n_comm:,}")),
        ("kv", ("ยอดงบรวม", f"ไฟล์หลัก {total_main:,} บาท ({total_main/1e9:,.2f} พันล้านบาท)")),
        ("kv", ("", f"ภาระผูกพัน {total_comm:,} บาท ({total_comm/1e9:,.2f} พันล้านบาท)")),
        ("kv", ("การเรียง", "ทุกชีตเรียงตาม ปีงบประมาณ → กระทรวง → หน่วยงาน (พร้อม autofilter + ตรึงหัวตาราง)")),
        ("b", ""),
        ("h2", "ชีตในไฟล์นี้"),
        ("kv", ("1) งบประมาณ_2566-2569", f"{n_main:,} แถว — ข้อมูลหลัก ปีงบประมาณ 2566–2569 (ค.ศ. 2022–2026)")),
        ("kv", ("2) ภาระผูกพัน_ปีอื่น", f"{n_comm:,} แถว — รายการที่ปีงบประมาณอยู่นอกช่วง (ส่วนใหญ่เป็นภาระผูกพันเดิม) แยกออกเพื่อไม่ให้ยอดรวมรายปีเพี้ยน")),
        ("kv", ("3) รายการรอตรวจ", f"{n_quar:,} แถว — รายการที่ติด dq_flag ให้ตรวจย้อนหลัง (ดูคอลัมน์ dq_flag)")),
        ("kv", ("4) สรุปการแก้ไข", "ทุก rule ที่แก้ พร้อมจำนวนแถวที่กระทบ (audit trail)")),
        ("kv", ("5) สถิติรายคอลัมน์", "จำนวนค่าที่ไม่ซ้ำ ก่อน → หลัง clean")),
        ("kv", ("6) คู่ที่ยังไม่รวม", "คู่ค่าที่ใกล้กันแต่จงใจไม่รวม เพราะยังพิสูจน์ไม่ได้ว่าเป็นรายการเดียวกัน")),
        ("b", ""),
        ("h2", "สรุปการ clean ที่สำคัญ (ตัวอย่างที่พบว่าหน่วยงานเดียวกันถูกสะกดหลายแบบ)"),
        ("kv", ("ลำดับสระ/วรรณยุกต์ผิด", "กรมทรัพยากรนำ้ → กรมทรัพยากรน้ำ (239 แถว) • กรมทรัพยากรนำ้บาดาล → กรมทรัพยากรน้ำบาดาล (153)")),
        ("kv", ("", "กรมอุทยานแห่งชาติ สัตว์ป่า และพันธ์ุพืช → ...และพันธุ์พืช (451)")),
        ("kv", ("วงเล็บปิดหายท้ายชื่อ", "สถาบันสารสนเทศทรัพยากรน้ำ (องค์การมหาชน → ...(องค์การมหาชน) (22) รวมทั้งไฟล์ 33 หน่วยงาน / 706 แถว")),
        ("kv", ("คำสะกดผิดอื่น", "สำนักงานตารวจแห่งชาติ → สำนักงานตำรวจแห่งชาติ (970) • กรมส่งเสริมการปกครองทองถิ่น → ...ท้องถิ่น (610)")),
        ("kv", ("หมวดงบประมาณ", "ค่าตอบแทนใช้สอยและวัสดุ → ค่าตอบแทน ใช้สอยและวัสดุ (11,400) • ค่าที่ดิน/สิ่งก่อสร้าง → ค่าที่ดินและสิ่งก่อสร้าง (11,831)")),
        ("kv", ("แผนแม่บท", "แผนแม่บทฯ:การบริหารจัดการน้าทั้งระบบ → ...น้ำทั้งระบบ (4,132)")),
        ("kv", ("ข้อความรายการ", "ก่อสร้ง → ก่อสร้าง (722) • สิงก่อสร้าง → สิ่งก่อสร้าง (475) • ไมต่ำกว่า → ไม่ต่ำกว่า (375)"),
                         ),
        ("kv", ("", "ลบพินทุ (ฺ) ที่หลงจาก PDF 3,587 แถว • ลบเศษ ' บาท' ท้ายรายการ 1,456 แถว")),
        ("b", ""),
        ("h2", "ข้อควรระวัง — 5 จุดที่ยังเหลือและจงใจไม่เดา"),
        ("kv", ("1. วงเล็บไม่สมดุล", "174 แถว — ต้นฉบับวงเล็บเปิดหาย เช่น 'เงินอุดหนุนทั่วไป 4,390,800 um1) ค่าใช้จ่าย...'")),
        ("kv", ("2. อักษรละตินปนไทย", "471 แถว — บางค่าเป็นชื่อจริง (C Band, MHz, UN R117) บางค่าเป็น glitch (รs.นอ., ทa.3191)")),
        ("kv", ("3. ค่าหมวดต่างกันแค่ตัวเลขท้าย", "เช่น 'ค่าควบคุมงาน... รวม 3 รายการ (รวม 3 หน่วย)' กับ '(รวม 2 หน่วย)' — ต้นฉบับระบุต่างกันจริง")),
        ("kv", ("4. ค่าที่อยู่ผิดระดับคอลัมน์", "'เงินอุดหนุนทั่วไป 1' และ 'ค่าที่ดิน/สิ่งก่อสร้าง รวม 201 รายการ' ในช่อง CATEGORY_LV3")),
        ("kv", ("5. จังหวัดย (15 แถว ปี 2567)", "อนุมานเป็น จังหวัดหนองคาย และติด flag unit_inferred ในคอลัมน์ dq_flag")),
        ("b", ""),
        ("h2", "คอลัมน์ในชีตข้อมูล (22 คอลัมน์)"),
        ("kv", ("REF_DOC / REF_PAGE_NO", "เอกสารและหน้าอ้างอิงต้นฉบับ (ตรวจย้อนกลับได้)")),
        ("kv", ("MINISTRY / BUDGETARY_UNIT", "กระทรวง / หน่วยงาน (ชื่อสะกดมาตรฐานแล้ว)")),
        ("kv", ("BUDGET_PLAN / OUTPUT / PROJECT", "แผนงาน / ผลผลิต / โครงการ")),
        ("kv", ("CATEGORY_LV1…LV6", "หมวดงบประมาณไล่ระดับ (LV1 = งบลงทุน/งบดำเนินงาน/...)")),
        ("kv", ("ITEM_DESCRIPTION", "รายการย่อย (86,259 → 84,765 ค่าที่ไม่ซ้ำ หลัง clean)")),
        ("kv", ("AMOUNT", "จำนวนเงิน (บาท) — ตัวเลขพร้อมจัดรูปแบบคั่นหลักพันแล้ว")),
        ("kv", ("FISCAL_YEAR", "ปีงบประมาณ ค.ศ. (2022–2026 = พ.ศ. 2565–2569)")),
        ("kv", ("CROSS_FUNC? / OBLIGED?", "เป็นรายการข้ามปี? / เป็นภาระผูกพัน?")),
        ("kv", ("Source_Sheet / STRATEGY / MOTHER_PLAN", "ชีตต้นฉบับ / ยุทธศาสตร์ / แผนแม่บท")),
        ("kv", ("dq_flag", "ธงคุณภาพข้อมูล — ว่าง = ปกติ; ที่พบ: amount_zero, cross_func_filled, category_lv1_unresolved, budget_plan_missing, item_description_missing, amount_negative, unit_inferred")),
        ("b", ""),
        ("h2", "วิธีใช้ใน Excel"),
        ("kv", ("กรอง/เรียง", "ทุกชีตมี autofilter ที่แถวหัวตาราง (กดลูกศรในหัวคอลัมน์ได้เลย)")),
        ("kv", ("PivotTable", "เลือกข้อมูลทั้งชีต → Insert > PivotTable เพื่อสรุปตามกระทรวง/หมวด/ปี")),
        ("kv", ("ยอดรวม", "คอลัมน์ AMOUNT เป็นตัวเลขจริง (ไม่ใช่ข้อความ) จึง SUM ได้ทันที")),
    ]
    r = 0
    for kind, val in guide:
        if kind == "title":
            ws.write_string(r, 0, val, FMT["title"]); r += 1
        elif kind == "h2":
            ws.write_string(r, 0, val, FMT["h2"]); r += 1
        elif kind == "kv":
            k, v = val
            if k:
                ws.write_string(r, 0, k, FMT["num_key"])
            ws.write_string(r, 1, v, FMT["body_wrap"])
            r += 1
        else:
            r += 1

    # ---------- ชีต 2-3: ข้อมูลหลัก + ภาระผูกพัน ----------
    print("⏳ เขียนชีต งบประมาณ_2566-2569 ...")
    w_main = widths_for(main_head, main_rows)
    n = write_table_sheet(wb, "งบประมาณ_2566-2569", main_head, main_rows, w_main, col_kinds(main_head))
    print(f"   {n:,} แถว")
    del main_rows
    gc.collect()

    print("⏳ เขียนชีต ภาระผูกพัน_ปีอื่น ...")
    w_comm = widths_for(comm_head, comm_rows)
    n = write_table_sheet(wb, "ภาระผูกพัน_ปีอื่น", comm_head, comm_rows, w_comm, col_kinds(comm_head))
    print(f"   {n:,} แถว")
    del comm_rows
    gc.collect()

    # ---------- ชีต 4: รายการรอตรวจ ----------
    print("⏳ เขียนชีต รายการรอตรวจ ...")
    w_quar = widths_for(quar_head, quar_rows)
    n = write_table_sheet(wb, "รายการรอตรวจ", quar_head, quar_rows, w_quar, col_kinds(quar_head))
    print(f"   {n:,} แถว")
    del quar_rows
    gc.collect()

    # ---------- ชีต 5: สรุปการแก้ไข (audit trail) ----------
    print("⏳ เขียนชีต สรุปการแก้ไข ...")
    with open(VARMAP_CSV, encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f)
        v_head = next(rd)
        v_rows = [row for row in rd]
    v_rows = [r for r in v_rows if len(r) >= 4]
    v_rows.sort(key=lambda r: (r[0], r[1], -int(r[4] or 0)))
    hdr = ["คอลัมน์", "ชนิด rule", "ค่าเดิม", "ค่าใหม่", "จำนวนแถวที่แก้"]
    ws = wb.add_worksheet("สรุปการแก้ไข")
    for i, (h, w) in enumerate(zip(hdr, [24, 14, 62, 62, 14])):
        ws.set_column(i, i, w)
    for i, h in enumerate(hdr):
        ws.write_string(0, i, h, FMT["head"])
    ws.freeze_panes(1, 0)
    r = 1
    for row in v_rows:
        ws.write_string(r, 0, row[0], FMT["text"])
        ws.write_string(r, 1, row[1], FMT["text"])
        ws.write_string(r, 2, row[2], FMT["text"])
        ws.write_string(r, 3, row[3], FMT["text"])
        ws.write_number(r, 4, int(row[4] or 0), FMT["amount"])
        r += 1
    ws.autofilter(0, 0, r - 1, len(hdr) - 1)

    # ---------- ชีต 6: สถิติรายคอลัมน์ ----------
    print("⏳ เขียนชีต สถิติรายคอลัมน์ ...")
    ws = wb.add_worksheet("สถิติรายคอลัมน์")
    hdr = ["คอลัมน์", "ค่าที่ไม่ซ้ำ (ดิบ)", "ค่าที่ไม่ซ้ำ (clean)", "ลดลง", "หมายเหตุ"]
    for i, (h, w) in enumerate(zip(hdr, [24, 18, 20, 12, 46])):
        ws.set_column(i, i, w)
    for i, h in enumerate(hdr):
        ws.write_string(0, i, h, FMT["head"])
    ws.freeze_panes(1, 0)
    notes = {
        "MINISTRY": "รวมชื่อกระทรวง/หน่วยงานนำส่งที่สะกดต่างกัน (อปท → องค์กรปกครองส่วนท้องถิ่น 11,754 แถว)",
        "BUDGETARY_UNIT": "ตัวอย่าง: กรมทรัพยากรนำ้ → กรมทรัพยากรน้ำ, พันธ์ุพืช → พันธุ์พืช, วงเล็บปิดหาย 33 หน่วยงาน",
        "BUDGET_PLAN": "ค่าถูกต้องอยู่แล้ว (แก้สะกดเฉพาะบางแถว)",
        "OUTPUT": "รวมค่าที่สะกดต่าง + ลบข้อความซ้ำจาก PDF",
        "PROJECT": "รวมค่าที่สะกดต่าง + ลบข้อความซ้ำ + เศษ ' บาท' ท้ายชื่อโครงการ",
        "CATEGORY_LV1": "แก้คอลัมน์เลื่อน (มีชื่อแผนงานปนในช่องหมวดงบ)",
        "CATEGORY_LV2": "ค่าตอบแทนใช้สอยและวัสดุ → ค่าตอบแทน ใช้สอยและวัสดุ",
        "CATEGORY_LV3": "ค่าที่ดิน/สิ่งก่อสร้าง → ค่าที่ดินและสิ่งก่อสร้าง; เงินอุ ดหนุนทั่วไป → เงินอุดหนุนทั่วไป",
        "CATEGORY_LV4": "ค่าก่อสร้ง → ค่าก่อสร้าง; ค่าที่ดิน/สิ่งก่อสร้าง → และ",
        "CATEGORY_LV5": "ช่อมสร้าง → ซ่อมสร้าง; พินทุ (ฺ) ถูกตัด",
        "CATEGORY_LV6": "แก้สะกดผิด + รวมค่าที่ต่างแค่ช่องว่าง",
        "ITEM_DESCRIPTION": "คำผิดบางส่วน 84 rules + ไม้ยมก + ตัวเลขชนคำนับ + เศษ ' บาท' + พินทุ",
        "STRATEGY": "ค่าถูกต้องอยู่แล้ว",
        "MOTHER_PLAN": "แผนแม่บทฯ:การบริหารจัดการน้าทั้งระบบ → ...น้ำทั้งระบบ",
    }
    deltas = []
    with gzip.open(RAW_CSV, "rt", encoding="utf-8-sig") as f:
        raw = pd.read_csv(f, dtype=str, keep_default_na=False)
    with gzip.open(MAIN_CSV, "rt", encoding="utf-8-sig") as f:
        clean = pd.read_csv(f, dtype=str, keep_default_na=False)
    r = 1
    for c in main_head:
        if c not in ("dq_flag",):
            ur = len(set(raw[c]) - {""})
            uc = len(set(clean[c]) - {""})
            deltas.append((c, ur, uc))
            ws.write_string(r, 0, c, FMT["text"])
            ws.write_number(r, 1, ur, FMT["amount"])
            ws.write_number(r, 2, uc, FMT["amount"])
            ws.write_number(r, 3, ur - uc, FMT["amount"])
            ws.write_string(r, 4, notes.get(c, ""), FMT["text"])
            r += 1
    ws.autofilter(0, 0, r - 1, len(hdr) - 1)
    del raw, clean
    gc.collect()

    # ---------- ชีต 7: คู่ที่ยังไม่รวม ----------
    print("⏳ เขียนชีต คู่ที่ยังไม่รวม ...")
    ws = wb.add_worksheet("คู่ที่ยังไม่รวม")
    hdr = ["คอลัมน์", "ค่า A", "ค่า B", "หมายเหตุ"]
    for i, (h, w) in enumerate(zip(hdr, [22, 54, 54, 26])):
        ws.set_column(i, i, w)
    for i, h in enumerate(hdr):
        ws.write_string(0, i, h, FMT["head"])
    ws.freeze_panes(1, 0)
    r = 1
    if os.path.exists(CHECKLIST_MD):
        with open(CHECKLIST_MD, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("|") or set(line) <= set("|- "):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 4 or cells[0] == "คอลัมน์":
                    continue
                for i, c in enumerate(cells[:4]):
                    ws.write_string(r, i, c, FMT["text"])
                r += 1
    ws.autofilter(0, 0, r - 1, len(hdr) - 1)

    wb.close()
    size_mb = os.path.getsize(XLSX) / 1024 / 1024
    print(f"\n🎉 สร้างเสร็จ: {XLSX}")
    print(f"   ขนาด {size_mb:,.1f} MB | ชีตทั้งหมด 7 ชีต")
    print(f"   ไฟล์หลัก {n_main:,} แถว | ภาระผูกพัน {n_comm:,} | รอตรวจ {n_quar:,} | audit {len(v_rows):,} rules")


if __name__ == "__main__":
    main()
