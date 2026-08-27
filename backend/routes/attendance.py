from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone, date, time
from bson import ObjectId
import uuid

from models.attendance import (
    AttendanceCheckIn,
    AttendanceCheckOut,
    AttendanceResponse,
    AttendanceStats,
)
from utils.auth import get_current_user
from utils.tz import dhaka_today_iso

router = APIRouter(prefix="/attendance", tags=["Attendance"])

def get_db(request: Request):
    return request.app.state.db

async def start_auto_gps_session(db, user, latitude, longitude):
    """Auto-start a GPS tracking session on check-in"""
    active = await db.gps_sessions.find_one({"user_id": user["_id"], "status": "active"})
    if active:
        return active["id"]
    
    initial_coords = []
    if latitude and longitude:
        initial_coords.append({
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    session_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "coordinates": initial_coords,
        "total_distance": 0.0,
        "status": "active",
        "notes": "Auto-started with attendance check-in",
        "created_at": datetime.now(timezone.utc),
    }
    await db.gps_sessions.insert_one(session_doc)
    return session_doc["id"]

async def stop_auto_gps_session(db, user_id):
    """Auto-stop the active GPS session on check-out"""
    active = await db.gps_sessions.find_one({"user_id": user_id, "status": "active"})
    if active:
        await db.gps_sessions.update_one(
            {"id": active["id"]},
            {"$set": {
                "status": "ended",
                "ended_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return active["id"]
    return None

def _build_attendance_response(record: dict, user_hint: dict = None) -> AttendanceResponse:
    sessions = record.get("sessions") or []
    # Backfill legacy single-session docs so total_hours is still correct
    if not sessions and record.get("check_in"):
        sessions = [{
            "check_in": record["check_in"],
            "check_out": record.get("check_out"),
            "hours": record.get("total_hours", 0.0),
            "check_in_location": record.get("check_in_location"),
            "check_out_location": record.get("check_out_location"),
        }]
    total_hours = round(sum((s.get("hours") or 0.0) for s in sessions), 2)
    is_working = any(s.get("check_out") is None for s in sessions)
    latest_session = sessions[-1] if sessions else {}
    return AttendanceResponse(
        id=record["id"],
        user_id=record["user_id"],
        user_name=(user_hint or {}).get("name"),
        date=record["date"],
        check_in=latest_session.get("check_in") or record.get("check_in"),
        check_out=latest_session.get("check_out") or record.get("check_out"),
        total_hours=total_hours,
        breaks=record.get("breaks", []),
        overtime_minutes=record.get("overtime_minutes", 0),
        status=record.get("status", "present"),
        check_in_location=latest_session.get("check_in_location") or record.get("check_in_location"),
        check_out_location=latest_session.get("check_out_location") or record.get("check_out_location"),
        notes=record.get("notes"),
        sessions=sessions,
        is_working=is_working,
        created_at=record["created_at"].isoformat() if isinstance(record.get("created_at"), datetime) else record.get("created_at", ""),
    )


@router.post("/check-in", response_model=AttendanceResponse)
async def check_in(data: AttendanceCheckIn, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    user_id = user["_id"]
    
    today = dhaka_today_iso()
    existing = await db.attendance.find_one({"user_id": user_id, "date": today})
    now_iso = datetime.now(timezone.utc).isoformat()
    location = {"latitude": data.latitude, "longitude": data.longitude} if data.latitude and data.longitude else None
    new_session = {
        "check_in": now_iso,
        "check_out": None,
        "hours": 0.0,
        "check_in_location": location,
        "check_out_location": None,
    }

    if existing:
        # If there's an active (open) session, block. Otherwise start a new one.
        sessions = existing.get("sessions") or []
        # Backfill legacy single-session docs
        if not sessions and existing.get("check_in"):
            sessions = [{
                "check_in": existing["check_in"],
                "check_out": existing.get("check_out"),
                "hours": existing.get("total_hours", 0.0),
                "check_in_location": existing.get("check_in_location"),
                "check_out_location": existing.get("check_out_location"),
            }]
        has_open = any(s.get("check_out") is None for s in sessions)
        if has_open:
            raise HTTPException(status_code=400, detail="You are already checked in. Check out first.")

        sessions.append(new_session)
        await db.attendance.update_one(
            {"user_id": user_id, "date": today},
            {"$set": {
                "sessions": sessions,
                "check_in": new_session["check_in"],
                "check_out": None,
                "check_in_location": new_session["check_in_location"],
                "check_out_location": None,
            }},
        )
        attendance_id = existing["id"]
    else:
        attendance_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "date": today,
            "check_in": now_iso,
            "check_out": None,
            "total_hours": 0.0,
            "breaks": [],
            "overtime_minutes": 0,
            "status": "present",
            "check_in_location": location,
            "check_out_location": None,
            "notes": data.notes,
            "sessions": [new_session],
            "created_at": datetime.now(timezone.utc),
        }
        await db.attendance.insert_one(attendance_doc)
        attendance_id = attendance_doc["id"]

    # Auto-start GPS tracking session
    await start_auto_gps_session(db, user, data.latitude, data.longitude)

    updated = await db.attendance.find_one({"user_id": user_id, "date": today}, {"_id": 0})
    return _build_attendance_response(updated, user)

@router.post("/check-out", response_model=AttendanceResponse)
async def check_out(data: AttendanceCheckOut, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    user_id = user["_id"]
    
    today = dhaka_today_iso()
    attendance = await db.attendance.find_one({"user_id": user_id, "date": today})
    
    if not attendance:
        raise HTTPException(status_code=400, detail="No check-in found for today")

    sessions = attendance.get("sessions") or []
    if not sessions and attendance.get("check_in"):
        sessions = [{
            "check_in": attendance["check_in"],
            "check_out": attendance.get("check_out"),
            "hours": attendance.get("total_hours", 0.0),
            "check_in_location": attendance.get("check_in_location"),
            "check_out_location": attendance.get("check_out_location"),
        }]

    # Find latest open session
    open_idx = None
    for i in range(len(sessions) - 1, -1, -1):
        if sessions[i].get("check_out") is None:
            open_idx = i
            break
    if open_idx is None:
        raise HTTPException(status_code=400, detail="No active work session to check out from")
    
    check_out_time = datetime.now(timezone.utc)
    check_in_time = datetime.fromisoformat(sessions[open_idx]["check_in"])
    session_hours = round((check_out_time - check_in_time).total_seconds() / 3600, 4)
    check_out_location = {"latitude": data.latitude, "longitude": data.longitude} if data.latitude and data.longitude else None

    sessions[open_idx]["check_out"] = check_out_time.isoformat()
    sessions[open_idx]["hours"] = session_hours
    sessions[open_idx]["check_out_location"] = check_out_location

    total_hours = round(sum((s.get("hours") or 0.0) for s in sessions), 2)

    await db.attendance.update_one(
        {"user_id": user_id, "date": today},
        {"$set": {
            "sessions": sessions,
            "check_out": check_out_time.isoformat(),
            "check_out_location": check_out_location,
            "total_hours": total_hours,
        }}
    )

    # Auto-stop GPS tracking session
    await stop_auto_gps_session(db, user_id)

    # Auto-flag overtime for manager approval when day total > 8h
    try:
        from routes.overtime import create_or_update_overtime_request
        await create_or_update_overtime_request(
            db,
            user_id=user_id,
            date_str=today,
            total_hours=total_hours,
            overtime_minutes=int(max(0, (total_hours - 8.0) * 60)),
        )
    except Exception:
        pass

    updated = await db.attendance.find_one({"user_id": user_id, "date": today}, {"_id": 0})
    return _build_attendance_response(updated, user)

@router.get("/today")
async def get_today_attendance(request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    user_id = user["_id"]
    
    today = dhaka_today_iso()
    attendance = await db.attendance.find_one({"user_id": user_id, "date": today}, {"_id": 0})
    
    if not attendance:
        return {"checked_in": False, "attendance": None}
    
    resp = _build_attendance_response(attendance, user)
    return {"checked_in": resp.is_working, "attendance": resp.model_dump()}

@router.get("/history", response_model=list[AttendanceResponse])
async def get_attendance_history(
    request: Request,
    db = Depends(get_db),
    user_id: str = None,
    start_date: str = None,
    end_date: str = None,
    skip: int = 0,
    limit: int = 30,
):
    current_user = await get_current_user(request, db)
    
    query = {}
    if user_id and current_user.get("role") in ["super_admin", "admin", "hr"]:
        query["user_id"] = user_id
    else:
        query["user_id"] = current_user["_id"]
    
    if start_date and end_date:
        query["date"] = {"$gte": start_date, "$lte": end_date}
    
    records = await db.attendance.find(query, {"_id": 0}).sort("date", -1).skip(skip).limit(limit).to_list(limit)
    
    result = []
    for record in records:
        user = await db.users.find_one({"_id": ObjectId(record["user_id"]) if isinstance(record["user_id"], str) else record["user_id"]}, {"password_hash": 0})
        result.append(
            AttendanceResponse(
                id=record["id"],
                user_id=record["user_id"],
                user_name=user["name"] if user else "Unknown",
                date=record["date"],
                check_in=record["check_in"],
                check_out=record.get("check_out"),
                total_hours=record.get("total_hours", 0.0),
                breaks=record.get("breaks", []),
                overtime_minutes=record.get("overtime_minutes", 0),
                status=record["status"],
                check_in_location=record.get("check_in_location"),
                check_out_location=record.get("check_out_location"),
                notes=record.get("notes"),
                created_at=record["created_at"].isoformat() if isinstance(record["created_at"], datetime) else record["created_at"],
            )
        )
    
    return result

@router.get("/stats", response_model=AttendanceStats)
async def get_attendance_stats(
    request: Request,
    db = Depends(get_db),
    user_id: str = None,
    month: int = None,
    year: int = None,
):
    current_user = await get_current_user(request, db)
    
    query = {}
    if user_id and current_user.get("role") in ["super_admin", "admin", "hr"]:
        query["user_id"] = user_id
    else:
        query["user_id"] = current_user["_id"]
    
    if month and year:
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        query["date"] = {"$gte": start_date, "$lt": end_date}
    
    records = await db.attendance.find(query, {"_id": 0}).to_list(1000)
    
    total_days = len(records)
    present_days = len([r for r in records if r["status"] == "present"])
    absent_days = len([r for r in records if r["status"] == "absent"])
    late_days = len([r for r in records if r["status"] == "late"])
    total_hours = sum([r.get("total_hours", 0) for r in records])
    average_hours = total_hours / total_days if total_days > 0 else 0
    
    return AttendanceStats(
        total_days=total_days,
        present_days=present_days,
        absent_days=absent_days,
        late_days=late_days,
        total_hours=round(total_hours, 2),
        average_hours=round(average_hours, 2),
    )