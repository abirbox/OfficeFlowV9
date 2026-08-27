from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
import uuid
import math

from models.gps_task import GPSSessionCreate, GPSLocationUpdate, GPSSessionResponse
from utils.auth import get_current_user

router = APIRouter(prefix="/gps", tags=["GPS Tracking"])

def get_db(request: Request):
    return request.app.state.db

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@router.post("/start", response_model=GPSSessionResponse)
async def start_tracking(data: GPSSessionCreate, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    user_id = user["_id"]
    
    active_session = await db.gps_sessions.find_one({"user_id": user_id, "status": "active"})
    if active_session:
        raise HTTPException(status_code=400, detail="You already have an active tracking session")
    
    initial_coords = []
    if data.initial_latitude and data.initial_longitude:
        initial_coords.append({
            "latitude": data.initial_latitude,
            "longitude": data.initial_longitude,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    
    session_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "coordinates": initial_coords,
        "total_distance": 0.0,
        "status": "active",
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc),
    }
    
    await db.gps_sessions.insert_one(session_doc)
    
    return GPSSessionResponse(
        id=session_doc["id"],
        user_id=user_id,
        user_name=user["name"],
        started_at=session_doc["started_at"],
        ended_at=session_doc["ended_at"],
        coordinates=session_doc["coordinates"],
        total_distance=session_doc["total_distance"],
        status=session_doc["status"],
        notes=session_doc["notes"],
    )

@router.post("/{session_id}/location")
async def update_location(session_id: str, data: GPSLocationUpdate, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    session = await db.gps_sessions.find_one({"id": session_id, "user_id": user["_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Session is not active")
    
    new_coord = {
        "latitude": data.latitude,
        "longitude": data.longitude,
        "accuracy": data.accuracy,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    total_distance = session.get("total_distance", 0.0)
    if session["coordinates"]:
        last_coord = session["coordinates"][-1]
        distance = calculate_distance(
            last_coord["latitude"], last_coord["longitude"],
            data.latitude, data.longitude
        )
        total_distance += distance
    
    await db.gps_sessions.update_one(
        {"id": session_id},
        {
            "$push": {"coordinates": new_coord},
            "$set": {"total_distance": total_distance}
        }
    )
    
    return {"success": True, "total_distance": round(total_distance, 2)}

@router.post("/{session_id}/stop", response_model=GPSSessionResponse)
async def stop_tracking(session_id: str, request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    session = await db.gps_sessions.find_one({"id": session_id, "user_id": user["_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.gps_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    updated = await db.gps_sessions.find_one({"id": session_id}, {"_id": 0})
    
    return GPSSessionResponse(
        id=updated["id"],
        user_id=updated["user_id"],
        user_name=user["name"],
        started_at=updated["started_at"],
        ended_at=updated["ended_at"],
        coordinates=updated["coordinates"],
        total_distance=updated["total_distance"],
        status=updated["status"],
        notes=updated.get("notes"),
    )

@router.get("/active")
async def get_active_session(request: Request, db = Depends(get_db)):
    user = await get_current_user(request, db)
    
    session = await db.gps_sessions.find_one({"user_id": user["_id"], "status": "active"}, {"_id": 0})
    if not session:
        return {"active": False, "session": None}
    
    return {
        "active": True,
        "session": GPSSessionResponse(
            id=session["id"],
            user_id=session["user_id"],
            user_name=user["name"],
            started_at=session["started_at"],
            ended_at=session.get("ended_at"),
            coordinates=session.get("coordinates", []),
            total_distance=session.get("total_distance", 0.0),
            status=session["status"],
            notes=session.get("notes"),
        ).model_dump()
    }

@router.get("/history", response_model=list[GPSSessionResponse])
async def get_gps_history(request: Request, db = Depends(get_db), limit: int = 20):
    user = await get_current_user(request, db)
    
    sessions = await db.gps_sessions.find(
        {"user_id": user["_id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return [
        GPSSessionResponse(
            id=s["id"],
            user_id=s["user_id"],
            user_name=user["name"],
            started_at=s["started_at"],
            ended_at=s.get("ended_at"),
            coordinates=s.get("coordinates", []),
            total_distance=s.get("total_distance", 0.0),
            status=s["status"],
            notes=s.get("notes"),
        )
        for s in sessions
    ]
