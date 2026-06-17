"""Seed ข้อมูลตัวอย่างรอบกรุงเทพ — รัน: python -m backend.seed"""
import random
from datetime import datetime, timedelta

from backend import db, ai

SPOTS = [
    # (lat, lng, category, ตัวอย่างคำอธิบาย)
    (13.7466, 100.5347, "lane_blocking", "รถเก๋งจอดขวางเลนซ้ายหน้าสยามพารากอน"),
    (13.7467, 100.5349, "lane_blocking", "รถจอดซ้อนคันขวางทางเข้าห้าง"),
    (13.7563, 100.5018, "sidewalk_parking", "มอเตอร์ไซค์จอดเต็มทางเท้าใกล้เสาชิงช้า"),
    (13.7244, 100.5292, "illegal_parking", "รถกระบะจอดในเขตห้ามจอด ถนนสีลม"),
    (13.7649, 100.5383, "wrong_way", "มอเตอร์ไซค์ย้อนศรซอยอารีย์"),
    (13.7308, 100.5697, "shoulder_driving", "รถขับไหล่ทางพระราม 4 ขาออก"),
    (13.8009, 100.5538, "illegal_parking", "รถตู้จอดแช่หน้าตลาดจตุจักร"),
    (13.7222, 100.5780, "sidewalk_parking", "รถยนต์จอดบนทางเท้าสุขุมวิท 40"),
    (13.7660, 100.6406, "lane_blocking", "รถสิบล้อจอดขวางเลนถนนลาดพร้าว"),
    (13.6900, 100.7501, "other", "ป้ายจราจรล้มขวางถนนใกล้สนามบิน"),
]


def seed():
    db.init_db()
    conn = db.get_conn()
    n_cases = conn.execute("SELECT COUNT(*) c FROM cases").fetchone()["c"]
    if n_cases:
        print(f"มีข้อมูลอยู่แล้ว {n_cases} เคส — ข้ามการ seed (ลบไฟล์ backend/roadwizdom.db เพื่อเริ่มใหม่)")
        return

    for i, (lat, lng, cat, desc) in enumerate(SPOTS):
        created = datetime.now() - timedelta(hours=random.randint(1, 72))
        ts = created.isoformat(timespec="seconds")
        impacted = random.randint(1, 6)
        score = ai.risk_score(cat, impacted, random.randint(0, 2))
        status = random.choice(["received", "received", "in_progress", "resolved"])
        title = f"{ai.CATEGORIES[cat]['th']} ({lat:.4f}, {lng:.4f})"
        cur = conn.execute(
            "INSERT INTO cases (title, category, lat, lng, status, risk_score, impacted_count, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (title, cat, lat, lng, status, score, impacted, ts, ts),
        )
        case_id = cur.lastrowid
        conn.execute(
            "INSERT INTO reports (case_id, description, ai_description, category, lat, lng, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (case_id, desc, ai.generate_description(cat, desc, lat, lng), cat, lat, lng, ts),
        )
        conn.execute(
            "INSERT INTO timeline_events (case_id, event_type, detail, created_at) VALUES (?,?,?,?)",
            (case_id, "created", f"เปิดเคสใหม่จากรายงานประชาชน — Risk Score {score}", ts),
        )
        if status != "received":
            conn.execute(
                "INSERT INTO timeline_events (case_id, event_type, detail, created_at) VALUES (?,?,?,?)",
                (case_id, "status_change",
                 f"เจ้าหน้าที่อัปเดตสถานะ: รับเรื่องแล้ว → {'กำลังดำเนินการ' if status=='in_progress' else 'แก้ไขเสร็จสิ้น'}",
                 (created + timedelta(hours=2)).isoformat(timespec="seconds")),
            )
    conn.commit()
    conn.close()
    print(f"Seed สำเร็จ: {len(SPOTS)} เคสตัวอย่างรอบกรุงเทพ")


if __name__ == "__main__":
    seed()
