from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone, date, time
from bson import ObjectId
from bson.errors import InvalidId
import uuid

from models.shifts import ShiftCreate, ShiftUpdate, ShiftResponse, ShiftSessionResponse, BulkShiftCreate
from utils.auth import get_current_user
from routes.attendance import start_auto_gps_session, stop_auto_gps_session
from utils.tz import get_org_timezone, local_minutes_of_day, local_date_iso, to_local, dhaka_today_iso
from datetime import timezone as _tz_ignored  # noqa: F401 (kept for future)

router = APIRouter(prefix="/shifts", tags=["Work Shifts"])

def get_db(request: Request):
    return request.app.state.db

async def require_admin(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin", "hr", "manager"]:
        raise HTTPException(status_code=403, detail="Admin/Manager access required")
    return user

async def notify_admins(db, from_user, notif_type: str, title: str, message: str, reference_id: str = None):
    admins = await db.users.find({"role": {"$in": ["super_admin", "admin"]}}, {"password_hash": 0}).to_list(100)
    now = datetime.now(timezone.utc)
    docs = []
    for a in admins:
        docs.append({
            "id": str(uuid.uuid4()),
            "user_id": str(a["_id"]),
            "type": notif_type,
            "title": title,
            "message": message,
            "from_user_id": str(from_user["_id"]),
            "from_user_name": from_user.get("name"),
            "reference_id": reference_id,
            "read": False,
            "created_at": now,
        })
    if docs:
        await db.notifications.insert_many(docs)

async def build_shift_response(shift: dict, db) -> ShiftResponse:
    user = None
    try:
        user = await db.users.find_one({"_id": ObjectId(shift["user_id"])}, {"password_hash": 0})
    except Exception:
        pass
    creator = None
    try:
        creator = await db.users.find_one({"_id": ObjectId(shift["created_by"])}, {"password_hash": 0})
    except Exception:
        pass
    return ShiftResponse(
        id=shift["id"],
        user_id=shift["user_id"],
        user_name=user.get("name") if user else None,
        user_email=user.get("email") if user else None,
        title=shift.get("title", "Shift"),
        work_location=shift["work_location"],
        start_time=shift["start_time"],
        end_time=shift["end_time"],
        days_of_week=shift.get("days_of_week", []),
        effective_from=shift["effective_from"],
        effective_to=shift["effective_to"],
        status=shift.get("status", "scheduled"),
        created_by=shift["created_by"],
        creator_name=creator.get("name") if creator else None,
        created_at=shift["created_at"].isoformat() if isinstance(shift["created_at"], datetime) else shift["created_at"],
    )

@router.post("/bulk")
async def create_bulk_shifts(data: BulkShiftCreate, request: Request, db = Depends(get_db)):
    """Assign one shift template to many employees in a single call."""
    admin = await require_admin(request, db)
    if not data.user_ids:
        raise HTTPException(status_code=400, detail="Pick at least one employee")
    if not data.days_of_week:
        raise HTTPException(status_code=400, detail="Pick at least one weekday")
    now = datetime.now(timezone.utc)
    created = []
    skipped = []
    for uid in data.user_ids:
        # Skip if the user has an overlapping shift already
        overlapping = await db.shifts.find_one({
            "user_id": uid,
            "status": {"$ne": "cancelled"},
            "effective_from": {"$lte": data.effective_to},
            "effective_to": {"$gte": data.effective_from},
        })
        if overlapping:
            skipped.append({"user_id": uid, "reason": "overlapping shift already assigned"})
            continue
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "title": data.title,
            "work_location": data.work_location,
            "start_time": data.start_time,
            "end_time": data.end_time,
            "days_of_week": data.days_of_week,
            "effective_from": data.effective_from,
            "effective_to": data.effective_to,
            "status": "scheduled",
            "created_by": admin["_id"],
            "created_at": now,
            "updated_at": now,
        }
        await db.shifts.insert_one(doc)
        # Notify assigned employee
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "type": "shift_assigned",
            "title": f"New shift: {data.title}",
            "message": f"You have been assigned to {data.title} ({data.start_time}-{data.end_time}) effective {data.effective_from}.",
            "from_user_id": str(admin["_id"]),
            "from_user_name": admin.get("name"),
            "reference_id": doc["id"],
            "read": False,
            "created_at": now,
        })
        created.append(doc["id"])
    return {"created_count": len(created), "created_ids": created, "skipped": skipped}


