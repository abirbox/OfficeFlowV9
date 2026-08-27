from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from models.overtime import OvertimeApproveRequest, OvertimeResponse
from utils.auth import get_current_user

router = APIRouter(prefix="/overtime", tags=["Overtime"])

DAILY_OVERTIME_THRESHOLD_HOURS = 8.0


def get_db(request: Request):
    return request.app.state.db


async def _require_manager(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin", "hr", "manager"]:
        raise HTTPException(status_code=403, detail="Manager access required")
    return user


async def create_or_update_overtime_request(
    db,
    *,
    user_id: str,
    date_str: str,
    total_hours: float,
    overtime_minutes: int,
    shift_id: str = None,
    shift_title: str = None,
) -> bool:
    """
    Called from shift end / attendance check-out. Creates a pending overtime
    request when total_hours exceeds the daily threshold. Idempotent per
    (user_id, date). Returns True if a request now exists.
    """
    if total_hours <= DAILY_OVERTIME_THRESHOLD_HOURS:
        return False

    overtime_hours = round(total_hours - DAILY_OVERTIME_THRESHOLD_HOURS, 2)
    computed_minutes = int(round(overtime_hours * 60))
    ot_minutes = max(overtime_minutes or 0, computed_minutes)

    existing = await db.overtime_requests.find_one({"user_id": user_id, "date": date_str})
    now = datetime.now(timezone.utc)
    if existing:
        # Only refresh numbers when still pending
        if existing.get("status") == "pending":
            await db.overtime_requests.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "total_hours": round(total_hours, 2),
                    "overtime_hours": overtime_hours,
                    "overtime_minutes": ot_minutes,
                    "shift_id": shift_id or existing.get("shift_id"),
                    "shift_title": shift_title or existing.get("shift_title"),
                    "updated_at": now,
                }}
            )
        return True

    await db.overtime_requests.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "date": date_str,
        "shift_id": shift_id,
        "shift_title": shift_title,
        "total_hours": round(total_hours, 2),
        "overtime_hours": overtime_hours,
        "overtime_minutes": ot_minutes,
        "status": "pending",
        "reviewer_id": None,
        "reviewer_name": None,
        "review_note": None,
        "reviewed_at": None,
        "created_at": now,
        "updated_at": now,
    })

    # Notify admins/managers
    reviewers = await db.users.find(
        {"role": {"$in": ["super_admin", "admin", "hr", "manager"]}}, {"password_hash": 0}
    ).to_list(200)
    employee = None
    try:
        employee = await db.users.find_one({"_id": ObjectId(user_id)}, {"password_hash": 0})
    except Exception:
        pass
    emp_name = employee.get("name") if employee else "Employee"
    for a in reviewers:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": str(a["_id"]),
            "type": "overtime_pending",
            "title": f"Overtime approval needed",
            "message": f"{emp_name} worked {round(total_hours, 2)}h on {date_str} (overtime {overtime_hours}h). Approve for payroll.",
            "from_user_id": user_id,
            "from_user_name": emp_name,
            "reference_id": date_str,
            "read": False,
            "created_at": now,
        })
    return True


async def _build_response(db, req: dict) -> OvertimeResponse:
    employee = None
    reviewer = None
    try:
        employee = await db.users.find_one({"_id": ObjectId(req["user_id"])}, {"password_hash": 0})
    except Exception:
        pass
    if req.get("reviewer_id"):
        try:
            reviewer = await db.users.find_one({"_id": ObjectId(req["reviewer_id"])}, {"password_hash": 0})
        except Exception:
            pass
    return OvertimeResponse(
        id=req["id"],
        user_id=req["user_id"],
        user_name=employee.get("name") if employee else None,
        user_email=employee.get("email") if employee else None,
        shift_id=req.get("shift_id"),
        shift_title=req.get("shift_title"),
        date=req["date"],
        total_hours=req.get("total_hours", 0.0),
        overtime_hours=req.get("overtime_hours", 0.0),
        overtime_minutes=req.get("overtime_minutes", 0),
        status=req.get("status", "pending"),
        reviewer_id=req.get("reviewer_id"),
        reviewer_name=reviewer.get("name") if reviewer else req.get("reviewer_name"),
        review_note=req.get("review_note"),
        reviewed_at=req["reviewed_at"].isoformat() if isinstance(req.get("reviewed_at"), datetime) else req.get("reviewed_at"),
        created_at=req["created_at"].isoformat() if isinstance(req["created_at"], datetime) else req["created_at"],
    )


@router.get("", response_model=list[OvertimeResponse])
async def list_overtime(request: Request, db=Depends(get_db), status: str = None, user_id: str = None):
    user = await get_current_user(request, db)
    query = {}
    role = user.get("role")
    if role == "employee":
        query["user_id"] = user["_id"]
    elif user_id:
        query["user_id"] = user_id
    if status:
        query["status"] = status
    reqs = await db.overtime_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [await _build_response(db, r) for r in reqs]


@router.post("/{req_id}/approve", response_model=OvertimeResponse)
async def approve_overtime(req_id: str, payload: OvertimeApproveRequest, request: Request, db=Depends(get_db)):
    reviewer = await _require_manager(request, db)
    existing = await db.overtime_requests.find_one({"id": req_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Overtime request not found")
    if existing.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {existing.get('status')}")

    now = datetime.now(timezone.utc)
    await db.overtime_requests.update_one(
        {"id": req_id},
        {"$set": {
            "status": "approved",
            "reviewer_id": reviewer["_id"],
            "reviewer_name": reviewer.get("name"),
            "review_note": payload.note,
            "reviewed_at": now,
            "updated_at": now,
        }}
    )

    # Notify employee
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": existing["user_id"],
        "type": "overtime_approved",
        "title": "Overtime approved",
        "message": f"Your overtime on {existing['date']} ({existing.get('overtime_hours', 0)}h) was approved for payroll.",
        "from_user_id": str(reviewer["_id"]),
        "from_user_name": reviewer.get("name"),
        "reference_id": existing["date"],
        "read": False,
        "created_at": now,
    })
    updated = await db.overtime_requests.find_one({"id": req_id}, {"_id": 0})
    return await _build_response(db, updated)


@router.post("/{req_id}/reject", response_model=OvertimeResponse)
async def reject_overtime(req_id: str, payload: OvertimeApproveRequest, request: Request, db=Depends(get_db)):
    reviewer = await _require_manager(request, db)
    existing = await db.overtime_requests.find_one({"id": req_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Overtime request not found")
    if existing.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {existing.get('status')}")

    now = datetime.now(timezone.utc)
    await db.overtime_requests.update_one(
        {"id": req_id},
        {"$set": {
            "status": "rejected",
            "reviewer_id": reviewer["_id"],
            "reviewer_name": reviewer.get("name"),
            "review_note": payload.note,
            "reviewed_at": now,
            "updated_at": now,
        }}
    )
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": existing["user_id"],
        "type": "overtime_rejected",
        "title": "Overtime rejected",
        "message": f"Your overtime on {existing['date']} was not approved. {(payload.note or '')}".strip(),
        "from_user_id": str(reviewer["_id"]),
        "from_user_name": reviewer.get("name"),
        "reference_id": existing["date"],
        "read": False,
        "created_at": now,
    })
    updated = await db.overtime_requests.find_one({"id": req_id}, {"_id": 0})
    return await _build_response(db, updated)
