from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CompanyBase(BaseModel):
    name: str
    logo_path: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    settings: Optional[dict] = None

class CompanyCreate(BaseModel):
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    logo_path: Optional[str] = None

class CompanyResponse(BaseModel):
    id: str
    name: str
    logo_path: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    created_at: str
    employee_count: Optional[int] = 0

class BranchCreate(BaseModel):
    company_id: str
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class BranchResponse(BaseModel):
    id: str
    company_id: str
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: str

class DepartmentCreate(BaseModel):
    company_id: str
    name: str
    description: Optional[str] = None

class DepartmentResponse(BaseModel):
    id: str
    company_id: str
    name: str
    description: Optional[str] = None
    created_at: str
    employee_count: Optional[int] = 0

class DesignationCreate(BaseModel):
    company_id: str
    name: str
    level: Optional[str] = None
    description: Optional[str] = None

class DesignationResponse(BaseModel):
    id: str
    company_id: str
    name: str
    level: Optional[str] = None
    description: Optional[str] = None
    created_at: str