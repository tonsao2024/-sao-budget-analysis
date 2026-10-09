# สรุปการ Clean ข้อมูล

- วันที่: 2026-10-09
- Input: `budget_2566-2569.csv.gz` (231,334 แถว)
- Output หลัก: `budget_2566-2569_clean.csv.gz` (210,895 แถว, ปี 2022-2026)
- ภาระผูกพัน: `budget_2566-2569_commitments.csv.gz` (20,326 แถว)
- Quarantine: `quarantine_review.csv.gz` (240 แถว)

## สิ่งที่ทำ

### อ่านข้อมูลต้นฉบับ budget_2566-2569.csv.gz ###
แถว: 231,334  คอลัมน์: 21

### ขั้น 1a: exact cell mapping (คำสะกดผิดทั้ง cell) ###
  BUDGETARY_UNIT: 13 รูปแบบ -> 2,166 cell
  OUTPUT: 6 รูปแบบ -> 209 cell
  PROJECT: 4 รูปแบบ -> 688 cell
  ITEM_DESCRIPTION: 14 รูปแบบ -> 2,663 cell
  CATEGORY_LV3: 2 รูปแบบ -> 10 cell
  CATEGORY_LV4: 5 รูปแบบ -> 85 cell
  CATEGORY_LV5: 1 รูปแบบ -> 1 cell
  CATEGORY_LV6: 16 รูปแบบ -> 121 cell

### ขั้น 1b: artifact rules (OCR/แปลงข้อมูล) ###
  nikhahit+sara-aa (อํานвой->อำนวย): 3,924 cells
  split sara-am w/ mai-tho (ซ ้า->ซ้ำ): 128 cells
  split sara-am w/ mai-ek (ก ่า->ก่ำ): 69 cells
  split sara-am (ก าลัง->กำลัง): 1,356 cells
  sara-am+stray mai-tho (นำ้->น้ำ): 679 cells

### ขั้น 1c: substring rules (คำสะกดผิดบางส่วน) ###
  ใช้ 84 rules
  ITEM_DESCRIPTION regex (ค่าเช่ารถยนต์ \d) ค้น: 57 cells

  เติม ')' ท้าย BUDGETARY_UNIT: 706 cells

### ขั้น 2: รวมชื่อ MINISTRY ที่สะกดหลายแบบ ###
  อปท  ->  องค์กรปกครองส่วนท้องถิ่น  (11,754 แถว)
  ส่วนราชการไม่สังกัดสำนักนายกรัฐมนตรี กระทรวง หรือทบวงและหน่วยงานภายใต้การควบคุมดูแลของนายกรัฐมนตรี  ->  ส่วนราชการไม่สังกัดสำนักนายกรัฐมนตรี กระทรวง หรือทบวง และหน่วยงานภายใต้การควบคุมดูแลของนายกรัฐมนตรี  (1,263 แถว)
  ส่วนราชการไม่สังกัดสำนักนายกรัฐมนตรีฯ  ->  ส่วนราชการไม่สังกัดสำนักนายกรัฐมนตรี กระทรวง หรือทบวง และหน่วยงานภายใต้การควบคุมดูแลของนายกรัฐมนตรี  (1,325 แถว)
  งบประมาณรายจ่ายเพื่อชดใช้เงินคงคลัง  ->  รายจ่ายเพื่อชดใช้เงินคงคลัง  (1 แถว)
  MINISTRY ไม่ซ้ำ: ก่อน 39 -> หลัง 35

### ขั้น 3: แก้ CATEGORY_LV1 (คอลัมน์เลื่อน/ว่าง) ###
  คอลัมน์เลื่อน (มีชื่อแผนงานในช่องหมวดงบ): 12 แถว -> เติมจากปีอื่นได้ 0 แถว, เหลือว่าง 12 แถว
  CATEGORY_LV1 ว่าง: 84 แถว -> เติมจากปีอื่นได้ 4 แถว, เหลือว่าง 80 แถว

### ขั้น 4: ลบแถวซ้ำซ้อน ###
  ลบแถวซ้ำ: 113 แถว -> เหลือ 231,221 แถว

