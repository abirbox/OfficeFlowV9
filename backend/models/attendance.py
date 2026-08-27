from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, time

class AttendanceCheckIn(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None

class AttendanceCheckOut(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None

class AttendanceBreak(BaseModel):
    break_type: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class AttendanceSession(BaseModel):
    check_in: str
    check_out: Optional[str] = None
    hours: Optional[float] = 0.0
    check_in_location: Optional[dict] = None
    check_out_location: Optional[dict] = None


class AttendanceResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    date: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    total_hours: Optional[float] = 0.0
    breaks: Optional[List[dict]] = []
    overtime_minutes: Optional[int] = 0
    status: str
    check_in_location: Optional[dict] = None
    check_out_location: Optional[dict] = None
    notes: Optional[str] = None
    sessions: Optional[List[dict]] = []
    is_working: Optional[bool] = False
    created_at: str

class AttendanceStats(BaseModel):
    total_days: int
    present_days: int
    absent_days: int
    late_days: int
    total_hours: float
    average_hours: float