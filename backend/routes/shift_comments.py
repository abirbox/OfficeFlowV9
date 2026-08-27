from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from models.shift_comments import ShiftCommentCreate, ShiftCommentResponse
from utils.auth import get_current_user

router = APIRouter(prefix="/shifts", tags=["Shift Comments"])


def get_db(request: Request):
    return request.app.state.db


async def _can_access_shift(shift: dict, user: dict) -> bool:
    role = user.get("role")
    if role in ["super_admin", "admin", "hr", "manager"]:
        return True
    return shift["user_id"] == user["_id"]


async def _notify(db, user_id: str, from_user: dict, shift_id: str, body: str, shift_title: str):
    if not user_id:
        return
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "shift_comment",
        "title": f"New message on {shift_title}",
        "message": f"{from_user.get('name', 'Someone')}: {body[:120]}",
        "from_user_id": str(from_user["_id"]),
        "from_user_name": from_user.get("name"),
        "reference_id": shift_id,
        "read": False,
        "created_at": datetime.now(timezone.utc),
    })


@router.get("/{shift_id}/comments", response_model=list[ShiftCommentResponse])
async def list_comments(shift_id: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    shift = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if not await _can_access_shift(shift, user):
        raise HTTPException(status_code=403, detail="Not allowed to view these comments")

    comments = await db.shift_comments.find({"shift_id": shift_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    out: list[ShiftCommentResponse] = []
    for c in comments:
        author = None
        try:
            author = await db.users.find_one({"_id": ObjectId(c["author_id"])}, {"password_hash": 0})
        except Exception:
            pass
        out.append(ShiftCommentResponse(
            id=c["id"],
            shift_id=c["shift_id"],
            author_id=c["author_id"],
            author_name=author.get("name") if author else c.get("author_name"),
            author_role=author.get("role") if author else c.get("author_role"),
            author_avatar=author.get("avatar_path") if author else None,
            body=c["body"],
            created_at=c["created_at"].isoformat() if isinstance(c["created_at"], datetime) else c["created_at"],
        ))
    return out


@router.post("/{shift_id}/comments", response_model=ShiftCommentResponse)
async def add_comment(shift_id: str, payload: ShiftCommentCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    shift = await db.shifts.find_one({"id": shift_id}, {"_id": 0})
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    if not await _can_access_shift(shift, user):
        raise HTTPException(status_code=403, detail="Not allowed to post here")

    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    if len(body) > 2000:
        raise HTTPException(status_code=400, detail="Comment too long (max 2000 chars)")

    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()),
        "shift_id": shift_id,
        "author_id": user["_id"],
        "author_name": user.get("name"),
        "author_role": user.get("role"),
        "body": body,
        "created_at": now,
    }
    await db.shift_comments.insert_one(doc)

    # Notify the counterpart
    shift_title = shift.get("title", "Shift")
    if user["_id"] == shift["user_id"]:
        # Employee posted -> notify admins/HR
        admins = await db.users.find({"role": {"$in": ["super_admin", "admin", "hr", "manager"]}}, {"password_hash": 0}).to_list(100)
        for a in admins:
            await _notify(db, str(a["_id"]), user, shift_id, body, shift_title)
    else:
        # Admin/manager posted -> notify the assigned employee
        await _notify(db, shift["user_id"], user, shift_id, body, shift_title)

    return ShiftCommentResponse(
        id=doc["id"],
        shift_id=doc["shift_id"],
        author_id=doc["author_id"],
        author_name=doc["author_name"],
        author_role=doc["author_role"],
        author_avatar=user.get("avatar_path"),
        body=doc["body"],
        created_at=now.isoformat(),
    )
