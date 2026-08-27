"""Dispatch module routes — Clients, Vendors, Officers, Post Sites, Schedule + Confirmation."""
from fastapi import APIRouter, HTTPException, Request, Depends, Query, UploadFile
import random
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, date, timedelta
from typing import Optional
from bson import ObjectId
import io
import uuid

from models.dispatch import (
    ClientCreate, ClientUpdate,
    VendorCreate, VendorUpdate,
    OfficerCreate, OfficerUpdate, OFFICER_STATUSES,
    PostSiteCreate, PostSiteUpdate,
    ScheduleCreate, ScheduleUpdate, ConfirmationUpdate, ShiftStatusUpdate,
    SHIFT_TYPES, SHIFT_STATUSES, COMPLETED_STATUSES, CONFIRMATION_STATUSES, CONFIRMATION_METHODS,
    OFFICER_TYPES,
    PayslipRecordCreate,
    ClientPortalCredentials,
)
from utils.auth import get_current_user, hash_password
from utils.permissions import (
    has_permission, require_permission, strip_financial,
    ALL_PERMISSIONS, FINANCIAL_FIELDS,
)
from utils.dispatch_reports import build_csv, build_pdf, build_xlsx
from utils.tz import dhaka_today, dhaka_today_iso

# Temporary scheduling placeholders.
# These are stored directly in officer_id and do not require
# a corresponding dispatch_officers MongoDB document.
SPECIAL_OFFICERS = {"TEMP", "OPEN_SHIFT"}
UMA_TIME = "UMA"
from utils.storage import to_public_url
from utils.ws import manager

router = APIRouter(prefix="/dispatch", tags=["Dispatch"])


def _format_pin(vendor_code, post_pin):
    """Return the standard "CODE # PIN" display string used everywhere."""
    if not post_pin:
        return None
    code = (vendor_code or "").strip()
    pin = str(post_pin).strip()
    return f"{code} # {pin}" if code else f"# {pin}"


async def _resolve_vendor_codes(db, vendor_ids) -> dict:
    """{vendor_id_str: code} for a set of vendor ids."""
    ids = {v for v in vendor_ids if v}
    if not ids:
        return {}
    obj_ids = []
    for v in ids:
        try:
            obj_ids.append(ObjectId(v))
        except Exception:
            pass
    if not obj_ids:
        return {}
    docs = await db.dispatch_vendors.find(
        {"_id": {"$in": obj_ids}}, {"code": 1}
    ).to_list(len(obj_ids))
    return {str(d["_id"]): d.get("code") for d in docs}


@router.post("/upload-logo")
async def upload_dispatch_logo(file: UploadFile, request: Request):
    """Upload a client/vendor logo and return its public URL."""
    db = request.app.state.db
    await get_current_user(request, db)
    from utils.storage import put_object, generate_upload_path, to_public_url
    data = await file.read()
    path = generate_upload_path("dispatch", file.filename)
    result = put_object(path, data, file.content_type or "image/png")
    return {"url": to_public_url(result["path"])}

def get_db(request: Request):
    return request.app.state.db


def _now():
    return datetime.now(timezone.utc)


def _oid(x: str):
    try:
        return ObjectId(x)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


def _doc_out(doc: dict) -> dict:
    if not doc:
        return doc

    d = dict(doc)
    d["id"] = str(d.pop("_id"))

    for k, v in list(d.items()):
        if isinstance(v, datetime):
            # MongoDB returns UTC datetimes as naive datetime objects.
            # Explicitly mark them as UTC before sending to the frontend.
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)

            d[k] = v.isoformat()

        elif isinstance(v, ObjectId):
            d[k] = str(v)

    return d


def _parse_hhmm(s: str) -> int:
    """Return minutes since midnight, or raise."""
    try:
        h, m = s.split(":")
        h, m = int(h), int(m)
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError()
        return h * 60 + m
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid time '{s}', expected HH:MM")


def _duty_hours(start: str, end: str) -> Optional[float]:
    """Compute duty hours, handling overnight.

    UMA means the time is not decided yet, so duty hours cannot
    be calculated until the actual time is assigned.
    """
    if start == UMA_TIME or end == UMA_TIME:
        return None

    s = _parse_hhmm(start)
    e = _parse_hhmm(end)

    if e <= s:  # overnight (e.g. 22:00 → 06:00)
        e += 24 * 60

    return round((e - s) / 60.0, 2)


# ---------- Permissions meta endpoint (used by frontend) ----------
@router.get("/permissions/registry")
async def get_permissions_registry(request: Request, db=Depends(get_db)):
    await get_current_user(request, db)
    return {"permissions": ALL_PERMISSIONS}


