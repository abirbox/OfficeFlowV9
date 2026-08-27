from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ShiftCreate(BaseModel):
    user_id: str
    title: Optional[str] = "Regular Shift"
    work_location: str = "in_office"  # in_office or work_from_home
    start_time: str  # HH:MM
    end_time: str    # HH:MM
    days_of_week: List[int]  # 1=Mon .. 7=Sun
    effective_from: str  # YYYY-MM-DD
    effective_to: str    # YYYY-MM-DD


class BulkShiftCreate(BaseModel):
    user_ids: List[str]
    title: Optional[str] = "Regular Shift"
    work_location: str = "in_office"
    start_time: str
    end_time: str
    days_of_week: List[int]
    effective_from: str
    effective_to: str

class ShiftUpdate(BaseModel):
    title: Optional[str] = None
    work_location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[str] = None

class ShiftResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    title: str
    work_location: str
    start_time: str
    end_time: str
    days_of_week: List[int]
    effective_from: str
    effective_to: str
    status: str
    created_by: str
    creator_name: Optional[str] = None
    created_at: str

class ShiftSessionResponse(BaseModel):
    id: str
    shift_id: str
    user_id: str
    date: str
    joined_at: str
    ended_at: Optional[str] = None
    is_late: bool = False
    late_minutes: int = 0
    overtime_minutes: int = 0
    status: str  # joined, ended
    work_hours: float = 0.0

class PayrollAllowance(BaseModel):
    label: str
    amount: float = 0.0


class PayrollCreate(BaseModel):
    user_id: str
    month: int
    year: int
    base_salary: float
    house_rent: float = 0.0
    medical: float = 0.0
    transport: float = 0.0
    communication: float = 0.0
    mobile_bill: float = 0.0
    allowances: List[PayrollAllowance] = []
    bonuses: float = 0.0
    deductions: float = 0.0
    notes: Optional[str] = None

class PayrollResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    month: int
    year: int
    base_salary: float
    house_rent: float = 0.0
    medical: float = 0.0
    transport: float = 0.0
    communication: float = 0.0
    mobile_bill: float = 0.0
    allowances: List[PayrollAllowance] = []
    total_hours: float = 0.0
    overtime_hours: float = 0.0
    leave_days: int = 0
    late_days: int = 0
    bonuses: float = 0.0
    deductions: float = 0.0
    net_salary: float
    status: str = "generated"
    notes: Optional[str] = None
    created_at: str
