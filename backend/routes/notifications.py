from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
from utils.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])

def get_db(request: Request):
    return request.app.state.db

@router.get("")
async def list_notifications(request: Request, db = Depends(get_db), unread_only: bool = False):
    user = await get_current_user(request, db)
    query = {"user_id": str(user["_id"])}
    if unread_only:
        query["read"] = False
    notifs = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    result = []
    for n in notifs:
        result.append({
            **n,
            "created_at": n["created_at"].isoformat() if isinstance(n["created_at"], datetime) else n["created_at"],
        })
    return result

@router.post("/{notif_id}/read")
async def mark_read(notif_id: str, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    await db.notifications.update_one({"id": notif_id, "user_id": str(user["_id"])}, {"$set": {"read": True}})
    return {"message": "Marked as read"}

@router.post("/read-all")
async def mark_all_read(request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    await db.notifications.update_many({"user_id": str(user["_id"]), "read": False}, {"$set": {"read": True}})
    return {"message": "All notifications marked as read"}
