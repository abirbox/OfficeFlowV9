from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from models.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from models.user import UserCreate
from utils.auth import get_current_user, hash_password
from utils.permissions import validate_permission_codes
from utils.storage import put_object, generate_upload_path

router = APIRouter(prefix="/employees", tags=["Employees"])

def get_db(request: Request):
    return request.app.state.db

PRIVILEGED_ROLES = {"super_admin", "hd"}

async def require_admin(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin", "hr"]:
        raise HTTPException(status_code=403, detail="Admin/HR access required")
    return user


def _ensure_can_assign_role(current_user: dict, target_role: str):
    """Only super_admin may create/promote to super_admin or hd."""
    if target_role in PRIVILEGED_ROLES and current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403,
            detail=f"Only Super Admin can assign the '{target_role}' role."
        )

@router.post("", response_model=EmployeeResponse)
async def create_employee(employee: EmployeeCreate, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    _ensure_can_assign_role(user, employee.role)
    
    email_lower = employee.email.lower()
    existing = await db.users.find_one({"email": email_lower})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Enforce password policy at the API boundary. Never silently substitute
    # a default — direct callers (curl, tests, third-party) must supply one.
    if not employee.password or len(employee.password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password is required and must be at least 6 characters.",
        )
    password_hash = hash_password(employee.password)
    
    user_doc = {
        "email": email_lower,
        "password_hash": password_hash,
        "name": employee.name,
        "phone": employee.phone,
        "role": employee.role,
        "company_id": employee.company_id,
        "branch_id": employee.branch_id,
        "department_id": employee.department_id,
        "designation_id": employee.designation_id,
        "date_of_birth": employee.date_of_birth,
        "date_of_joining": employee.date_of_joining,
        "address": employee.address,
        "emergency_contact": employee.emergency_contact,
        "emergency_contact_name": employee.emergency_contact_name,
        "salary": employee.salary,
        "base_salary": employee.base_salary if employee.base_salary is not None else employee.salary,
        "house_rent": employee.house_rent or 0,
        "medical": employee.medical or 0,
        "transport": employee.transport or 0,
        "communication": employee.communication or 0,
        "mobile_bill": employee.mobile_bill or 0,
        "permissions": validate_permission_codes(employee.permissions),
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    company = await db.companies.find_one({"id": employee.company_id}, {"_id": 0})
    branch = await db.branches.find_one({"id": employee.branch_id}, {"_id": 0}) if employee.branch_id else None
    department = await db.departments.find_one({"id": employee.department_id}, {"_id": 0}) if employee.department_id else None
    designation = await db.designations.find_one({"id": employee.designation_id}, {"_id": 0}) if employee.designation_id else None
    
    return EmployeeResponse(
        id=user_id,
        email=email_lower,
        name=employee.name,
        phone=employee.phone,
        company_id=employee.company_id,
        company_name=company.get("name") if company else None,
        branch_id=employee.branch_id,
        branch_name=branch.get("name") if branch else None,
        department_id=employee.department_id,
        department_name=department.get("name") if department else None,
        designation_id=employee.designation_id,
        designation_name=designation.get("name") if designation else None,
        role=employee.role,
        date_of_birth=employee.date_of_birth,
        date_of_joining=employee.date_of_joining,
        address=employee.address,
        emergency_contact=employee.emergency_contact,
        emergency_contact_name=employee.emergency_contact_name,
        salary=employee.salary,
        base_salary=employee.base_salary if employee.base_salary is not None else employee.salary,
        house_rent=employee.house_rent or 0,
        medical=employee.medical or 0,
        transport=employee.transport or 0,
        communication=employee.communication or 0,
        mobile_bill=employee.mobile_bill or 0,
        permissions=validate_permission_codes(employee.permissions),
        status="active",
        created_at=user_doc["created_at"].isoformat(),
    )

@router.get("", response_model=list[EmployeeResponse])
async def get_employees(
    request: Request,
    db = Depends(get_db),
    company_id: str = None,
    department_id: str = None,
    status: str = None,
    skip: int = 0,
    limit: int = 100,
):
    user = await get_current_user(request, db)
    
    # Employees cannot list all employees
    if user.get("role") == "employee":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    query = {}
    if company_id:
        query["company_id"] = company_id
    if department_id:
        query["department_id"] = department_id
    if status:
        query["status"] = status
    
    employees = await db.users.find(query, {"password_hash": 0}).skip(skip).limit(limit).to_list(limit)
    
    result = []
    for emp in employees:
        company = await db.companies.find_one({"id": emp.get("company_id")}, {"_id": 0}) if emp.get("company_id") else None
        branch = await db.branches.find_one({"id": emp.get("branch_id")}, {"_id": 0}) if emp.get("branch_id") else None
        department = await db.departments.find_one({"id": emp.get("department_id")}, {"_id": 0}) if emp.get("department_id") else None
        designation = await db.designations.find_one({"id": emp.get("designation_id")}, {"_id": 0}) if emp.get("designation_id") else None
        
        result.append(
            EmployeeResponse(
                id=str(emp["_id"]),
                email=emp["email"],
                name=emp["name"],
                phone=emp.get("phone"),
                avatar_path=emp.get("avatar_path"),
                company_id=emp.get("company_id"),
                company_name=company.get("name") if company else None,
                branch_id=emp.get("branch_id"),
                branch_name=branch.get("name") if branch else None,
                department_id=emp.get("department_id"),
                department_name=department.get("name") if department else None,
                designation_id=emp.get("designation_id"),
                designation_name=designation.get("name") if designation else None,
                role=emp.get("role", "employee"),
                date_of_birth=emp.get("date_of_birth"),
                date_of_joining=emp.get("date_of_joining"),
                address=emp.get("address"),
                emergency_contact=emp.get("emergency_contact"),
                emergency_contact_name=emp.get("emergency_contact_name"),
                salary=emp.get("salary"),
                base_salary=emp.get("base_salary", emp.get("salary")),
                house_rent=emp.get("house_rent") or 0,
                medical=emp.get("medical") or 0,
                transport=emp.get("transport") or 0,
                communication=emp.get("communication") or 0,
                mobile_bill=emp.get("mobile_bill") or 0,
                permissions=emp.get("permissions") or [],
                status=emp.get("status", "active"),
                created_at=emp["created_at"].isoformat() if isinstance(emp["created_at"], datetime) else emp["created_at"],
            )
        )
    
    return result

@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: str, request: Request, db = Depends(get_db)):
    await get_current_user(request, db)
    
    emp = await db.users.find_one({"_id": ObjectId(employee_id)}, {"password_hash": 0})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    company = await db.companies.find_one({"id": emp.get("company_id")}, {"_id": 0}) if emp.get("company_id") else None
    branch = await db.branches.find_one({"id": emp.get("branch_id")}, {"_id": 0}) if emp.get("branch_id") else None
    department = await db.departments.find_one({"id": emp.get("department_id")}, {"_id": 0}) if emp.get("department_id") else None
    designation = await db.designations.find_one({"id": emp.get("designation_id")}, {"_id": 0}) if emp.get("designation_id") else None
    
    return EmployeeResponse(
        id=str(emp["_id"]),
        email=emp["email"],
        name=emp["name"],
        phone=emp.get("phone"),
        avatar_path=emp.get("avatar_path"),
        company_id=emp.get("company_id"),
        company_name=company.get("name") if company else None,
        branch_id=emp.get("branch_id"),
        branch_name=branch.get("name") if branch else None,
        department_id=emp.get("department_id"),
        department_name=department.get("name") if department else None,
        designation_id=emp.get("designation_id"),
        designation_name=designation.get("name") if designation else None,
        role=emp.get("role", "employee"),
        date_of_birth=emp.get("date_of_birth"),
        date_of_joining=emp.get("date_of_joining"),
        address=emp.get("address"),
        emergency_contact=emp.get("emergency_contact"),
        emergency_contact_name=emp.get("emergency_contact_name"),
        salary=emp.get("salary"),
        base_salary=emp.get("base_salary", emp.get("salary")),
        house_rent=emp.get("house_rent") or 0,
        medical=emp.get("medical") or 0,
        transport=emp.get("transport") or 0,
        communication=emp.get("communication") or 0,
        mobile_bill=emp.get("mobile_bill") or 0,
        permissions=emp.get("permissions") or [],
        status=emp.get("status", "active"),
        created_at=emp["created_at"].isoformat() if isinstance(emp["created_at"], datetime) else emp["created_at"],
    )

@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(employee_id: str, employee: EmployeeUpdate, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    existing = await db.users.find_one({"_id": ObjectId(employee_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Guard privileged role assignment/demotion
    if employee.role is not None and employee.role != existing.get("role"):
        _ensure_can_assign_role(user, employee.role)
    # Prevent non-super-admins from editing a super_admin/hd account at all
    if existing.get("role") in PRIVILEGED_ROLES and user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can modify a privileged account.")
    update_data = {k: v for k, v in employee.model_dump().items() if v is not None}
    # Hash password on the fly when admin resets it
    if update_data.get("password"):
        pw = update_data.pop("password")
        if len(pw) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        update_data["password_hash"] = hash_password(pw)
    if "permissions" in update_data:
        update_data["permissions"] = validate_permission_codes(update_data["permissions"])
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.users.update_one({"_id": ObjectId(employee_id)}, {"$set": update_data})
    
    return await get_employee(employee_id, request, db)

@router.delete("/{employee_id}")
async def delete_employee(employee_id: str, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)

    existing = await db.users.find_one({"_id": ObjectId(employee_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Refuse to delete the last super_admin so admins cannot lock themselves out.
    if existing.get("role") == "super_admin":
        remaining = await db.users.count_documents({"role": "super_admin", "_id": {"$ne": ObjectId(employee_id)}})
        if remaining == 0:
            raise HTTPException(status_code=400, detail="Cannot delete the last super admin")

    await db.users.delete_one({"_id": ObjectId(employee_id)})
    # Cascade: purge dependent records so historical views don't reference a ghost user.
    await db.attendance.delete_many({"user_id": employee_id})
    await db.shifts.delete_many({"user_id": employee_id})
    await db.overtime_requests.delete_many({"user_id": employee_id})
    await db.leave_requests.delete_many({"user_id": employee_id})

    return {"message": "Employee deleted"}

@router.post("/{employee_id}/avatar")
async def upload_avatar(employee_id: str, file: UploadFile, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    if str(user["_id"]) != employee_id and user.get("role") not in ["super_admin", "admin", "hr"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    emp = await db.users.find_one({"_id": ObjectId(employee_id)})
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    data = await file.read()
    path = generate_upload_path(employee_id, file.filename)
    result = put_object(path, data, file.content_type or "image/png")
    
    await db.users.update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {"avatar_path": result["path"], "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"avatar_path": result["path"], "message": "Avatar uploaded successfully"}