from pydantic import BaseModel
from typing import Optional

class ShiftCommentCreate(BaseModel):
    body: str

class ShiftCommentResponse(BaseModel):
    id: str
    shift_id: str
    author_id: str
    author_name: Optional[str] = None
    author_role: Optional[str] = None
    author_avatar: Optional[str] = None
    body: str
    created_at: str
