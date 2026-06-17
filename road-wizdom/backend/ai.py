"""AI pipeline — rule-based fallbacks that run fully offline.

ออกแบบเป็น layer แยก: ถ้าต่อ LLM API หรือ YOLO ภายหลัง
แค่เปลี่ยน implementation ในไฟล์นี้ไฟล์เดียว
"""
import math
from datetime import datetime
from difflib import SequenceMatcher

# ---------- Category metadata ----------

CATEGORIES = {
    "illegal_parking": {"th": "จอดรถผิดกฎหมาย", "base_severity": 60},
    "lane_blocking": {"th": "จอดขวางช่องจราจร", "base_severity": 75},
    "sidewalk_parking": {"th": "จอดบนทางเท้า", "base_severity": 65},
    "wrong_way": {"th": "ขับย้อนศร", "base_severity": 85},
    "shoulder_driving": {"th": "ขับไหล่ทาง", "base_severity": 70},
    "other": {"th": "อื่น ๆ", "base_severity": 40},
}

DUPLICATE_RADIUS_M = 150  # รายงานใหม่ภายในรัศมีนี้ + หมวดเดียวกัน = เรื่องซ้ำ


def haversine_m(lat1, lng1, lat2, lng2):
    """ระยะทางระหว่างสองพิกัด (เมตร)"""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# ---------- 1) AI Description ----------

def generate_description(category: str, description: str, lat: float, lng: float) -> str:
    """สร้างคำอธิบายมาตรฐานจากข้อมูลที่ผู้แจ้งส่งมา (rule-based fallback ของ LLM)"""
    cat = CATEGORIES.get(category, CATEGORIES["other"])
    hour = datetime.now().hour
    is_rush = 7 <= hour <= 9 or 16 <= hour <= 19
    time_ctx = "ช่วงชั่วโมงเร่งด่วน" if is_rush else "นอกชั่วโมงเร่งด่วน"
    base = f"พบเหตุ{cat['th']} บริเวณพิกัด ({lat:.5f}, {lng:.5f}) {time_ctx}"
    if description:
        base += f" — รายละเอียดจากผู้แจ้ง: {description.strip()}"
    return base


# ---------- 2) Risk Scoring ----------

def risk_score(category: str, impacted_count: int, recurrence_count: int) -> float:
    """คะแนนความเสี่ยง 0-100: ความรุนแรงหมวด + ชั่วโมงเร่งด่วน + จำนวนผู้แจ้ง + การเกิดซ้ำ"""
    cat = CATEGORIES.get(category, CATEGORIES["other"])
    score = float(cat["base_severity"])
    hour = datetime.now().hour
    if 7 <= hour <= 9 or 16 <= hour <= 19:
        score += 10
    score += min(impacted_count - 1, 5) * 4      # ทุกคนที่แจ้งซ้ำ +4 (สูงสุด +20)
    score += min(recurrence_count, 3) * 3        # ปัญหาเกิดซ้ำจุดเดิม +3/ครั้ง (สูงสุด +9)
    return round(min(score, 100), 1)


def risk_level(score: float) -> str:
    if score >= 80:
        return "สูงมาก"
    if score >= 65:
        return "สูง"
    if score >= 45:
        return "ปานกลาง"
    return "ต่ำ"


# ---------- 3) Duplicate Detection ----------

def find_duplicate_case(open_cases, category, lat, lng, description):
    """หาเคสเปิดอยู่ที่น่าจะเป็นเรื่องเดียวกัน: หมวดเดียวกัน + ระยะ < 150m
    (text similarity ใช้เป็นตัวเสริม ไม่ใช่เงื่อนไขบังคับ)"""
    best = None
    best_dist = DUPLICATE_RADIUS_M
    for case in open_cases:
        if case["category"] != category:
            continue
        d = haversine_m(lat, lng, case["lat"], case["lng"])
        if d < best_dist:
            best, best_dist = case, d
    return best
