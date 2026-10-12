#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
คัดเลือกงบประมาณด้านการบริหารจัดการน้ำ พ.ศ. 2566–2569 ที่ลงในพื้นที่ “ลุ่มน้ำป่าสัก”
จากผลลัพธ์ของ analyze_water_budget.py (output/water/water_budget_detail_2566-2569.csv.gz)

หลักการ
------
ข้อมูลชุดนี้ไม่มีคอลัมน์พิกัด/รหัสลุ่มน้ำ มีแต่ข้อความบรรยายรายการ (ชื่อโครงการ/รายการไอเทม/
ชื่อหน่วยงาน) จึงใช้ “การคัดกรองด้วยคำบอกตำแหน่ง (keyword screening)” แล้วแยกเป็นกลุ่มเหตุผล
พร้อมระบุหลักฐาน (คำที่พบ + พื้นที่ที่ระบุ) และช่องทางตรวจย้อนกลับ (REF_DOC / REF_PAGE_NO /
Source_Sheet) ทุกแถว

กลุ่มเหตุผล
----------
G1  หลักฐานตรง “ป่าสัก”        : ข้อความระบุชื่อระบบป่าสัก (เขื่อนป่าสักชลสิทธิ์ / ลุ่มน้ำป่าสัก /
                                 ลำน้ำป่าสัก / โครงการส่งน้ำและบำรุงรักษาป่าสัก* / คลองชัยนาท-ป่าสัก)
                                 และพื้นที่งานอยู่ในจังหวัดของลุ่มน้ำป่าสัก
G2  อำเภอ/ตำบลในลุ่มน้ำป่าสัก  : ระบุอำเภอ/ตำบลที่อยู่ในทะเบียนอำเภอของลุ่มน้ำป่าสัก
G3  จังหวัดหลักของลุ่มน้ำ       : ระบุจังหวัด เพชรบูรณ์ / ลพบุรี / สระบุรี (แต่ไม่ระบุอำเภอ/ตำบล)
G4  จังหวัด/อำเภอ “บางส่วน”      : จังหวัดหรืออำเภอที่มีพื้นที่ในลุ่มน้ำป่าสักเพียงบางส่วน
                                 (พระนครศรีอยุธยา เลย ด่านซ้าย ชัยภูมิ นครราชสีมา นครนายก) → ต้องตรวจซ้ำ
GS  เชิงระบบ แต่นอกพื้นที่ลุ่มน้ำ : งานในระบบชลประทานชัยนาท-ป่าสัก ที่พื้นที่งานอยู่ จ.ชัยนาท
                                 สิงห์บุรี หรือนครสวรรค์ (ไม่นับเป็น “ในพื้นที่ลุ่มน้ำป่าสัก”)
GX  ตัดออก                      : คำว่า “ป่าสัก” เป็นชื่อสถานที่/ชื่อสถานีซ้ำในจังหวัดอื่น
                                 (แพร่ เชียงราย สุโขทัย หนองคาย พิษณุโลก)

