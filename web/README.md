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

## API endpoints

`GET /api/meta` · `/api/overview?year=` · `/api/search?...` · `/api/export?...` (CSV) ·
`/api/ministries?year=` · `/api/ministry?name=&year=` · `/api/compare?names=` ·
`/api/categories?year=&path=` · `/api/category_rows?...` · `/api/plans?year=&q=` ·
`/api/plan?name=&year=` · `/api/commitments` · `/api/commitments_rows?...` · `/api/flags?...`
