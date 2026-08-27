from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from models.company import (
    CompanyCreate,
    CompanyUpdate,
    CompanyResponse,
    BranchCreate,
    BranchResponse,
    DepartmentCreate,
    DepartmentResponse,
    DesignationCreate,
    DesignationResponse,
)
from utils.auth import get_current_user
from utils.storage import put_object, generate_upload_path, to_public_url

router = APIRouter(prefix="/companies", tags=["Companies"])

def get_db(request: Request):
    return request.app.state.db

async def require_admin(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.post("", response_model=CompanyResponse)
async def create_company(company: CompanyCreate, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    company_doc = {
        "id": str(uuid.uuid4()),
        **company.model_dump(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    
    await db.companies.insert_one(company_doc)
    
    employee_count = await db.users.count_documents({"company_id": company_doc["id"]})
    
    return CompanyResponse(
        id=company_doc["id"],
        name=company_doc["name"],
        logo_path=company_doc.get("logo_path"),
        address=company_doc.get("address"),
        phone=company_doc.get("phone"),
        email=company_doc.get("email"),
        website=company_doc.get("website"),
        industry=company_doc.get("industry"),
        size=company_doc.get("size"),
        created_at=company_doc["created_at"].isoformat(),
        employee_count=employee_count,
    )

@router.get("", response_model=list[CompanyResponse])
async def get_companies(request: Request, db = Depends(get_db), skip: int = 0, limit: int = 100):
    user = await get_current_user(request, db)
    
    # Employees cannot list all companies
    if user.get("role") == "employee":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    companies = await db.companies.find({"deleted_at": None}, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    result = []
    for company in companies:
        employee_count = await db.users.count_documents({"company_id": company["id"]})
        result.append(
            CompanyResponse(
                id=company["id"],
                name=company["name"],
                logo_path=company.get("logo_path"),
                address=company.get("address"),
                phone=company.get("phone"),
                email=company.get("email"),
                website=company.get("website"),
                industry=company.get("industry"),
                size=company.get("size"),
                created_at=company["created_at"].isoformat() if isinstance(company["created_at"], datetime) else company["created_at"],
                employee_count=employee_count,
            )
        )
    
    return result

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str, request: Request, db = Depends(get_db)):
    await get_current_user(request, db)
    
    company = await db.companies.find_one({"id": company_id, "deleted_at": None}, {"_id": 0})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    employee_count = await db.users.count_documents({"company_id": company_id})
    
    return CompanyResponse(
        id=company["id"],
        name=company["name"],
        logo_path=company.get("logo_path"),
        address=company.get("address"),
        phone=company.get("phone"),
        email=company.get("email"),
        website=company.get("website"),
        industry=company.get("industry"),
        size=company.get("size"),
        created_at=company["created_at"].isoformat() if isinstance(company["created_at"], datetime) else company["created_at"],
        employee_count=employee_count,
    )

@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: str, company: CompanyUpdate, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    existing = await db.companies.find_one({"id": company_id, "deleted_at": None})
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
    
    update_data = {k: v for k, v in company.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.companies.update_one({"id": company_id}, {"$set": update_data})
    
    updated = await db.companies.find_one({"id": company_id}, {"_id": 0})
    employee_count = await db.users.count_documents({"company_id": company_id})
    
    return CompanyResponse(
        id=updated["id"],
        name=updated["name"],
        logo_path=updated.get("logo_path"),
        address=updated.get("address"),
        phone=updated.get("phone"),
        email=updated.get("email"),
        website=updated.get("website"),
        industry=updated.get("industry"),
        size=updated.get("size"),
        created_at=updated["created_at"].isoformat() if isinstance(updated["created_at"], datetime) else updated["created_at"],
        employee_count=employee_count,
    )

@router.delete("/{company_id}")
async def delete_company(company_id: str, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    existing = await db.companies.find_one({"id": company_id, "deleted_at": None})
    if not existing:
        raise HTTPException(status_code=404, detail="Company not found")
    
    await db.companies.update_one(
        {"id": company_id},
        {"$set": {"deleted_at": datetime.now(timezone.utc)}}
    )
    
    return {"message": "Company deleted successfully"}

@router.post("/{company_id}/logo")
async def upload_company_logo(company_id: str, file: UploadFile, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    company = await db.companies.find_one({"id": company_id, "deleted_at": None})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    data = await file.read()
    path = generate_upload_path(company_id, file.filename)
    result = put_object(path, data, file.content_type or "image/png")
    logo_url = to_public_url(result["path"])

    await db.companies.update_one(
        {"id": company_id},
        {"$set": {"logo_path": logo_url, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"logo_path": logo_url, "message": "Logo uploaded successfully"}

@router.post("/{company_id}/branches", response_model=BranchResponse)
async def create_branch(company_id: str, branch: BranchCreate, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    branch_doc = {
        "id": str(uuid.uuid4()),
        **branch.model_dump(),
        "created_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    
    await db.branches.insert_one(branch_doc)
    
    return BranchResponse(
        id=branch_doc["id"],
        company_id=branch_doc["company_id"],
        name=branch_doc["name"],
        address=branch_doc.get("address"),
        phone=branch_doc.get("phone"),
        latitude=branch_doc.get("latitude"),
        longitude=branch_doc.get("longitude"),
        created_at=branch_doc["created_at"].isoformat(),
    )

@router.get("/{company_id}/branches", response_model=list[BranchResponse])
async def get_branches(company_id: str, request: Request, db = Depends(get_db)):
    await get_current_user(request, db)
    
    branches = await db.branches.find({"company_id": company_id, "deleted_at": None}, {"_id": 0}).to_list(100)
    
    return [
        BranchResponse(
            id=branch["id"],
            company_id=branch["company_id"],
            name=branch["name"],
            address=branch.get("address"),
            phone=branch.get("phone"),
            latitude=branch.get("latitude"),
            longitude=branch.get("longitude"),
            created_at=branch["created_at"].isoformat() if isinstance(branch["created_at"], datetime) else branch["created_at"],
        )
        for branch in branches
    ]

@router.post("/{company_id}/departments", response_model=DepartmentResponse)
async def create_department(company_id: str, department: DepartmentCreate, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    dept_doc = {
        "id": str(uuid.uuid4()),
        **department.model_dump(),
        "created_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    
    await db.departments.insert_one(dept_doc)
    
    employee_count = await db.users.count_documents({"department_id": dept_doc["id"]})
    
    return DepartmentResponse(
        id=dept_doc["id"],
        company_id=dept_doc["company_id"],
        name=dept_doc["name"],
        description=dept_doc.get("description"),
        created_at=dept_doc["created_at"].isoformat(),
        employee_count=employee_count,
    )

@router.get("/{company_id}/departments", response_model=list[DepartmentResponse])
async def get_departments(company_id: str, request: Request, db = Depends(get_db)):
    await get_current_user(request, db)
    
    departments = await db.departments.find({"company_id": company_id, "deleted_at": None}, {"_id": 0}).to_list(100)
    
    result = []
    for dept in departments:
        employee_count = await db.users.count_documents({"department_id": dept["id"]})
        result.append(
            DepartmentResponse(
                id=dept["id"],
                company_id=dept["company_id"],
                name=dept["name"],
                description=dept.get("description"),
                created_at=dept["created_at"].isoformat() if isinstance(dept["created_at"], datetime) else dept["created_at"],
                employee_count=employee_count,
            )
        )
    
    return result

@router.post("/{company_id}/designations", response_model=DesignationResponse)
async def create_designation(company_id: str, designation: DesignationCreate, request: Request, db = Depends(get_db)):
    user = await require_admin(request, db)
    
    desig_doc = {
        "id": str(uuid.uuid4()),
        **designation.model_dump(),
        "created_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }
    
    await db.designations.insert_one(desig_doc)
    
    return DesignationResponse(
        id=desig_doc["id"],
        company_id=desig_doc["company_id"],
        name=desig_doc["name"],
        level=desig_doc.get("level"),
        description=desig_doc.get("description"),
        created_at=desig_doc["created_at"].isoformat(),
    )

@router.get("/{company_id}/designations", response_model=list[DesignationResponse])
async def get_designations(company_id: str, request: Request, db = Depends(get_db)):
    await get_current_user(request, db)
    
    designations = await db.designations.find({"company_id": company_id, "deleted_at": None}, {"_id": 0}).to_list(100)
    
    return [
        DesignationResponse(
            id=desig["id"],
            company_id=desig["company_id"],
            name=desig["name"],
            level=desig.get("level"),
            description=desig.get("description"),
            created_at=desig["created_at"].isoformat() if isinstance(desig["created_at"], datetime) else desig["created_at"],
        )
        for desig in designations
    ]