# 🚦 Road Wizdom — ระบบจัดการเรื่องร้องเรียนจราจร กทม.

Working Prototype สำหรับ HackaTech Bangkok 2569
แจ้งปัญหา → AI จัดลำดับความสำคัญ → รวมเรื่องซ้ำ → ติดตาม Timeline → Analytics

## วิธีรัน

```bash
cd road-wizdom
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# ใส่ข้อมูลตัวอย่าง 10 เคสรอบกรุงเทพ (ครั้งแรกครั้งเดียว)
python -m backend.seed

# รันเซิร์ฟเวอร์
uvicorn backend.main:app --reload
```

เปิด http://127.0.0.1:8000

## ฟีเจอร์ที่ทำงานจริง

| ฟีเจอร์ | วิธีทำงาน |
|---|---|
| แจ้งปัญหา + แนบรูป | เลือกจุดบนแผนที่ → ส่งรายงาน |
| AI Description | สร้างคำอธิบายมาตรฐานอัตโนมัติ (rule-based, สลับเป็น LLM API ได้ที่ `backend/ai.py`) |
| Duplicate Detection | รายงานหมวดเดียวกันในรัศมี 150 ม. → รวมเป็นเคสเดียว ผู้กระทบ +1 |
| AI Risk Score | ความรุนแรงหมวด + ชั่วโมงเร่งด่วน + จำนวนผู้แจ้ง + การเกิดซ้ำจุดเดิม |
| Officer Dashboard | เคสเรียงตาม Risk + แผนที่ + กดรับเรื่อง/ปิดเคส |
| Case Timeline | ทุก event ถูกบันทึกและแสดงให้ผู้แจ้งเห็น |
| Analytics | สถิติตามประเภท + Top 5 เคสเสี่ยงสูง |

## โครงสร้าง

```
road-wizdom/
├── backend/
│   ├── main.py    # FastAPI endpoints
│   ├── ai.py      # AI pipeline (description / risk / duplicate)
│   ├── db.py      # SQLite layer
│   └── seed.py    # ข้อมูลตัวอย่าง
├── frontend/      # HTML + JS + Leaflet (เสิร์ฟโดย FastAPI)
└── uploads/       # รูปที่ผู้ใช้อัปโหลด
```

## Demo Scenario (3 นาที)

1. แจ้งเหตุ "จอดขวางช่องจราจร" จุดใดจุดหนึ่ง → ได้เคสใหม่ + Risk Score
2. แจ้งซ้ำจุดเดิม (ภายใน 150 ม.) → ระบบรวมเป็นเคสเดียว Priority ขยับขึ้น
3. เปิด Dashboard → เคสเรียงตาม Risk → กด "เริ่มดำเนินการ" → Timeline อัปเดต
4. เปิด Analytics → ภาพรวมที่ผู้บริหารเมืองเห็น
