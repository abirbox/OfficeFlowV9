from pydantic import BaseModel
from typing import Optional

class OvertimeApproveRequest(BaseModel):
    note: Optional[str] = None

class OvertimeResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    shift_id: Optional[str] = None
    shift_title: Optional[str] = None
    date: str
    total_hours: float
    overtime_hours: float
    overtime_minutes: int
    status: str  # pending, approved, rejected
    reviewer_id: Optional[str] = None
    reviewer_name: Optional[str] = None
    review_note: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str
