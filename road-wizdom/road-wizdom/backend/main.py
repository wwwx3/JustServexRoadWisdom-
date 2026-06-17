"""Road Wizdom — Bangkok Traffic Report Management (Working Prototype)

รัน:  uvicorn backend.main:app --reload
"""
import os
import shutil
import uuid
from typing import Optional

from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend import db, ai

app = FastAPI(title="Road Wizdom API")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
os.makedirs(UPLOAD_DIR, exist_ok=True)

db.init_db()

STATUS_TH = {
    "received": "รับเรื่องแล้ว",
    "in_progress": "กำลังดำเนินการ",
    "resolved": "แก้ไขเสร็จสิ้น",
}


# ---------- API ----------

@app.post("/api/reports")
async def create_report(
    description: str = Form(""),
    category: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    photo: Optional[UploadFile] = File(None),
):
    if category not in ai.CATEGORIES:
        raise HTTPException(400, "unknown category")

    photo_path = None
    if photo and photo.filename:
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        fname = f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
            shutil.copyfileobj(photo.file, f)
        photo_path = f"/uploads/{fname}"

    ai_desc = ai.generate_description(category, description, lat, lng)

    conn = db.get_conn()
    open_cases = conn.execute(
        "SELECT * FROM cases WHERE status != 'resolved'"
    ).fetchall()
    dup = ai.find_duplicate_case(open_cases, category, lat, lng, description)

    # การเกิดซ้ำ: เคยมีเคส resolved ในรัศมีเดียวกันหมวดเดียวกันกี่ครั้ง
    resolved_cases = conn.execute(
        "SELECT * FROM cases WHERE status = 'resolved' AND category = ?", (category,)
    ).fetchall()
    recurrence = sum(
        1 for c in resolved_cases
        if ai.haversine_m(lat, lng, c["lat"], c["lng"]) < ai.DUPLICATE_RADIUS_M
    )

    ts = db.now()
    if dup:
        case_id = dup["id"]
        impacted = dup["impacted_count"] + 1
        score = ai.risk_score(category, impacted, recurrence)
        conn.execute(
            "UPDATE cases SET impacted_count=?, risk_score=?, updated_at=? WHERE id=?",
            (impacted, score, ts, case_id),
        )
        conn.execute(
            "INSERT INTO timeline_events (case_id, event_type, detail, created_at) VALUES (?,?,?,?)",
            (case_id, "merged",
             f"AI รวมรายงานซ้ำเข้าเคสนี้ (ผู้ได้รับผลกระทบ {impacted} ราย) — Risk Score ปรับเป็น {score}",
             ts),
        )
        merged = True
    else:
        score = ai.risk_score(category, 1, recurrence)
        title = f"{ai.CATEGORIES[category]['th']} ({lat:.4f}, {lng:.4f})"
        cur = conn.execute(
            "INSERT INTO cases (title, category, lat, lng, risk_score, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (title, category, lat, lng, score, ts, ts),
        )
        case_id = cur.lastrowid
        detail = f"เปิดเคสใหม่จากรายงานประชาชน — Risk Score {score}"
        if recurrence:
            detail += f" (จุดนี้เคยเกิดปัญหาแล้ว {recurrence} ครั้ง — Flag ปัญหาซ้ำซาก)"
        conn.execute(
            "INSERT INTO timeline_events (case_id, event_type, detail, created_at) VALUES (?,?,?,?)",
            (case_id, "created", detail, ts),
        )
        merged = False

    conn.execute(
        "INSERT INTO reports (case_id, description, ai_description, category, lat, lng, photo_path, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (case_id, description, ai_desc, category, lat, lng, photo_path, ts),
    )
    conn.commit()
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    conn.close()

    return {
        "case_id": case_id,
        "merged": merged,
        "ai_description": ai_desc,
        "risk_score": case["risk_score"],
        "risk_level": ai.risk_level(case["risk_score"]),
        "impacted_count": case["impacted_count"],
    }


@app.get("/api/cases")
def list_cases():
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM cases ORDER BY (status='resolved'), risk_score DESC"
    ).fetchall()
    conn.close()
    return [
        {**dict(r),
         "risk_level": ai.risk_level(r["risk_score"]),
         "category_th": ai.CATEGORIES.get(r["category"], {}).get("th", r["category"]),
         "status_th": STATUS_TH.get(r["status"], r["status"])}
        for r in rows
    ]


@app.get("/api/cases/{case_id}")
def get_case(case_id: int):
    conn = db.get_conn()
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        conn.close()
        raise HTTPException(404, "case not found")
    reports = conn.execute(
        "SELECT * FROM reports WHERE case_id=? ORDER BY created_at", (case_id,)
    ).fetchall()
    events = conn.execute(
        "SELECT * FROM timeline_events WHERE case_id=? ORDER BY created_at", (case_id,)
    ).fetchall()
    conn.close()
    return {
        **dict(case),
        "risk_level": ai.risk_level(case["risk_score"]),
        "category_th": ai.CATEGORIES.get(case["category"], {}).get("th", case["category"]),
        "status_th": STATUS_TH.get(case["status"], case["status"]),
        "reports": [dict(r) for r in reports],
        "timeline": [dict(e) for e in events],
    }


class StatusUpdate(BaseModel):
    status: str


@app.post("/api/cases/{case_id}/status")
def update_status(case_id: int, body: StatusUpdate):
    if body.status not in STATUS_TH:
        raise HTTPException(400, "invalid status")
    conn = db.get_conn()
    case = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        conn.close()
        raise HTTPException(404, "case not found")
    ts = db.now()
    conn.execute(
        "UPDATE cases SET status=?, updated_at=? WHERE id=?", (body.status, ts, case_id)
    )
    conn.execute(
        "INSERT INTO timeline_events (case_id, event_type, detail, created_at) VALUES (?,?,?,?)",
        (case_id, "status_change",
         f"เจ้าหน้าที่อัปเดตสถานะ: {STATUS_TH[case['status']]} → {STATUS_TH[body.status]}", ts),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "status": body.status, "status_th": STATUS_TH[body.status]}


@app.get("/api/analytics")
def analytics():
    conn = db.get_conn()
    by_category = conn.execute(
        "SELECT category, COUNT(*) n FROM cases GROUP BY category ORDER BY n DESC"
    ).fetchall()
    by_status = conn.execute(
        "SELECT status, COUNT(*) n FROM cases GROUP BY status"
    ).fetchall()
    top = conn.execute(
        "SELECT * FROM cases WHERE status != 'resolved' ORDER BY risk_score DESC LIMIT 5"
    ).fetchall()
    totals = conn.execute(
        "SELECT COUNT(*) cases, (SELECT COUNT(*) FROM reports) reports, "
        "SUM(impacted_count) impacted FROM cases"
    ).fetchone()
    conn.close()
    return {
        "totals": dict(totals),
        "by_category": [
            {"category": r["category"],
             "category_th": ai.CATEGORIES.get(r["category"], {}).get("th", r["category"]),
             "count": r["n"]} for r in by_category
        ],
        "by_status": [
            {"status": r["status"], "status_th": STATUS_TH.get(r["status"], r["status"]),
             "count": r["n"]} for r in by_status
        ],
        "top_risk": [
            {**dict(r), "risk_level": ai.risk_level(r["risk_score"]),
             "category_th": ai.CATEGORIES.get(r["category"], {}).get("th", r["category"])}
            for r in top
        ],
    }


@app.get("/api/categories")
def categories():
    return [{"key": k, "th": v["th"]} for k, v in ai.CATEGORIES.items()]


# ---------- Static files ----------

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
