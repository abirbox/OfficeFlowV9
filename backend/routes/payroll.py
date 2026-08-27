from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from io import BytesIO
import uuid
import logging

from models.shifts import PayrollCreate, PayrollResponse
from utils.auth import get_current_user
from routes.settings import get_settings_doc
from utils.payslip_pdf import build_payslip_pdf
from utils.email import send_email_with_attachment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payroll", tags=["Payroll"])

def get_db(request: Request):
    return request.app.state.db

async def require_admin(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin", "hr"]:
        raise HTTPException(status_code=403, detail="Admin/HR access required")
    return user

async def compute_employee_period_stats(db, user_id: str, month: int, year: int) -> dict:
    """Auto-calculate work hours, overtime, and leave days for an employee for the given month"""
    start_of_month = f"{year}-{month:02d}-01"
    if month == 12:
        end_of_month = f"{year + 1}-01-01"
    else:
        end_of_month = f"{year}-{month + 1:02d}-01"
    
    attendance = await db.attendance.find({
        "user_id": user_id,
        "date": {"$gte": start_of_month, "$lt": end_of_month}
    }, {"_id": 0}).to_list(100)
    
    total_hours = sum(a.get("total_hours", 0) for a in attendance)
    overtime_hours = round(sum(a.get("overtime_minutes", 0) for a in attendance) / 60, 2)
    late_days = len([a for a in attendance if a.get("status") == "late"])
    
    # Approved leaves within this month
    leaves = await db.leaves.find({
        "user_id": user_id,
        "status": "approved",
    }, {"_id": 0}).to_list(100)
    leave_days = 0
    for l in leaves:
        if l["start_date"] < end_of_month and l["end_date"] >= start_of_month:
            leave_days += l.get("days", 0)
    
    return {
        "total_hours": round(total_hours, 2),
        "overtime_hours": overtime_hours,
        "leave_days": leave_days,
        "late_days": late_days,
    }

@router.get("/preview/{user_id}")
async def preview_payroll(user_id: str, request: Request, db = Depends(get_db), month: int = None, year: int = None):
    """Preview auto-computed stats before creating payroll"""
    await require_admin(request, db)
    
    now = datetime.now(timezone.utc)
    stats = await compute_employee_period_stats(db, user_id, month or now.month, year or now.year)
    
    try:
        emp = await db.users.find_one({"_id": ObjectId(user_id)}, {"password_hash": 0})
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid employee id")
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return {
        "user_id": user_id,
        "user_name": emp["name"],
        "user_email": emp["email"],
        "current_salary": emp.get("salary", 0),
        "base_salary": emp.get("base_salary", emp.get("salary")) or 0,
        "house_rent": emp.get("house_rent") or 0,
        "medical": emp.get("medical") or 0,
        "transport": emp.get("transport") or 0,
        "communication": emp.get("communication") or 0,
        "mobile_bill": emp.get("mobile_bill") or 0,
        **stats,
    }

@router.post("", response_model=PayrollResponse)
async def create_payroll(data: PayrollCreate, request: Request, db = Depends(get_db)):
    await require_admin(request, db)
    
    stats = await compute_employee_period_stats(db, data.user_id, data.month, data.year)
    allowances = [a.model_dump() for a in data.allowances]
    allowances_total = sum(float(a.get("amount", 0) or 0) for a in allowances)
    gross = (data.base_salary + data.house_rent + data.medical + data.transport
             + data.communication + data.mobile_bill + allowances_total + data.bonuses)
    net_salary = gross - data.deductions
    
    try:
        emp = await db.users.find_one({"_id": ObjectId(data.user_id)}, {"password_hash": 0})
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail="Invalid employee id")
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    existing = await db.payroll.find_one({"user_id": data.user_id, "month": data.month, "year": data.year})
    if existing:
        raise HTTPException(status_code=400, detail="Payroll already exists for this month")
    
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": data.user_id,
        "user_name": emp["name"],
        "month": data.month,
        "year": data.year,
        "base_salary": data.base_salary,
        "house_rent": data.house_rent,
        "medical": data.medical,
        "transport": data.transport,
        "communication": data.communication,
        "mobile_bill": data.mobile_bill,
        "allowances": allowances,
        "bonuses": data.bonuses,
        "deductions": data.deductions,
        "notes": data.notes,
        "net_salary": net_salary,
        "status": "generated",
        **stats,
        "created_at": datetime.now(timezone.utc),
    }
    await db.payroll.insert_one(doc)

    # Fire-and-note: email PDF payslip to the employee. Non-blocking of the response.
    try:
        pdf_bytes, invoice_no = await build_payslip_pdf(db, doc)
        settings = await get_settings_doc(db)
        brand = settings.get("brand_name", "OfficeFlow")
        currency_symbol = settings.get("currency_symbol", "৳")
        months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        period = f"{months[data.month]} {data.year}"
        html = f"""
          <div style=\"font-family:Arial,sans-serif;max-width:560px;margin:auto\">\
            <h2 style=\"color:#4F46E5\">{brand}</h2>
            <p>Hi {emp.get('name','there')},</p>
            <p>Your payslip for <b>{period}</b> is ready. Net salary: <b>{currency_symbol} {net_salary:,.2f}</b>.</p>
            <p>The full PDF is attached to this email. You can also download it any time from your dashboard.</p>
            <p style=\"color:#64748B;font-size:12px\">Invoice #{invoice_no}</p>
            <hr style=\"border:none;border-top:1px solid #E2E8F0\"/>
            <p style=\"color:#64748B;font-size:12px\">This is an automated message from {brand}. Please do not reply.</p>
          </div>
        """
        email_result = await send_email_with_attachment(
            to=emp["email"],
            subject=f"Your payslip for {period}",
            html=html,
            attachment_bytes=pdf_bytes,
            attachment_filename=f"payslip_{period.replace(' ', '_')}.pdf",
        )
        await db.payroll.update_one(
            {"id": doc["id"]},
            {"$set": {
                "email_sent": bool(email_result.get("sent")),
                "email_result": email_result,
                "email_attempted_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Payslip email failed for user %s: %s", data.user_id, e)

    return PayrollResponse(**{k: v for k, v in doc.items() if k != "created_at"}, created_at=doc["created_at"].isoformat())

@router.get("", response_model=list[PayrollResponse])
async def list_payroll(request: Request, db = Depends(get_db), user_id: str = None):
    user = await get_current_user(request, db)
    
    query = {}
    if user.get("role") == "employee":
        query["user_id"] = user["_id"]
    elif user_id:
        query["user_id"] = user_id
    
    records = await db.payroll.find(query, {"_id": 0}).sort("year", -1).sort("month", -1).to_list(200)
    return [
        PayrollResponse(
            **{k: v for k, v in r.items() if k != "created_at"},
            created_at=r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else r["created_at"],
        )
        for r in records
    ]


@router.get("/{payroll_id}/pdf")
async def download_payroll_pdf(payroll_id: str, request: Request, db = Depends(get_db)):
    """Generate a PDF invoice for a payslip. Employees can download their own; admin/hr any."""
    user = await get_current_user(request, db)
    record = await db.payroll.find_one({"id": payroll_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Payslip not found")
    if user.get("role") == "employee" and record["user_id"] != user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to download this payslip")

    pdf_bytes, invoice_no = await build_payslip_pdf(db, record)
    months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    period = f"{months[record['month']]}_{record['year']}"
    filename = f"payslip_{period}_{invoice_no}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{payroll_id}/email")
async def resend_payslip_email(payroll_id: str, request: Request, db = Depends(get_db)):
    """Admin/HR can resend the payslip email + PDF attachment."""
    await require_admin(request, db)
    record = await db.payroll.find_one({"id": payroll_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Payslip not found")
    try:
        emp = await db.users.find_one({"_id": ObjectId(record["user_id"])}, {"password_hash": 0})
    except Exception:
        emp = None
    if not emp or not emp.get("email"):
        raise HTTPException(status_code=400, detail="Employee has no email on file")

    settings = await get_settings_doc(db)
    brand = settings.get("brand_name", "OfficeFlow")
    currency_symbol = settings.get("currency_symbol", "৳")
    months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    period = f"{months[record['month']]} {record['year']}"
    pdf_bytes, invoice_no = await build_payslip_pdf(db, record)
    html = f"""
      <div style='font-family:Arial,sans-serif;max-width:560px;margin:auto'>\
        <h2 style='color:#4F46E5'>{brand}</h2>
        <p>Hi {emp.get('name','there')},</p>
        <p>Your payslip for <b>{period}</b> is attached. Net salary: <b>{currency_symbol} {record.get('net_salary',0):,.2f}</b>.</p>
        <p style='color:#64748B;font-size:12px'>Invoice #{invoice_no}</p>
      </div>
    """
    result = await send_email_with_attachment(
        to=emp["email"],
        subject=f"Your payslip for {period}",
        html=html,
        attachment_bytes=pdf_bytes,
        attachment_filename=f"payslip_{period.replace(' ', '_')}.pdf",
    )
    await db.payroll.update_one(
        {"id": payroll_id},
        {"$set": {
            "email_sent": bool(result.get("sent")),
            "email_result": result,
            "email_attempted_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if not result.get("sent"):
        return {"sent": False, "reason": result.get("reason"), "message": "Email service not configured (RESEND_API_KEY missing) or send failed. Check backend logs."}
    return {"sent": True, "id": result.get("id"), "to": emp["email"]}
