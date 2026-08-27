from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class GPSCoordinate(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: Optional[str] = None

class GPSSessionCreate(BaseModel):
    initial_latitude: Optional[float] = None
    initial_longitude: Optional[float] = None
    notes: Optional[str] = None

class GPSLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    accuracy: Optional[float] = None

class GPSSessionResponse(BaseModel):
    id: str
    user_id: str
    user_name: Optional[str] = None
    started_at: str
    ended_at: Optional[str] = None
    coordinates: List[dict] = []
    total_distance: Optional[float] = 0.0
    status: str
    notes: Optional[str] = None

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    assigned_to: Optional[str] = None
    status: str = "todo"
    priority: str = "medium"
    labels: Optional[List[str]] = []
    due_date: Optional[str] = None
    work_type: str = "in_office"  # in_office or work_from_home

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[str] = None
    assigned_to: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    labels: Optional[List[str]] = None
    due_date: Optional[str] = None
    progress: Optional[int] = None
    work_type: Optional[str] = None

class TaskComment(BaseModel):
    content: str

class SubtaskCreate(BaseModel):
    title: str
    completed: bool = False

class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    assigned_to: Optional[str] = None
    assignee_name: Optional[str] = None
    created_by: str
    creator_name: Optional[str] = None
    status: str
    priority: str
    labels: List[str] = []
    due_date: Optional[str] = None
    progress: int = 0
    work_type: str = "in_office"
    comments: List[dict] = []
    subtasks: List[dict] = []
    attachments: List[dict] = []
    created_at: str
    updated_at: Optional[str] = None