# =====================================================================
#  CLIENTS
# =====================================================================
@router.post("/clients")
async def create_client(payload: ClientCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.create")
    doc = payload.model_dump()
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_clients.insert_one(doc)
    await _audit(db, user, "create", "client", res.inserted_id, doc.get("name"))
    return _doc_out(await db.dispatch_clients.find_one({"_id": res.inserted_id}))


def _enrich_logo(d: dict) -> dict:
    """Attach a browser-loadable logo_url derived from logo_path (if any)."""
    if d.get("logo_path"):
        d["logo_url"] = to_public_url(d["logo_path"])
    return d


@router.get("/clients")
async def list_clients(request: Request, db=Depends(get_db), search: str = "",
                       status: str = None, skip: int = 0, limit: int = 100):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.view")
    q = {}
    if status: q["status"] = status
    if search: q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                            {"code": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_clients.find(q).skip(skip).limit(limit).to_list(limit)
    return [_enrich_logo(_doc_out(d)) for d in docs]


@router.get("/clients/{cid}")
async def get_client(cid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.view")
    doc = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    if not doc: raise HTTPException(404, "Client not found")
    return _enrich_logo(_doc_out(doc))


@router.put("/clients/{cid}")
async def update_client(cid: str, payload: ClientUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.edit")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    r = await db.dispatch_clients.update_one({"_id": _oid(cid)}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Client not found")
    saved = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    await _audit(db, user, "update", "client", cid, saved.get("name"),
                 changes={k: v for k, v in upd.items() if k not in ("updated_by", "updated_at")})
    return _doc_out(saved)


@router.delete("/clients/{cid}")
async def delete_client(cid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.delete")
    existing = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    r = await db.dispatch_clients.delete_one({"_id": _oid(cid)})
    if r.deleted_count == 0: raise HTTPException(404, "Client not found")
    await _audit(db, user, "delete", "client", cid, (existing or {}).get("name"))
    return {"message": "Client deleted"}


# =====================================================================
#  VENDORS
# =====================================================================
@router.post("/vendors")
async def create_vendor(payload: VendorCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.create")
    doc = payload.model_dump()
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_vendors.insert_one(doc)
    await _audit(db, user, "create", "vendor", res.inserted_id, doc.get("name"))
    return _doc_out(await db.dispatch_vendors.find_one({"_id": res.inserted_id}))


@router.get("/vendors")
async def list_vendors(request: Request, db=Depends(get_db), search: str = "",
                       status: str = None, skip: int = 0, limit: int = 100):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.view")
    q = {}
    if status: q["status"] = status
    if search: q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                            {"code": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_vendors.find(q).skip(skip).limit(limit).to_list(limit)
    return [_doc_out(d) for d in docs]


@router.get("/vendors/{vid}")
async def get_vendor(vid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.view")
    doc = await db.dispatch_vendors.find_one({"_id": _oid(vid)})
    if not doc: raise HTTPException(404, "Vendor not found")
    return _doc_out(doc)


@router.put("/vendors/{vid}")
async def update_vendor(vid: str, payload: VendorUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.edit")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    r = await db.dispatch_vendors.update_one({"_id": _oid(vid)}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Vendor not found")
    saved = await db.dispatch_vendors.find_one({"_id": _oid(vid)})
    await _audit(db, user, "update", "vendor", vid, saved.get("name"),
                 changes={k: v for k, v in upd.items() if k not in ("updated_by", "updated_at")})
    return _doc_out(saved)


@router.delete("/vendors/{vid}")
async def delete_vendor(vid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.delete")
    existing = await db.dispatch_vendors.find_one({"_id": _oid(vid)})
    r = await db.dispatch_vendors.delete_one({"_id": _oid(vid)})
    if r.deleted_count == 0: raise HTTPException(404, "Vendor not found")
    await _audit(db, user, "delete", "vendor", vid, (existing or {}).get("name"))
    return {"message": "Vendor deleted"}


# =====================================================================
#  CLIENT PORTAL LOGIN  (admin creates/manages a client's login account)
# =====================================================================
@router.get("/clients/{cid}/portal")
async def get_client_portal(cid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.view")
    client = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    if not client:
        raise HTTPException(404, "Client not found")
    portal_user = await db.users.find_one({"role": "client", "client_id": cid})
    return {"enabled": bool(portal_user),
            "email": portal_user.get("email") if portal_user else None}


@router.put("/clients/{cid}/portal")
async def set_client_portal(cid: str, payload: ClientPortalCredentials,
                            request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.edit")
    client = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    if not client:
        raise HTTPException(404, "Client not found")

    email = payload.email.lower().strip()
    portal_user = await db.users.find_one({"role": "client", "client_id": cid})

    # Email must be unique across ALL users (except this client's own account).
    dup = await db.users.find_one({"email": email})
    if dup and (not portal_user or str(dup["_id"]) != str(portal_user["_id"])):
        raise HTTPException(400, "Email already in use by another account")

    if portal_user:
        upd = {"email": email, "name": client.get("name"),
               "client_id": cid, "updated_at": _now()}
        if payload.password:
            upd["password_hash"] = hash_password(payload.password)
        await db.users.update_one({"_id": portal_user["_id"]}, {"$set": upd})
    else:
        if not payload.password:
            raise HTTPException(400, "Password is required to create a client login")
        await db.users.insert_one({
            "email": email,
            "password_hash": hash_password(payload.password),
            "name": client.get("name"),
            "role": "client",
            "client_id": cid,
            "permissions": [],
            "status": "active",
            "created_at": _now(),
            "updated_at": _now(),
        })

    await _audit(db, user, "update", "client", cid, client.get("name"),
                 changes={"portal_login": email})
    return {"enabled": True, "email": email}


@router.delete("/clients/{cid}/portal")
async def delete_client_portal(cid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.edit")
    client = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    if not client:
        raise HTTPException(404, "Client not found")
    await db.users.delete_one({"role": "client", "client_id": cid})
    await _audit(db, user, "update", "client", cid, client.get("name"),
                 changes={"portal_login": "removed"})
    return {"enabled": False}


# =====================================================================
#  SECURITY OFFICERS  (NO GPS — external persons)
# =====================================================================

async def _generate_officer_code(db, client_code: str, exclude_id=None):
    """
    Generate a unique Security Officer Code:
        CLIENTCODE + 6 digits

    Example:
        ARS012345
    """
    client_code = str(client_code or "").strip()

    if not client_code:
        raise HTTPException(400, "Client Code is required")

    query = {}

    for _ in range(100):
        number = random.randint(0, 999999)
        code = f"{client_code}{number:06d}"

        query["officer_code"] = code

        if exclude_id is not None:
            query["_id"] = {"$ne": exclude_id}

        existing = await db.dispatch_officers.find_one(query)

        if not existing:
            return code

    raise HTTPException(
        500,
        "Unable to generate a unique Officer Code"
    )

@router.post("/officers")
async def create_officer(payload: OfficerCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.create")

    if payload.status not in OFFICER_STATUSES:
        raise HTTPException(400, "Invalid officer status")

    if payload.type not in OFFICER_TYPES:
        raise HTTPException(400, f"Invalid officer type. Allowed values: {', '.join(OFFICER_TYPES)}")

    # Client is required and Officer Code always comes from the Client code.
    client = await db.dispatch_clients.find_one({"_id": _oid(payload.client_id)})
    if not client:
        raise HTTPException(400, "Selected client not found")

    client_code = str(client.get("code") or "").strip()
    if not client_code:
        raise HTTPException(400, "Selected client does not have a Client Code")

    doc = payload.model_dump()
    doc["client_id"] = str(client["_id"])
    doc["officer_code"] = await _generate_officer_code(db, client_code)
    doc["created_by"] = str(user["_id"])
    doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"])
    doc["updated_at"] = _now()

    res = await db.dispatch_officers.insert_one(doc)
    await _audit(db, user, "create", "officer", res.inserted_id, doc.get("name"))
    return _doc_out(await db.dispatch_officers.find_one({"_id": res.inserted_id}))


@router.get("/officers")
async def list_officers(request: Request, db=Depends(get_db), search: str = "",
                        client_id: str = None, type: str = None, status: str = None,
                        skip: int = 0, limit: int = 200):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.view")
    q = {}
    if status: q["status"] = status
    if client_id: q["client_id"] = client_id
    if type:
        if type not in OFFICER_TYPES:
            raise HTTPException(
                400,
                f"Invalid officer type. Allowed values: {', '.join(OFFICER_TYPES)}"
            )
        q["type"] = type
    if search:
        q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                    {"contact_number": {"$regex": search, "$options": "i"}},
                    {"officer_code": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_officers.find(q).skip(skip).limit(limit).to_list(limit)

    # Attach Client name/code for the Security Officer table.
    client_ids = []
    for d in docs:
        cid = d.get("client_id")
        if cid:
            try:
                client_ids.append(ObjectId(str(cid)))
            except Exception:
                pass

    client_map = {}
    if client_ids:
        client_docs = await db.dispatch_clients.find(
            {"_id": {"$in": client_ids}},
            {"name": 1, "code": 1}
        ).to_list(len(client_ids))

        client_map = {
            str(c["_id"]): c
            for c in client_docs
        }

    output = []
    for d in docs:
        row = _doc_out(d)
        cid = d.get("client_id")
        client = client_map.get(str(cid)) if cid else None

        row["client_name"] = client.get("name") if client else None
        row["client_code"] = client.get("code") if client else None

        output.append(row)

    return output


@router.get("/officers/{oid}")
async def get_officer(oid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.view")
    doc = await db.dispatch_officers.find_one({"_id": _oid(oid)})
    if not doc: raise HTTPException(404, "Officer not found")
    return _doc_out(doc)


@router.put("/officers/{oid}")
async def update_officer(oid: str, payload: OfficerUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.edit")

    existing = await db.dispatch_officers.find_one({"_id": _oid(oid)})
    if not existing:
        raise HTTPException(404, "Officer not found")

    upd = {k: v for k, v in payload.model_dump().items() if v is not None}

    if "status" in upd and upd["status"] not in OFFICER_STATUSES:
        raise HTTPException(400, "Invalid officer status")

    if "type" in upd and upd["type"] not in OFFICER_TYPES:
        raise HTTPException(
            400,
            f"Invalid officer type. Allowed values: {', '.join(OFFICER_TYPES)}"
        )

    # If the Client changes, regenerate the Officer Code from the new Client.
    # Also repair the code automatically when editing an existing officer.
    client_id = upd.get("client_id") or existing.get("client_id")

    if not client_id:
        raise HTTPException(400, "Security Officer must have a Client")

    client = await db.dispatch_clients.find_one({"_id": _oid(client_id)})
    if not client:
        raise HTTPException(400, "Selected client not found")

    client_code = str(client.get("code") or "").strip()
    if not client_code:
        raise HTTPException(400, "Selected client does not have a Client Code")

    upd["client_id"] = str(client["_id"])

    # Generate a new Officer Code only when the Client changes.
    # Otherwise preserve the existing Officer Code.
    if str(existing.get("client_id") or "") != str(client["_id"]):
        upd["officer_code"] = await _generate_officer_code(
            db,
            client_code,
            exclude_id=existing["_id"]
        )
    else:
        upd["officer_code"] = existing.get("officer_code")

    upd["updated_by"] = str(user["_id"])
    upd["updated_at"] = _now()

    r = await db.dispatch_officers.update_one(
        {"_id": _oid(oid)},
        {"$set": upd}
    )

    if r.matched_count == 0:
        raise HTTPException(404, "Officer not found")

    saved = await db.dispatch_officers.find_one({"_id": _oid(oid)})

    await _audit(
        db,
        user,
        "update",
        "officer",
        oid,
        saved.get("name"),
        changes={
            k: v for k, v in upd.items()
            if k not in ("updated_by", "updated_at")
        }
    )

    return _doc_out(saved)


@router.delete("/officers/{oid}")
async def delete_officer(oid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.delete")
    existing = await db.dispatch_officers.find_one({"_id": _oid(oid)})
    r = await db.dispatch_officers.delete_one({"_id": _oid(oid)})
    if r.deleted_count == 0: raise HTTPException(404, "Officer not found")
    await _audit(db, user, "delete", "officer", oid, (existing or {}).get("name"))
    return {"message": "Officer deleted"}


# =====================================================================
#  POST SITES  (NO GPS)
# =====================================================================
@router.post("/post-sites")
async def create_post_site(payload: PostSiteCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.create")
    if not payload.location.strip():
        raise HTTPException(422, "Location is required")
    # ensure post_pin unique
    if await db.dispatch_post_sites.find_one({"post_pin": payload.post_pin}):
        raise HTTPException(400, "Post Pin already exists")
    doc = payload.model_dump()
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_post_sites.insert_one(doc)
    await _audit(db, user, "create", "post_site", res.inserted_id, f"{doc.get('post_pin')} — {doc.get('name')}")
    return _doc_out(await db.dispatch_post_sites.find_one({"_id": res.inserted_id}))


@router.get("/post-sites")
async def list_post_sites(request: Request, db=Depends(get_db), search: str = "",
                          client_id: str = None, vendor_id: str = None, status: str = None,
                          skip: int = 0, limit: int = 200):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.view")
    q = {}
    if status: q["status"] = status
    if client_id: q["client_id"] = client_id
    if vendor_id: q["vendor_id"] = vendor_id
    if search:
        q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                    {"post_pin": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_post_sites.find(q).skip(skip).limit(limit).to_list(limit)
    return [_doc_out(d) for d in docs]


@router.get("/post-sites/{pid}")
async def get_post_site(pid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.view")
    doc = await db.dispatch_post_sites.find_one({"_id": _oid(pid)})
    if not doc: raise HTTPException(404, "Post Site not found")
    return _doc_out(doc)


@router.put("/post-sites/{pid}")
async def update_post_site(pid: str, payload: PostSiteUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.edit")
    if payload.location is not None and not payload.location.strip():
        raise HTTPException(422, "Location is required")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "post_pin" in upd:
        dup = await db.dispatch_post_sites.find_one({"post_pin": upd["post_pin"], "_id": {"$ne": _oid(pid)}})
        if dup: raise HTTPException(400, "Post Pin already exists")
    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    r = await db.dispatch_post_sites.update_one({"_id": _oid(pid)}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Post Site not found")
    saved = await db.dispatch_post_sites.find_one({"_id": _oid(pid)})
    await _audit(db, user, "update", "post_site", pid, f"{saved.get('post_pin')} — {saved.get('name')}",
                 changes={k: v for k, v in upd.items() if k not in ("updated_by", "updated_at")})
    return _doc_out(saved)


@router.delete("/post-sites/{pid}")
async def delete_post_site(pid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.delete")
    existing = await db.dispatch_post_sites.find_one({"_id": _oid(pid)})
    r = await db.dispatch_post_sites.delete_one({"_id": _oid(pid)})
    if r.deleted_count == 0: raise HTTPException(404, "Post Site not found")
    await _audit(db, user, "delete", "post_site", pid,
                 f"{(existing or {}).get('post_pin')} — {(existing or {}).get('name')}")
    return {"message": "Post Site deleted"}


# =====================================================================
#  DISPATCH SCHEDULES
# =====================================================================
async def _check_conflict(db, officer_id: str, sched_date: str,
                          start: str, end: str, exclude_id: str = None):
    """Return existing conflicting schedule for the officer on the same date."""
    s = _parse_hhmm(start)
    e = _parse_hhmm(end)
    if e <= s:
        e += 24 * 60
    q = {"officer_id": officer_id, "date": sched_date}
    if exclude_id:
        q["_id"] = {"$ne": _oid(exclude_id)}
    existing = await db.dispatch_schedules.find(q).to_list(500)
    for ex in existing:
        xs = _parse_hhmm(ex["start_time"])
        xe = _parse_hhmm(ex["end_time"])
        if xe <= xs:
            xe += 24 * 60
        if s < xe and xs < e:
            return ex
    return None


def _merge_remark(existing, new_remark):
    """Append a remark line to the combined remarks store (dedup, newline-joined)."""
    lines = [x.strip() for x in str(existing or "").split("\n") if x.strip()]
    nl = str(new_remark or "").strip()
    if nl and nl not in lines:
        lines.append(nl)
    return "\n".join(lines)


async def _log_action(db, schedule_id: str, actor: dict, action: str,
                      old_value=None, new_value=None, remarks: str = None):
    """Append to dispatch_action_history and update last_modified_* on schedule."""
    now = _now()
    await db.dispatch_action_history.insert_one({
        "schedule_id": schedule_id,
        "action": action,
        "old_value": old_value,
        "new_value": new_value,
        "remarks": remarks,
        "actor_id": str(actor.get("_id")),
        "actor_name": actor.get("name"),
        "actor_role": actor.get("role"),
        "at": now,
    })
    set_doc = {
        "last_modified_by_id": str(actor.get("_id")),
        "last_modified_by_name": actor.get("name"),
        "last_modified_action": action,
        "last_modified_at": now,
    }
    if remarks is not None and str(remarks).strip() != "":
        set_doc["last_modified_remarks"] = remarks
    await db.dispatch_schedules.update_one(
        {"_id": _oid(schedule_id)},
        {"$set": set_doc},
    )


async def _audit(db, actor, action, entity_type, entity_id,
                 entity_name=None, changes=None):
    """Append an entry to the global dispatch audit trail."""
    await db.dispatch_audit.insert_one({
        "action": action,               # create | update | delete | cancel | status | confirm
        "entity_type": entity_type,     # client | vendor | officer | post_site | schedule
        "entity_id": str(entity_id) if entity_id else None,
        "entity_name": entity_name,
        "changes": changes,
        "actor_id": str(actor.get("_id")),
        "actor_name": actor.get("name"),
        "actor_role": actor.get("role"),
        "at": _now(),
    })


async def _notify_dispatch(db, actor, title, message, link, event):
    """Persist a notification for every dispatch-privileged user (except the
    actor) and push a live event to any connected WebSocket clients."""
    recipients = await db.users.find({"$or": [
        {"role": {"$in": ["super_admin", "hd"]}},
        {"permissions": {"$in": [
            "dispatch.confirmation.view", "dispatch.schedule.view", "dispatch.dashboard.view",
        ]}},
    ]}, {"_id": 1}).to_list(2000)
    actor_id = str(actor.get("_id"))
    ids = [str(u["_id"]) for u in recipients if str(u["_id"]) != actor_id]
    now = _now()
    if ids:
        await db.notifications.insert_many([{
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "title": title,
            "message": message,
            "type": "dispatch",
            "link": link,
            "read": False,
            "created_at": now,
        } for uid in ids])
    await manager.send_to_users(ids, {**event, "title": title,
                                      "message": message,
                                      "created_at": now.isoformat()})



@router.post("/schedules")
async def create_schedule(payload: ScheduleCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.create")

    if payload.shift_type not in SHIFT_TYPES:
        raise HTTPException(400, f"Shift type must be one of {SHIFT_TYPES}")

    # Determine creation mode. Existing clients that do not send schedule_mode
    # automatically remain in the original single-date behavior.
    mode = (payload.schedule_mode or "once").strip().lower()
    if mode not in ("once", "multiple"):
        raise HTTPException(400, "Schedule mode must be either 'once' or 'multiple'.")

    # Build the list of dates to create.
    if mode == "once":
        if not payload.date:
            raise HTTPException(422, "Date is required.")

        dates = [payload.date]

    else:
        if not payload.date_from:
            raise HTTPException(422, "From date is required.")
        if not payload.date_to:
            raise HTTPException(422, "To date is required.")

        try:
            from datetime import date as _date, timedelta as _timedelta

            start_date = _date.fromisoformat(payload.date_from)
            end_date = _date.fromisoformat(payload.date_to)
        except ValueError:
            raise HTTPException(422, "From date and To date must be valid dates in YYYY-MM-DD format.")

        if end_date < start_date:
            raise HTTPException(422, "To date cannot be earlier than From date.")

        # Safety limit prevents accidental extremely large submissions.
        total_days = (end_date - start_date).days + 1
        if total_days > 366:
            raise HTTPException(422, "Multiple schedule range cannot exceed 366 days.")

        dates = [
            (start_date + _timedelta(days=i)).isoformat()
            for i in range(total_days)
        ]

    # Financial fields require permission.
    financial_write = has_permission(user, "dispatch.financial.view")
    if not financial_write and (
        payload.duty_rate is not None
        or payload.billing_rate is not None
        or payload.work_order_number is not None
    ):
        raise HTTPException(403, "You do not have permission to set financial fields.")

    # Verify references exist once before creating the schedules.
    client = await db.dispatch_clients.find_one({"_id": _oid(payload.client_id)})
    if not client:
        raise HTTPException(400, "Invalid client")

    vendor = await db.dispatch_vendors.find_one({"_id": _oid(payload.vendor_id)})
    if not vendor:
        raise HTTPException(400, "Invalid vendor")

    post = await db.dispatch_post_sites.find_one({"_id": _oid(payload.post_site_id)})
    if not post:
        raise HTTPException(400, "Invalid post site")

    # TEMP / Open Shift are intentional placeholders.
    # They do not require a real Security Officer record yet.
    if payload.officer_id not in SPECIAL_OFFICERS:
        officer = await db.dispatch_officers.find_one({
            "_id": _oid(payload.officer_id)
        })

        if not officer:
            raise HTTPException(400, "Invalid officer")

        if officer.get("status") != "active":
            raise HTTPException(400, "Security Officer is not active.")

        # A real Security Officer must belong to the selected Client.
        if str(officer.get("client_id") or "") != str(client["_id"]):
            raise HTTPException(
                400,
                "Selected Security Officer does not belong to the selected Client."
            )

    # Validate ALL dates before inserting anything.
    # This prevents a multiple-date submission from being partially created.
    conflicts = []

    # Conflict checking only makes sense when we have:
    # 1. a real Security Officer
    # 2. actual start/end times
    #
    # TEMP / Open Shift and UMA are placeholders and therefore
    # intentionally skip conflict checking.
    can_check_conflict = (
        payload.officer_id not in SPECIAL_OFFICERS
        and payload.start_time != UMA_TIME
        and payload.end_time != UMA_TIME
    )

    if can_check_conflict:
        for sched_date in dates:
            conflict = await _check_conflict(
                db,
                payload.officer_id,
                sched_date,
                payload.start_time,
                payload.end_time,
            )

            if conflict:
                conflicts.append(
                    f"{conflict['date']} {conflict['start_time']}–{conflict['end_time']}"
                )

    # Also detect conflicts within the new date range itself.
    # This is mostly defensive because each generated schedule uses a
    # different date, but keeps the validation explicit.
    if conflicts:
        if len(conflicts) == 1:
            message = f"Security Officer already has another shift on {conflicts[0]}."
        else:
            message = (
                "Security Officer already has conflicting shifts on: "
                + ", ".join(conflicts)
                + "."
            )
        raise HTTPException(409, message)

    hours = _duty_hours(payload.start_time, payload.end_time)
    now = _now()

    created_ids = []

    for sched_date in dates:
        doc = payload.model_dump()

        # These are request-control fields, not schedule database fields.
        doc.pop("schedule_mode", None)
        doc.pop("date_from", None)
        doc.pop("date_to", None)

        doc["date"] = sched_date
        doc["duty_hours"] = hours
        doc["shift_status"] = "Not Started"
        doc["confirmation_status"] = "Not Confirmed"
        doc["confirmation_method"] = None
        doc["confirmed_by_id"] = None
        doc["confirmed_by_name"] = None
        doc["confirmed_at"] = None
        doc["actual_check_in"] = None
        doc["actual_check_out"] = None
        doc["actual_duty_hours"] = None
        doc["late_minutes"] = 0
        doc["early_minutes"] = 0
        doc["overtime_minutes"] = 0
        doc["created_by"] = str(user["_id"])
        doc["created_at"] = now
        doc["updated_by"] = str(user["_id"])
        doc["updated_at"] = now
        doc["last_modified_by_id"] = str(user["_id"])
        doc["last_modified_by_name"] = user.get("name")
        doc["last_modified_action"] = "Created"
        doc["last_modified_at"] = now

        if doc.get("remarks"):
            doc["last_modified_remarks"] = doc.get("remarks")

        res = await db.dispatch_schedules.insert_one(doc)
        created_ids.append(str(res.inserted_id))

        await db.dispatch_action_history.insert_one({
            "schedule_id": str(res.inserted_id),
            "action": "Created",
            "old_value": None,
            "new_value": doc.get("shift_status"),
            "remarks": None,
            "actor_id": str(user["_id"]),
            "actor_name": user.get("name"),
            "actor_role": user.get("role"),
            "at": now,
        })

        await _audit(
            db,
            user,
            "create",
            "schedule",
            res.inserted_id,
            f"{doc.get('date')} {doc.get('shift_type')} · "
            f"{doc.get('start_time')}–{doc.get('end_time')}",
        )

    # Return the same style of response for a single schedule, while
    # providing a useful summary for multiple-date creation.
    if mode == "once":
        saved = await db.dispatch_schedules.find_one(
            {"_id": _oid(created_ids[0])}
        )
        return strip_financial(_doc_out(saved), user)

    saved_docs = await db.dispatch_schedules.find(
        {"_id": {"$in": [_oid(x) for x in created_ids]}}
    ).sort([("date", 1), ("start_time", 1)]).to_list(len(created_ids))

    return {
        "message": f"{len(created_ids)} schedules created",
        "created": len(created_ids),
        "date_from": dates[0],
        "date_to": dates[-1],
        "items": [
            strip_financial(_doc_out(doc), user)
            for doc in saved_docs
        ],
    }


@router.post("/schedules/import")
async def import_schedules(file: UploadFile, request: Request, db=Depends(get_db),
                           dry_run: bool = False):
    """Bulk-create schedules from a CSV upload.

    Required columns (case-insensitive):
      date, shift_type, start_time, end_time, officer_name (or officer_email),
      post_pin
    Optional columns:
      work_order_number, client_name, vendor_name, duty_rate, billing_rate, remarks

    Query params:
      dry_run=true  — validate only, do not persist anything. Returns the same
                       shape so the frontend can render a preview.
    """
    import csv as _csv
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.create")
    financial_write = has_permission(user, "dispatch.financial.view")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except Exception:
            raise HTTPException(400, "Could not decode file as UTF-8 or Latin-1")

    reader = _csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV has no header row")

    # Normalise headers to lowercase snake so users can capitalise however they like
    def _norm(h):
        return (h or "").strip().lower().replace(" ", "_")
    header_map = {h: _norm(h) for h in reader.fieldnames}

    required = {"date", "shift_type", "start_time", "end_time", "post_pin"}
    lowered = set(header_map.values())
    if not ({"officer_name", "officer_email"} & lowered):
        raise HTTPException(400, "CSV must include either an 'officer_name' or 'officer_email' column")
    missing = required - lowered
    if missing:
        raise HTTPException(400, f"CSV is missing required columns: {', '.join(sorted(missing))}")

    created = []
    errors = []
    skipped = []
    row_num = 1  # header is row 1

    # In-memory cache to avoid re-querying the same pin / officer many times
    post_cache: dict = {}
    officer_cache: dict = {}

    for raw_row in reader:
        row_num += 1
        # Rebuild row with normalised keys
        row = {header_map.get(k, _norm(k)): (v or "").strip() for k, v in raw_row.items()}
        # Skip completely empty rows
        if not any(row.values()):
            continue
        try:
            shift_type = row.get("shift_type")
            if shift_type not in SHIFT_TYPES:
                raise ValueError(f"shift_type must be one of {SHIFT_TYPES}")
            date_val = row.get("date")
            if not date_val or len(date_val) != 10 or date_val[4] != "-" or date_val[7] != "-":
                raise ValueError("date must be YYYY-MM-DD")
            start_time = row.get("start_time"); end_time = row.get("end_time")
            if not start_time or not end_time:
                raise ValueError("start_time and end_time are required")

            post_pin = row.get("post_pin")
            if not post_pin:
                raise ValueError("post_pin is required")
            if post_pin not in post_cache:
                post = await db.dispatch_post_sites.find_one({"post_pin": post_pin})
                if not post:
                    raise ValueError(f"Post site with pin '{post_pin}' not found")
                post_cache[post_pin] = post
            post = post_cache[post_pin]

            # Client / vendor: use the post-site's link, or fall back to
            # explicit CSV values (name OR code) when the post site has none.
            client_id = post.get("client_id")
            vendor_id = post.get("vendor_id")
            if not client_id:
                cname = row.get("client_name") or row.get("client_code")
                if not cname:
                    raise ValueError(
                        f"Post site '{post_pin}' has no client. Add a 'client_name' "
                        f"or 'client_code' column to the CSV."
                    )
                cli = await db.dispatch_clients.find_one({
                    "$or": [{"name": cname}, {"code": cname}]
                })
                if not cli:
                    raise ValueError(f"Client '{cname}' not found")
                client_id = str(cli["_id"])
            if not vendor_id:
                vname = row.get("vendor_name") or row.get("vendor_code")
                if not vname:
                    raise ValueError(
                        f"Post site '{post_pin}' has no vendor. Add a 'vendor_name' "
                        f"or 'vendor_code' column to the CSV."
                    )
                ven = await db.dispatch_vendors.find_one({
                    "$or": [{"name": vname}, {"code": vname}]
                })
                if not ven:
                    raise ValueError(f"Vendor '{vname}' not found")
                vendor_id = str(ven["_id"])

            officer = None
            officer_email = row.get("officer_email")
            officer_name = row.get("officer_name")
            key = f"e:{officer_email}" if officer_email else f"n:{officer_name}"
            if key in officer_cache:
                officer = officer_cache[key]
            else:
                if officer_email:
                    officer = await db.dispatch_officers.find_one({"email": officer_email})
                if officer is None and officer_name:
                    officer = await db.dispatch_officers.find_one({"name": officer_name})
                if not officer:
                    who = officer_email or officer_name or "?"
                    raise ValueError(f"Officer '{who}' not found")
                officer_cache[key] = officer
            if officer.get("status") != "active":
                raise ValueError(f"Officer '{officer.get('name')}' is not active")

            work_order = row.get("work_order_number") or None

            duty_rate = row.get("duty_rate") or None
            billing_rate = row.get("billing_rate") or None
            if (duty_rate or billing_rate or work_order) and not financial_write:
                raise ValueError("You do not have permission to set financial fields")
            duty_rate = float(duty_rate) if duty_rate not in (None, "") else None
            billing_rate = float(billing_rate) if billing_rate not in (None, "") else None

            officer_id = str(officer["_id"])

            # Duplicate guard: skip when an identical shift already exists
            # (same officer + date + start_time). This is the "already
            # scheduled" case — treated as a soft skip, not an error.
            existing_dup = await db.dispatch_schedules.find_one({
                "officer_id": officer_id,
                "date": date_val,
                "start_time": start_time,
            })
            if existing_dup:
                skipped.append({
                    "row": row_num,
                    "reason": f"Duplicate of an existing shift on {date_val} at {start_time} for this officer",
                })
                continue

            conflict = await _check_conflict(db, officer_id, date_val, start_time, end_time)
            if conflict:
                raise ValueError(
                    f"Officer already has another shift on {conflict['date']} "
                    f"{conflict['start_time']}–{conflict['end_time']}"
                )

            hours = _duty_hours(start_time, end_time)
            doc = {
                "date": date_val,
                "shift_type": shift_type,
                "start_time": start_time,
                "end_time": end_time,
                "client_id": str(client_id),
                "vendor_id": str(vendor_id),
                "post_site_id": str(post["_id"]),
                "officer_id": officer_id,
                "work_order_number": work_order,
                "duty_rate": duty_rate,
                "billing_rate": billing_rate,
                "remarks": row.get("remarks") or None,
                "duty_hours": hours,
                "shift_status": "Not Started",
                "confirmation_status": "Not Confirmed",
                "confirmation_method": None,
                "confirmed_by_id": None,
                "confirmed_by_name": None,
                "confirmed_at": None,
                "actual_check_in": None,
                "actual_check_out": None,
                "actual_duty_hours": None,
                "late_minutes": 0, "early_minutes": 0, "overtime_minutes": 0,
                "created_by": str(user["_id"]), "created_at": _now(),
                "updated_by": str(user["_id"]), "updated_at": _now(),
                "last_modified_by_id": str(user["_id"]),
                "last_modified_by_name": user.get("name"),
                "last_modified_action": "Created (CSV import)",
                "last_modified_at": _now(),
            }
            if dry_run:
                # Count the row as valid but do not persist anything.
                created.append(None)
                continue

            res = await db.dispatch_schedules.insert_one(doc)
            await db.dispatch_action_history.insert_one({
                "schedule_id": str(res.inserted_id),
                "action": "Created (CSV import)",
                "old_value": None,
                "new_value": doc["shift_status"],
                "remarks": None,
                "actor_id": str(user["_id"]),
                "actor_name": user.get("name"),
                "actor_role": user.get("role"),
                "at": _now(),
            })
            created.append(str(res.inserted_id))
        except ValueError as ve:
            errors.append({"row": row_num, "message": str(ve)})
        except Exception as ex:  # pragma: no cover — surface unexpected errors
            errors.append({"row": row_num, "message": f"Unexpected error: {ex}"})

    if created and not dry_run:
        await _audit(db, user, "create", "schedule", None,
                     f"CSV import: {len(created)} created, {len(skipped)} skipped, {len(errors)} errors")

    return {
        "dry_run": dry_run,
        "created": len(created),
        "created_ids": [c for c in created if c],
        "skipped": skipped,
        "errors": errors,
    }



@router.get("/schedules")
async def list_schedules(request: Request, db=Depends(get_db),
                         officer_id: str = None, vendor_id: str = None,
                         client_id: str = None, post_site_id: str = None,
                         post_pin: str = None, work_order: str = None,
                         date_from: str = None, date_to: str = None,
                         shift_type: str = None,
                         confirmation_status: str = None,
                         shift_status: str = None,
                         search: str = "",
                         page: int = 1, limit: int = 50):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.view")
    limit = min(max(limit, 1), 250)
    page = max(page, 1)

    q = {}
    if officer_id: q["officer_id"] = officer_id
    if vendor_id: q["vendor_id"] = vendor_id
    if client_id: q["client_id"] = client_id
    if post_site_id: q["post_site_id"] = post_site_id
    if shift_type: q["shift_type"] = shift_type
    if confirmation_status: q["confirmation_status"] = confirmation_status
    if shift_status: q["shift_status"] = shift_status
    if work_order:
        q["work_order_number"] = {"$regex": work_order, "$options": "i"}
    if date_from or date_to:
        date_q = {}
        if date_from: date_q["$gte"] = date_from
        if date_to: date_q["$lte"] = date_to
        q["date"] = date_q

    # Post Pin lookup — resolve to post_site ids
    if post_pin:
        posts = await db.dispatch_post_sites.find(
            {"post_pin": {"$regex": post_pin, "$options": "i"}}, {"_id": 1}
        ).to_list(500)
        pids = [str(p["_id"]) for p in posts]
        # combine with existing post_site_id if any
        if post_site_id and post_site_id not in pids:
            pids = []
        q["post_site_id"] = {"$in": pids} if pids else "__none__"

    total = await db.dispatch_schedules.count_documents(q)
    docs = await db.dispatch_schedules.find(q).sort([("date", 1), ("start_time", 1)]) \
        .skip((page - 1) * limit).limit(limit).to_list(limit)

    # Enrich with names + strip financial
    def _cache_key(coll, _id): return f"{coll}:{_id}"
    cache = {}

    async def _name(coll, _id, field="name"):
        if not _id: return None
        k = _cache_key(coll, _id)
        if k in cache: return cache[k]
        try:
            d = await db[coll].find_one({"_id": _oid(_id)}, {field: 1, "code": 1, "post_pin": 1, "city": 1, "location": 1})
        except Exception:
            d = None
        cache[k] = d
        return d

    out = []
    for d in docs:
        row = strip_financial(_doc_out(d), user)
        cli = await _name("dispatch_clients", d.get("client_id"))
        ven = await _name("dispatch_vendors", d.get("vendor_id"))
        off = await _name("dispatch_officers", d.get("officer_id"))
        pst = await _name("dispatch_post_sites", d.get("post_site_id"))
        row["client_name"] = cli.get("name") if cli else None
        row["vendor_name"] = ven.get("name") if ven else None
        row["vendor_code"] = ven.get("code") if ven else None
        row["officer_name"] = off.get("name") if off else None
        row["post_site_name"] = pst.get("name") if pst else None
        row["location"] = pst.get("location") if pst else None
        row["address"] = pst.get("location") if pst else None
        row["post_site_location"] = pst.get("location") if pst else None
        row["post_pin"] = pst.get("post_pin") if pst else None
        row["post_pin_display"] = _format_pin(row.get("vendor_code"), row.get("post_pin"))
        row["city"] = pst.get("city") if pst else None
        out.append(row)

    return {"items": out, "total": total, "page": page, "limit": limit}


@router.get("/schedules/{sid}")
async def get_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.view")
    doc = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not doc: raise HTTPException(404, "Schedule not found")
    return strip_financial(_doc_out(doc), user)


@router.put("/schedules/{sid}")
async def update_schedule(sid: str, payload: ScheduleUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.edit")
    existing = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not existing: raise HTTPException(404, "Schedule not found")

    # Use exclude_unset so callers can explicitly clear nullable fields (remarks/etc.)
    upd = payload.model_dump(exclude_unset=True)

    # Financial field guard
    fin_write = has_permission(user, "dispatch.financial.view")
    if not fin_write:
        for f in FINANCIAL_FIELDS:
            if f in upd:
                raise HTTPException(403, "You do not have permission to modify financial fields.")

    # Validate shift type / statuses
    if "shift_type" in upd and upd["shift_type"] not in SHIFT_TYPES:
        raise HTTPException(400, f"Shift type must be one of {SHIFT_TYPES}")
    if "shift_status" in upd and upd["shift_status"] not in SHIFT_STATUSES:
        raise HTTPException(400, f"Shift status must be one of {SHIFT_STATUSES}")

    # Validate Security Officer belongs to the selected Client.
    selected_client_id = upd.get("client_id", existing.get("client_id"))
    selected_officer_id = upd.get("officer_id", existing.get("officer_id"))

    if selected_client_id and selected_officer_id:
        client = await db.dispatch_clients.find_one(
            {"_id": _oid(selected_client_id)}
        )
        if not client:
            raise HTTPException(400, "Invalid client")

        # TEMP / Open Shift are valid placeholders and do not have
        # a corresponding dispatch_officers document.
        if selected_officer_id not in SPECIAL_OFFICERS:
            officer = await db.dispatch_officers.find_one(
                {"_id": _oid(selected_officer_id)}
            )

            if not officer:
                raise HTTPException(400, "Invalid officer")

            if officer.get("status") != "active":
                raise HTTPException(400, "Security Officer is not active.")

            if str(officer.get("client_id") or "") != str(client["_id"]):
                raise HTTPException(
                    400,
                    "Selected Security Officer does not belong to the selected Client."
                )

    # Duty hours: an explicit override (from the payslip editor) wins. Otherwise
    # recompute from the start/end time only when the times actually changed, so
    # a previously saved manual override is not wiped when editing other fields.
    st = upd.get("start_time", existing["start_time"])
    et = upd.get("end_time", existing["end_time"])
    if "duty_hours" in upd and upd.get("duty_hours") is not None:
        upd["duty_hours"] = round(float(upd["duty_hours"]), 2)
    elif "start_time" in upd or "end_time" in upd:
        upd["duty_hours"] = _duty_hours(st, et)

    # Conflict re-check when officer/date/times change.
    # Skip this for TEMP / Open Shift and UMA times because these
    # are placeholders until the schedule is finalized.
    conflict_officer = upd.get("officer_id", existing["officer_id"])
    conflict_date = upd.get("date", existing["date"])

    can_check_conflict = (
        conflict_officer not in SPECIAL_OFFICERS
        and st != UMA_TIME
        and et != UMA_TIME
    )

    if (
        can_check_conflict
        and any(k in upd for k in ("officer_id", "date"))
    ):
        conflict = await _check_conflict(
            db,
            conflict_officer,
            conflict_date,
            st,
            et,
            exclude_id=sid
        )

        if conflict:
            raise HTTPException(
                409,
                f"Security Officer already has another shift on {conflict['date']} "
                f"{conflict['start_time']}–{conflict['end_time']}."
            )

    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    await db.dispatch_schedules.update_one({"_id": _oid(sid)}, {"$set": upd})
    # Log only meaningful user-editable changes
    old_snapshot = {k: existing.get(k) for k in upd.keys() if k not in ("updated_by", "updated_at", "duty_hours")}
    new_snapshot = {k: upd.get(k) for k in upd.keys() if k not in ("updated_by", "updated_at", "duty_hours")}
    if "shift_status" in upd:
        await _log_action(db, sid, user, upd["shift_status"],
                          old_value=existing.get("shift_status"), new_value=upd["shift_status"],
                          remarks=upd.get("remarks"))
    elif new_snapshot:
        await _log_action(db, sid, user, "Edited",
                          old_value=old_snapshot, new_value=new_snapshot,
                          remarks=upd.get("remarks"))
    await _audit(db, user, "update", "schedule", sid,
                 f"{existing.get('date')} {existing.get('shift_type')}",
                 changes=new_snapshot or None)
    return strip_financial(_doc_out(await db.dispatch_schedules.find_one({"_id": _oid(sid)})), user)


@router.post("/schedules/{sid}/status")
async def update_shift_status(sid: str, payload: ShiftStatusUpdate, request: Request, db=Depends(get_db)):
    """Quick action endpoint used by the Dispatch Schedule row buttons.
    Records who performed the action and appends to the action history."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.edit")
    if payload.shift_status not in SHIFT_STATUSES:
        raise HTTPException(400, f"Shift status must be one of {SHIFT_STATUSES}")
    existing = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not existing: raise HTTPException(404, "Schedule not found")
    old_status = existing.get("shift_status")
    upd = {"shift_status": payload.shift_status,
           "updated_by": str(user["_id"]), "updated_at": _now()}
    if payload.actual_check_in is not None:
        upd["actual_check_in"] = payload.actual_check_in
    if payload.actual_check_out is not None:
        upd["actual_check_out"] = payload.actual_check_out
    # Accumulate the status remark into the combined remarks cell.
    if payload.remarks and str(payload.remarks).strip():
        upd["remarks"] = _merge_remark(existing.get("remarks"), payload.remarks)
    await db.dispatch_schedules.update_one({"_id": _oid(sid)}, {"$set": upd})
    await _log_action(db, sid, user, payload.shift_status,
                      old_value=old_status, new_value=payload.shift_status,
                      remarks=payload.remarks)
    await _audit(db, user, "status", "schedule", sid,
                 f"{existing.get('date')} {existing.get('shift_type')}",
                 changes={"shift_status": {"from": old_status, "to": payload.shift_status}})
    return strip_financial(_doc_out(await db.dispatch_schedules.find_one({"_id": _oid(sid)})), user)


@router.post("/schedules/{sid}/cancel")
async def cancel_schedule(sid: str, request: Request, db=Depends(get_db)):
    """Kept for backwards compatibility with existing clients: cancelling a
    schedule now hard-deletes it, since the Cancelled status has been
    removed in favour of a leaner Not Started / Clocked In / Clocked Out
    state model. Prefer DELETE /dispatch/schedules/{sid} in new code."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.cancel")
    existing = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not existing:
        raise HTTPException(404, "Schedule not found")
    await db.dispatch_action_history.insert_one({
        "schedule_id": sid, "action": "Deleted (via cancel)",
        "old_value": existing.get("shift_status"), "new_value": None,
        "remarks": None,
        "actor_id": str(user["_id"]), "actor_name": user.get("name"),
        "actor_role": user.get("role"), "at": _now(),
    })
    await db.dispatch_schedules.delete_one({"_id": _oid(sid)})
    await _audit(db, user, "delete", "schedule", sid,
                 f"{existing.get('date')} {existing.get('shift_type')}")
    return {"message": "Schedule deleted"}


@router.delete("/schedules/{sid}")
async def delete_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.delete")
    existing = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not existing: raise HTTPException(404, "Schedule not found")
    # Log BEFORE deleting the schedule (history is a separate collection)
    await db.dispatch_action_history.insert_one({
        "schedule_id": sid, "action": "Deleted",
        "old_value": existing.get("shift_status"), "new_value": None,
        "remarks": None,
        "actor_id": str(user["_id"]), "actor_name": user.get("name"),
        "actor_role": user.get("role"), "at": _now(),
    })
    await db.dispatch_schedules.delete_one({"_id": _oid(sid)})
    await _audit(db, user, "delete", "schedule", sid,
                 f"{existing.get('date')} {existing.get('shift_type')}")
    return {"message": "Schedule deleted"}


@router.get("/schedules/{sid}/actions")
async def schedule_actions(sid: str, request: Request, db=Depends(get_db)):
    """Full action history for a schedule — every check-in, edit, cancel etc."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.view")
    docs = await db.dispatch_action_history.find({"schedule_id": sid}) \
        .sort("at", -1).to_list(500)
    return [_doc_out(d) for d in docs]


# ---------- Confirmation ----------
@router.post("/schedules/{sid}/confirm")
async def confirm_schedule(sid: str, payload: ConfirmationUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.confirmation.manage")
    if payload.confirmation_status not in CONFIRMATION_STATUSES:
        raise HTTPException(400, f"Confirmation status must be one of {CONFIRMATION_STATUSES}")
    if payload.confirmation_method and payload.confirmation_method not in CONFIRMATION_METHODS:
        raise HTTPException(400, f"Method must be one of {CONFIRMATION_METHODS}")

    sched = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not sched: raise HTTPException(404, "Schedule not found")

    now = _now()
    set_doc = {
        "confirmation_status": payload.confirmation_status,
        "confirmation_method": payload.confirmation_method,
        "confirmed_by_id": str(user["_id"]),
        "confirmed_by_name": user.get("name"),
        "confirmed_at": now,
        "updated_by": str(user["_id"]),
        "updated_at": now,
    }
    # Accumulate the confirmation remark into the combined remarks cell.
    if payload.remarks and str(payload.remarks).strip():
        set_doc["remarks"] = _merge_remark(sched.get("remarks"), payload.remarks)
    await db.dispatch_schedules.update_one(
        {"_id": _oid(sid)},
        {"$set": set_doc}
    )
    # Append history entry
    await db.dispatch_confirmation_history.insert_one({
        "schedule_id": sid,
        "officer_id": sched.get("officer_id"),
        "status": payload.confirmation_status,
        "method": payload.confirmation_method,
        "remarks": payload.remarks,
        "contacted_by_id": str(user["_id"]),
        "contacted_by_name": user.get("name"),
        "contacted_by_role": user.get("role"),
        "contacted_by_department_id": user.get("department_id"),
        "contacted_at": now,
    })
    method_note = f" ({payload.confirmation_method})" if payload.confirmation_method else ""
    await _log_action(db, sid, user, f"Confirmation: {payload.confirmation_status}{method_note}",
                      old_value=sched.get("confirmation_status"),
                      new_value=payload.confirmation_status,
                      remarks=payload.remarks)
    await _audit(db, user, "confirm", "schedule", sid,
                 f"{sched.get('date')} {sched.get('shift_type')}",
                 changes={"confirmation_status": {"from": sched.get("confirmation_status"),
                                                  "to": payload.confirmation_status},
                          "method": payload.confirmation_method})
    # Resolve officer + post-site names for a human-friendly notification.
    # TEMP / OPEN_SHIFT are placeholders and are not MongoDB ObjectIds.
    officer_id = sched.get("officer_id")
    if officer_id in SPECIAL_OFFICERS:
        officer_name = "Temporary Officer" if officer_id == "TEMP" else "Open Shift"
    elif officer_id:
        officer = await db.dispatch_officers.find_one(
            {"_id": _oid(officer_id)},
            {"name": 1}
        )
        officer_name = (officer or {}).get("name", "Officer")
    else:
        officer_name = "Officer"

    post = await db.dispatch_post_sites.find_one(
        {"_id": _oid(sched["post_site_id"])},
        {"name": 1, "post_pin": 1}
    ) if sched.get("post_site_id") else None
    post_label = f"{(post or {}).get('post_pin', '')} {(post or {}).get('name', '')}".strip() or "post site"
    await _notify_dispatch(
        db, user,
        title="Dispatch Confirmation Updated",
        message=f"{officer_name} @ {post_label} on {sched.get('date')} → {payload.confirmation_status}{method_note} by {user.get('name')}",
        link="/dashboard/dispatch/schedules",
        event={
            "type": "dispatch_confirmation",
            "schedule_id": sid,
            "status": payload.confirmation_status,
            "method": payload.confirmation_method,
        },
    )
    return {"message": "Confirmation updated"}


@router.get("/schedules/{sid}/history")
async def schedule_history(sid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.confirmation.history")
    docs = await db.dispatch_confirmation_history.find({"schedule_id": sid}) \
        .sort("contacted_at", -1).to_list(500)
    return [_doc_out(d) for d in docs]


# =====================================================================
#  AUDIT TRAIL  (global — every dispatch write action)
# =====================================================================
AUDIT_ENTITY_TYPES = ["client", "vendor", "officer", "post_site", "schedule"]
AUDIT_ACTIONS = ["create", "update", "delete", "cancel", "status", "confirm"]


@router.get("/audit")
async def list_audit(request: Request, db=Depends(get_db),
                     entity_type: str = None, action: str = None,
                     actor_id: str = None, search: str = "",
                     date_from: str = None, date_to: str = None,
                     page: int = 1, limit: int = 50):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.audit.view")
    limit = min(max(limit, 1), 200)
    page = max(page, 1)

    q = {}
    if entity_type: q["entity_type"] = entity_type
    if action: q["action"] = action
    if actor_id: q["actor_id"] = actor_id
    if search:
        q["$or"] = [
            {"entity_name": {"$regex": search, "$options": "i"}},
            {"actor_name": {"$regex": search, "$options": "i"}},
        ]
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        if date_to:
            rng["$lte"] = datetime.fromisoformat(date_to).replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc)
        q["at"] = rng

    total = await db.dispatch_audit.count_documents(q)
    docs = await db.dispatch_audit.find(q).sort("at", -1) \
        .skip((page - 1) * limit).limit(limit).to_list(limit)
    return {"items": [_doc_out(d) for d in docs], "total": total,
            "page": page, "limit": limit,
            "entity_types": AUDIT_ENTITY_TYPES, "actions": AUDIT_ACTIONS}


@router.get("/audit/actors")
async def list_audit_actors(request: Request, db=Depends(get_db)):
    """Distinct actors that appear in the audit trail (for the filter dropdown)."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.audit.view")
    rows = await db.dispatch_audit.aggregate([
        {"$group": {"_id": "$actor_id", "name": {"$last": "$actor_name"},
                    "role": {"$last": "$actor_role"}}},
        {"$sort": {"name": 1}},
    ]).to_list(500)
    return [{"actor_id": r["_id"], "name": r.get("name"), "role": r.get("role")}
            for r in rows if r.get("_id")]


# =====================================================================
#  DASHBOARD  (aggregates)
# =====================================================================
@router.get("/dashboard/stats")
async def dashboard_stats(request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.dashboard.view")
    today = dhaka_today_iso()
    base = {"date": today}
    stats = {
        "today_total": await db.dispatch_schedules.count_documents(base),
        "confirmed": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Confirmed"}),
        "pending": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Pending"}),
        "no_response": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "No Response"}),
        "declined": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Declined"}),
        "not_confirmed": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Not Confirmed"}),
        "late": 0,
        "absent": 0,
        "checked_in": await db.dispatch_schedules.count_documents({**base, "shift_status": "Clocked In"}),
        "checked_out": await db.dispatch_schedules.count_documents({**base, "shift_status": "Clocked Out"}),
        "clients": await db.dispatch_clients.count_documents({"status": "active"}),
        "vendors": await db.dispatch_vendors.count_documents({"status": "active"}),
        "officers": await db.dispatch_officers.count_documents({"status": "active"}),
        "post_sites": await db.dispatch_post_sites.count_documents({"status": "active"}),
    }
    # Open posts (required - assigned today)
    posts = await db.dispatch_post_sites.find({"status": "active"}).to_list(1000)
    open_positions = 0
    for p in posts:
        assigned = await db.dispatch_schedules.count_documents({
            "post_site_id": str(p["_id"]), "date": today,
        })
        # Post sites no longer carry required_officers — count as 1 slot / site.
        if assigned < 1:
            open_positions += 1
    stats["open_positions"] = open_positions
    return stats



# =====================================================================
#  REPORTS
# =====================================================================
def _validate_date_range(date_from: str | None, date_to: str | None):
    """Enforce 3-month cap on report queries. Returns (from, to) strings."""
    today = dhaka_today()
    if not date_to:
        date_to = today.isoformat()
    if not date_from:
        date_from = (today - timedelta(days=30)).isoformat()
    try:
        d_from = datetime.fromisoformat(date_from).date()
        d_to = datetime.fromisoformat(date_to).date()
    except Exception:
        raise HTTPException(400, "Invalid date format, expected YYYY-MM-DD")
    if d_to < d_from:
        raise HTTPException(400, "date_to must be on or after date_from")
    if (d_to - d_from).days > 92:
        raise HTTPException(400, "Report date range cannot exceed 3 months (92 days).")
    return date_from, date_to


async def _resolve_names(db, ids: set[str], coll: str, key: str = "name") -> dict[str, str]:
    if not ids:
        return {}
    obj_ids = []
    for i in ids:
        try:
            obj_ids.append(ObjectId(i))
        except Exception:
            pass
    docs = await db[coll].find({"_id": {"$in": obj_ids}}, {key: 1, "post_pin": 1}).to_list(len(obj_ids) or 1)
    out = {}
    for d in docs:
        out[str(d["_id"])] = d.get(key) or d.get("post_pin") or "—"
    return out


@router.get("/reports/schedules")
async def report_schedules(
    request: Request, db=Depends(get_db),
    officer_id: str = None, vendor_id: str = None, client_id: str = None,
    post_site_id: str = None, post_pin: str = None,
    date_from: str = None, date_to: str = None,
    shift_type: str = None, confirmation_status: str = None, shift_status: str = None,
    q: str = None,
    limit: int = 50,
):
    """Latest-N raw dispatch records for the report page (default 50)."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    date_from, date_to = _validate_date_range(date_from, date_to)
    limit = min(max(limit, 1), 1000)

    q_str = (q or "").strip()
    query = {"date": {"$gte": date_from, "$lte": date_to}}
    if officer_id: query["officer_id"] = officer_id
    if vendor_id: query["vendor_id"] = vendor_id
    if client_id: query["client_id"] = client_id
    if post_site_id: query["post_site_id"] = post_site_id
    if shift_type: query["shift_type"] = shift_type
    if confirmation_status: query["confirmation_status"] = confirmation_status
    if shift_status: query["shift_status"] = shift_status
    if post_pin:
        posts = await db.dispatch_post_sites.find(
            {"post_pin": {"$regex": post_pin, "$options": "i"}}, {"_id": 1}
        ).to_list(500)
        pids = [str(p["_id"]) for p in posts]
        query["post_site_id"] = {"$in": pids} if pids else "__none__"

    if q_str:
        # Free-text search across officer/client/vendor names and post_site name/pin
        rx = {"$regex": q_str, "$options": "i"}
        officer_matches = await db.dispatch_officers.find({"$or": [{"name": rx}, {"email": rx}, {"phone": rx}]}, {"_id": 1}).to_list(500)
        client_matches = await db.dispatch_clients.find({"$or": [{"name": rx}, {"code": rx}]}, {"_id": 1}).to_list(500)
        vendor_matches = await db.dispatch_vendors.find({"$or": [{"name": rx}, {"code": rx}]}, {"_id": 1}).to_list(500)
        post_matches = await db.dispatch_post_sites.find({"$or": [{"name": rx}, {"post_pin": rx}, {"address": rx}]}, {"_id": 1}).to_list(500)
        or_clauses = []
        if officer_matches: or_clauses.append({"officer_id": {"$in": [str(x["_id"]) for x in officer_matches]}})
        if client_matches: or_clauses.append({"client_id": {"$in": [str(x["_id"]) for x in client_matches]}})
        if vendor_matches: or_clauses.append({"vendor_id": {"$in": [str(x["_id"]) for x in vendor_matches]}})
        if post_matches: or_clauses.append({"post_site_id": {"$in": [str(x["_id"]) for x in post_matches]}})
        if not or_clauses:
            return {"items": [], "date_from": date_from, "date_to": date_to, "count": 0}
        query["$or"] = or_clauses

    docs = await db.dispatch_schedules.find(query).sort([("date", -1), ("start_time", -1)]).limit(limit).to_list(limit)

    officer_ids = {d.get("officer_id") for d in docs if d.get("officer_id")}
    vendor_ids = {d.get("vendor_id") for d in docs if d.get("vendor_id")}
    client_ids = {d.get("client_id") for d in docs if d.get("client_id")}
    post_ids = {d.get("post_site_id") for d in docs if d.get("post_site_id")}

    officers = await _resolve_names(db, officer_ids, "dispatch_officers")
    vendors = await _resolve_names(db, vendor_ids, "dispatch_vendors")
    vendor_codes = await _resolve_vendor_codes(db, vendor_ids)
    clients = await _resolve_names(db, client_ids, "dispatch_clients")
    post_docs = await db.dispatch_post_sites.find(
        {"_id": {"$in": [ObjectId(i) for i in post_ids if ObjectId.is_valid(i)]}},
        {"name": 1, "post_pin": 1}
    ).to_list(len(post_ids) or 1)
    posts_map = {str(p["_id"]): p for p in post_docs}

    fin = has_permission(user, "dispatch.financial.view")
    out = []
    for d in docs:
        row = strip_financial(_doc_out(d), user)
        row["officer_name"] = officers.get(d.get("officer_id", ""))
        row["vendor_name"] = vendors.get(d.get("vendor_id", ""))
        row["vendor_code"] = vendor_codes.get(d.get("vendor_id", ""))
        row["client_name"] = clients.get(d.get("client_id", ""))
        p = posts_map.get(d.get("post_site_id", ""), {})
        row["post_site_name"] = p.get("name")
        row["post_pin"] = p.get("post_pin")
        row["post_pin_display"] = _format_pin(row.get("vendor_code"), row.get("post_pin"))
        # Paid/completed hours + payout are computed here so the row-level
        # numbers match the aggregate reports (Clocked In counts as complete).
        h = d.get("duty_hours") or 0
        is_complete = d.get("shift_status") in COMPLETED_STATUSES
        paid_hours = h if is_complete else 0
        row["completed_hours"] = round(paid_hours, 2)
        if fin:
            b = paid_hours * (d.get("billing_rate") or 0)
            c = paid_hours * (d.get("duty_rate") or 0)
            row["billing_amount"] = round(b, 2)
            row["cost_amount"] = round(c, 2)
            row["margin"] = round(b - c, 2)
        out.append(row)

    return {"items": out, "date_from": date_from, "date_to": date_to, "count": len(out)}


async def _resolve_search_ids(db, group_field: str, q: str):
    """Resolve a free-text search to a list of entity IDs for pre-aggregation
    filtering. Returns None when q is empty, an empty list when nothing matches
    (caller should short-circuit).
    """
    if not q:
        return None
    q = q.strip()
    if not q:
        return None
    coll_map = {
        "officer_id": ("dispatch_officers", ["name", "email", "phone"]),
        "client_id": ("dispatch_clients", ["name", "code"]),
        "vendor_id": ("dispatch_vendors", ["name", "code"]),
        "post_site_id": ("dispatch_post_sites", ["name", "post_pin", "address"]),
    }
    coll, fields = coll_map.get(group_field, (None, []))
    if not coll:
        return None
    or_terms = [{f: {"$regex": q, "$options": "i"}} for f in fields]
    docs = await db[coll].find({"$or": or_terms}, {"_id": 1}).to_list(1000)
    return [str(d["_id"]) for d in docs]


async def _aggregate_by(db, group_field: str, date_from: str, date_to: str,
                        include_financial: bool, search_ids=None):
    """Aggregation helper for by-officer / by-post / by-client / by-vendor.

    Hours, billing_amount and cost_amount are summed **only for shifts whose
    shift_status is Clocked In / Clocked Out** so reports reflect actual
    worked/paid hours (a Clocked In shift already counts as complete).
    """
    match = {"date": {"$gte": date_from, "$lte": date_to}}
    if search_ids is not None:
        match[group_field] = {"$in": search_ids}
    completed_cond = {"$in": ["$shift_status", COMPLETED_STATUSES]}
    pipeline = [
        {"$match": match},
        {"$group": {
            "_id": f"${group_field}",
            "total_shifts": {"$sum": 1},
            "completed": {"$sum": {"$cond": [completed_cond, 1, 0]}},
            "absent": {"$sum": 0},
            "late": {"$sum": 0},
            "early_checkout": {"$sum": 0},
            "cancelled": {"$sum": 0},
            "confirmed": {"$sum": {"$cond": [{"$eq": ["$confirmation_status", "Confirmed"]}, 1, 0]}},
            "total_hours": {"$sum": {"$cond": [completed_cond, {"$ifNull": ["$duty_hours", 0]}, 0]}},
            **({"billing_amount": {"$sum": {"$cond": [completed_cond,
                    {"$multiply": [{"$ifNull": ["$duty_hours", 0]}, {"$ifNull": ["$billing_rate", 0]}]}, 0]}},
                "cost_amount": {"$sum": {"$cond": [completed_cond,
                    {"$multiply": [{"$ifNull": ["$duty_hours", 0]}, {"$ifNull": ["$duty_rate", 0]}]}, 0]}}}
               if include_financial else {}),
        }},
        {"$sort": {"total_shifts": -1}},
    ]
    return await db.dispatch_schedules.aggregate(pipeline).to_list(1000)


@router.get("/reports/by-officer")
async def report_by_officer(request: Request, db=Depends(get_db),
                            date_from: str = None, date_to: str = None,
                            q: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    date_from, date_to = _validate_date_range(date_from, date_to)
    fin = has_permission(user, "dispatch.financial.view")
    search_ids = await _resolve_search_ids(db, "officer_id", q)
    if search_ids == []:
        return {"items": [], "date_from": date_from, "date_to": date_to, "count": 0}
    rows = await _aggregate_by(db, "officer_id", date_from, date_to, fin, search_ids)
    ids = {r["_id"] for r in rows if r["_id"]}
    officers = await _resolve_names(db, ids, "dispatch_officers")
    out = []
    for r in rows:
        oid = r.pop("_id")
        r["officer_id"] = oid
        r["officer_name"] = officers.get(oid, "—")
        r["total_hours"] = round(r.get("total_hours", 0), 2)
        r["attendance_pct"] = round(100.0 * r["completed"] / r["total_shifts"], 1) if r["total_shifts"] else 0
        if fin:
            r["billing_amount"] = round(r.get("billing_amount", 0), 2)
            r["cost_amount"] = round(r.get("cost_amount", 0), 2)
            r["margin"] = round(r["billing_amount"] - r["cost_amount"], 2)
        out.append(r)
    return {"items": out, "date_from": date_from, "date_to": date_to, "count": len(out)}


@router.get("/reports/by-post-site")
async def report_by_post_site(request: Request, db=Depends(get_db),
                              date_from: str = None, date_to: str = None,
                              q: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    date_from, date_to = _validate_date_range(date_from, date_to)
    fin = has_permission(user, "dispatch.financial.view")
    search_ids = await _resolve_search_ids(db, "post_site_id", q)
    if search_ids == []:
        return {"items": [], "date_from": date_from, "date_to": date_to, "count": 0}
    rows = await _aggregate_by(db, "post_site_id", date_from, date_to, fin, search_ids)
    ids = {r["_id"] for r in rows if r["_id"]}
    obj_ids = [ObjectId(i) for i in ids if ObjectId.is_valid(i)]
    post_docs = await db.dispatch_post_sites.find(
        {"_id": {"$in": obj_ids}}, {"name": 1, "post_pin": 1, "vendor_id": 1}
    ).to_list(len(obj_ids) or 1)
    posts_map = {str(p["_id"]): p for p in post_docs}
    vendor_codes = await _resolve_vendor_codes(db, {p.get("vendor_id") for p in post_docs})
    out = []
    for r in rows:
        pid = r.pop("_id")
        p = posts_map.get(pid, {})
        r["post_site_id"] = pid
        r["post_site_name"] = p.get("name", "—")
        r["post_pin"] = p.get("post_pin", "—")
        r["vendor_code"] = vendor_codes.get(p.get("vendor_id", ""))
        r["post_pin_display"] = _format_pin(r.get("vendor_code"), p.get("post_pin"))
        r["total_hours"] = round(r.get("total_hours", 0), 2)
        r["coverage_pct"] = round(100.0 * r["completed"] / r["total_shifts"], 1) if r["total_shifts"] else 0
        if fin:
            r["billing_amount"] = round(r.get("billing_amount", 0), 2)
            r["cost_amount"] = round(r.get("cost_amount", 0), 2)
            r["margin"] = round(r["billing_amount"] - r["cost_amount"], 2)
        out.append(r)
    return {"items": out, "date_from": date_from, "date_to": date_to, "count": len(out)}


@router.get("/reports/by-client")
async def report_by_client(request: Request, db=Depends(get_db),
                           date_from: str = None, date_to: str = None,
                           q: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    date_from, date_to = _validate_date_range(date_from, date_to)
    fin = has_permission(user, "dispatch.financial.view")
    search_ids = await _resolve_search_ids(db, "client_id", q)
    if search_ids == []:
        return {"items": [], "date_from": date_from, "date_to": date_to, "count": 0}
    rows = await _aggregate_by(db, "client_id", date_from, date_to, fin, search_ids)
    ids = {r["_id"] for r in rows if r["_id"]}
    clients = await _resolve_names(db, ids, "dispatch_clients")
    out = []
    for r in rows:
        cid = r.pop("_id")
        r["client_id"] = cid
        r["client_name"] = clients.get(cid, "—")
        r["total_hours"] = round(r.get("total_hours", 0), 2)
        if fin:
            r["billing_amount"] = round(r.get("billing_amount", 0), 2)
            r["cost_amount"] = round(r.get("cost_amount", 0), 2)
            r["margin"] = round(r["billing_amount"] - r["cost_amount"], 2)
        out.append(r)
    return {"items": out, "date_from": date_from, "date_to": date_to, "count": len(out)}


@router.get("/reports/by-vendor")
async def report_by_vendor(request: Request, db=Depends(get_db),
                           date_from: str = None, date_to: str = None,
                           q: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    date_from, date_to = _validate_date_range(date_from, date_to)
    fin = has_permission(user, "dispatch.financial.view")
    search_ids = await _resolve_search_ids(db, "vendor_id", q)
    if search_ids == []:
        return {"items": [], "date_from": date_from, "date_to": date_to, "count": 0}
    rows = await _aggregate_by(db, "vendor_id", date_from, date_to, fin, search_ids)
    ids = {r["_id"] for r in rows if r["_id"]}
    vendors = await _resolve_names(db, ids, "dispatch_vendors")
    out = []
    for r in rows:
        vid = r.pop("_id")
        r["vendor_id"] = vid
        r["vendor_name"] = vendors.get(vid, "—")
        r["total_hours"] = round(r.get("total_hours", 0), 2)
        if fin:
            r["billing_amount"] = round(r.get("billing_amount", 0), 2)
            r["cost_amount"] = round(r.get("cost_amount", 0), 2)
            r["margin"] = round(r["billing_amount"] - r["cost_amount"], 2)
        out.append(r)
    return {"items": out, "date_from": date_from, "date_to": date_to, "count": len(out)}





@router.get("/advance-salary")
async def get_advance_salary(
    request: Request,
    db=Depends(get_db),
    officer_id: str = None,
    client_id: str = None,
    date_from: str = None,
    date_to: str = None,
):
    """Advance-salary ledger for one officer + client.

    'advance' entries increase the outstanding balance; 'repayment' entries
    reduce it. The balance carries across payslips (per officer + client).
    """
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.financial.view")

    if not officer_id:
        raise HTTPException(400, "officer_id is required")

    q = {"officer_id": officer_id}
    if client_id:
        q["client_id"] = client_id

    docs = await db.dispatch_advance_salary.find(q).sort(
        [("entry_date", 1), ("created_at", 1)]
    ).to_list(2000)

    balance = 0.0
    entries = []
    for doc in docs:
        entry = _doc_out(doc)
        amount = float(entry.get("amount") or 0)
        if entry.get("type") == "advance":
            balance += amount
        else:
            balance -= amount
        entry["balance_after"] = round(balance, 2)
        # System repayments created from payslip deductions reduce the balance
        # but are managed from the payslip Deductions editor, so they are hidden
        # from the manual ledger table.
        if doc.get("source") == "payslip_deduction":
            continue
        entries.append(entry)

    def _in_period(d):
        ed = str(d.get("entry_date") or "")
        if date_from and ed < date_from:
            return False
        if date_to and ed > date_to:
            return False
        return True

    # Totals are computed over ALL docs (including hidden system payslip
    # deduction repayments) so that remaining_balance == total_advanced -
    # total_repaid always holds, even though the system rows are not listed.
    total_advanced = round(
        sum(float(x.get("amount") or 0) for x in docs if x.get("type") == "advance"), 2)
    total_repaid = round(
        sum(float(x.get("amount") or 0) for x in docs if x.get("type") == "repayment"), 2)
    period_taken = round(
        sum(float(x.get("amount") or 0) for x in docs
            if x.get("type") == "advance" and _in_period(x)), 2)
    period_repaid = round(
        sum(float(x.get("amount") or 0) for x in docs
            if x.get("type") == "repayment" and _in_period(x)), 2)

    return {
        "officer_id": officer_id,
        "client_id": client_id,
        "entries": entries,
        "total_advanced": total_advanced,
        "total_repaid": total_repaid,
        "remaining_balance": round(balance, 2),
        "period_taken": period_taken,
        "period_repaid": period_repaid,
    }


@router.post("/advance-salary")
async def create_advance_salary_entry(request: Request, db=Depends(get_db)):
    """Record one advance taken or one repayment with a manual date."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.financial.adjust")

    payload = await request.json()

    officer_id = str(payload.get("officer_id") or "").strip()
    client_id = str(payload.get("client_id") or "").strip() or None
    if not officer_id:
        raise HTTPException(400, "officer_id is required")
    if not client_id:
        raise HTTPException(400, "client_id is required")

    entry_type = str(payload.get("type") or "").strip().lower()
    if entry_type not in ("advance", "repayment"):
        raise HTTPException(400, "type must be 'advance' or 'repayment'")

    entry_date = str(payload.get("entry_date") or "").strip()
    if not entry_date:
        raise HTTPException(400, "entry_date is required")

    note = str(payload.get("note") or "").strip()

    try:
        amount = round(float(payload.get("amount") or 0), 2)
    except (TypeError, ValueError):
        raise HTTPException(400, "amount must be a number")
    if amount <= 0:
        raise HTTPException(400, "amount must be greater than zero")

    existing = await db.dispatch_advance_salary.find(
        {"officer_id": officer_id, "client_id": client_id}
    ).to_list(2000)
    current_balance = 0.0
    for doc in existing:
        amt = float(doc.get("amount") or 0)
        if doc.get("type") == "advance":
            current_balance += amt
        else:
            current_balance -= amt
    current_balance = round(current_balance, 2)

    if entry_type == "repayment" and amount > current_balance + 0.001:
        raise HTTPException(
            400,
            f"Repayment cannot exceed the outstanding advance balance "
            f"of ${current_balance:,.2f}",
        )

    now = _now()
    doc = {
        "officer_id": officer_id,
        "client_id": client_id,
        "type": entry_type,
        "amount": amount,
        "entry_date": entry_date,
        "note": note,
        "created_at": now,
        "created_by": str(user.get("id") or user.get("_id") or ""),
    }
    result = await db.dispatch_advance_salary.insert_one(doc)
    saved = await db.dispatch_advance_salary.find_one({"_id": result.inserted_id})

    new_balance = (
        current_balance + amount if entry_type == "advance"
        else current_balance - amount
    )
    out = _doc_out(saved)
    out["balance_after"] = round(new_balance, 2)
    return out


@router.delete("/advance-salary/{entry_id}")
async def delete_advance_salary_entry(entry_id: str, request: Request, db=Depends(get_db)):
    """Delete one advance/repayment entry, keeping the ledger valid."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.financial.adjust")

    try:
        oid = ObjectId(entry_id)
    except Exception:
        raise HTTPException(400, "Invalid advance entry id")

    doc = await db.dispatch_advance_salary.find_one({"_id": oid})
    if not doc:
        raise HTTPException(404, "Advance entry not found")

    if doc.get("type") == "advance":
        others = await db.dispatch_advance_salary.find({
            "officer_id": doc.get("officer_id"),
            "client_id": doc.get("client_id"),
            "_id": {"$ne": oid},
        }).to_list(2000)
        balance = 0.0
        for x in others:
            amt = float(x.get("amount") or 0)
            balance += amt if x.get("type") == "advance" else -amt
        if balance < -0.001:
            raise HTTPException(
                400,
                "This advance cannot be deleted because repayments depend on it.",
            )

    await db.dispatch_advance_salary.delete_one({"_id": oid})
    return {"ok": True, "id": entry_id}


@router.get("/advance-salary/statement")
async def advance_salary_statement(
    request: Request,
    db=Depends(get_db),
    officer_id: str = None,
    client_id: str = None,
):
    """Downloadable PDF: an officer's full advance history (per client if a
    client_id is given) with every advance, repayment and running balance."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.financial.view")

    if not officer_id:
        raise HTTPException(400, "officer_id is required")

    q = {"officer_id": officer_id}
    if client_id:
        q["client_id"] = client_id

    docs = await db.dispatch_advance_salary.find(q).sort(
        [("entry_date", 1), ("created_at", 1)]
    ).to_list(2000)

    balance = 0.0
    entries = []
    total_advanced = 0.0
    total_repaid = 0.0
    for d in docs:
        amount = float(d.get("amount") or 0)
        if d.get("type") == "advance":
            balance += amount
            total_advanced += amount
        else:
            balance -= amount
            total_repaid += amount
        entries.append({
            "entry_date": d.get("entry_date"),
            "type": d.get("type"),
            "note": d.get("note"),
            "amount": amount,
            "balance_after": round(balance, 2),
        })

    officer = await db.dispatch_officers.find_one({"_id": _oid(officer_id)}) if ObjectId.is_valid(officer_id) else None
    officer_name = (officer or {}).get("name") or officer_id
    client_name = None
    if client_id and ObjectId.is_valid(client_id):
        client = await db.dispatch_clients.find_one({"_id": ObjectId(client_id)})
        client_name = (client or {}).get("name")

    from utils.dispatch_reports import build_advance_statement_pdf
    body = build_advance_statement_pdf(
        officer_name=officer_name,
        client_name=client_name,
        entries=entries,
        total_advanced=round(total_advanced, 2),
        total_repaid=round(total_repaid, 2),
        remaining_balance=round(balance, 2),
    )
    fname = f"advance-statement-{officer_name}.pdf".replace(" ", "-")
    return StreamingResponse(
        io.BytesIO(body), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/payslip-adjustment")
async def get_payslip_adjustment(
    request: Request,
    db=Depends(get_db),
    officer_id: str = None,
    client_id: str = None,
    date_from: str = None,
    date_to: str = None,
):
    """Return the saved financial adjustments for one officer/client payslip."""

    user = await get_current_user(request, db)
    require_permission(user, "dispatch.financial.view")

    if not officer_id:
        raise HTTPException(400, "officer_id is required")
    if not client_id:
        raise HTTPException(400, "client_id is required")
    if not date_from or not date_to:
        raise HTTPException(400, "date_from and date_to are required")

    doc = await db.dispatch_payslip_adjustments.find_one({
        "officer_id": officer_id,
        "client_id": client_id,
        "date_from": date_from,
        "date_to": date_to,
    })

    if not doc:
        return {
            "officer_id": officer_id,
            "client_id": client_id,
            "date_from": date_from,
            "date_to": date_to,
            "extra_payments": [],
            "deductions": [],
        }

    out = _doc_out(doc)
    if not isinstance(out.get("extra_payments"), list):
        out["extra_payments"] = []
    if not isinstance(out.get("deductions"), list):
        out["deductions"] = []
    return out


@router.put("/payslip-adjustment")
async def save_payslip_adjustment(
    request: Request,
    db=Depends(get_db),
    officer_id: str = None,
    client_id: str = None,
    date_from: str = None,
    date_to: str = None,
):
    """Create/update Advance, Addition and Deduction for an officer payslip."""

    user = await get_current_user(request, db)
    require_permission(user, "dispatch.financial.adjust")

    if not officer_id:
        raise HTTPException(400, "officer_id is required")
    if not client_id:
        raise HTTPException(400, "client_id is required")
    if not date_from or not date_to:
        raise HTTPException(400, "date_from and date_to are required")

    payload = await request.json()

    raw = payload.get("extra_payments") or []
    if not isinstance(raw, list):
        raise HTTPException(400, "extra_payments must be a list")

    extra_payments = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        try:
            amount = round(float(r.get("amount") or 0), 2)
        except (TypeError, ValueError):
            raise HTTPException(400, "amount must be a number")
        if amount < 0:
            raise HTTPException(400, "amount cannot be negative")
        purpose = str(r.get("purpose") or "").strip()
        date_v = str(r.get("date") or "").strip()
        if amount == 0 and not purpose and not date_v:
            continue
        extra_payments.append({"date": date_v, "purpose": purpose, "amount": amount})

    # ---- Manual deductions (plain line items that reduce net pay) -----------
    # These are fully independent from the advance ledger. They only reduce the
    # payslip net pay and appear as line items on the PDF (styled like extra
    # payments). Advances have zero effect on net pay.
    raw_ded = payload.get("deductions") or []
    if not isinstance(raw_ded, list):
        raise HTTPException(400, "deductions must be a list")

    deductions = []
    for r in raw_ded:
        if not isinstance(r, dict):
            continue
        try:
            amount = round(float(r.get("amount") or 0), 2)
        except (TypeError, ValueError):
            raise HTTPException(400, "deduction amount must be a number")
        if amount < 0:
            raise HTTPException(400, "deduction amount cannot be negative")
        purpose = str(r.get("purpose") or "").strip()
        date_v = str(r.get("date") or "").strip()
        if amount == 0 and not purpose and not date_v:
            continue
        deductions.append({"date": date_v, "purpose": purpose, "amount": amount})

    now = _now()

    key = {
        "officer_id": officer_id,
        "client_id": client_id,
        "date_from": date_from,
        "date_to": date_to,
    }

    update = {
        "$set": {
            **key,
            "extra_payments": extra_payments,
            "deductions": deductions,
            "updated_at": now,
            "updated_by": str(user.get("id") or user.get("_id") or ""),
        },
        "$setOnInsert": {
            "created_at": now,
            "created_by": str(user.get("id") or user.get("_id") or ""),
        },
        "$unset": {"addition": "", "deduction": ""},
    }

    await db.dispatch_payslip_adjustments.update_one(
        key,
        update,
        upsert=True,
    )

    # Clean up any legacy system repayments that older payslip-deduction logic
    # may have posted to the advance ledger. Deductions no longer touch the
    # ledger, so the advance statement stays fully independent.
    await db.dispatch_advance_salary.delete_many({
        "officer_id": officer_id,
        "client_id": client_id,
        "source": "payslip_deduction",
    })

    saved = await db.dispatch_payslip_adjustments.find_one(key)

    return _doc_out(saved)


@router.get("/reports/entity-detail")
async def report_entity_detail(
    request: Request, db=Depends(get_db),
    entity_type: str = None, entity_id: str = None,
    date_from: str = None, date_to: str = None,
    client_id: str = None,
):
    """Full per-entity report: all schedules for one officer/client/vendor/post_site,
    day-by-day with actual check-in/out, remarks, hours, rates, billing.
    When entity_type='officer' and client_id is provided, results are further
    filtered so the report shows one officer against one client (matches the
    per-client payslip layout).
    Financial fields still respect dispatch.financial.view.
    """
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    if entity_type not in ("officer", "client", "vendor", "post_site"):
        raise HTTPException(400, "entity_type must be officer|client|vendor|post_site")
    if not entity_id:
        raise HTTPException(400, "entity_id is required")
    date_from, date_to = _validate_date_range(date_from, date_to)
    fin = has_permission(user, "dispatch.financial.view")

    key = {"officer": "officer_id", "client": "client_id",
           "vendor": "vendor_id", "post_site": "post_site_id"}[entity_type]
    q = {key: entity_id, "date": {"$gte": date_from, "$lte": date_to}}
    if client_id and entity_type == "officer":
        q["client_id"] = client_id
    docs = await db.dispatch_schedules.find(q).sort([("date", 1), ("start_time", 1)]).to_list(2000)

    # Enrich names
    off_ids = {d.get("officer_id") for d in docs if d.get("officer_id")}
    ven_ids = {d.get("vendor_id") for d in docs if d.get("vendor_id")}
    cli_ids = {d.get("client_id") for d in docs if d.get("client_id")}
    post_ids = {d.get("post_site_id") for d in docs if d.get("post_site_id")}
    officers = await _resolve_names(db, off_ids, "dispatch_officers")
    vendors = await _resolve_names(db, ven_ids, "dispatch_vendors")
    vendor_codes = await _resolve_vendor_codes(db, ven_ids)
    clients = await _resolve_names(db, cli_ids, "dispatch_clients")

    # Full post-site records (we need city + address for the payslip layout)
    posts_map = {}
    if post_ids:
        obj_ids = [ObjectId(i) for i in post_ids if ObjectId.is_valid(i)]
        pdocs = await db.dispatch_post_sites.find(
            {"_id": {"$in": obj_ids}}, {"name": 1, "post_pin": 1, "address": 1, "city": 1}
        ).to_list(len(obj_ids))
        posts_map = {str(p["_id"]): p for p in pdocs}

    # List of unique clients this officer worked for in the range — used by the
    # frontend to render a client-filter dropdown.
    clients_available = []
    if entity_type == "officer" and cli_ids:
        cobjs = [ObjectId(c) for c in cli_ids if ObjectId.is_valid(c)]
        cdocs = await db.dispatch_clients.find(
            {"_id": {"$in": cobjs}}, {"name": 1, "logo_path": 1, "address": 1, "city": 1}
        ).to_list(len(cobjs))
        clients_available = [
            {
                "id": str(c["_id"]),
                "name": c.get("name"),
                "logo_url": to_public_url(c.get("logo_path")) if c.get("logo_path") else None,
            }
            for c in cdocs
        ]

    items = []
    total_duty_hours = 0.0; total_actual_hours = 0.0
    total_bill = 0.0; total_cost = 0.0
    completed = absent = late = early = cancelled = 0
    for d in docs:
        row = strip_financial(_doc_out(d), user)
        row["officer_name"] = officers.get(d.get("officer_id", ""))
        row["vendor_name"] = vendors.get(d.get("vendor_id", ""))
        row["vendor_code"] = vendor_codes.get(d.get("vendor_id", ""))
        row["client_name"] = clients.get(d.get("client_id", ""))
        p = posts_map.get(d.get("post_site_id", ""), {})
        row["post_site_name"] = p.get("name")
        row["post_pin"] = p.get("post_pin")
        row["post_pin_display"] = _format_pin(row.get("vendor_code"), row.get("post_pin"))
        row["city"] = p.get("city")
        row["post_site_address"] = p.get("address")
        h = d.get("duty_hours") or 0
        actual_h = d.get("actual_duty_hours") or 0
        is_complete = d.get("shift_status") in COMPLETED_STATUSES
        # Once an officer is Clocked In (or Clocked Out) the shift counts
        # toward paid/billed hours & amounts.
        paid_hours = h if is_complete else 0
        rate = d.get("duty_rate") or 0
        if fin:
            b = paid_hours * (d.get("billing_rate") or 0)
            c = paid_hours * rate
            row["billing_amount"] = round(b, 2)
            row["cost_amount"] = round(c, 2)
            row["margin"] = round(b - c, 2)
            row["hourly_rate"] = rate
            row["total"] = round(c, 2)  # payslip Total column = paid_hours × rate
            total_bill += b; total_cost += c
        # Surface a per-row completed hours field so the UI can show it.
        row["completed_hours"] = round(paid_hours, 2)
        row["actual_hours"] = round(actual_h, 2)
        items.append(row)
        total_duty_hours += paid_hours
        total_actual_hours += actual_h if is_complete else 0
        if is_complete:
            completed += 1

    # Entity header
    header = {}
    coll_map = {"officer": "dispatch_officers", "client": "dispatch_clients",
                "vendor": "dispatch_vendors", "post_site": "dispatch_post_sites"}
    entity = await db[coll_map[entity_type]].find_one({"_id": _oid(entity_id)})
    if entity:
        header = _doc_out(entity)
        # Resolve logo_path → public URL for whichever entity this is
        if header.get("logo_path"):
            header["logo_url"] = to_public_url(header["logo_path"])

    # If entity is an officer and a client_id filter is active (or every shift
    # in the range shares a single client), surface that client's info for the
    # payslip-style header the UI renders.
    client_header = None
    if entity_type == "officer":
        pick_client_id = client_id
        if not pick_client_id and len(clients_available) == 1:
            pick_client_id = clients_available[0]["id"]
        if pick_client_id and ObjectId.is_valid(pick_client_id):
            c = await db.dispatch_clients.find_one({"_id": ObjectId(pick_client_id)})
            if c:
                cdoc = _doc_out(c)
                client_header = {
                    "id": str(c["_id"]),
                    "name": cdoc.get("name"),
                    "logo_url": to_public_url(cdoc["logo_path"]) if cdoc.get("logo_path") else None,
                    "address": cdoc.get("address"),
                    "city": cdoc.get("city"),
                    "phone": cdoc.get("contact_number"),
                    "email": cdoc.get("email"),
                    "website": cdoc.get("website"),
                }

    # ---- Advance salary + payslip adjustments (officer payslip only) ----
    advance_summary = None
    extra_payments_list = []
    deductions_list = []

    if entity_type == "officer" and fin:
        eff_client_id = client_id
        if not eff_client_id and len(clients_available) == 1:
            eff_client_id = clients_available[0]["id"]

        adv_q = {"officer_id": entity_id}
        if eff_client_id:
            adv_q["client_id"] = eff_client_id
        adv_docs = await db.dispatch_advance_salary.find(adv_q).to_list(2000)

        total_advanced = total_repaid = 0.0
        period_taken = period_repaid = 0.0
        for d in adv_docs:
            amt = float(d.get("amount") or 0)
            ed = str(d.get("entry_date") or "")
            in_period = (not date_from or ed >= date_from) and (not date_to or ed <= date_to)
            if d.get("type") == "advance":
                total_advanced += amt
                if in_period:
                    period_taken += amt
            else:
                total_repaid += amt
                if in_period:
                    period_repaid += amt

        advance_summary = {
            "remaining_balance": round(total_advanced - total_repaid, 2),
            "total_advanced": round(total_advanced, 2),
            "total_repaid": round(total_repaid, 2),
            "period_taken": round(period_taken, 2),
            "period_repaid": round(period_repaid, 2),
        }

        # NOTE: Extra payments & deductions are NO LONGER pre-filled from a
        # persisted adjustment doc. They are transient in the payslip editor and
        # only persist when a payslip PDF record is generated. Reopening a saved
        # record pre-fills them via GET /payslip-records/{id} on the frontend.

    summary = {
        "total_shifts": len(items),
        "completed": completed, "absent": absent, "late": late,
        "early_checkout": early, "cancelled": cancelled,
        "total_hours": round(total_duty_hours, 2),
        "total_duty_hours": round(total_duty_hours, 2),
        "total_actual_hours": round(total_actual_hours, 2),
    }
    if fin:
        summary["billing_amount"] = round(total_bill, 2)
        summary["cost_amount"] = round(total_cost, 2)
        summary["margin"] = round(total_bill - total_cost, 2)
        summary["total_amount"] = round(total_cost, 2)

    return {
        "entity_type": entity_type, "entity_id": entity_id,
        "entity": header,
        "client_info": client_header,
        "clients_available": clients_available,
        "client_filter_id": client_id,
        "date_from": date_from, "date_to": date_to,
        "summary": summary,
        "advance": advance_summary,
        "advance_remaining_balance": (
            advance_summary.get("remaining_balance", 0) if advance_summary else 0
        ),
        "advance_taken_period": (
            advance_summary.get("period_taken", 0) if advance_summary else 0
        ),
        "advance_repaid_period": (
            advance_summary.get("period_repaid", 0) if advance_summary else 0
        ),
        "extra_payments": extra_payments_list,
        "extra_payments_total": round(
            sum(float(r.get("amount") or 0) for r in extra_payments_list), 2
        ),
        "deductions": deductions_list,
        "deductions_total": round(
            sum(float(r.get("amount") or 0) for r in deductions_list), 2
        ),
        "net_payment": (
            round(
                total_cost
                + sum(float(r.get("amount") or 0) for r in extra_payments_list)
                - sum(float(r.get("amount") or 0) for r in deductions_list),
                2,
            )
            if fin else None
        ),

        "items": items,
        "count": len(items),
    }


@router.get("/reports/export/entity-detail")
async def export_entity_detail(
    request: Request, db=Depends(get_db),
    entity_type: str = None, entity_id: str = None,
    date_from: str = None, date_to: str = None,
    client_id: str = None,
    format: str = "csv",
    columns: str = None,  # comma-separated column keys
    template: str = None,  # 'payslip' to use the branded per-officer layout
):
    """CSV / PDF export of the entity-detail report with user-selected columns.

    When entity_type='officer' and template='payslip' (or format='pdf' with a
    single client selected) we render the branded payslip PDF matching the
    OfficeFlow reports mockup.
    """
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.export")
    fmt = format.lower()
    if fmt not in ("csv", "pdf", "xlsx"):
        raise HTTPException(400, "format must be 'csv', 'pdf' or 'xlsx'")

    data = await report_entity_detail(request, db,
        entity_type=entity_type, entity_id=entity_id,
        date_from=date_from, date_to=date_to,
        client_id=client_id)

    fin = has_permission(user, "dispatch.financial.view")

    # -- Branded per-officer payslip PDF --------------------------------------
    use_payslip = (
        entity_type == "officer"
        and fmt == "pdf"
        and (template == "payslip" or data.get("client_info") is not None)
    )
    if use_payslip:
        from utils.dispatch_reports import build_officer_payslip_pdf
        client_info = data.get("client_info") or {}
        officer_name = (data.get("entity") or {}).get("name") or entity_id

        eff_client_id = client_id or (client_info.get("id") if client_info else None)

        extra_payment_rows = data.get("extra_payments") or []
        deduction_rows = data.get("deductions") or []
        advance_entries = []
        remaining_balance = 0.0
        period_taken = 0.0
        period_repaid = 0.0

        if fin and eff_client_id:
            adv_docs = await db.dispatch_advance_salary.find({
                "officer_id": entity_id,
                "client_id": eff_client_id,
            }).sort([("entry_date", 1), ("created_at", 1)]).to_list(2000)

            total_adv = total_rep = 0.0
            for d in adv_docs:
                amt = float(d.get("amount") or 0)
                ed = str(d.get("entry_date") or "")
                in_period = (ed >= data["date_from"]) and (ed <= data["date_to"])
                if d.get("type") == "advance":
                    total_adv += amt
                    if in_period:
                        period_taken += amt
                        advance_entries.append({"date": ed, "amount": amt})
                else:
                    total_rep += amt
                    if in_period:
                        period_repaid += amt
            remaining_balance = round(total_adv - total_rep, 2)

        body = build_officer_payslip_pdf(
            client_name=client_info.get("name"),
            client_logo_url=client_info.get("logo_url"),
            officer_name=officer_name,
            date_from=data["date_from"],
            date_to=data["date_to"],
            rows=data["items"],
            show_financial=fin,
            extra_payment_rows=extra_payment_rows,
            deduction_rows=deduction_rows,
            advance_taken=round(period_taken, 2),
            advance_repaid=round(period_repaid, 2),
            remaining_balance=remaining_balance,
            advance_entries=advance_entries,
            client_address=client_info.get("address"),
            client_phone=client_info.get("phone"),
            client_email=client_info.get("email"),
            client_website=client_info.get("website"),
            officer_ssn=(data.get("entity") or {}).get("social_security_code"),
        )
        return StreamingResponse(io.BytesIO(body), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="payslip-{officer_name}-{data["date_from"]}-{data["date_to"]}.pdf"'})

    ALL_COLS = [
        ("Date", "date"), ("Shift", "shift_type"),
        ("Start", "start_time"), ("End", "end_time"),
        ("Actual Check-In", "actual_check_in"), ("Actual Check-Out", "actual_check_out"),
        ("Duty Hours", "duty_hours"), ("Actual Hours", "actual_hours"),
        ("Officer", "officer_name"), ("Post Pin", "post_pin_display"), ("Post Site", "post_site_name"),
        ("City", "city"),
        ("Client", "client_name"), ("Vendor", "vendor_name"),
        ("Confirmation", "confirmation_status"), ("Confirmation Method", "confirmation_method"),
        ("Shift Status", "shift_status"), ("Remarks", "remarks"),
        ("Last Modified By", "last_modified_by_name"),
        ("Last Modified Action", "last_modified_action"),
    ]
    if fin:
        ALL_COLS += [("Hourly Rate", "hourly_rate"), ("Total", "total"),
                     ("Duty Rate", "duty_rate"), ("Billing Rate", "billing_rate"),
                     ("Work Order", "work_order_number")]

    if columns:
        # Preserve caller's order (comma-separated); drop unknown/duplicate keys
        seen = set()
        wanted_order = []
        for k in columns.split(","):
            k = k.strip()
            if k and k not in seen:
                seen.add(k); wanted_order.append(k)
        col_map = {key: label for label, key in ALL_COLS}
        cols = [(col_map[k], k) for k in wanted_order if k in col_map]
        if not cols:
            cols = ALL_COLS
    else:
        cols = ALL_COLS

    title = f"{entity_type.title()} Detail — {data['entity'].get('name') or data['entity'].get('post_pin') or entity_id}"
    subtitle = f"{data['date_from']} → {data['date_to']} · {data['count']} shift(s)"
    fname_base = f"dispatch-{entity_type}-{entity_id}-{data['date_from']}-{data['date_to']}"
    if fmt == "csv":
        body = build_csv(data["items"], cols)
        return StreamingResponse(io.BytesIO(body), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname_base}.csv"'})
    if fmt == "xlsx":
        body = build_xlsx(data["items"], cols, title=title, subtitle=subtitle)
        return StreamingResponse(io.BytesIO(body),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname_base}.xlsx"'})
    body = build_pdf(title, subtitle, data["items"], cols)
    return StreamingResponse(io.BytesIO(body), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname_base}.pdf"'})


# ---------- Saved payslip records (generate → save → preview/modify) ----------

def _normalize_payslip_lines(raw):
    """Coerce incoming extra/deduction lines to clean {date, purpose, amount}."""
    out = []
    for r in (raw or []):
        r = r.model_dump() if hasattr(r, "model_dump") else dict(r or {})
        try:
            amount = round(float(r.get("amount") or 0), 2)
        except (TypeError, ValueError):
            amount = 0.0
        if amount < 0:
            raise HTTPException(400, "amount cannot be negative")
        purpose = str(r.get("purpose") or "").strip()
        date_v = str(r.get("date") or "").strip()
        if amount == 0 and not purpose and not date_v:
            continue
        out.append({"date": date_v, "purpose": purpose, "amount": amount})
    return out


async def _build_officer_payslip_bytes(
    request, db, user, officer_id, client_id, date_from, date_to,
    extra_payment_rows, deduction_rows,
):
    """Generate the branded payslip PDF bytes for the given values and return
    (bytes, snapshot) where snapshot has gross / net / officer_name / client_name.
    Advances have zero effect on net; only 'Remaining Advance Balance' is shown."""
    from utils.dispatch_reports import build_officer_payslip_pdf

    fin = has_permission(user, "dispatch.financial.view")
    data = await report_entity_detail(
        request, db, entity_type="officer", entity_id=officer_id,
        date_from=date_from, date_to=date_to, client_id=client_id,
    )
    client_info = data.get("client_info") or {}
    officer_name = (data.get("entity") or {}).get("name") or officer_id
    eff_client_id = client_id or (client_info.get("id") if client_info else None)

    remaining_balance = 0.0
    if fin and eff_client_id:
        adv_docs = await db.dispatch_advance_salary.find({
            "officer_id": officer_id, "client_id": eff_client_id,
        }).to_list(2000)
        total_adv = sum(float(d.get("amount") or 0) for d in adv_docs if d.get("type") == "advance")
        total_rep = sum(float(d.get("amount") or 0) for d in adv_docs if d.get("type") != "advance")
        remaining_balance = round(total_adv - total_rep, 2)

    body = build_officer_payslip_pdf(
        client_name=client_info.get("name"),
        client_logo_url=client_info.get("logo_url"),
        officer_name=officer_name,
        date_from=data["date_from"],
        date_to=data["date_to"],
        rows=data["items"],
        show_financial=fin,
        extra_payment_rows=extra_payment_rows,
        deduction_rows=deduction_rows,
        advance_taken=0.0,
        advance_repaid=0.0,
        remaining_balance=remaining_balance,
        advance_entries=[],
        client_address=client_info.get("address"),
        client_phone=client_info.get("phone"),
        client_email=client_info.get("email"),
        client_website=client_info.get("website"),
        officer_ssn=(data.get("entity") or {}).get("social_security_code"),
    )

    gross = float((data.get("summary") or {}).get("total_amount") or 0) if fin else 0.0
    extra_total = sum(float(r.get("amount") or 0) for r in extra_payment_rows)
    ded_total = sum(float(r.get("amount") or 0) for r in deduction_rows)
    net = round(gross + extra_total - ded_total, 2)
    return body, {
        "gross": round(gross, 2),
        "net_payment": net,
        "officer_name": officer_name,
        "client_name": client_info.get("name"),
    }


def _payslip_record_out(doc):
    out = _doc_out(doc)
    if doc.get("pdf_path"):
        out["pdf_url"] = to_public_url(doc["pdf_path"])
    out.setdefault("extra_payments", [])
    out.setdefault("deductions", [])
    return out


@router.post("/payslip-records")
async def create_payslip_record(payload: PayslipRecordCreate, request: Request, db=Depends(get_db)):
    """Generate a payslip PDF and SAVE it as a record (one per officer+client+
    period; regenerating overwrites). Extra payments & deductions are baked into
    the PDF and stored so the record can later be previewed, downloaded, or
    reopened for editing."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.export")

    officer_id = payload.officer_id
    client_id = payload.client_id
    date_from = payload.date_from
    date_to = payload.date_to
    if not (officer_id and client_id and date_from and date_to):
        raise HTTPException(400, "officer_id, client_id, date_from and date_to are required")

    extra_rows = _normalize_payslip_lines(payload.extra_payments)
    ded_rows = _normalize_payslip_lines(payload.deductions)

    body, snap = await _build_officer_payslip_bytes(
        request, db, user, officer_id, client_id, date_from, date_to, extra_rows, ded_rows,
    )

    # Persist the PDF file (overwrite the previous file for this period).
    from utils.storage import put_object, generate_upload_path
    key = {"officer_id": officer_id, "client_id": client_id,
           "date_from": date_from, "date_to": date_to}
    prev = await db.dispatch_payslip_records.find_one(key)
    path = generate_upload_path(f"payslips/{officer_id}", f"payslip-{date_from}-{date_to}.pdf")
    put_object(path, body, "application/pdf")

    now = _now()
    doc = {
        **key,
        "extra_payments": extra_rows,
        "deductions": ded_rows,
        "pdf_path": path,
        "gross": snap["gross"],
        "net_payment": snap["net_payment"],
        "officer_name": snap["officer_name"],
        "client_name": snap["client_name"],
        "generated_at": now,
        "generated_by": str(user.get("id") or user.get("_id") or ""),
    }
    await db.dispatch_payslip_records.update_one(
        key,
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    saved = await db.dispatch_payslip_records.find_one(key)
    return _payslip_record_out(saved)


@router.get("/payslip-records")
async def list_payslip_records(request: Request, db=Depends(get_db),
                               officer_id: str = None, client_id: str = None):
    """List saved payslip records (most recent first). Filter by officer/client."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    q = {}
    if officer_id:
        q["officer_id"] = officer_id
    if client_id:
        q["client_id"] = client_id
    docs = await db.dispatch_payslip_records.find(q).sort(
        [("generated_at", -1)]).to_list(500)
    return [_payslip_record_out(d) for d in docs]


@router.get("/payslip-records/{rid}")
async def get_payslip_record(rid: str, request: Request, db=Depends(get_db)):
    """Fetch one saved payslip record (extra/deductions pre-fill on modify)."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    doc = await db.dispatch_payslip_records.find_one({"_id": _oid(rid)})
    if not doc:
        raise HTTPException(404, "Payslip record not found")
    return _payslip_record_out(doc)


@router.get("/payslip-records/{rid}/pdf")
async def download_payslip_record_pdf(rid: str, request: Request, db=Depends(get_db)):
    """Stream the saved PDF for a record."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    doc = await db.dispatch_payslip_records.find_one({"_id": _oid(rid)})
    if not doc or not doc.get("pdf_path"):
        raise HTTPException(404, "Payslip PDF not found")
    from utils.storage import get_object
    try:
        data, _ = get_object(doc["pdf_path"])
    except FileNotFoundError:
        raise HTTPException(404, "Payslip PDF file missing")
    fname = f"payslip-{doc.get('officer_name') or 'officer'}-{doc.get('date_from')}-{doc.get('date_to')}.pdf"
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'})


@router.delete("/payslip-records/{rid}")
async def delete_payslip_record(rid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.export")
    doc = await db.dispatch_payslip_records.find_one({"_id": _oid(rid)})
    if not doc:
        raise HTTPException(404, "Payslip record not found")
    await db.dispatch_payslip_records.delete_one({"_id": _oid(rid)})
    return {"ok": True}



# ---------- Export (CSV / PDF) — respects financial permission ----------
REPORT_TYPES = {
    "schedules": {
        "fetcher": report_schedules,
        "title": "Dispatch Schedules",
        "cols_base": [
            ("Date", "date"), ("Officer", "officer_name"), ("Post Pin", "post_pin_display"),
            ("Post Site", "post_site_name"), ("Client", "client_name"), ("Vendor", "vendor_name"),
            ("Shift", "shift_type"), ("Start", "start_time"), ("End", "end_time"),
            ("Hours", "duty_hours"), ("Confirmation", "confirmation_status"), ("Status", "shift_status"),
        ],
        "cols_fin": [("Duty Rate", "duty_rate"), ("Billing Rate", "billing_rate"), ("Work Order", "work_order_number")],
    },
    "by-officer": {
        "title": "Report by Officer",
        "cols_base": [
            ("Officer", "officer_name"), ("Shifts", "total_shifts"), ("Completed", "completed"),
            ("Confirmed", "confirmed"),
            ("Total Hours", "total_hours"), ("Attendance %", "attendance_pct"),
        ],
        "cols_fin": [("Billing", "billing_amount"), ("Cost", "cost_amount"), ("Margin", "margin")],
    },
    "by-post-site": {
        "title": "Report by Post Site",
        "cols_base": [
            ("Post Pin", "post_pin_display"), ("Post Site", "post_site_name"),
            ("Shifts", "total_shifts"),
            ("Completed", "completed"),
            ("Total Hours", "total_hours"), ("Coverage %", "coverage_pct"),
        ],
        "cols_fin": [("Billing", "billing_amount"), ("Cost", "cost_amount"), ("Margin", "margin")],
    },
    "by-client": {
        "title": "Report by Client",
        "cols_base": [
            ("Client", "client_name"), ("Shifts", "total_shifts"), ("Completed", "completed"),
            ("Total Hours", "total_hours"),
        ],
        "cols_fin": [("Billing", "billing_amount"), ("Cost", "cost_amount"), ("Margin", "margin")],
    },
    "by-vendor": {
        "title": "Report by Vendor",
        "cols_base": [
            ("Vendor", "vendor_name"), ("Shifts", "total_shifts"), ("Completed", "completed"),
            ("Total Hours", "total_hours"),
        ],
        "cols_fin": [("Billing", "billing_amount"), ("Cost", "cost_amount"), ("Margin", "margin")],
    },
}


@router.get("/reports/export")
async def export_report(
    request: Request, db=Depends(get_db),
    type: str = "schedules",
    format: str = "csv",
    date_from: str = None, date_to: str = None,
    officer_id: str = None, vendor_id: str = None, client_id: str = None,
    post_site_id: str = None, post_pin: str = None,
    shift_type: str = None, confirmation_status: str = None, shift_status: str = None,
    q: str = None,
):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.export")
    if type not in REPORT_TYPES:
        raise HTTPException(400, f"Unknown report type: {type}")
    fmt = format.lower()
    if fmt not in ("csv", "pdf", "xlsx"):
        raise HTTPException(400, "format must be 'csv', 'pdf' or 'xlsx'")

    # Fetch data by calling the report handler internally
    if type == "schedules":
        data = await report_schedules(request, db,
            officer_id=officer_id, vendor_id=vendor_id, client_id=client_id,
            post_site_id=post_site_id, post_pin=post_pin,
            date_from=date_from, date_to=date_to,
            shift_type=shift_type, confirmation_status=confirmation_status,
            shift_status=shift_status, q=q, limit=1000)
    elif type == "by-officer":
        data = await report_by_officer(request, db, date_from=date_from, date_to=date_to, q=q)
    elif type == "by-post-site":
        data = await report_by_post_site(request, db, date_from=date_from, date_to=date_to, q=q)
    elif type == "by-client":
        data = await report_by_client(request, db, date_from=date_from, date_to=date_to, q=q)
    elif type == "by-vendor":
        data = await report_by_vendor(request, db, date_from=date_from, date_to=date_to, q=q)

    spec = REPORT_TYPES[type]
    cols = list(spec["cols_base"])
    if has_permission(user, "dispatch.financial.view"):
        cols += spec["cols_fin"]

    subtitle = f"{data['date_from']} → {data['date_to']} · {data['count']} record(s)"
    fname_base = f"dispatch-{type}-{data['date_from']}-{data['date_to']}"
    if fmt == "csv":
        body = build_csv(data["items"], cols)
        return StreamingResponse(io.BytesIO(body), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname_base}.csv"'})
    if fmt == "xlsx":
        body = build_xlsx(data["items"], cols, title=spec["title"], subtitle=subtitle)
        return StreamingResponse(io.BytesIO(body),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{fname_base}.xlsx"'})
    body = build_pdf(spec["title"], subtitle, data["items"], cols)
    return StreamingResponse(io.BytesIO(body), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname_base}.pdf"'})
