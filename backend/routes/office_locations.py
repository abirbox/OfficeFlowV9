from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone
import uuid
import math
import urllib.parse
import httpx

from models.office_location import (
    OfficeLocationCreate, OfficeLocationUpdate, OfficeLocationResponse,
)
from utils.auth import get_current_user

router = APIRouter(prefix="/office-locations", tags=["Office Locations"])


def get_db(request: Request):
    return request.app.state.db


async def require_admin(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def haversine_meters(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def geocode_address(address: str) -> tuple[float, float] | None:
    """Free geocoding via OpenStreetMap Nominatim. Returns (lat, lng) or None."""
    if not address or not address.strip():
        return None
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=1"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, headers={"User-Agent": "OfficeFlow/1.0"})
            r.raise_for_status()
            data = r.json()
            if data and len(data) > 0:
                return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None
    return None


def _to_response(doc: dict) -> OfficeLocationResponse:
    return OfficeLocationResponse(
        id=doc["id"],
        name=doc["name"],
        address=doc.get("address"),
        latitude=doc["latitude"],
        longitude=doc["longitude"],
        radius_meters=doc.get("radius_meters", 100),
        created_at=doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at", ""),
    )


@router.get("", response_model=list[OfficeLocationResponse])
async def list_offices(request: Request, db=Depends(get_db)):
    await get_current_user(request, db)  # any authenticated user can view
    docs = await db.office_locations.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return [_to_response(d) for d in docs]


@router.post("", response_model=OfficeLocationResponse)
async def create_office(payload: OfficeLocationCreate, request: Request, db=Depends(get_db)):
    await require_admin(request, db)
    lat = payload.latitude
    lng = payload.longitude
    # Geocode address when coordinates are missing
    if (lat is None or lng is None) and payload.address:
        geo = await geocode_address(payload.address)
        if geo:
            lat, lng = geo
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Could not resolve coordinates. Provide latitude/longitude or a geocodable address.")
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "address": payload.address,
        "latitude": float(lat),
        "longitude": float(lng),
        "radius_meters": payload.radius_meters,
        "created_at": datetime.now(timezone.utc),
    }
    await db.office_locations.insert_one(doc)
    return _to_response(doc)


@router.get("/geocode")
async def geocode_endpoint(address: str, request: Request, db=Depends(get_db)):
    """Look up lat/lng for an address via Nominatim. Any authenticated user can call."""
    await get_current_user(request, db)
    if not address or not address.strip():
        raise HTTPException(status_code=400, detail="address is required")
    result = await geocode_address(address)
    if not result:
        return {"found": False, "latitude": None, "longitude": None}
    return {"found": True, "latitude": result[0], "longitude": result[1]}


@router.put("/{office_id}", response_model=OfficeLocationResponse)
async def update_office(office_id: str, payload: OfficeLocationUpdate, request: Request, db=Depends(get_db)):
    await require_admin(request, db)
    existing = await db.office_locations.find_one({"id": office_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Office not found")
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    update["updated_at"] = datetime.now(timezone.utc)
    await db.office_locations.update_one({"id": office_id}, {"$set": update})
    doc = await db.office_locations.find_one({"id": office_id}, {"_id": 0})
    return _to_response(doc)


@router.delete("/{office_id}")
async def delete_office(office_id: str, request: Request, db=Depends(get_db)):
    await require_admin(request, db)
    res = await db.office_locations.delete_one({"id": office_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Office not found")
    return {"message": "Office deleted"}


@router.get("/nearest")
async def nearest_office(request: Request, db=Depends(get_db), lat: float = None, lng: float = None):
    """Return the nearest office to given lat/lng with distance in meters."""
    await get_current_user(request, db)
    if lat is None or lng is None:
        raise HTTPException(status_code=400, detail="lat and lng are required")
    offices = await db.office_locations.find({}, {"_id": 0}).to_list(200)
    if not offices:
        return {"office": None, "distance_meters": None, "within_geofence": False}
    best = None
    best_dist = None
    for o in offices:
        d = haversine_meters(lat, lng, o["latitude"], o["longitude"])
        if best_dist is None or d < best_dist:
            best, best_dist = o, d
    within = best_dist is not None and best_dist <= best.get("radius_meters", 100)
    return {
        "office": _to_response(best).model_dump(),
        "distance_meters": round(best_dist, 1),
        "within_geofence": within,
    }