เอาต์พุต: output/water/water_budget_pasak_basin_2566-2569.xlsx (+ สำเนา docs/data)
"""
import csv
import gzip
import io
import os
import re
import collections

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(ROOT, "output", "water")
DOCSDATA = os.path.join(ROOT, "docs", "data")
SRC_ANNUAL = os.path.join(OUTDIR, "water_budget_detail_2566-2569.csv.gz")
SRC_COMMIT = os.path.join(OUTDIR, "water_commitments_2566-2569.csv.gz")
OUT_XLSX = os.path.join(OUTDIR, "water_budget_pasak_basin_2566-2569.xlsx")

# ---------------------------------------------------------------------------
# ทะเบียนคำค้น (gazetteer) — แต่ละรายการมีแหล่งอ้างอิงที่ใช้อ้างได้
# ---------------------------------------------------------------------------
# 1) คำเฉพาะระบบป่าสัก (หลักฐานตรง)
PASAK_SYSTEM = [
    "ป่าสักชลสิทธิ์", "ลุ่มน้ำป่าสัก", "แม่น้ำป่าสัก", "ลำน้ำป่าสัก", "น้ำป่าสัก",
    "โครงการส่งน้ำและบำรุงรักษาป่าสัก", "ป่าสักใต้", "คลองชัยนาท-ป่าสัก", "คลองชัยนาท - ป่าสัก",
    "ชัยนาท-ป่าสัก",
]

# 2) อำเภอ/ตำบลในลุ่มน้ำป่าสัก (จังหวัด : อำเภอ)
#    อ้างอิง: 1) 8 ลุ่มน้ำสาขาของลุ่มน้ำป่าสัก (กรมทรัพยากรน้ำ)
#            2) พื้นที่โครงการเขื่อนป่าสักชลสิทธิ์ (ลพบุรี: พัฒนานิคม ท่าหลวง ชัยบาดาล / สระบุรี: วังม่วง)
#            3) พื้นที่ชลประทานของโครงการส่งน้ำและบำรุงรักษาป่าสักใต้–ป่าสักชลสิทธิ์ (สระบุรี อยุธยา)
# อำเภอที่อยู่ในลุ่มน้ำป่าสักอย่างชัดเจน (อ้างอิง 8 ลุ่มน้ำสาขา/พื้นที่เขื่อน/พื้นที่ชลประทานป่าสัก)
BASIN_DISTRICTS_HIGH = {
    # เพชรบูรณ์ — ลุ่มน้ำสาขาแม่น้ำป่าสักตอนบน, ห้วยน้ำพุง, ลำกง, แม่น้ำป่าสักส่วนที่ 2–3, ห้วยเกาะแก้ว
    "เพชรบูรณ์": ["หล่มเก่า", "หล่มสัก", "หนองไผ่", "บึงสามพัน", "วิเชียรบุรี", "ศรีเทพ", "น้ำหนาว"],
    # ลพบุรี — พื้นที่โครงการเขื่อนป่าสักชลสิทธิ์ + ลุ่มน้ำสาขาลำสนธิ
    "ลพบุรี": ["พัฒนานิคม", "ท่าหลวง", "ชัยบาดาล", "ลำสนธิ", "โคกเจริญ"],
    # สระบุรี — ลุ่มน้ำสาขาแม่น้ำป่าสักตอนล่าง/ห้วยมวกเหล็ก + พื้นที่ชลประทานป่าสักใต้
    "สระบุรี": ["แก่งคอย", "วังม่วง", "มวกเหล็ก", "วิหารแดง", "หนองแค", "เมืองสระบุรี", "เสาไห้",
                "เฉลิมพระเกียรติ", "โคกตูม"],
}
# อำเภอที่อยู่ในเขตบริการน้ำของระบบป่าสัก แต่ยังต้องยืนยันกับแผนที่ลุ่มน้ำ (ความเชื่อมั่นกลาง)
BASIN_DISTRICTS_MED = {
    "เพชรบูรณ์": ["เขาค้อ", "วังโป่ง", "ชนแดน", "เมืองเพชรบูรณ์"],
    "ลพบุรี": ["สระโบสถ์", "หนองม่วง", "โคกสำโรง", "บ้านหมี่", "ท่าวุ้ง", "เมืองลพบุรี"],
    "สระบุรี": ["หนองแซง", "บ้านหมอ", "ดอนพุด", "หนองโดน", "พระพุทธบาท"],
}
BASIN_DISTRICTS = {p: ds + BASIN_DISTRICTS_MED.get(p, []) for p, ds in BASIN_DISTRICTS_HIGH.items()}

# 2.1) ชื่อสำนักงาน/โครงการชลประทานที่ตั้งอยู่ในลุ่มน้ำป่าสัก (หลักฐานระดับหน่วยปฏิบัติ)
PASAK_OFFICES = [
    "โครงการชลประทานเพชรบูรณ์", "โครงการชลประทานลพบุรี", "โครงการชลประทานสระบุรี",
    "สำนักงานชลประทานที่ 10", "โครงการส่งน้ำและบำรุงรักษาเริงราง",
    "โครงการส่งน้ำและบำรุงรักษาป่าสัก",
]
# 2.2) สำนักงาน/โครงการที่อยู่ในระบบชัยนาท-ป่าสัก แต่อยู่นอกขอบเขตลุ่มน้ำ
OFFICES_OUTSIDE = ["โครงการส่งน้ำและบำรุงรักษามโนรมย์", "โครงการส่งน้ำและบำรุงรักษาช่องแค", "มโนรมย์"]
# 2.3) สำนักงานที่ดูแลพื้นที่ซึ่งมีลุ่มน้ำป่าสักเพียงบางส่วน (ยังต้องตรวจตำแหน่งงาน)
PARTIAL_OFFICES = ["โครงการชลประทานพระนครศรีอยุธยา"]

# 3) จังหวัดหลักของลุ่มน้ำป่าสัก (มีพื้นที่ในลุ่มน้ำเป็นสัดส่วนมาก)
BASIN_PROVINCES = ["เพชรบูรณ์", "ลพบุรี", "สระบุรี"]

# 4) พื้นที่ “บางส่วน” ของลุ่มน้ำป่าสัก (ต้องตรวจซ้ำ)
PARTIAL_PROVINCES = {
    "พระนครศรีอยุธยา": "มีพื้นที่ในลุ่มน้ำ 5.5% (เฉพาะฝั่งตะวันออกของลุ่มน้ำป่าสักตอนล่าง)",
    "เลย": "ต้นน้ำป่าสัก-ห้วยน้ำพุง เฉพาะอำเภอด่านซ้าย",
    "ชัยภูมิ": "เฉพาะลุ่มน้ำสาขาลำสนธิ/ภูเขียว–คอนสาร (บางส่วน)",
    "นครราชสีมา": "เฉพาะลุ่มน้ำสาขาแม่น้ำป่าสักตอนบน (ปากช่อง สีคิ้ว เทพารักษ์)",
    "นครนายก": "พื้นที่บางส่วนตามเอกสารสำนักงานเลขาธิการวุฒิสภา",
}
PARTIAL_DISTRICTS = {
    # อยุธยา: เฉพาะอำเภอฝั่งตะวันออกของลุ่มน้ำป่าสักตอนล่าง/พื้นที่ชลประทานป่าสักใต้
    "พระนครศรีอยุธยา": ["ท่าเรือ", "นครหลวง", "ภาชี", "บ้านแพรก", "บางปะหัน", "มหาราช", "วังน้อย", "อุทัย"],
    "เลย": ["ด่านซ้าย"],
    "ชัยภูมิ": ["ภูเขียว", "คอนสาร", "เนินสง่า", "ซับใหญ่", "เทพสถิต"],
    "นครราชสีมา": ["ปากช่อง", "สีคิ้ว", "เทพารักษ์", "วังน้ำเขียว"],
    "นครนายก": ["ปากพลี", "บ้านนา"],
}

# 5) ระบบชลประทานชัยนาท-ป่าสัก ในพื้นที่นอกลุ่มน้ำ (เชิงระบบ ไม่นับเป็น “ในพื้นที่ลุ่มน้ำ”)
SYSTEM_OUTSIDE_PROVINCES = ["ชัยนาท", "สิงห์บุรี", "นครสวรรค์"]

# 6) คำว่า “ป่าสัก” ที่เป็นชื่อซ้ำในจังหวัดอื่น (ตัดออก) — ตรวจจากรายการจริงแล้ว
HOMONYM = {
    "แพร่": ["วังชิ้น", "ป่าสัก"],
    "เชียงราย": ["เชียงแสน", "แม่จัน", "ป่าสัก"],
    "สุโขทัย": ["สวรรคโลก", "ป่าสัก"],
    "หนองคาย": ["ศรีเชียงใหม่", "ป่าสัก"],
    "พิษณุโลก": ["ชาติตระการ", "ป่าสัก"],
}

GROUP_LABEL = {
    "G1": "G1 · หลักฐานตรง “ป่าสัก”",
    "G2": "G2 · อำเภอ/ตำบลในลุ่มน้ำป่าสัก",
    "G3": "G3 · จังหวัดหลักของลุ่มน้ำ (เพชรบูรณ์/ลพบุรี/สระบุรี)",
    "G4": "G4 · จังหวัด/อำเภอ “บางส่วน” (ต้องตรวจซ้ำ)",
    "GS": "GS · ระบบชัยนาท-ป่าสัก แต่อยู่นอกพื้นที่ลุ่มน้ำ",
    "GX": "GX · ตรวจแล้วตัดออก (ชื่อ “ป่าสัก” ซ้ำกับจังหวัดอื่น)",
    "G5": "G5 · ระบุเพียงจังหวัดที่มีพื้นที่บางส่วน (ยังไม่ยืนยัน)",
    "GN": "GN · ระบุพื้นที่จังหวัด/อำเภออื่น (นอกลุ่มน้ำป่าสัก)",
    "GU": "GU · ไม่ระบุพื้นที่ (ระบุไม่ได้จากข้อมูลชุดนี้)",
}
CONFIDENCE = {"G1": "สูง", "G2": "สูง–กลาง", "G3": "กลาง", "G4": "ต้องตรวจซ้ำ",
              "GS": "ไม่นับเป็นในพื้นที่", "GX": "ตัดออก", "G5": "ต้องตรวจซ้ำ", "GN": "นอกพื้นที่",
              "GU": "ระบุไม่ได้"}
IN_BASIN_GROUPS = ["G1", "G2", "G3", "G4"]


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield row


def blob_of(row):
    return " ".join([row.get("PROJECT", ""), row.get("ITEM_DESCRIPTION", ""),
                     row.get("BUDGETARY_UNIT", ""), row.get("BUDGET_PLAN", ""),
                     row.get("OUTPUT", "")])


# รายชื่อจังหวัดทั้ง 77 จังหวัด ใช้ตัดข้อความส่วนเกินออกจากชื่อจังหวัดที่จับได้
PROVINCES_77 = [
    "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น", "จันทบุรี", "ฉะเชิงเทรา",
    "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด", "ตาก", "นครนายก",
    "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ",
    "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา",
    "พัทลุง", "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร",
    "แม่ฮ่องสอน", "ยโสธร", "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย",
    "ศรีสะเกษ", "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี",
    "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู", "อ่างทอง",
    "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี",
]


def canon_province(raw):
    """ตัดข้อความส่วนเกินที่ติดมากับชื่อจังหวัด (เช่น “ลพบุรีฝ่ายส่งน้ำและบำรุงรักษาที่ 3”)"""
    for name in sorted(PROVINCES_77 + list(HOMONYM) + list(SYSTEM_OUTSIDE_PROVINCES),
                       key=len, reverse=True):
        if raw.startswith(name):
            return name
    return raw


def find_provinces(text):
    return [canon_province(p) for p in re.findall(r"จังหวัด\s*([ก-๙]+?)(?=[\s,()]|$)", text)]


def find_districts(text):
    return re.findall(r"อำเภอ\s*([ก-๙]+?)(?=[\s,()]|จังหวัด|ตำบล|อำเภอ|$)", text)


def find_tambons(text):
    return re.findall(r"ตำบล\s*([ก-๙]+?)(?=[\s,()]|จังหวัด|อำเภอ|ตำบล|$)", text)


def province_of(text):
    """จังหวัดที่ระบุในข้อความ (เอาตัวแรกที่มี ไม่งั้นคืน '')"""
    ps = find_provinces(text)
    return ps[0] if ps else ""


def classify(row):
    """คืน (group, reason, จังหวัดที่ระบุ, อำเภอที่ระบุ, คำหลักฐาน, ความเชื่อมั่น)"""
    text = blob_of(row)
    provs = find_provinces(text)
    dists = find_districts(text)
    prov = provs[0] if provs else ""
    dist = dists[0] if dists else ""

    # --- ค้นคำระบบป่าสัก
    sys_hits = [k for k in PASAK_SYSTEM if k in text]
    pasak_word = "ป่าสัก" in text

    # --- GX: ชื่อซ้ำในจังหวัดอื่น (ตรวจก่อน เพื่อไม่ให้ถูกนับเข้า G1)
    for p, marks in HOMONYM.items():
        if p in provs and pasak_word:
            # ถ้าในข้อความเดียวกันมีอำเภอที่พิสูจน์ว่าเป็นลุ่มน้ำป่าสักจริง ให้ไม่ตัด
            for bp, bd in BASIN_DISTRICTS.items():
                if bp in provs and any(d in dists for d in bd):
                    break
            else:
                return ("GX", f"คำว่า “ป่าสัก” เป็นชื่อสถานที่/ชื่อสถานีในจังหวัด{p}"
                              f"{(' อำเภอ' + dist) if dist else ''} — ไม่อยู่ในลุ่มน้ำป่าสัก",
                        " / ".join(provs), " / ".join(dict.fromkeys(dists)), "ป่าสัก(ชื่อซ้ำ)", "ตัดออก")

    # --- G1: หลักฐานตรงระบบป่าสัก
    if sys_hits:
        in_prov = [p for p in provs if p in BASIN_PROVINCES + ["พระนครศรีอยุธยา"]] or \
                  [p for p in PARTIAL_PROVINCES if p in provs]
        if in_prov or not provs:
            where = " ".join(x for x in [f"อ.{dist}" if dist else "", f"จ.{in_prov[0]}" if in_prov else f"จ.{prov}" if prov else ""] if x)
            return ("G1", f"ระบุระบบป่าสักโดยตรง: “{sys_hits[0]}”"
                          + (f" — พื้นที่งาน {where}" if where else ""),
                    " / ".join(provs), " / ".join(dict.fromkeys(dists)), sys_hits[0], "สูง")

    # --- G1b: ชื่อสำนักงาน/โครงการชลประทานที่ตั้งในลุ่มน้ำป่าสัก
    office_hits = [k for k in PASAK_OFFICES if k in text]
    outside_hits = [k for k in OFFICES_OUTSIDE if k in text]
    partial_hits = [k for k in PARTIAL_OFFICES if k in text]
    if office_hits:
        if provs and any(p not in BASIN_PROVINCES + ["พระนครศรีอยุธยา"] for p in provs):
            return ("GS", f"งานในระบบชลประทานลุ่มน้ำป่าสัก (“{office_hits[0]}”) "
                          f"แต่พื้นที่งานระบุ จ.{prov} ซึ่งอยู่นอกขอบเขตลุ่มน้ำป่าสัก",
                    " / ".join(provs), " / ".join(dict.fromkeys(dists)), office_hits[0],
                    "ไม่นับเป็นในพื้นที่")
        return ("G1", f"สังกัด/โครงการชลประทานในลุ่มน้ำป่าสัก: “{office_hits[0]}”"
                      + (f" — พื้นที่งาน อ.{dist} จ.{prov}" if dist or prov else ""),
                " / ".join(provs), " / ".join(dict.fromkeys(dists)), office_hits[0], "สูง")
    if outside_hits and not provs:
        return ("GS", f"งานของหน่วยปฏิบัติในระบบชัยนาท-ป่าสัก (“{outside_hits[0]}”) "
                      "แต่พื้นที่งานอยู่นอกขอบเขตลุ่มน้ำป่าสัก",
                " / ".join(provs), " / ".join(dict.fromkeys(dists)), outside_hits[0],
                "ไม่นับเป็นในพื้นที่")
    if partial_hits:
        return ("G5", f"สังกัด “{partial_hits[0]}” ซึ่งดูแลพื้นที่ที่มีลุ่มน้ำป่าสักเพียงบางส่วน "
                      "และข้อความไม่ระบุอำเภอที่ยืนยันได้ — ต้องตรวจตำแหน่งงาน",
                " / ".join(provs), " / ".join(dict.fromkeys(dists)), partial_hits[0], "ต้องตรวจซ้ำ")

    # --- G2: อำเภอในลุ่มน้ำป่าสัก (สองชั้นความเชื่อมั่น)
    for tier, table in (("สูง", BASIN_DISTRICTS_HIGH), ("กลาง", BASIN_DISTRICTS_MED)):
        for bp, bd in table.items():
            for d in dists:
                if d in bd and (not provs or bp in provs or prov == ""):
                    if provs and bp not in provs:
                        continue
                    return ("G2", f"ระบุอำเภอ/ตำบลในลุ่มน้ำป่าสัก: อ.{d} จ.{bp} "
                                  f"(เทียบทะเบียนอำเภอของลุ่มน้ำป่าสัก — ความเชื่อมั่น{tier})",
                            " / ".join(provs) or bp, " / ".join(dict.fromkeys(dists)),
                            f"อำเภอ {d}", f"{'สูง–กลาง' if tier == 'สูง' else 'กลาง'}")

    # --- G3: จังหวัดหลัก
    hit_primary = [p for p in BASIN_PROVINCES if p in provs]
    if hit_primary:
        return ("G3", f"ระบุจังหวัดหลักของลุ่มน้ำป่าสัก: จ.{hit_primary[0]}"
                      " (จังหวัดมีพื้นที่ในลุ่มน้ำเป็นสัดส่วนสูง แต่ข้อมูลไม่ระบุอำเภอ)",
                " / ".join(provs), " / ".join(dict.fromkeys(dists)), f"จังหวัด {hit_primary[0]}", "กลาง")

    # --- G4: บางส่วน
    for p in PARTIAL_PROVINCES:
        if p in provs:
            ds = PARTIAL_DISTRICTS.get(p, [])
            if ds and dists:
                if any(d in ds for d in dists):
                    return ("G4", f"จังหวัด/อำเภอที่มีพื้นที่ในลุ่มน้ำป่าสักบางส่วน: อ.{dist} จ.{p}"
                                  f" — {PARTIAL_PROVINCES[p]}",
                            " / ".join(provs), " / ".join(dict.fromkeys(dists)), f"อำเภอ {dist}",
                            "ต้องตรวจซ้ำ")
                break   # จังหวัดบางส่วน แต่อำเภอไม่อยู่ในทะเบียน → ตกไปตรวจต่อที่ GN
            return ("G5", f"ระบุเพียงจังหวัดที่มีพื้นที่ในลุ่มน้ำป่าสักบางส่วน: จ.{p} — {PARTIAL_PROVINCES[p]} "
                           "(ไม่ระบุอำเภอ จึงยังยืนยันตำแหน่งไม่ได้ — ไม่นับในยอดหลัก)",
                    " / ".join(provs), " / ".join(dict.fromkeys(dists)), f"จังหวัด {p}", "ต้องตรวจซ้ำ")

    # --- GS: ระบบชัยนาท-ป่าสัก แต่อยู่นอกพื้นที่ลุ่มน้ำ
    if pasak_word and any(p in provs for p in SYSTEM_OUTSIDE_PROVINCES):
        return ("GS", "งานอยู่ในระบบชลประทานชัยนาท-ป่าสัก แต่พื้นที่งานอยู่นอกขอบเขตลุ่มน้ำป่าสัก: "
                      f"จ.{prov}" + (f" อ.{dist}" if dist else ""),
                " / ".join(provs), " / ".join(dict.fromkeys(dists)), "ชัยนาท-ป่าสัก (นอกพื้นที่)",
                "ไม่นับเป็นในพื้นที่")

    # --- GN: ระบุพื้นที่อื่น (นอกลุ่มน้ำป่าสัก)
    if provs or dists:
        return ("GN", "ระบุพื้นที่จังหวัด/อำเภอที่อยู่นอกขอบเขตทะเบียนลุ่มน้ำป่าสัก: "
                      + " ".join([f"จ.{p}" for p in provs] + [f"อ.{d}" for d in dict.fromkeys(dists)]),
                " / ".join(provs), " / ".join(dict.fromkeys(dists)),
                f"จังหวัด {provs[0]}" if provs else f"อำเภอ {dists[0]}", "นอกพื้นที่")

    # --- GU: ไม่ระบุพื้นที่
    return ("GU", "ข้อความรายการไม่ระบุจังหวัด/อำเภอ/ตำบล (ระบุพื้นที่ไม่ได้จากข้อมูลชุดนี้)",
            "", "", "", "ระบุไม่ได้")


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


def main():
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        from openpyxl.formatting.rule import DataBarRule
        from openpyxl.chart import BarChart, Reference
    except ImportError:
        print("ต้องติดตั้ง openpyxl ก่อน:  pip install --break-system-packages openpyxl")
        return

    annual = list(read_rows(SRC_ANNUAL))
    commits = list(read_rows(SRC_COMMIT))

    rows_out = []
    for i, r in enumerate(annual, 1):
        g, reason, prov, dist, ev, conf = classify(r)
        rows_out.append({**r, "_group": g, "_reason": reason, "_prov": prov, "_dist": dist, "_ev": ev,
                         "_conf": conf, "_srcrow": i, "AMOUNT": to_num(r.get("AMOUNT"))})
    commits_out = []
    for i, r in enumerate(commits, 1):
        g, reason, prov, dist, ev, conf = classify(r)
        commits_out.append({**r, "_group": g, "_reason": reason, "_prov": prov, "_dist": dist, "_ev": ev,
                            "_conf": conf, "_srcrow": i, "AMOUNT": to_num(r.get("AMOUNT"))})

    # ------------------------------- สรุป -------------------------------
    def agg(rows, key):
        d = collections.defaultdict(lambda: {"n": 0, "amt": 0})
        for r in rows:
            k = key(r)
            d[k]["n"] += 1
            d[k]["amt"] += r["AMOUNT"]
        return d

    tot_all = sum(r["AMOUNT"] for r in rows_out)
    by_group = agg(rows_out, lambda r: r["_group"] or "(อื่น ๆ)")
    by_group_year = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rows_out:
        by_group_year[r["_group"] or "(อื่น ๆ)"][thai_year(r["FISCAL_YEAR"])] += r["AMOUNT"]
    years = sorted({thai_year(r["FISCAL_YEAR"]) for r in rows_out})
    in_basin = [r for r in rows_out if r["_group"] in IN_BASIN_GROUPS]
    tot_in = sum(r["AMOUNT"] for r in in_basin)
    tot_in_g123 = sum(r["AMOUNT"] for r in rows_out if r["_group"] in ("G1", "G2", "G3"))

    print("=" * 78)
    print("คัดเลือกงบประมาณด้านน้ำในพื้นที่ลุ่มน้ำป่าสัก พ.ศ. 2566–2569")
    print("=" * 78)
    print(f"รายการงบรายปีทั้งหมด           {len(rows_out):,} รายการ  {tot_all/1e9:,.3f} พันล้านบาท")
    print(f"เข้าเกณฑ์ในลุ่มน้ำป่าสัก (G1–G4) {len(in_basin):,} รายการ  {tot_in/1e9:,.3f} พันล้านบาท")
    print(f"  · หลักฐานชัด (G1–G3)         {sum(1 for r in rows_out if r['_group'] in ('G1','G2','G3')):,} รายการ  "
          f"{tot_in_g123/1e9:,.3f} พันล้านบาท")
    for g in ["G1", "G2", "G3", "G4", "G5", "GS", "GX", "GN", "GU"]:
        v = by_group.get(g, {"n": 0, "amt": 0})
        print(f"   {GROUP_LABEL[g]:<52} {v['n']:>5} รายการ  {v['amt']/1e9:>8.3f} พันล้านบาท")
    n_other = sum(v["n"] for k, v in by_group.items() if k not in GROUP_LABEL)
    if n_other:
        print(f"   (อื่น ๆ ที่ไม่เข้าเกณฑ์)                            {n_other:>5} รายการ")

    # --------------------------- เขียน Excel ---------------------------
    wb = Workbook()
    HEAD_FILL = PatternFill("solid", fgColor="1F4E79")
    HEAD_FONT = Font(bold=True, color="FFFFFF", size=11)
    TITLE_FONT = Font(bold=True, size=14, color="1F4E79")
    NOTE_FONT = Font(italic=True, size=10, color="555555")
    TOTAL_FILL = PatternFill("solid", fgColor="DDEBF7")
    BOLD = Font(bold=True)

    def add_sheet(title, cols, rows, widths=None, money_cols=(), year_cols=(), total_row=None,
                  data_bar_cols=(), wrap_all=False):
        ws = wb.create_sheet(title)
        ws.append(cols)
        for c in range(1, len(cols) + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = HEAD_FONT
            cell.fill = HEAD_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for r in rows:
            ws.append(r)
        ws.row_dimensions[1].height = 32
        if total_row is not None:
            ws.append(total_row)
            for c in range(1, len(cols) + 1):
                ws.cell(row=ws.max_row, column=c).font = BOLD
                ws.cell(row=ws.max_row, column=c).fill = TOTAL_FILL
        for i, w in enumerate(widths or [], start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        last = ws.max_row - (1 if total_row is not None else 0)
        for col in money_cols:
            for r in range(2, last + 1):
                ws.cell(row=r, column=col).number_format = "#,##0"
        for col in year_cols:
            for r in range(2, last + 1):
                ws.cell(row=r, column=col).number_format = "0"
        if total_row is not None:
            for col in range(2, len(cols) + 1):
                if isinstance(ws.cell(row=ws.max_row, column=col).value, (int, float)):
                    ws.cell(row=ws.max_row, column=col).number_format = "#,##0"
        if wrap_all:
            for r in range(2, last + 1):
                for c in range(1, len(cols) + 1):
                    ws.cell(row=r, column=c).alignment = Alignment(vertical="top", wrap_text=False)
        ws.freeze_panes = "A2"
        if last >= 1:
            ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{last}"
        for col in data_bar_cols:
            L = get_column_letter(col)
            ws.conditional_formatting.add(f"{L}2:{L}{last}",
                                          DataBarRule(start_type="num", start_value=0,
                                                      end_type="max", color="5B9BD5"))
        return ws

    # --- 1) วิธีคัดเลือก
    ws = wb.active
    ws.title = "วิธีคัดเลือก"
    ws.column_dimensions["A"].width = 120
    ctx = "".join(
        f"<br><b>{p}</b>: {PARTIAL_PROVINCES[p]}" for p in PARTIAL_PROVINCES)
    lines = [
        ("T", "โครงการงบประมาณด้านการบริหารจัดการน้ำ พ.ศ. 2566–2569 ในพื้นที่ “ลุ่มน้ำป่าสัก”"),
        ("", ""),
        ("B", "คำถาม/ขอบเขตของงาน"),
        ("", "คัดเลือกรายการงบประมาณด้านการบริหารจัดการน้ำ (จากผลวิเคราะห์ 3 แผนงานด้านทรัพยากรน้ำ + รายการน้ำ "
             "ที่อยู่นอกแผนงาน = 8,365 รายการ) เฉพาะรายการที่ “ลงในพื้นที่ลุ่มน้ำป่าสัก” พร้อมระบุเหตุผลการเลือก "
             "เป็นกลุ่มเหตุผล และช่องทางตรวจย้อนกลับไปยังเอกสารต้นฉบับ"),
        ("", ""),
        ("B", "ลุ่มน้ำป่าสัก — ขอบเขตอ้างอิง"),
        ("", "พื้นที่ลุ่มน้ำ 15,625.87 ตร.กม. ประกอบด้วย 8 ลุ่มน้ำสาขา (แม่น้ำป่าสักตอนบน · ห้วยน้ำพุง · "
             "แม่น้ำป่าสักส่วนที่ 2 · ส่วนที่ 3 · ห้วยเกาะแก้ว · ลำสนธิ · แม่น้ำป่าสักตอนล่าง · ห้วยมวกเหล็ก) "
             "แม่น้ำป่าสักไหลจากเทือกเขาเพชรบูรณ์ (อ.ด่านซ้าย จ.เลย) ผ่าน จ.เพชรบูรณ์ ลพบุรี สระบุรี "
             "ลงสู่แม่น้ำเจ้าพระยาที่ จ.พระนครศรีอยุธยา — พื้นที่หลักอยู่ใน 4 จังหวัด: เพชรบูรณ์ (68.8% ของจังหวัด) "
             "สระบุรี (69.9%) ลพบุรี (48.3%) และพระนครศรีอยุธยา (5.5%) และมีพื้นที่บางส่วนใน จ.เลย ชัยภูมิ "
             "นครราชสีมา (ตามเอกสาร “ข้อมูลพื้นฐาน 25 ลุ่มน้ำ” และเว็บไซต์ลุ่มน้ำป่าสัก กรมทรัพยากรน้ำ)"),
        ("", ""),
        ("B", "วิธีคัดเลือก (ขั้นตอน)"),
        ("", "1) ดึงข้อความบรรยายของแต่ละรายการ (ชื่อโครงการ · รายการไอเทม · หน่วยงาน · แผนงาน)"),
        ("", "2) ค้นคำบอกตำแหน่ง: ชื่อระบบป่าสัก (เขื่อนป่าสักชลสิทธิ์ · ลุ่มน้ำป่าสัก · ลำน้ำป่าสัก · "
             "โครงการส่งน้ำและบำรุงรักษาป่าสัก* · คลองชัยนาท-ป่าสัก) · ชื่ออำเภอ · ชื่อจังหวัด"),
        ("", "3) เทียบกับทะเบียนอำเภอ/จังหวัดของลุ่มน้ำป่าสัก (ชีต “ทะเบียนคำค้น”) แล้วจัดกลุ่มเหตุผล G1–G4"),
        ("", "4) แยกรายการที่ “เกี่ยวข้องเชิงระบบ” (งานในคลองชัยนาท-ป่าสัก แต่พื้นที่งานอยู่นอกลุ่มน้ำ: "
             "ชัยนาท สิงห์บุรี นครสวรรค์) เป็นกลุ่ม GS และรายการที่คำว่า “ป่าสัก” เป็นชื่อซ้ำในจังหวัดอื่น "
             "(แพร่ เชียงราย สุโขทัย หนองคาย พิษณุโลก) เป็นกลุ่ม GX เพื่อความโปร่งใส"),
        ("", "5) รายการที่ไม่ระบุพื้นที่ใด ๆ ในข้อความ เก็บไว้ในชีต “GU ไม่ระบุพื้นที่” เพื่อให้เห็นขนาดของ "
             "ส่วนที่ระบุพื้นที่ไม่ได้ (ไม่นับเป็นลุ่มน้ำป่าสัก)"),
        ("", ""),
        ("B", "กลุ่มเหตุผลการเลือก (คอลัมน์ “กลุ่มเหตุผล” และ “เหตุผลการคัดเลือก”)"),
        ("", "G1 · หลักฐานตรง — ข้อความระบุระบบป่าสักโดยตรง และพื้นที่งานอยู่ในจังหวัดของลุ่มน้ำป่าสัก "
             "(ความเชื่อมั่น สูง)"),
        ("", "G2 · อำเภอ/ตำบลในลุ่มน้ำป่าสัก — ระบุอำเภอที่อยู่ในทะเบียนอำเภอของลุ่มน้ำป่าสัก "
             "(ความเชื่อมั่น สูง–กลาง)"),
        ("", "G3 · จังหวัดหลักของลุ่มน้ำ — ระบุจังหวัด เพชรบูรณ์/ลพบุรี/สระบุรี แต่ไม่ระบุอำเภอ "
             "(ความเชื่อมั่น กลาง: จังหวัดมีพื้นที่ในลุ่มน้ำ 48–70% จึงอาจมีรายการที่อยู่นอกลุ่มน้ำปนอยู่)"),
        ("", "G4 · อำเภอ “บางส่วน” — ระบุอำเภอที่อยู่ในทะเบียนของจังหวัดที่มีพื้นที่ในลุ่มน้ำบางส่วน "
             "(อยุธยา: ท่าเรือ นครหลวง ภาชี บ้านแพรก บางปะหัน มหาราช วังน้อย อุทัย · เลย: ด่านซ้าย · "
             "ชัยภูมิ: ภูเขียว คอนสาร เนินสง่า ซับใหญ่ เทพสถิต · นครราชสีมา: ปากช่อง สีคิ้ว เทพารักษ์ "
             "วังน้ำเขียว · นครนายก: ปากพลี บ้านนา) — ต้องตรวจซ้ำกับแผนที่ลุ่มน้ำก่อนใช้ตัดสินใจ"),
        ("", "G5 · ระบุเพียงจังหวัดที่มีพื้นที่บางส่วน (ไม่ระบุอำเภอ) — ยังยืนยันตำแหน่งไม่ได้ "
             "จึงแยกไว้ต่างหาก ไม่นับรวมในยอด “ในพื้นที่ลุ่มน้ำป่าสัก”"),
        ("", "GS · ระบบชัยนาท-ป่าสัก แต่นอกพื้นที่ — งานในระบบส่งน้ำที่เกี่ยวข้องกับป่าสัก แต่พื้นที่งานอยู่ "
             "จ.ชัยนาท/สิงห์บุรี/นครสวรรค์ (ไม่นับเป็น “ในพื้นที่ลุ่มน้ำป่าสัก”)"),
        ("", "GX · ตัดออก — คำว่า “ป่าสัก” เป็นชื่อตำบล/บ้าน/สถานีในจังหวัดอื่น (แพร่ เชียงราย สุโขทัย "
             "หนองคาย พิษณุโลก) ตรวจทีละรายการแล้ว"),
        ("", ""),
        ("B", "การตรวจย้อนกลับไปยังไฟล์ต้นฉบับ (ทุกชีตรายการ)"),
        ("", "คอลัมน์ REF_DOC = ชื่อไฟล์/เล่มเอกสารต้นทาง · REF_PAGE_NO = เลขหน้า/ลำดับในเอกสารนั้น · "
             "Source_Sheet = ชีตที่ดึงข้อมูลมา (66_RELEASE_22-07-14 = เอกสารปีงบประมาณ 2566, "
             "67_ขาวคาดแดง… = 2567, 68_2024-06-15 = 2568, 69_2025-05-25 = 2569) · "
             "แถวในไฟล์กลาง (data row) = ลำดับแถวข้อมูลในไฟล์กลาง (เริ่มที่ 1 ไม่นับหัวตาราง)"),
        ("", "ขั้นตอนตรวจย้อนกลับ: 1) เปิด output/water/water_budget_detail_2566-2569.csv.gz "
             "2) ไปที่ “แถวในไฟล์กลาง” ที่ระบุ (แม่นยำที่สุด) หรือค้นด้วย REF_DOC + REF_PAGE_NO + ข้อความรายการ "
             "3) เปิดเอกสารต้นฉบับตามชื่อ REF_DOC ที่หน้า REF_PAGE_NO 4) เทียบข้อความ ITEM_DESCRIPTION "
             "กับเอกสาร — ใช้ 4 มิติร่วมกัน (REF_DOC + หน้า + จำนวนเงิน + ข้อความรายการ) เพราะเอกสารประเภท "
             "Excel มีเลขหน้าซ้ำได้"),
        ("", "เอกสารต้นฉบับอยู่ที่ไหน: ชื่อไฟล์ใน REF_DOC อ้างอิงไฟล์ต้นทางของโครงการวิเคราะห์นี้ "
             "(ฉบับร่างพระราชบัญญัติงบประมาณรายจ่าย PDF/Excel ของสำนักงบประมาณ) — ดูสาราง "
             "“ตรวจย้อนกลับเอกสาร” ท้ายไฟล์สำหรับสรุปจำนวนรายการต่อเอกสาร"),
        ("", ""),
        ("B", f"ผลการคัดเลือก — เข้าเกณฑ์ในลุ่มน้ำป่าสัก {len(in_basin):,} รายการ "
              f"{tot_in/1e9:,.3f} พันล้านบาท (จากรายการงบน้ำทั้งหมด {len(rows_out):,} รายการ "
              f"{tot_all/1e9:,.3f} พันล้านบาท)"),
        ("", f"แยกกลุ่ม: " + " · ".join(
            f"{g} {by_group.get(g, {}).get('n', 0):,} รายการ {by_group.get(g, {}).get('amt', 0)/1e9:,.3f} พันล้านบาท"
            for g in ["G1", "G2", "G3", "G4"])),
        ("", f"นอกรายการที่เข้าเกณฑ์: G5 {by_group.get('G5', {}).get('n', 0):,} รายการ · "
             f"GS {by_group.get('GS', {}).get('n', 0):,} รายการ · "
             f"GX {by_group.get('GX', {}).get('n', 0):,} รายการ · "
             f"GU (ไม่ระบุพื้นที่) {by_group.get('GU', {}).get('n', 0):,} รายการ"),
        ("", ""),
        ("B", "สารบัญชีต"),
        ("", "1. วิธีคัดเลือก (ชีตนี้) · 2. สรุปภาพรวม · 3. สรุปโครงการ (ระดับโครงการ) · 4. รายการที่คัดเลือก "
             "(ทุกรายการ G1–G4 พร้อมเหตุผล) · 5–8. G1 / G2 / G3 / G4 (แยกกลุ่ม) · 9. G5 ระบุจังหวัด-รอตรวจ · "
             "10. GS นอกพื้นที่ · 11. GX ตัดออก · 12. GU ไม่ระบุพื้นที่ · 13. สรุปหน่วยงาน · 14. สรุปพื้นที่ · "
             "15. ทะเบียนคำค้น (gazetteer) · 16. ภาระผูกพันในพื้นที่ลุ่มน้ำ · 17. ตรวจย้อนกลับเอกสารต้นฉบับ"),
        ("", ""),
        ("B", "ข้อจำกัดที่ต้องแจ้งก่อนใช้ตัวเลข"),
        ("", "· การคัดเลือกอิง “ข้อความบรรยายรายการ” ไม่ใช่พิกัดพิกัด/รหัสลุ่มน้ำ — รายการที่ไม่ได้ระบุชื่อ "
             "อำเภอ/จังหวัดในข้อความ (แม้องค์กรจะอยู่ในลุ่มน้ำ) จะถูกจัดเป็น GU และไม่ถูกรวม"),
        ("", "· รายการระดับจังหวัด (G3) และจังหวัดบางส่วน (G4) อาจมีพื้นที่บางรายการนอกลุ่มน้ำ "
             "ควรตรวจกับแผนที่/รายงานของหน่วยงานก่อนใช้ตัดสินใจลงทุน"),
        ("", "· งานในระบบชลประทานชัยนาท-ป่าสัก ที่ตั้งอยู่ใน จ.ชัยนาท สิงห์บุรี นครสวรรค์ ถูกแยกเป็น GS "
             "เพราะเป็น “การส่งน้ำเข้าสู่ลุ่มน้ำ” ไม่ใช่พื้นที่ปลายทางของงบ"),
        ("", "· ตัวเลขเป็นงบประมาณรายจ่ายรายปีจากร่าง พ.ร.บ. ฉบับที่ 3–4 ไม่ใช่ยอดเบิกจ่ายจริง"),
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

    # --- 1.1) ตารางตรวจความครอบคลุมรายจังหวัด (สำหรับผู้ตรวจสอบ)
    ws.append([""])
    ws.append(["ตารางตรวจความครอบคลุมรายจังหวัด (สำหรับผู้ตรวจสอบ — ทำไมรายการจึงถูก/ไม่ถูกคัดเข้า)"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, color="1F4E79")
    audit_provs = list(BASIN_PROVINCES) + list(PARTIAL_PROVINCES)
    cov = collections.defaultdict(lambda: {"n": 0, "in": 0, "amt": 0, "grp": collections.Counter()})
    for r in rows_out:
        t = blob_of(r)
        for p in audit_provs:
            if p in t:
                cov[p]["n"] += 1
                if r["_group"] in IN_BASIN_GROUPS:
                    cov[p]["in"] += 1
                    cov[p]["amt"] += r["AMOUNT"]
                    cov[p]["grp"][r["_group"]] += 1
    ws.append(["จังหวัด", "รายการที่ระบุชื่อจังหวัดนี้", "ถูกจัดเป็น “ในลุ่มน้ำป่าสัก” (G1–G4)",
               "สัดส่วน", "เงินที่คัด (บาท)", "กลุ่มที่พบ"])
    for c in ws[ws.max_row]:
        c.font = BOLD
    for p, v in sorted(cov.items(), key=lambda kv: -kv[1]["n"]):
        ws.append([p, v["n"], v["in"], v["in"] / v["n"] if v["n"] else 0, v["amt"],
                   ", ".join(f"{g} {n}" for g, n in sorted(v["grp"].items()))])
        ws.cell(row=ws.max_row, column=4).number_format = "0.0%"
        ws.cell(row=ws.max_row, column=5).number_format = "#,##0"
    ws.append(["หมายเหตุ: พระนครศรีอยุธยามีพื้นที่ในลุ่มน้ำป่าสักเพียง ~5.5% (ฝั่งตะวันออกของจังหวัด) "
               "รายการส่วนใหญ่จึงอยู่ฝั่งตะวันตก (บางไทร บางบาล เสนา ผักไห่ ลาดบัวหลวง) และถูกจัดเป็น GN "
               "โดยเจตนา — จังหวัดที่มีพื้นที่บางส่วน (เลย/ชัยภูมิ/นครราชสีมา/นครนายก) จะถูกจัดเป็น G4/G5 "
               "เมื่อระบุอำเภอที่อยู่ในทะเบียน"])
    ws.cell(row=ws.max_row, column=1).font = NOTE_FONT
    ws.cell(row=ws.max_row, column=1).alignment = Alignment(wrap_text=True, vertical="top")

    # --- 2) สรุปภาพรวม
    ws2 = add_sheet("สรุปภาพรวม", ["กลุ่มเหตุผล", "จำนวนรายการ", "จำนวนเงิน (บาท)", "สัดส่วนของรายการที่คัดเลือก"],
                    [[GROUP_LABEL[g], by_group.get(g, {"n": 0})["n"], by_group.get(g, {"amt": 0})["amt"],
                      (by_group.get(g, {"amt": 0})["amt"] / tot_in if tot_in and g in IN_BASIN_GROUPS else 0)]
                     for g in ["G1", "G2", "G3", "G4", "G5", "GS", "GX", "GN", "GU"]],
                    widths=[46, 14, 20, 24], money_cols=[3],
                    total_row=["รวมรายการที่คัดเลือกเขาลุ่มน้ำป่าสัก", len(in_basin), tot_in, 1.0])
    for r in range(2, 10):
        ws2.cell(row=r, column=4).number_format = "0.0%"
    ws2.cell(row=ws2.max_row, column=4).number_format = "0.0%"
    # ตารางรายปี
    r0 = ws2.max_row + 3
    ws2.cell(row=r0, column=1, value="ยอดรายปี (เฉพาะ G1–G4 = ในพื้นที่ลุ่มน้ำป่าสัก)").font = BOLD
    ws2.cell(row=r0 + 1, column=1, value="ปีงบประมาณ (พ.ศ.)").font = BOLD
    for i, y in enumerate(years):
        c = ws2.cell(row=r0 + 1, column=2 + i, value=y)
        c.number_format = "0"
        c.font = BOLD
    ws2.cell(row=r0 + 2, column=1, value="จำนวนเงิน (บาท)").font = BOLD
    for i, y in enumerate(years):
        ws2.cell(row=r0 + 2, column=2 + i,
                 value=sum(r["AMOUNT"] for r in in_basin if thai_year(r["FISCAL_YEAR"]) == y)).number_format = "#,##0"
    # ตารางกลุ่ม × ปี
    r1 = r0 + 4
    ws2.cell(row=r1, column=1, value="แยกตามกลุ่มเหตุผล × ปี (บาท)").font = BOLD
    heads = ["กลุ่มเหตุผล"] + [f"พ.ศ. {y}" for y in years] + ["รวม"]
    for i, h in enumerate(heads):
        c = ws2.cell(row=r1 + 1, column=1 + i, value=h)
        c.font = HEAD_FONT
        c.fill = HEAD_FILL
    for j, g in enumerate(["G1", "G2", "G3", "G4", "G5", "GS", "GX", "GN", "GU"]):
        rr = r1 + 2 + j
        ws2.cell(row=rr, column=1, value=GROUP_LABEL[g])
        for i, y in enumerate(years):
            ws2.cell(row=rr, column=2 + i, value=by_group_year.get(g, {}).get(y, 0)).number_format = "#,##0"
        ws2.cell(row=rr, column=2 + len(years),
                 value=sum(by_group_year.get(g, {}).values())).number_format = "#,##0"
    ch = BarChart()
    ch.type = "col"
    ch.title = "งบประมาณด้านน้ำในลุ่มน้ำป่าสัก รายปี (บาท) — กลุ่ม G1–G4"
    ch.y_axis.title = "บาท"
    ch.x_axis.title = "ปีงบประมาณ (พ.ศ.)"
    data = Reference(ws2, min_col=2, max_col=1 + len(years), min_row=r0 + 1, max_row=r0 + 2)
    ch.add_data(data, titles_from_data=True, from_rows=True)
    ch.set_categories(Reference(ws2, min_col=2, max_col=1 + len(years), min_row=r0 + 1, max_row=r0 + 1))
    ch.height, ch.width = 9, 20
    ws2.add_chart(ch, f"A{r1 + 14}")

    # --- 3) สรุปโครงการ
    proj = collections.defaultdict(lambda: {"n": 0, "amt": 0, "by": collections.defaultdict(float),
                                            "groups": collections.Counter(), "unit": "", "years": set()})
    for r in in_basin:
        k = (r["PROJECT"] or "(ไม่ระบุโครงการ)", r["BUDGETARY_UNIT"])
        p = proj[k]
        p["n"] += 1
        p["amt"] += r["AMOUNT"]
        p["by"][thai_year(r["FISCAL_YEAR"])] += r["AMOUNT"]
        p["groups"][r["_group"]] += 1
        p["years"].add(r["FISCAL_YEAR"])
    proj_rows = []
    for (name, unit), p in sorted(proj.items(), key=lambda kv: -kv[1]["amt"]):
        proj_rows.append([name, unit, ", ".join(sorted(p["groups"], key=lambda g: g)), p["n"]]
                         + [p["by"].get(y, 0) for y in years] + [p["amt"]])
    add_sheet("สรุปโครงการ", ["โครงการ", "หน่วยงาน", "กลุ่มเหตุผลที่พบ", "จำนวนรายการ"]
              + [f"พ.ศ. {y}" for y in years] + ["รวม (บาท)"],
              proj_rows, widths=[64, 30, 18, 10] + [16] * len(years) + [20],
              money_cols=list(range(5, 6 + len(years))), data_bar_cols=[5 + len(years)],
              total_row=["รวมทุกโครงการ", "", "", len(in_basin)] +
                        [sum(r["AMOUNT"] for r in in_basin if thai_year(r["FISCAL_YEAR"]) == y) for y in years]
                        + [tot_in])

    # --- 4) รายการที่คัดเลือก (G1–G4)
    DET_COLS = ["ลำดับ", "กลุ่มเหตุผล", "เหตุผลการคัดเลือก", "ความเชื่อมั่น",
                "ปีงบประมาณ (พ.ศ.)", "ปี (ค.ศ.)", "ขอบเขตน้ำ", "กระทรวง", "หน่วยงาน", "แผนงาน",
                "โครงการ", "รายการ (ไอเทม)", "จำนวนเงิน (บาท)",
                "จังหวัดที่ระบุ", "อำเภอที่ระบุ", "คำหลักฐาน",
                "REF_DOC (เอกสารต้นฉบับ)", "REF_PAGE_NO (หน้า)", "Source_Sheet (ชีตต้นทาง)",
                "แถวในไฟล์กลาง (data row)", "dq_flag"]
    DET_W = [7, 22, 56, 12, 14, 10, 10, 26, 30, 40, 50, 62, 18, 22, 22, 24, 46, 10, 18, 16, 22]

    def det_rows(rows):
        out = []
        for i, r in enumerate(sorted(rows, key=lambda r: (-r["AMOUNT"])), 1):
            out.append([i, r["_group"], r["_reason"], r.get("_conf") or CONFIDENCE.get(r["_group"], ""),
                        thai_year(r["FISCAL_YEAR"]), to_num(r["FISCAL_YEAR"]), r["water_scope"],
                        r["MINISTRY"], r["BUDGETARY_UNIT"], r["BUDGET_PLAN"], r["PROJECT"],
                        r["ITEM_DESCRIPTION"], r["AMOUNT"], r["_prov"], r["_dist"], r["_ev"],
                        r["REF_DOC"], r["REF_PAGE_NO"], r["Source_Sheet"], r["_srcrow"], r["dq_flag"]])
        return out

    add_sheet("รายการที่คัดเลือก(G1-G4)", DET_COLS, det_rows(in_basin), widths=DET_W,
              money_cols=[13], year_cols=[5, 6], data_bar_cols=[13])
    sheet_of = {"G1": "G1 หลักฐานตรง ป่าสัก", "G2": "G2 อำเภอในลุ่มน้ำ",
                "G3": "G3 จังหวัดหลัก", "G4": "G4 บางส่วน-ตรวจซ้ำ"}
    for g in ["G1", "G2", "G3", "G4"]:
        add_sheet(sheet_of[g], DET_COLS, det_rows([r for r in rows_out if r["_group"] == g]),
                  widths=DET_W, money_cols=[13], year_cols=[5, 6], data_bar_cols=[13])
    add_sheet("G5 ระบุจังหวัด-รอตรวจ", DET_COLS, det_rows([r for r in rows_out if r["_group"] == "G5"]),
              widths=DET_W, money_cols=[13], year_cols=[5, 6])
    add_sheet("GS นอกพื้นที่ลุ่มน้ำ", DET_COLS, det_rows([r for r in rows_out if r["_group"] == "GS"]),
              widths=DET_W, money_cols=[13], year_cols=[5, 6])
    add_sheet("GX ตัดออก", DET_COLS, det_rows([r for r in rows_out if r["_group"] == "GX"]),
              widths=DET_W, money_cols=[13], year_cols=[5, 6])

    # --- 11) GU ไม่ระบุพื้นที่ (สรุป + รายการ)
    gu = [r for r in rows_out if r["_group"] == "GU"]
    gu_rows = [[i, r["water_scope"], thai_year(r["FISCAL_YEAR"]), r["MINISTRY"], r["BUDGETARY_UNIT"],
                r["BUDGET_PLAN"], r["PROJECT"], r["ITEM_DESCRIPTION"], r["AMOUNT"],
                r["REF_DOC"], r["REF_PAGE_NO"], r["Source_Sheet"], r["_srcrow"]]
               for i, r in enumerate(sorted(gu, key=lambda r: -r["AMOUNT"]), 1)]
    add_sheet("GU ไม่ระบุพื้นที่", ["ลำดับ", "ขอบเขตน้ำ", "ปีงบประมาณ (พ.ศ.)", "กระทรวง", "หน่วยงาน", "แผนงาน",
                                   "โครงการ", "รายการ (ไอเทม)", "จำนวนเงิน (บาท)",
                                   "REF_DOC (เอกสารต้นฉบับ)", "REF_PAGE_NO (หน้า)", "Source_Sheet (ชีตต้นทาง)",
                                   "แถวในไฟล์กลาง (data row)"],
              gu_rows, widths=[7, 10, 14, 26, 30, 40, 50, 62, 18, 46, 10, 18, 16], money_cols=[9],
              year_cols=[3],
              total_row=["รวม", "", "", "", "", "", "", "", sum(r["AMOUNT"] for r in gu), "", "", "", ""])

    # --- 11.2) สรุปหน่วยงาน (เฉพาะที่คัดเลือก)
    un = collections.defaultdict(lambda: {"n": 0, "amt": 0, "by": collections.defaultdict(float),
                                          "groups": collections.Counter()})
    for r in in_basin:
        u = un[r["BUDGETARY_UNIT"]]
        u["n"] += 1
        u["amt"] += r["AMOUNT"]
        u["by"][thai_year(r["FISCAL_YEAR"])] += r["AMOUNT"]
        u["groups"][r["_group"]] += 1
    add_sheet("สรุปหน่วยงาน",
              ["หน่วยงาน", "กระทรวง", "กลุ่มเหตุผล", "จำนวนรายการ"] + [f"พ.ศ. {y}" for y in years] + ["รวม (บาท)"],
              [[k, next((r["MINISTRY"] for r in in_basin if r["BUDGETARY_UNIT"] == k), ""),
                ", ".join(sorted(v["groups"], key=lambda g: g)), v["n"]]
               + [v["by"].get(y, 0) for y in years] + [v["amt"]]
               for k, v in sorted(un.items(), key=lambda kv: -kv[1]["amt"])],
              widths=[44, 30, 16, 12] + [16] * len(years) + [20],
              money_cols=list(range(5, 6 + len(years))), data_bar_cols=[5 + len(years)],
              total_row=["รวมทุกหน่วยงาน", "", "", len(in_basin)]
                        + [sum(r["AMOUNT"] for r in in_basin if thai_year(r["FISCAL_YEAR"]) == y) for y in years]
                        + [tot_in])

    # --- 11.3) สรุปพื้นที่ (จังหวัด × อำเภอ)
    ar = collections.defaultdict(lambda: {"n": 0, "amt": 0, "by": collections.defaultdict(float),
                                          "groups": collections.Counter()})
    for r in in_basin:
        key = (r["_prov"].split(" / ")[0] or "(ไม่ระบุจังหวัด)", r["_dist"].split(" / ")[0] or "(ไม่ระบุอำเภอ)")
        a = ar[key]
        a["n"] += 1
        a["amt"] += r["AMOUNT"]
        a["by"][thai_year(r["FISCAL_YEAR"])] += r["AMOUNT"]
        a["groups"][r["_group"]] += 1
    add_sheet("สรุปพื้นที่",
              ["จังหวัดที่ระบุ", "อำเภอที่ระบุ", "กลุ่มเหตุผล", "จำนวนรายการ"]
              + [f"พ.ศ. {y}" for y in years] + ["รวม (บาท)"],
              [[k[0], k[1], ", ".join(sorted(v["groups"], key=lambda g: g)), v["n"]]
               + [v["by"].get(y, 0) for y in years] + [v["amt"]]
               for k, v in sorted(ar.items(), key=lambda kv: -kv[1]["amt"])],
              widths=[22, 24, 16, 12] + [16] * len(years) + [20],
              money_cols=list(range(5, 6 + len(years))), data_bar_cols=[5 + len(years)],
              total_row=["รวม", "", "", len(in_basin)]
                        + [sum(r["AMOUNT"] for r in in_basin if thai_year(r["FISCAL_YEAR"]) == y) for y in years]
                        + [tot_in])

    # --- 12) ทะเบียนคำค้น
    gaz = []
    for p, ds in BASIN_DISTRICTS.items():
        for d in ds:
            gaz.append([f"อำเภอ {d}", "อำเภอในลุ่มน้ำป่าสัก", p,
                        "ทะเบียนอำเภอของลุ่มน้ำป่าสัก (8 ลุ่มน้ำสาขา + พื้นที่โครงการเขื่อนป่าสักชลสิทธิ์/"
                        "พื้นที่ชลประทานป่าสักใต้)", "สูง", "G2"])
    for p, note in PARTIAL_PROVINCES.items():
        gaz.append([f"จังหวัด {p}", "จังหวัดที่มีพื้นที่ในลุ่มน้ำบางส่วน", p, note, "ต้องตรวจซ้ำ", "G4"])
        for d in PARTIAL_DISTRICTS.get(p, []):
            gaz.append([f"อำเภอ {d}", "อำเภอที่มีพื้นที่ในลุ่มน้ำบางส่วน", p, note, "ต้องตรวจซ้ำ", "G4"])
    for p in BASIN_PROVINCES:
        gaz.append([f"จังหวัด {p}", "จังหวัดหลักของลุ่มน้ำป่าสัก", p,
                    "พื้นที่จังหวัดในลุ่มน้ำ: เพชรบูรณ์ 68.8% · สระบุรี 69.9% · ลพบุรี 48.3% "
                    "(กรมทรัพยากรน้ำ/เอกสารข้อมูลพื้นฐาน 25 ลุ่มน้ำ)", "กลาง", "G3"])
    for k in PASAK_OFFICES:
        gaz.append([f"หน่วยงาน/โครงการ “{k}”", "สำนักงานชลประทาน/โครงการในลุ่มน้ำป่าสัก", "-",
                    "ชื่อหน่วยปฏิบัติที่ตั้งอยู่ในลุ่มน้ำป่าสัก (เช่น โครงการส่งน้ำและบำรุงรักษาเริงราง "
                    "และสำนักงานชลประทานที่ 10 ซึ่งดูแลพื้นที่ลุ่มน้ำป่าสัก)", "สูง", "G1"])
    for k in OFFICES_OUTSIDE:
        gaz.append([f"หน่วยงาน/โครงการ “{k}”", "หน่วยปฏิบัติในระบบชัยนาท-ป่าสัก แต่อยู่นอกลุ่มน้ำ", "-",
                    "งานส่งน้ำของคลองชัยนาท-ป่าสักที่ตั้งอยู่ใน จ.ชัยนาท/นครสวรรค์", "ไม่นับเป็นในพื้นที่", "GS"])
    for k in PARTIAL_OFFICES:
        gaz.append([f"หน่วยงาน/โครงการ “{k}”", "หน่วยปฏิบัติที่ดูแลพื้นที่บางส่วนของลุ่มน้ำ", "-",
                    "จังหวัดพระนครศรีอยุธยามีพื้นที่ในลุ่มน้ำป่าสักเพียง 5.5% — ต้องตรวจตำแหน่งงานเป็นรายกรณี",
                    "ต้องตรวจซ้ำ", "G5"])
    for k in PASAK_SYSTEM:
        gaz.append([f"คำเฉพาะ “{k}”", "ชื่อระบบ/โครงการของลุ่มน้ำป่าสัก", "-",
                    "เขื่อนป่าสักชลสิทธิ์ · โครงการส่งน้ำและบำรุงรักษาป่าสักชลสิทธิ์/ป่าสักใต้ · "
                    "คลองชัยนาท-ป่าสัก", "สูง", "G1"])
    for p, marks in HOMONYM.items():
        gaz.append([f"คำว่า “ป่าสัก” ในจังหวัด {p}", "ชื่อซ้ำ — ตัดออก", p,
                    "ชื่อตำบล/บ้าน/สถานีที่ซ้ำกับคำว่าป่าสัก: " + ", ".join(marks), "ตัดออก", "GX"])
    for p in SYSTEM_OUTSIDE_PROVINCES:
        gaz.append([f"จังหวัด {p}", "พื้นที่ในระบบชัยนาท-ป่าสัก แต่อยู่นอกลุ่มน้ำ", p,
                    "งานคลองชัยนาท-ป่าสักที่ตั้งอยู่ในจังหวัดนี้ (ส่งน้ำเข้าสู่ลุ่มน้ำ)", "ไม่นับเป็นในพื้นที่", "GS"])
    add_sheet("ทะเบียนคำค้น(gazetteer)",
              ["คำค้นที่ใช้", "ประเภท", "จังหวัด", "หลักฐาน/แหล่งอ้างอิง", "ระดับความเชื่อมั่น", "กลุ่มเหตุผล"],
              gaz, widths=[30, 34, 18, 62, 18, 12])

    # --- 13) ภาระผูกพันในพื้นที่ลุ่มน้ำ
    cb = [r for r in commits_out if r["_group"] in IN_BASIN_GROUPS]
    cb_rows = det_rows(cb)
    add_sheet("ภาระผูกพันในลุ่มน้ำ", DET_COLS, cb_rows, widths=DET_W, money_cols=[13], year_cols=[5, 6])
    r0 = ws2.max_row  # (ไม่ใช้)
    ws_cb = wb["ภาระผูกพันในลุ่มน้ำ"]
    rr = ws_cb.max_row + 2
    ws_cb.cell(row=rr, column=1,
               value=f"รวมภาระผูกพันในพื้นที่ลุ่มน้ำป่าสัก {len(cb):,} รายการ "
                     f"{sum(r['AMOUNT'] for r in cb)/1e6:,.1f} ล้านบาท — "
                     "เป็น “สัญญาที่ผูกพันไว้แล้ว” จากตารางภาระผูกพันของเอกสารแต่ละฉบับ "
                     "ห้ามนำไปรวมกับงบประมาณรายจ่ายรายปี").font = Font(bold=True, color="C00000")

    # --- 14) ตรวจย้อนกลับเอกสารต้นฉบับ
    docs = collections.defaultdict(lambda: {"n": 0, "amt": 0, "rows": 0})
    for r in rows_out:
        d = (r["REF_DOC"] or "").split("/")[0].strip() or "(ไม่ระบุ)"
        shell = (r["Source_Sheet"] or "").split("#")[0]
        key = (shell, d)
        docs[key]["n"] += 1
        docs[key]["amt"] += r["AMOUNT"]
        if r["_group"] in IN_BASIN_GROUPS:
            docs[key]["rows"] += 1
    rev = [[shell, d, ({"66_RELEASE_22-07-14": "เอกสารงบประมาณ พ.ศ. 2566",
                        "67_ขาวคาดแดง RELEASE_2023-12-30": "เอกสารงบประมาณ พ.ศ. 2567",
                        "68_2024-06-15": "เอกสารงบประมาณ พ.ศ. 2568",
                        "69_2025-05-25": "เอกสารงบประมาณ พ.ศ. 2569"}).get(shell, ""),
            v["n"], v["rows"], v["amt"]]
           for (shell, d), v in sorted(docs.items(), key=lambda kv: kv[0])]
    add_sheet("ตรวจย้อนกลับเอกสาร",
              ["Source_Sheet (ชีตต้นทาง)", "REF_DOC (เอกสาร)", "เอกสารคือ", "จำนวนรายการในไฟล์นี้",
               "จำนวนรายการที่คัดเลือก", "จำนวนเงิน (บาท)"],
              rev, widths=[34, 42, 24, 18, 18, 20], money_cols=[6],
              total_row=["รวม", "", "", sum(v["n"] for v in docs.values()),
                         sum(v["rows"] for v in docs.values()),
                         sum(v["amt"] for v in docs.values())])
    ws_rev = wb["ตรวจย้อนกลับเอกสาร"]
    rr = ws_rev.max_row + 2
    ws_rev.cell(row=rr, column=1,
                value="วิธีตรวจ: เปิด output/water/water_budget_detail_2566-2569.csv.gz → กรอง REF_DOC + "
                      "REF_PAGE_NO ของแถวที่ต้องการ → เปิดเอกสารต้นฉบับตามชื่อ REF_DOC ที่หน้าที่ระบุ → "
                      "เทียบข้อความรายการกับ ITEM_DESCRIPTION").font = Font(bold=True, color="1F4E79")

    os.makedirs(DOCSDATA, exist_ok=True)
    wb.save(OUT_XLSX)
    try:
        with open(OUT_XLSX, "rb") as src, open(os.path.join(DOCSDATA, os.path.basename(OUT_XLSX)), "wb") as dst:
            dst.write(src.read())
    except OSError as exc:
        print("  ! คัดลอกไฟล์ไป docs/data ไม่ได้:", exc)
    print(f"\n  → {os.path.relpath(OUT_XLSX, ROOT)} ({len(wb.sheetnames)} ชีต)")
    print("     " + ", ".join(wb.sheetnames))


if __name__ == "__main__":
    main()
