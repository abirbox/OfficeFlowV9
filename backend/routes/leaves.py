from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone, date
from bson import ObjectId
import uuid

from models.leaves import LeaveCreate, LeaveUpdate, LeaveResponse
from utils.auth import get_current_user

router = APIRouter(prefix="/leaves", tags=["Leaves"])

def get_db(request: Request):
    return request.app.state.db

def days_between(start: str, end: str) -> int:
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    return (e - s).days + 1

async def build_leave_response(leave: dict, db) -> LeaveResponse:
    user = None
    try:
        user = await db.users.find_one({"_id": ObjectId(leave["user_id"])}, {"password_hash": 0})
    except Exception:
        pass
    
    approver_name = None
    if leave.get("approved_by"):
        try:
            approver = await db.users.find_one({"_id": ObjectId(leave["approved_by"])}, {"password_hash": 0})
            approver_name = approver.get("name") if approver else None
        except Exception:
            pass
    
    return LeaveResponse(
        id=leave["id"],
        user_id=leave["user_id"],
        user_name=user.get("name") if user else None,
        user_email=user.get("email") if user else None,
        type=leave["type"],
        start_date=leave["start_date"],
        end_date=leave["end_date"],
        days=leave.get("days", days_between(leave["start_date"], leave["end_date"])),
        reason=leave.get("reason"),
        status=leave["status"],
        admin_note=leave.get("admin_note"),
        approved_by=leave.get("approved_by"),
        approver_name=approver_name,
        created_at=leave["created_at"].isoformat() if isinstance(leave["created_at"], datetime) else leave["created_at"],
        updated_at=leave["updated_at"].isoformat() if leave.get("updated_at") and isinstance(leave["updated_at"], datetime) else leave.get("updated_at"),
    )

@router.post("", response_model=LeaveResponse)
async def create_leave(data: LeaveCreate, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    leave_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "type": data.type,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "days": days_between(data.start_date, data.end_date),
        "reason": data.reason,
        "status": "pending",
        "admin_note": None,
        "approved_by": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    await db.leaves.insert_one(leave_doc)
    return await build_leave_response(leave_doc, db)

@router.get("", response_model=list[LeaveResponse])
async def get_leaves(request: Request, db = Depends(get_db), status: str = None, user_id: str = None):
    user = await get_current_user(request, db)
    
    query = {}
    if user.get("role") == "employee":
        query["user_id"] = user["_id"]
    elif user_id:
        query["user_id"] = user_id
    
    if status:
        query["status"] = status
    
    leaves = await db.leaves.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [await build_leave_response(leave, db) for leave in leaves]

@router.put("/{leave_id}", response_model=LeaveResponse)
async def update_leave(leave_id: str, data: LeaveUpdate, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    if user.get("role") not in ["super_admin", "admin", "hr"]:
        raise HTTPException(status_code=403, detail="Only admin/HR can approve leaves")
    
    leave = await db.leaves.find_one({"id": leave_id})
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    
    await db.leaves.update_one(
        {"id": leave_id},
        {"$set": {
            "status": data.status,
            "admin_note": data.admin_note,
            "approved_by": user["_id"],
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    
    updated = await db.leaves.find_one({"id": leave_id}, {"_id": 0})
    return await build_leave_response(updated, db)
