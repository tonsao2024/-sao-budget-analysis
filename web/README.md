# เว็บวิเคราะห์งบประมาณไทย 2566–2569

เว็บแอปสำหรับสำรวจและวิเคราะห์ข้อมูลงบประมาณรายจ่ายประจำปี ที่ผ่านการทำความสะอาดแล้ว
(`output/budget_2566-2569_clean.csv.gz` + `output/budget_2566-2569_commitments.csv.gz`)

## วิธีรัน

```bash
# 1. ติดตั้ง dependencies (ครั้งเดียว)
pip install fastapi uvicorn pandas

# 2. รันเซิร์ฟเวอร์ (จาก root ของ repo)
python3 web/server.py

# 3. เปิดเบราว์เซอร์
http://localhost:8000
```

## หน้าที่มีในเว็บ (7 หน้า)

| หน้า | ทำอะไรได้ |
|---|---|
| **ภาพรวม** | KPI งบปีปัจจุบัน, กราฟรายปี, สัดส่วนหมวดงบ, Top 10 กระทรวง/หน่วยงาน/แผนงาน, การกระจายวงเงิน, ภาระผูกพัน |
| **ค้นหารายการ** | full-text search + ฟิลเตอร์ (ปี/กระทรวง/หมวด/แผนงาน/วงเงิน/ผูกพัน/flag) + เรียงลำดับ + **ส่งออก CSV** |
| **กระทรวง** | ตารางอันดับพร้อมแนวโน้ม 5 ปี, เจาะลึกแต่ละกระทรวง, **เปรียบเทียบสูงสุด 4 กระทรวง** |
| **หมวดงบ** | drill-down หมวดงบ 6 ระดับ พร้อมกราฟและตารางรายการ |
| **แผนงาน** | รายชื่อแผนงาน + เจาะลึก (กระทรวง/หน่วยงาน/ยุทธศาสตร์/แผนแม่บทที่เกี่ยวข้อง) |
| **ภาระผูกพัน** | สรุปยอดผูกพันรายปี/รายกระทรวง + สำรวจรายการ (เน้นแถวปีน่าสงสัย) |
| **คุณภาพข้อมูล** | สถิติ DQ flags + กรองดูรายการที่มีประเด็นคุณภาพ |

ฟีเจอร์ทั่วไป: เปลี่ยนปีงบประมาณที่แถบบน · โหมดสว่าง/มืด · คลิกรายการเพื่อดูรายละเอียดเต็ม ·
ทุกกราฟคลิกเพื่อเจาะลึกได้ · responsive รองรับมือถือ

## โครงสร้างไฟล์

```
web/
├── server.py          # Backend (FastAPI) + API 14 endpoints
└── static/
    ├── index.html     # โครงหน้าเว็บ
    ├── style.css      # ดีไซน์โทนอบอุ่น (paper + terracotta)
    ├── app.js         # Frontend: routing, 7 วิว, กราฟ, ตาราง
    ├── vendor/        # Chart.js + treemap plugin (โหลดในเครื่อง ไม่พึ่ง CDN)
    └── fonts/         # Noto Sans/Serif Thai (woff2)
```

## เวอร์ชัน Static (GitHub Pages)

GitHub Pages รัน Python ไม่ได้ จึงมีบิลด์ static ที่คำนวณทุกอย่างในเบราว์เซอร์
(`web/static/api.js` = data engine ฝั่ง client, logic ตรงกับ backend ผ่านเทสต์ parity 18/18):

```bash
python3 web/build_static.py   # สร้าง docs/ จาก web/static + output/*.csv.gz
cd docs && python3 -m http.server 8000
```

- เบราว์เซอร์โหลด `.csv.gz` 2 ไฟล์ (~13.7 MB) แล้วแกะ gzip + parse เอง (PapaParse)
- ไม่ต้องมีเซิร์ฟเวอร์ — เปิดผ่าน GitHub Pages (โฟลเดอร์ `docs/`) ได้เลย
- ถ้าแก้ `web/static/*` แล้ว ให้รัน `build_static.py` ใหม่ทุกครั้งก่อน push

## การส่งออกไฟล์ (เวอร์ชัน static)

หน้า**ค้นหารายการ**มีปุ่มส่งออก 3 แบบ (สร้างไฟล์ในเบราว์เซอร์ด้วย SheetJS):

| ปุ่ม | ได้อะไร |
|---|---|
| **CSV ที่กรอง** | ผลตามตัวกรองปัจจุบัน (สูงสุด 100,000 แถว, มี BOM เปิด Excel ได้เลย) |
| **Excel ที่กรอง** | ผลตามตัวกรองปัจจุบันทั้งหมด (.xlsx หัวตารางภาษาไทย + ชีต "สรุป" บอกเงื่อนไข/ยอดรวม) |
| **Excel ทั้งฐาน** | ข้อมูลทั้ง 231,221 แถว (ไฟล์หลัก + ภาระผูกพัน) — ไฟล์ใหญ่ อาจใช้เวลา 1–2 นาที |

## API endpoints (เวอร์ชัน FastAPI)

`GET /api/meta` · `/api/overview?year=` · `/api/search?...` · `/api/export?...` (CSV) ·
`/api/ministries?year=` · `/api/ministry?name=&year=` · `/api/compare?names=` ·
`/api/categories?year=&path=` · `/api/category_rows?...` · `/api/plans?year=&q=` ·
`/api/plan?name=&year=` · `/api/commitments` · `/api/commitments_rows?...` · `/api/flags?...`
