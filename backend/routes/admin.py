from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone, date
from bson import ObjectId
from bson.errors import InvalidId

from utils.auth import get_current_user
from utils.tz import dhaka_today, dhaka_today_iso

router = APIRouter(prefix="/admin", tags=["Admin"])

def get_db(request: Request):
    return request.app.state.db

async def require_admin(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/dashboard-stats")
async def get_dashboard_stats(request: Request, db = Depends(get_db)):
    await require_admin(request, db)
    
    total_employees = await db.users.count_documents({"role": {"$ne": "super_admin"}})
    active_employees = await db.users.count_documents({"status": "active"})
    
    today = dhaka_today_iso()
    present_today = await db.attendance.count_documents({"date": today})
    active_gps = await db.gps_sessions.count_documents({"status": "active"})
    
    total_tasks = await db.tasks.count_documents({})
    active_tasks = await db.tasks.count_documents({"status": {"$in": ["todo", "in_progress"]}})
    completed_tasks = await db.tasks.count_documents({"status": "done"})
    
    total_shifts = await db.shifts.count_documents({})
    active_shifts = await db.shifts.count_documents({"status": "active"})
    scheduled_shifts = await db.shifts.count_documents({"status": "scheduled"})
    
    pending_leaves = await db.leaves.count_documents({"status": "pending"})
    pending_overtime = await db.overtime_requests.count_documents({"status": "pending"})
    
    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "present_today": present_today,
        "active_on_field": active_gps,
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
        "completed_tasks": completed_tasks,
        "total_shifts": total_shifts,
        "active_shifts": active_shifts,
        "scheduled_shifts": scheduled_shifts,
        "pending_leaves": pending_leaves,
        "pending_overtime": pending_overtime,
    }

@router.get("/employee-status")
async def get_all_employee_status(request: Request, db = Depends(get_db)):
    """Real-time snapshot of every employee's current status - for admin dashboard"""
    await require_admin(request, db)
    
    today = dhaka_today_iso()
    employees = await db.users.find({}, {"password_hash": 0}).to_list(1000)
    
    result = []
    for emp in employees:
        emp_id = str(emp["_id"])
        attendance = await db.attendance.find_one({"user_id": emp_id, "date": today}, {"_id": 0})
        active_gps = await db.gps_sessions.find_one({"user_id": emp_id, "status": "active"}, {"_id": 0})
        
        current_location = None
        if active_gps and active_gps.get("coordinates"):
            last_coord = active_gps["coordinates"][-1]
            current_location = {
                "latitude": last_coord.get("latitude"),
                "longitude": last_coord.get("longitude"),
                "timestamp": last_coord.get("timestamp"),
            }
        # Fallback: use check-in location if GPS session hasn't received coords yet
        if not current_location and attendance and attendance.get("check_in_location"):
            loc = attendance["check_in_location"]
            if loc and loc.get("latitude") and loc.get("longitude"):
                current_location = {
                    "latitude": loc["latitude"],
                    "longitude": loc["longitude"],
                    "timestamp": attendance.get("check_in"),
                }
        
        if attendance and not attendance.get("check_out"):
            status = "working"
        elif attendance and attendance.get("check_out"):
            status = "checked_out"
        else:
            status = "not_started"
        
        result.append({
            "id": emp_id,
            "name": emp["name"],
            "email": emp["email"],
            "role": emp.get("role", "employee"),
            "avatar_path": emp.get("avatar_path"),
            "status": status,
            "check_in": attendance.get("check_in") if attendance else None,
            "check_out": attendance.get("check_out") if attendance else None,
            "total_hours": attendance.get("total_hours", 0) if attendance else 0,
            "current_location": current_location,
            "gps_active": bool(active_gps),
            "coordinates_today": active_gps.get("coordinates", []) if active_gps else [],
        })
    
    return result

@router.get("/employee/{employee_id}/stats")
async def get_employee_stats(
    employee_id: str,
    request: Request,
    db = Depends(get_db),
    month: int = None,
    year: int = None,
):
    """Monthly/yearly attendance stats + GPS history for an employee"""
    await require_admin(request, db)
    
    today = dhaka_today()
    target_year = year or today.year
    target_month = month or today.month
    
    start_of_month = f"{target_year}-{target_month:02d}-01"
    if target_month == 12:
        end_of_month = f"{target_year + 1}-01-01"
    else:
        end_of_month = f"{target_year}-{target_month + 1:02d}-01"
    
    start_of_year = f"{target_year}-01-01"
    end_of_year = f"{target_year + 1}-01-01"
    
    # Monthly attendance
    monthly_records = await db.attendance.find(
        {"user_id": employee_id, "date": {"$gte": start_of_month, "$lt": end_of_month}},
        {"_id": 0}
    ).to_list(100)
    
    # Yearly attendance
    yearly_records = await db.attendance.find(
        {"user_id": employee_id, "date": {"$gte": start_of_year, "$lt": end_of_year}},
        {"_id": 0}
    ).to_list(500)
    
    monthly_hours = sum(r.get("total_hours", 0) for r in monthly_records)
    yearly_hours = sum(r.get("total_hours", 0) for r in yearly_records)
    
    # Recent GPS sessions
    gps_sessions = await db.gps_sessions.find(
        {"user_id": employee_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(30).to_list(30)
    
    monthly_distance = sum(s.get("total_distance", 0) for s in gps_sessions if s.get("started_at", "").startswith(f"{target_year}-{target_month:02d}"))
    
    return {
        "monthly": {
            "days_present": len(monthly_records),
            "days_late": len([r for r in monthly_records if r.get("status") == "late"]),
            "total_hours": round(monthly_hours, 2),
            "average_hours": round(monthly_hours / len(monthly_records), 2) if monthly_records else 0,
            "total_distance_km": round(monthly_distance, 2),
        },
        "yearly": {
            "days_present": len(yearly_records),
            "total_hours": round(yearly_hours, 2),
        },
        "attendance_records": monthly_records,
        "gps_sessions": gps_sessions[:10],
    }

@router.put("/employee/{employee_id}/role")
async def change_employee_role(
    employee_id: str,
    request: Request,
    db = Depends(get_db),
    role: str = None,
):
    """Change an employee's role - only super_admin can promote to admin/super_admin"""
    user = await require_admin(request, db)
    
    valid_roles = ["super_admin", "admin", "hr", "manager", "employee"]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
    
    # Only super_admin can create other super_admins or admins
    if role in ["super_admin", "admin"] and user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admin can assign admin roles")
    
    try:
        oid = ObjectId(employee_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid employee id")
    
    target = await db.users.find_one({"_id": oid})
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    await db.users.update_one(
        {"_id": oid},
        {"$set": {"role": role, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": f"Role updated to {role}", "employee_id": employee_id, "new_role": role}