### ขั้น 5-6: flag / เติมค่า / แยกภาระผูกพัน / แปลงชนิดข้อมูล ###
  ไฟล์หลัก (ปี 2022-2026): 210,895 แถว
  ภาระผูกพัน (ปีนอกช่วง): 20,326 แถว (ปี <=2021 น่าสงสัย: 9,058 แถว, ปี <=2005 เป็นไปไม่ได้: 156 แถว)

### เขียนไฟล์ output ###
  output/budget_2566-2569_clean.csv.gz
  output/budget_2566-2569_commitments.csv.gz
  output/quarantine_review.csv.gz (240 แถว)

### ขั้น 7: ตรวจสอบยอดรวมก่อน-หลัง ###
  ปี 2022: ดิบ 313.05B -> clean 313.05B (ต่าง -2.3M จากการลบซ้ำ)
  ปี 2023: ดิบ 3,447.09B -> clean 3,446.91B (ต่าง -183.9M จากการลบซ้ำ)
  ปี 2024: ดิบ 3,942.26B -> clean 3,942.26B (ต่าง -3.9M จากการลบซ้ำ)
  ปี 2025: ดิบ 4,304.96B -> clean 4,304.91B (ต่าง -46.7M จากการลบซ้ำ)
  ปี 2026: ดิบ 4,295.01B -> clean 4,294.97B (ต่าง -37.1M จากการลบซ้ำ)
  รวมทุกปีไฟล์หลัก: 16,302.10B
  รวมภาระผูกพัน: 6,294.80B

## ตาราง audit การแก้สะกด

