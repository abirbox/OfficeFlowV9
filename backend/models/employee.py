from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date

class EmployeeCreate(BaseModel):
    email: EmailStr
    name: str
    password: Optional[str] = None  # If not provided, defaults to Welcome@123
    phone: Optional[str] = None
    company_id: Optional[str] = None
    branch_id: Optional[str] = None
    department_id: Optional[str] = None
    designation_id: Optional[str] = None
    role: str = "employee"
    date_of_birth: Optional[str] = None
    date_of_joining: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    salary: Optional[float] = None
    base_salary: Optional[float] = None
    house_rent: Optional[float] = None
    medical: Optional[float] = None
    transport: Optional[float] = None
    communication: Optional[float] = None
    mobile_bill: Optional[float] = None
    permissions: Optional[list] = None

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[str] = None
    department_id: Optional[str] = None
    designation_id: Optional[str] = None
    role: Optional[str] = None
    date_of_birth: Optional[str] = None
    date_of_joining: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    salary: Optional[float] = None
    base_salary: Optional[float] = None
    house_rent: Optional[float] = None
    medical: Optional[float] = None
    transport: Optional[float] = None
    communication: Optional[float] = None
    mobile_bill: Optional[float] = None
    avatar_path: Optional[str] = None
    status: Optional[str] = None
    permissions: Optional[list] = None

class EmployeeResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: Optional[str] = None
    avatar_path: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    branch_id: Optional[str] = None
    branch_name: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    designation_id: Optional[str] = None
    designation_name: Optional[str] = None
    role: str
    date_of_birth: Optional[str] = None
    date_of_joining: Optional[str] = None
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    salary: Optional[float] = None
    base_salary: Optional[float] = None
    house_rent: Optional[float] = None
    medical: Optional[float] = None
    transport: Optional[float] = None
    communication: Optional[float] = None
    mobile_bill: Optional[float] = None
    permissions: list = []
    status: str
    created_at: str