@router.post("", response_model=ShiftResponse)
async def create_shift(data: ShiftCreate, request: Request, db = Depends(get_db)):
    admin = await require_admin(request, db)
    doc = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "status": "scheduled",
        "created_by": admin["_id"],        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.shifts.insert_one(doc)
    return await build_shift_response(doc, db)

@router.get("", response_model=list[ShiftResponse])
async def get_shifts(request: Request, db = Depends(get_db), user_id: str = None):
    user = await get_current_user(request, db)
    query = {}
    if user.get("role") == "employee":
        query["user_id"] = user["_id"]
    elif user_id:
        query["user_id"] = user_id
    shifts = await db.shifts.find(query, {"_id": 0}).sort("effective_from", -1).to_list(500)
    return [await build_shift_response(s, db) for s in shifts]

@router.get("/all")
async def get_all_shifts_calendar(request: Request, db = Depends(get_db)):
    """All shifts across the org - for calendar view (readable by anyone logged in)"""
    await get_current_user(request, db)
    shifts = await db.shifts.find({"status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(1000)
    return [(await build_shift_response(s, db)).model_dump() for s in shifts]

@router.put("/{shift_id}", response_model=ShiftResponse)
async def update_shift(shift_id: str, data: ShiftUpdate, request: Request, db = Depends(get_db)):
    await require_admin(request, db)
    existing = await db.shifts.find_one({"id": shift_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Shift not found")
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = datetime.now(timezone.utc)
    await db.shifts.update_one({"id": shift_id}, {"$set": update})
    updated = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
    return await build_shift_response(updated, db)

@router.delete("/{shift_id}")
async def delete_shift(shift_id: str, request: Request, db = Depends(get_db)):
    await require_admin(request, db)
    existing = await db.shifts.find_one({"id": shift_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Shift not found")
    await db.shifts.delete_one({"id": shift_id})
    return {"message": "Shift deleted"}

def parse_time(t: str) -> time:
    h, m = t.split(":")
    return time(int(h), int(m))

@router.post("/{shift_id}/join", response_model=ShiftSessionResponse)
async def join_shift(shift_id: str, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    shift = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift["user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="This shift is not assigned to you")
    if shift.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="This shift was cancelled")
    
    today = dhaka_today_iso()
    tz_code, tz_off = await get_org_timezone(db)
    today_local = local_date_iso(datetime.now(timezone.utc), tz_code, tz_off)
    today = today_local
    # Ensure not already joined today
    existing_session = await db.shift_sessions.find_one({"shift_id": shift_id, "user_id": user["_id"], "date": today})
    if existing_session and existing_session.get("status") == "joined":
        raise HTTPException(status_code=400, detail="You already joined this shift today")
    
    now = datetime.now(timezone.utc)
    # Compute late using organization timezone
    shift_start = parse_time(shift["start_time"])
    now_local_mins = local_minutes_of_day(now, tz_code, tz_off)
    start_mins = shift_start.hour * 60 + shift_start.minute
    late_minutes = 0
    is_late = False
    if now_local_mins > start_mins:
        late_minutes = now_local_mins - start_mins
        is_late = late_minutes > 5  # grace period 5 minutes
    
    session_doc = {
        "id": str(uuid.uuid4()),
        "shift_id": shift_id,
        "user_id": user["_id"],
        "date": today,
        "joined_at": now.isoformat(),
        "ended_at": None,
        "is_late": is_late,
        "late_minutes": late_minutes if is_late else 0,
        "overtime_minutes": 0,
        "status": "joined",
        "work_hours": 0.0,
        "created_at": now,
    }
    await db.shift_sessions.insert_one(session_doc)
    
    # Auto attendance check-in
    attendance = await db.attendance.find_one({"user_id": user["_id"], "date": today})
    if not attendance:
        await db.attendance.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["_id"],
            "date": today,
            "check_in": now.isoformat(),
            "check_out": None,
            "total_hours": 0.0,
            "breaks": [],
            "overtime_minutes": 0,
            "status": "late" if is_late else "present",
            "check_in_location": None,
            "check_out_location": None,
            "notes": f"Joined shift {shift.get('title','Shift')}",
            "created_at": now,
        })
    
    # Auto GPS start
    await start_auto_gps_session(db, user, None, None)
    
    # Mark shift active
    await db.shifts.update_one({"id": shift_id}, {"$set": {"status": "active"}})
    
    return ShiftSessionResponse(**{k: v for k, v in session_doc.items() if k != "created_at"})

@router.post("/{shift_id}/end", response_model=ShiftSessionResponse)
async def end_shift(shift_id: str, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    shift = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    today = dhaka_today_iso()
    tz_code, tz_off = await get_org_timezone(db)
    today = local_date_iso(datetime.now(timezone.utc), tz_code, tz_off)
    session = await db.shift_sessions.find_one({"shift_id": shift_id, "user_id": user["_id"], "date": today, "status": "joined"}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=400, detail="You haven't joined this shift today")
    
    now = datetime.now(timezone.utc)
    joined_at = datetime.fromisoformat(session["joined_at"])
    work_hours = (now - joined_at).total_seconds() / 3600
    
    # Compute overtime using org timezone
    shift_end = parse_time(shift["end_time"])
    overtime_minutes = 0
    now_local_mins = local_minutes_of_day(now, tz_code, tz_off)
    end_mins = shift_end.hour * 60 + shift_end.minute
    if now_local_mins > end_mins:
        overtime_minutes = now_local_mins - end_mins
    
    await db.shift_sessions.update_one(
        {"id": session["id"]},
        {"$set": {
            "ended_at": now.isoformat(),
            "status": "ended",
            "work_hours": round(work_hours, 2),
            "overtime_minutes": overtime_minutes,
        }}
    )
    
    # Update attendance
    await db.attendance.update_one(
        {"user_id": user["_id"], "date": today},
        {"$set": {
            "check_out": now.isoformat(),
            "total_hours": round(work_hours, 2),
            "overtime_minutes": overtime_minutes,
        }}
    )
    
    # Stop GPS
    await stop_auto_gps_session(db, user["_id"])
    
    # Auto-flag overtime request for manager approval if worked > 8h
    try:
        from routes.overtime import create_or_update_overtime_request
        await create_or_update_overtime_request(
            db,
            user_id=user["_id"],
            date_str=today,
            total_hours=work_hours,
            overtime_minutes=overtime_minutes,
            shift_id=shift_id,
            shift_title=shift.get("title", "Shift"),
        )
    except Exception:
        pass
    
    await db.shifts.update_one({"id": shift_id}, {"$set": {"status": "scheduled"}})
    
    updated_session = await db.shift_sessions.find_one({"id": session["id"]}, {"_id": 0, "created_at": 0})
    return ShiftSessionResponse(**updated_session)

@router.post("/{shift_id}/cancel")
async def cancel_shift(shift_id: str, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    shift = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if shift["user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not your shift")
    
    await db.shifts.update_one({"id": shift_id}, {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}})
    
    await notify_admins(
        db, user, "shift_cancelled",
        f"Shift cancelled by {user['name']}",
        f"{user['name']} cancelled shift '{shift.get('title', 'Shift')}' ({shift['start_time']}-{shift['end_time']}). You can reassign to someone else.",
        shift_id,
    )
    
    return {"message": "Shift cancelled and admin notified"}

@router.get("/sessions/mine")
async def my_shift_sessions(request: Request, db = Depends(get_db), limit: int = 30):
    user = await get_current_user(request, db)
    sessions = await db.shift_sessions.find({"user_id": user["_id"]}, {"_id": 0}).sort("date", -1).limit(limit).to_list(limit)
    return sessions
