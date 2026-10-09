#!/usr/bin/env python3
"""
สร้างเว็บเวอร์ชัน static ลง docs/ สำหรับ GitHub Pages

- คัดลอก web/static/* -> docs/static/* (พร้อม patch 5 จุดให้ใช้ data engine ในเครื่อง)
- คัดลอก output/*.csv.gz -> docs/data/* (ไฟล์เดียวกันทั้งแท่ง เบราว์เซอร์แกะ gzip เอง)
- รันซ้ำได้ทุกเมื่อ:  python3 web/build_static.py

หมายเหตุ: ถ้า anchor สำหรับ patch ไม่เจอ สคริปต์จะ error ทันที (fail loudly)
เพื่อให้รู้ว่า web/static เปลี่ยนจน patch ใช้ไม่ได้แล้ว
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "web", "static")
DOCS = os.path.join(ROOT, "docs")


def patch(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        print(f"❌ PATCH FAILED [{label}]: เจอ anchor {n} ครั้ง (ต้องเจอ 1 ครั้งพอดี)")
        sys.exit(1)
    return text.replace(old, new, 1)


def main() -> None:
    # --- 1. โครงโฟลเดอร์ ---
    for d in (DOCS, os.path.join(DOCS, "static"), os.path.join(DOCS, "data")):
        os.makedirs(d, exist_ok=True)

    # --- 2. index.html ---
    html = open(os.path.join(SRC, "index.html"), encoding="utf-8").read()
    html = patch(html,
                 '<script src="/static/app.js"></script>',
                 '<script src="static/vendor/papaparse.min.js"></script>\n'
                 '<script src="static/vendor/xlsx.full.min.js"></script>\n'
                 '<script src="static/api.js"></script>\n'
                 '<script src="static/app.js"></script>',
                 "index.html scripts")
    html = html.replace("/static/", "static/")  # relative path สำหรับ project pages
    open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(html)

    # --- 3. style.css ---
    css = open(os.path.join(SRC, "style.css"), encoding="utf-8").read()
    css = css.replace("/static/fonts/", "../fonts/")
    open(os.path.join(DOCS, "static", "style.css"), "w", encoding="utf-8").write(css)

    # --- 4. app.js + patches ---
    app = open(os.path.join(SRC, "app.js"), encoding="utf-8").read()

    # (a) ใช้ local api แทน fetch backend
    app = patch(app,
                "async function api(path) {\n"
                "  const r = await fetch(path);\n"
                "  if (!r.ok) throw new Error(`API ${r.status}`);\n"
                "  return r.json();\n"
                "}",
                "async function api(path) {\n"
                "  return window.__localApi(path); // static build: คำนวณในเครื่อง (api.js)\n"
                "}",
                "app.js api()")
    # (b) รอโหลดข้อมูลก่อน render ครั้งแรก
    app = patch(app,
                "    state.meta = await api('/api/meta');",
                "    await window.__dataReady;\n"
                "    state.meta = await api('/api/meta');",
                "app.js boot")
    # (c) export ฝั่ง client (CSV/Excel ที่กรอง + Excel ทั้งฐาน)
    app = patch(app,
                "  exportCSV() {\n"
                "    toast('กำลังส่งออก CSV…');\n"
                "    window.location = `/api/export?${searchQuery()}`;\n"
                "  },",
                "  exportCSV() { DSX.csv(searchQuery()); },\n"
                "  exportExcel() { DSX.excel(searchQuery(), false); },\n"
                "  exportFullExcel() { DSX.excel('', true); },",
                "app.js export fns")
    # (d) ปุ่ม Excel ในผลการค้นหา
    app = patch(app,
                '        <div style="flex:1"></div>\n'
                '        <div style="align-self:center"><button class="btn btn-primary" onclick="S.exportCSV()">\n'
                '          <svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></svg>ส่งออก CSV</button></div>',
                '        <div style="flex:1"></div>\n'
                '        <div style="align-self:center;display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">\n'
                '          <button class="btn" onclick="S.exportCSV()">\n'
                '            <svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></svg>CSV ที่กรอง</button>\n'
                '          <button class="btn btn-primary" onclick="S.exportExcel()">\n'
                '            <svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></svg>Excel ที่กรอง</button>\n'
                '        </div>',
                "app.js excel buttons")
    # (e) ปุ่ม Excel ทั้งฐาน
    app = patch(app,
                '    <button class="btn" onclick="S.resetSearch()">ล้างตัวกรอง</button>',
                '    <button class="btn" onclick="S.exportFullExcel()">\n'
                '      <svg viewBox="0 0 24 24"><path d="M12 3v12M7 10l5 5 5-5M4 21h16"/></svg>'
                'Excel ทั้งฐาน (${fmtInt(state.meta.counts.main_rows + state.meta.counts.commitments_rows)} แถว)</button>\n'
                '    <button class="btn" onclick="S.resetSearch()">ล้างตัวกรอง</button>',
                "app.js full excel button")
    open(os.path.join(DOCS, "static", "app.js"), "w", encoding="utf-8").write(app)

    # --- 5. ไฟล์ที่คัดลอกตรง ๆ ---
    shutil.copy2(os.path.join(SRC, "api.js"), os.path.join(DOCS, "static", "api.js"))
    for sub in ("vendor", "fonts"):
        dst = os.path.join(DOCS, "static", sub)
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(os.path.join(SRC, sub), dst)

    # --- 6. ข้อมูล .gz (ไฟล์เดียวกันกับ output/ ทั้งแท่ง) ---
    for f in ("budget_2566-2569_clean.csv.gz", "budget_2566-2569_commitments.csv.gz"):
        shutil.copy2(os.path.join(ROOT, "output", f), os.path.join(DOCS, "data", f))

    # --- 7. .nojekyll ---
    open(os.path.join(DOCS, ".nojekyll"), "w").write("")

    print("✅ สร้าง docs/ เสร็จ")
    total = 0
    for dp, _, fns in os.walk(DOCS):
        for fn in fns:
            total += os.path.getsize(os.path.join(dp, fn))
    print(f"   ขนาดรวม: {total / 1048576:.1f} MB (ข้อมูล .gz ใช้ blob เดียวกับ output/)")
    print("   ทดสอบ: cd docs && python3 -m http.server 8000")


if __name__ == "__main__":
    main()
