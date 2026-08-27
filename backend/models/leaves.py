from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LeaveCreate(BaseModel):
    type: str  # annual, sick, casual, unpaid
    start_date: str
    end_date: str
    reason: Optional[str] = None

class LeaveUpdate(BaseModel):
    status: str  # pending, approved, rejected
    admin_note: Optional[str] = None

class LeaveResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    type: str
    start_date: str
    end_date: str
    days: int
    reason: Optional[str] = None
    status: str
    admin_note: Optional[str] = None
    approved_by: Optional[str] = None
    approver_name: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

class RoleChangeRequest(BaseModel):
    role: str  # super_admin, admin, hr, manager, employee
