from fastapi import APIRouter, Request, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from utils.auth import get_current_user
from utils.tz import dhaka_now

router = APIRouter(prefix="/reports", tags=["Reports"])


def get_db(request: Request):
    return request.app.state.db


async def require_manager(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin", "hr", "manager"]:
        raise HTTPException(status_code=403, detail="Manager access required")
    return user


@router.get("/summary")
async def summary(request: Request, db=Depends(get_db), month: int = None, year: int = None):
    """Aggregate stats across attendance, shifts, payroll, leaves, overtime for a month.
    Defaults to the current month in server clock (Asia/Dhaka default via zoneinfo)."""
    await require_manager(request, db)
    now = dhaka_now()
    y = year or now.year
    m = month or now.month
    start = f"{y}-{m:02d}-01"
    if m == 12:
        end = f"{y + 1}-01-01"
    else:
        end = f"{y}-{m + 1:02d}-01"

    # Attendance
    att_records = await db.attendance.find({"date": {"$gte": start, "$lt": end}}, {"_id": 0}).to_list(10000)
    total_att_days = len(att_records)
    total_work_hours = round(sum(r.get("total_hours", 0) for r in att_records), 2)
    late_days = len([r for r in att_records if r.get("status") == "late"])
    absent_days = len([r for r in att_records if r.get("status") == "absent"])

    # Shifts + sessions
    shift_sessions = await db.shift_sessions.count_documents({"date": {"$gte": start, "$lt": end}})
    shifts_total = await db.shifts.count_documents({})

    # Overtime
    ot_pending = await db.overtime_requests.count_documents({"status": "pending"})
    ot_approved_month = await db.overtime_requests.find({"status": "approved", "date": {"$gte": start, "$lt": end}}, {"_id": 0}).to_list(2000)
    ot_hours_approved = round(sum(o.get("overtime_hours", 0) for o in ot_approved_month), 2)

    # Leaves
    leaves_pending = await db.leaves.count_documents({"status": "pending"})
    leaves_approved_month = await db.leaves.count_documents({"status": "approved", "created_at": {"$gte": datetime(y, m, 1, tzinfo=timezone.utc)}})

    # Payroll
    payroll_records = await db.payroll.find({"month": m, "year": y}, {"_id": 0}).to_list(5000)
    total_gross = round(sum(p.get("base_salary", 0) + p.get("bonuses", 0) for p in payroll_records), 2)
    total_net = round(sum(p.get("net_salary", 0) for p in payroll_records), 2)
    total_payslips = len(payroll_records)
    emails_sent = len([p for p in payroll_records if p.get("email_sent")])

    # Employees
    total_employees = await db.users.count_documents({"role": {"$ne": "super_admin"}, "status": {"$ne": "inactive"}})
    suspended = await db.users.count_documents({"status": "suspended"})

    return {
        "period": {"month": m, "year": y, "start": start, "end": end},
        "employees": {"total_active": total_employees, "suspended": suspended},
        "attendance": {
            "records": total_att_days,
            "total_work_hours": total_work_hours,
            "late_days": late_days,
            "absent_days": absent_days,
        },
        "shifts": {"defined": shifts_total, "sessions_this_month": shift_sessions},
        "overtime": {"pending": ot_pending, "approved_this_month": len(ot_approved_month), "approved_hours": ot_hours_approved},
        "leaves": {"pending": leaves_pending, "approved_this_month": leaves_approved_month},
        "payroll": {
            "payslips_generated": total_payslips,
            "total_gross": total_gross,
            "total_net": total_net,
            "emails_sent": emails_sent,
        },
    }


@router.get("/attendance")
async def attendance_report(request: Request, db=Depends(get_db), month: int = None, year: int = None, user_id: str = None):
    await require_manager(request, db)
    now = dhaka_now()
    y = year or now.year
    m = month or now.month
    start = f"{y}-{m:02d}-01"
    end = f"{y + (1 if m == 12 else 0)}-{1 if m == 12 else m + 1:02d}-01"
    query = {"date": {"$gte": start, "$lt": end}}
    if user_id:
        query["user_id"] = user_id
    records = await db.attendance.find(query, {"_id": 0}).sort("date", -1).to_list(5000)
    users_by_id = {}
    rows = []
    for r in records:
        uid = r["user_id"]
        if uid not in users_by_id:
            try:
                u = await db.users.find_one({"_id": ObjectId(uid)}, {"password_hash": 0})
            except Exception:
                u = None
            users_by_id[uid] = u
        u = users_by_id[uid]
        sessions = r.get("sessions") or []
        rows.append({
            "date": r["date"],
            "user_id": uid,
            "user_name": u.get("name") if u else "Unknown",
            "email": u.get("email") if u else "",
            "sessions_count": len(sessions),
            "total_hours": r.get("total_hours", 0),
            "status": r.get("status"),
            "overtime_minutes": r.get("overtime_minutes", 0),
        })
    return {"rows": rows, "total": len(rows)}


@router.get("/payroll")
async def payroll_report(request: Request, db=Depends(get_db), month: int = None, year: int = None):
    await require_manager(request, db)
    now = dhaka_now()
    y = year or now.year
    m = month or now.month
    records = await db.payroll.find({"month": m, "year": y}, {"_id": 0}).to_list(5000)
    return {
        "rows": [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "user_name": r.get("user_name"),
                "base_salary": r.get("base_salary", 0),
                "bonuses": r.get("bonuses", 0),
                "deductions": r.get("deductions", 0),
                "net_salary": r.get("net_salary", 0),
                "total_hours": r.get("total_hours", 0),
                "overtime_hours": r.get("overtime_hours", 0),
                "leave_days": r.get("leave_days", 0),
                "email_sent": r.get("email_sent", False),
                "created_at": r["created_at"].isoformat() if isinstance(r.get("created_at"), datetime) else r.get("created_at"),
            } for r in records
        ],
        "total": len(records),
    }


@router.get("/overtime")
async def overtime_report(request: Request, db=Depends(get_db), status: str = None, month: int = None, year: int = None):
    await require_manager(request, db)
    query = {}
    if status:
        query["status"] = status
    if month and year:
        start = f"{year}-{month:02d}-01"
        end = f"{year + (1 if month == 12 else 0)}-{1 if month == 12 else month + 1:02d}-01"
        query["date"] = {"$gte": start, "$lt": end}
    records = await db.overtime_requests.find(query, {"_id": 0}).sort("date", -1).to_list(2000)
    return {"rows": records, "total": len(records)}
