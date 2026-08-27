from fastapi import APIRouter, Request, Depends
from datetime import datetime, timezone, timedelta

from utils.auth import get_current_user

router = APIRouter(prefix="/presence", tags=["Presence"])

ONLINE_WINDOW_SECONDS = 45


def get_db(request: Request):
    return request.app.state.db


@router.post("/heartbeat")
async def heartbeat(request: Request, db=Depends(get_db)):
    """Called periodically by every logged-in client to mark itself online."""
    user = await get_current_user(request, db)
    uid = str(user["_id"])
    now = datetime.now(timezone.utc)
    await db.user_presence.update_one(
        {"user_id": uid},
        {"$set": {"user_id": uid, "last_seen": now}},
        upsert=True,
    )
    return {"status": "ok", "user_id": uid}


@router.get("/online")
async def online_users(request: Request, db=Depends(get_db)):
    """Return the set of user_ids seen within the online window."""
    await get_current_user(request, db)
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ONLINE_WINDOW_SECONDS)
    rows = await db.user_presence.find(
        {"last_seen": {"$gte": cutoff}}, {"_id": 0, "user_id": 1}
    ).to_list(5000)
    return {"online": [r["user_id"] for r in rows]}