| ประเภท | scope | rule | cells |
|---|---|---|---|
| exact | BUDGETARY_UNIT | 13 mappings | 2,166 |
| exact | OUTPUT | 6 mappings | 209 |
| exact | PROJECT | 4 mappings | 688 |
| exact | ITEM_DESCRIPTION | 14 mappings | 2,663 |
| exact | CATEGORY_LV3 | 2 mappings | 10 |
| exact | CATEGORY_LV4 | 5 mappings | 85 |
| exact | CATEGORY_LV5 | 1 mappings | 1 |
| exact | CATEGORY_LV6 | 16 mappings | 121 |
| artifact | ALL | nikhahit+sara-aa (อํานвой->อำนวย) | 3,924 |
| artifact | ALL | split sara-am w/ mai-tho (ซ ้า->ซ้ำ) | 128 |
| artifact | ALL | split sara-am w/ mai-ek (ก ่า->ก่ำ) | 69 |
| artifact | ALL | split sara-am (ก าลัง->กำลัง) | 1,356 |
| artifact | ALL | sara-am+stray mai-tho (นำ้->น้ำ) | 679 |
| substring | ALL | ไชเบอร์ -> ไซเบอร์ | 28 |
| substring | ALL | ขึดความสามารถ -> ขีดความสามารถ | 49 |
| substring | ALL | เบิ้ลแค็บ -> เบิ้ลแคบ | 1,712 |
| substring | ALL | เคุ้มครอง -> คุ้มครอง | 37 |
| substring | ALL | เจ้าพ้า -> เจ้าฟ้า | 117 |
| substring | ALL | TotalStation -> Total Station | 1 |
| substring | ALL | สะดาก -> สะดวก | 26 |
| substring | ALL | ราดเร็ว -> รวดเร็ว | 26 |
| substring | ALL | พิริศพ -> พิธีศพ | 41 |
| substring | ALL | ทีเกี่ยวข้อง -> ที่เกี่ยวข้อง | 44 |
| substring | ALL | ทางหลางชนบท -> ทางหลวงชนบท | 41 |
| substring | ALL | โลจิสติกล์ -> โลจิสติกส์ | 140 |
| substring | ALL | ปราจินบุรี -> ปราจีนบุรี | 58 |
| substring | ALL | ให้เด้ตาม -> ให้ได้ตาม | 27 |
| substring | ALL | สงปใน -> สงบใน | 45 |
| substring | ALL | สัตว์ปาหายาก -> สัตว์ป่าหายาก | 10 |
| substring | ALL | สูความเป็นเลิศ -> สู่ความเป็นเลิศ | 40 |
| substring | ALL | ข้าวนาวี -> ข้าวนาปี | 11 |
| substring | ALL | เข้อมูล -> ข้อมูล | 50 |
| substring | ALL | มุ่งสูอุตสาหกรรม -> มุ่งสู่อุตสาหกรรม | 10 |
| substring | ALL | โครงสร้างพิื้นฐาน -> โครงสร้างพื้นฐาน | 8 |
| substring | ALL | เหลื่อมล้า -> เหลื่อมล้ำ | 11 |
| substring | ALL | อุบัติช้ำ -> อุบัติซ้ำ | 9 |
| substring | ALL | กัดเชาะ ชายฝั่ง -> กัดเซาะชายฝั่ง | 9 |
| substring | ALL | เผาซากพืช -> เผาชากพืช | 5 |
| substring | ALL | รงท้าราคาประหยัด -> ธงฟ้าราคาประหยัด | 5 |
| substring | ALL | ให้มสมรรถนะ -> ให้มีสมรรถนะ | 8 |
| substring | ALL | ศตวรรษที่่ -> ศตวรรษที่ | 40 |
| substring | ALL | ทเคโนโลยี -> เทคโนโลยี | 3 |
| substring | ALL | สถาบัตยกรรม -> สถาปัตยกรรม | 3 |
| substring | ALL | ชำระหนี เงินกู้ -> ชำระหนี้เงินกู้ | 33 |
| substring | ALL | การตลาดสูสากล -> การตลาดสู่สากล | 2 |
| substring | ALL | ปุ่ยอินทรีย์ -> ปุ๋ยอินทรีย์ | 2 |
| substring | ALL | คีตศีลป์ -> คีตศิลป์ | 3 |
| substring | ALL | ค่าประกัน พ.ร.ก. -> ค้ำประกัน พ.ร.ก. | 1 |
| substring | ALL | กะทู้- ป้าตอง -> กะทู้-ป่าตอง | 1 |
| substring | ALL | มีนบุรี -> มืนบุรี | 183 |
| substring | ALL | รามอนทรา -> รามอินทรา | 1 |
| substring | ALL | การป้ องกัน -> การป้องกัน | 3 |
| substring | ALL | ชือสัตย์สุจริต -> ซื่อสัตย์สุจริต | 1 |
| substring | ALL | ทรายสูเกษตรกร -> ทรายสู่เกษตรกร | 1 |
| substring | ALL | ยุทรศาสตร์ -> ยุทธศาสตร์ | 1 |
| substring | ALL | หน่อยปฏิบัติการ -> หน่วยปฏิบัติการ | 12 |
| substring | ALL | แสงชินโครตรอน -> แสงซินโครตรอน | 22 |
| substring | ALL | ไห้แก่รนาคาร -> ให้แก่ธนาคาร | 27 |
| substring | ALL | คลองยม 7 น่าน -> คลองยม-น่าน | 17 |
| substring | ALL | บางซื่อ 7 รังสิต -> บางซื่อ - รังสิต | 3 |
| substring | ALL |  =แก่งคอย ->  - แก่งคอย | 2 |
| substring | ALL | มัน่ คง -> มั่นคง | 8 |
| substring | ALL | กระทรวงศึกษาธการ -> กระทรวงศึกษาธิการ | 18 |
| substring | ALL | เข็นไปเพื่อ -> เป็นไปเพื่อ | 26 |
| substring | ALL | ค่าเชารถยนต์ -> ค่าเช่ารถยนต์ | 222 |
| substring | ALL | ที่เดินการรถไฟ -> ที่ดินการรถไฟ | 144 |
| substring | ALL | ค่าประป๋า -> ค่าประปา | 79 |
| substring | ALL | ค่าบัจจัยพื้นฐาน -> ค่าปัจจัยพื้นฐาน | 78 |
| substring | ALL | อำนาจหน้าทีและ -> อำนาจหน้าที่และ | 75 |
| substring | ALL | หน้าที่ และภารกิจถ่ายโอน -> หน้าที่และภารกิจถ่ายโอน | 296 |
| substring | ALL | ผู้บ้วยเอดส์ -> ผู้ป่วยเอดส์ | 67 |
| substring | ALL | เงินสบทบ -> เงินสมทบ | 65 |
| substring | ALL | 1d ล้านบาท -> 10 ล้านบาท | 395 |
| substring | ALL | 6d พรรษา -> 60 พรรษา | 17 |
| substring | ALL | วัสดุเซื้อเพลิง -> วัสดุเชื้อเพลิง | 22 |
| substring | ALL | ซ่อมแชม -> ซ่อมแซม | 36 |
| substring | ALL | ช่อมแซม -> ซ่อมแซม | 161 |
| substring | ALL | ช่อมแชม -> ซ่อมแซม | 163 |
| substring | ALL | ขนสง -> ขนส่ง | 61 |
| substring | ALL | ฝั่งช้าย -> ฝั่งซ้าย | 113 |
| substring | ALL | คุกดาม -> คุกคาม | 8 |
| substring | BUDGETARY_UNIT | องค์กรมหาชน -> องค์การมหาชน | 64 |
| substring | ALL | พระเจ้า น้องนางเธอ -> พระเจ้าน้องนางเธอ | 219 |
| substring | ALL | สวางควัฒน วรขัตติยราชนารี -> สวางควัฒนฺวรขัตติยราชนารี | 242 |
| substring | ALL | สวางควัฒนวรขัตติยราชนารี -> สวางควัฒนฺวรขัตติยราชนารี | 7 |
| substring | ALL | สวางควัฒนวรชัตติยราชนารี -> สวางควัฒนฺวรขัตติยราชนารี | 1 |
| substring | ALL | สวางควัฒนฺวรชัตติยราชนารี -> สวางควัฒนฺวรขัตติยราชนารี | 2 |
| substring | ALL | ฺและ -> และ | 32 |
| substring | ALL | ฺรักษา -> รักษา | 268 |
| substring | ALL | ฺปกป้อง -> ปกป้อง | 44 |
| substring | ALL | ผูกพันข้ามขีงบประมาณ -> ผูกพันข้ามปีงบประมาณ | 13 |
| substring | ALL | ผูกพันข้ามปึงบประมาณ -> ผูกพันข้ามปีงบประมาณ | 20 |
| substring | ALL | ครุภัณฑ์ไฟฟ้าเละวิทยุ -> ครุภัณฑ์ไฟฟ้าและวิทยุ | 5 |
| substring | ALL | ค่าปรับปรุงอาดาร -> ค่าปรับปรุงอาคาร | 4 |
| substring | ALL | หน่วยตำกว่า -> หน่วยต่ำกว่า | 448 |
| substring | ALL | เด็กเล็ก232 -> เด็กเล็ก 232 | 7 |
| substring | OUTPUT | ดูแลความปลอดภัยทางนิวเคลียร์ -> ดูแล ความปลอดภัยทางนิวเคลียร์ | 31 |
| regex | ITEM_DESCRIPTION | (ค่าเช่ารถยนต์ \d) ค้น | 57 |
| rule | BUDGETARY_UNIT | append ')' after (องค์การมหาชน | 706 |

## Flag (dq_flag) ที่ติดในไฟล์ output

| flag | ความหมาย | จำนวน (ไฟล์หลัก+ผูกพัน) |
|---|---|---|
| amount_negative | - | 1 |
| amount_zero | - | 2,237 |
| item_description_missing | - | 3 |
| budget_plan_missing | - | 48 |
| cross_func_filled | - | 130 |
| ref_page_no_invalid | - | 1 |
| commitment_year_outside_range | - | 20,326 |
| commitment_year_suspect_past | - | 9,058 |
| commitment_year_impossible | - | 156 |
| ministry_inferred | - | 0 |
| category_lv1_unresolved | - | 80 |

## สิ่งที่ยังไม่แก้ (เหลือเช็คกับต้นฉบับ)

- แถวภาระผูกพันปี <= 2021 (9,063 แถว) น่าจะเป็น artifact จากการแปลงไฟล์ (ปีในเอกสารไม่ควรย้อนหลัง) — อยู่ในไฟล์ commitments พร้อม flag
- รูปแบบเว้นวรรคบางแบบใน OUTPUT/PROJECT/ITEM_DESCRIPTION ที่ไม่มั่นใจว่าแบบไหนถูกต้อง (เช่น `การร่วมลงทุน ระหว่าง` vs `การร่วมลงทุนระหว่าง`) — ไม่แก้เพราะเดาไม่ได้
- คอลัมน์ OUTPUT/PROJECT/STRATEGY/MOTHER_PLAN ว่างค่อนข้างมาก — เป็นลักษณะโครงสร้างของข้อมูล ไม่ใช่ missing
