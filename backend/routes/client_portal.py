"""Client Portal routes.

Read-only, strictly client-scoped endpoints. Every response is limited to the
data that belongs to the logged-in client's own `client_id`. A client can never
see another client's data. Financial fields (duty/billing rate, work orders)
are never exposed here.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel
from bson import ObjectId

from utils.auth import get_current_user
from utils.storage import to_public_url
from utils.tz import dhaka_today_iso, dhaka_today
from models.dispatch import COMPLETED_STATUSES, SHIFT_TYPES

router = APIRouter(prefix="/portal", tags=["Client Portal"])

# Never expose these to a client
FINANCIAL_FIELDS = ("duty_rate", "billing_rate", "work_order_number")

# Scheduling placeholders that are not real officers
SPECIAL_OFFICERS = {"TEMP", "OPEN_SHIFT"}


def _amt(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def get_db(request: Request):
    return request.app.state.db


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
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            d[k] = v.isoformat()
        elif isinstance(v, ObjectId):
            d[k] = str(v)
    return d


def _strip_financial(d: dict) -> dict:
    for f in FINANCIAL_FIELDS:
        d.pop(f, None)
    return d


async def get_client_user(request: Request, db) -> dict:
    """Return the authenticated user, but only if they are a client with a
    linked client_id. Enforces the portal is client-only."""
    user = await get_current_user(request, db)
    if user.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client portal access only")
    if not user.get("client_id"):
        raise HTTPException(status_code=403, detail="No client is linked to this account")
    return user


@router.get("/me")
async def portal_me(request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    client = await db.dispatch_clients.find_one({"_id": _oid(user["client_id"])})
    out = _doc_out(client) if client else None
    if out and out.get("logo_path"):
        out["logo_url"] = to_public_url(out["logo_path"])
    return {
        "client": out,
        "user": {"name": user.get("name"), "email": user.get("email")},
    }


@router.get("/summary")
async def portal_summary(request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    today = dhaka_today_iso()

    total_schedules = await db.dispatch_schedules.count_documents({"client_id": cid})
    upcoming = await db.dispatch_schedules.count_documents(
        {"client_id": cid, "date": {"$gte": today}}
    )
    completed = await db.dispatch_schedules.count_documents(
        {"client_id": cid, "shift_status": {"$in": COMPLETED_STATUSES}}
    )
    vendors = await db.dispatch_vendors.count_documents({"client_ids": cid})
    officers = await db.dispatch_officers.count_documents({"client_id": cid})
    post_sites = await db.dispatch_post_sites.count_documents({"client_id": cid})

    # Officer check-ins today: this client's schedules dated today where the
    # officer has clocked in (Clocked In / Clocked Out both count as checked-in).
    checkins_today = await db.dispatch_schedules.count_documents(
        {"client_id": cid, "date": today, "shift_status": {"$in": COMPLETED_STATUSES}}
    )

    # Active post sites linked to this client.
    active_post_sites = await db.dispatch_post_sites.count_documents(
        {"client_id": cid, "status": "active"}
    )

    # 7-day payslip summary for officers assigned to this client: total earnings
    # (duty_hours × duty_rate) across this client's schedules over the last 7 days.
    week_from = (dhaka_today() - timedelta(days=6)).isoformat()
    week_scheds = await db.dispatch_schedules.find(
        {"client_id": cid, "date": {"$gte": week_from, "$lte": today}}
    ).to_list(10000)
    payslip_total = 0.0
    officer_ids = set()
    for s in week_scheds:
        payslip_total += _amt(s.get("duty_hours")) * _amt(s.get("duty_rate"))
        oid = s.get("officer_id")
        if oid and oid not in SPECIAL_OFFICERS:
            officer_ids.add(str(oid))

    return {
        "total_schedules": total_schedules,
        "upcoming_schedules": upcoming,
        "completed_schedules": completed,
        "vendors": vendors,
        "officers": officers,
        "post_sites": post_sites,
        "checkins_today": checkins_today,
        "active_post_sites": active_post_sites,
        "payslip_7d": {
            "from": week_from,
            "to": today,
            "total": round(payslip_total, 2),
            "officers": len(officer_ids),
            "shifts": len(week_scheds),
        },
    }


@router.get("/vendors")
async def portal_vendors(request: Request, db=Depends(get_db), search: str = ""):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    q = {"client_ids": cid}
    if search:
        q["$and"] = [
            {"client_ids": cid},
            {"$or": [{"name": {"$regex": search, "$options": "i"}},
                     {"code": {"$regex": search, "$options": "i"}}]},
        ]
        q.pop("client_ids", None)
    docs = await db.dispatch_vendors.find(q).limit(500).to_list(500)
    out = []
    for d in docs:
        row = _doc_out(d)
        if row.get("logo_path"):
            row["logo_url"] = to_public_url(row["logo_path"])
        out.append(row)
    return out


async def _allowed_vendor_ids(db, cid):
    docs = await db.dispatch_vendors.find({"client_ids": cid}, {"_id": 1}).to_list(500)
    return {str(d["_id"]) for d in docs}


@router.get("/schedules")
async def portal_schedules(request: Request, db=Depends(get_db),
                           vendor_id: str = None, shift_status: str = None,
                           date_from: str = None, date_to: str = None,
                           page: int = 1, limit: int = 100):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    limit = min(max(limit, 1), 250)
    page = max(page, 1)

    q = {"client_id": cid}
    if vendor_id:
        # only allow vendors that actually serve this client
        allowed = await _allowed_vendor_ids(db, cid)
        if vendor_id not in allowed:
            return {"items": [], "total": 0, "page": page, "limit": limit}
        q["vendor_id"] = vendor_id
    if shift_status:
        q["shift_status"] = shift_status
    if date_from or date_to:
        dq = {}
        if date_from:
            dq["$gte"] = date_from
        if date_to:
            dq["$lte"] = date_to
        q["date"] = dq

    total = await db.dispatch_schedules.count_documents(q)
    docs = await db.dispatch_schedules.find(q).sort([("date", -1), ("start_time", 1)]) \
        .skip((page - 1) * limit).limit(limit).to_list(limit)

    cache = {}

    async def _name(coll, _id):
        if not _id:
            return None
        k = f"{coll}:{_id}"
        if k in cache:
            return cache[k]
        try:
            d = await db[coll].find_one({"_id": _oid(_id)},
                                        {"name": 1, "code": 1, "post_pin": 1,
                                         "city": 1, "location": 1})
        except Exception:
            d = None
        cache[k] = d
        return d

    out = []
    for d in docs:
        row = _strip_financial(_doc_out(d))
        ven = await _name("dispatch_vendors", d.get("vendor_id"))
        off = await _name("dispatch_officers", d.get("officer_id"))
        pst = await _name("dispatch_post_sites", d.get("post_site_id"))
        row["vendor_name"] = ven.get("name") if ven else None
        row["vendor_code"] = ven.get("code") if ven else None
        row["officer_name"] = off.get("name") if off else None
        row["post_site_name"] = pst.get("name") if pst else None
        row["post_pin"] = pst.get("post_pin") if pst else None
        row["location"] = pst.get("location") if pst else None
        row["city"] = pst.get("city") if pst else None
        out.append(row)

    return {"items": out, "total": total, "page": page, "limit": limit}


@router.get("/reports")
async def portal_reports(request: Request, db=Depends(get_db),
                         date_from: str = None, date_to: str = None):
    user = await get_client_user(request, db)
    cid = user["client_id"]

    q = {"client_id": cid}
    if date_from or date_to:
        dq = {}
        if date_from:
            dq["$gte"] = date_from
        if date_to:
            dq["$lte"] = date_to
        q["date"] = dq

    docs = await db.dispatch_schedules.find(q).limit(5000).to_list(5000)

    # Resolve vendor names for grouping
    vendor_ids = {str(d.get("vendor_id")) for d in docs if d.get("vendor_id")}
    vendor_map = {}
    if vendor_ids:
        obj_ids = []
        for v in vendor_ids:
            try:
                obj_ids.append(ObjectId(v))
            except Exception:
                pass
        vdocs = await db.dispatch_vendors.find({"_id": {"$in": obj_ids}},
                                               {"name": 1}).to_list(len(obj_ids))
        vendor_map = {str(v["_id"]): v.get("name") for v in vdocs}

    by_vendor = {}
    by_status = {}
    total_hours = 0.0
    for d in docs:
        vid = str(d.get("vendor_id") or "")
        vname = vendor_map.get(vid, "—")
        hours = d.get("duty_hours") or 0
        try:
            hours = float(hours)
        except Exception:
            hours = 0.0
        total_hours += hours
        bv = by_vendor.setdefault(vid, {"vendor_name": vname, "shifts": 0, "hours": 0.0})
        bv["shifts"] += 1
        bv["hours"] = round(bv["hours"] + hours, 2)
        status = d.get("shift_status") or "Not Started"
        by_status[status] = by_status.get(status, 0) + 1

    return {
        "totals": {"shifts": len(docs), "hours": round(total_hours, 2)},
        "by_vendor": sorted(by_vendor.values(), key=lambda x: -x["shifts"]),
        "by_status": by_status,
    }


# =====================================================================
#  OFFICERS (read-only, scoped to this client)
# =====================================================================
@router.get("/officers")
async def portal_officers(request: Request, db=Depends(get_db), search: str = ""):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    q = {"client_id": cid}
    if search:
        q = {"$and": [{"client_id": cid}, {"$or": [
            {"name": {"$regex": search, "$options": "i"}},
            {"officer_code": {"$regex": search, "$options": "i"}},
            {"contact_number": {"$regex": search, "$options": "i"}},
        ]}]}
    docs = await db.dispatch_officers.find(q).sort("name", 1).limit(500).to_list(500)
    out = []
    for d in docs:
        row = _doc_out(d)
        if row.get("profile_image"):
            row["profile_image_url"] = to_public_url(row["profile_image"])
        out.append(row)
    return out


@router.get("/post-sites")
async def portal_post_sites(request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    docs = await db.dispatch_post_sites.find({"client_id": cid}).sort("name", 1).limit(500).to_list(500)
    return [_doc_out(d) for d in docs]


# =====================================================================
#  SCHEDULE CRUD (client-scoped). A client may only add/edit/delete
#  dispatches for their OWN post sites, officers and vendors.
# =====================================================================
class PortalScheduleCreate(BaseModel):
    date: str
    shift_type: str
    start_time: str
    end_time: str
    post_site_id: str
    officer_id: str
    vendor_id: str
    remarks: Optional[str] = None


class PortalScheduleUpdate(BaseModel):
    date: Optional[str] = None
    shift_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    post_site_id: Optional[str] = None
    officer_id: Optional[str] = None
    vendor_id: Optional[str] = None
    remarks: Optional[str] = None


def _parse_hhmm(s: str) -> int:
    try:
        h, m = str(s).split(":")
        h, m = int(h), int(m)
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError()
        return h * 60 + m
    except Exception:
        raise HTTPException(400, f"Invalid time '{s}', expected HH:MM")


def _duty_hours(start: str, end: str):
    s = _parse_hhmm(start)
    e = _parse_hhmm(end)
    if e <= s:
        e += 24 * 60
    return round((e - s) / 60.0, 2)


def _now():
    return datetime.now(timezone.utc)


async def _validate_owned_refs(db, cid, post_site_id, officer_id, vendor_id):
    """Ensure the post site + officer belong to this client and the vendor
    serves this client. Returns nothing; raises 400 on any violation."""
    post = await db.dispatch_post_sites.find_one({"_id": _oid(post_site_id)})
    if not post or str(post.get("client_id") or "") != str(cid):
        raise HTTPException(400, "Post site does not belong to your account")
    officer = await db.dispatch_officers.find_one({"_id": _oid(officer_id)})
    if not officer or str(officer.get("client_id") or "") != str(cid):
        raise HTTPException(400, "Officer does not belong to your account")
    vendor = await db.dispatch_vendors.find_one({"_id": _oid(vendor_id)})
    if not vendor or cid not in (vendor.get("client_ids") or []):
        raise HTTPException(400, "Vendor is not assigned to your account")


async def _check_conflict(db, officer_id, sched_date, start, end, exclude_id=None):
    s = _parse_hhmm(start)
    e = _parse_hhmm(end)
    if e <= s:
        e += 24 * 60
    q = {"officer_id": officer_id, "date": sched_date}
    if exclude_id:
        q["_id"] = {"$ne": _oid(exclude_id)}
    for ex in await db.dispatch_schedules.find(q).to_list(500):
        xs = _parse_hhmm(ex["start_time"])
        xe = _parse_hhmm(ex["end_time"])
        if xe <= xs:
            xe += 24 * 60
        if s < xe and xs < e:
            return ex
    return None


async def _portal_audit(db, user, action, sid, name):
    """Lightweight audit entry so admins can see client-made changes."""
    try:
        await db.dispatch_audit.insert_one({
            "action": action, "entity_type": "schedule",
            "entity_id": str(sid) if sid else None, "entity_name": name,
            "changes": None, "actor_id": str(user.get("_id")),
            "actor_name": user.get("name"), "actor_role": "client",
            "at": _now(),
        })
    except Exception:
        pass


@router.post("/schedules")
async def portal_create_schedule(payload: PortalScheduleCreate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    if payload.shift_type not in SHIFT_TYPES:
        raise HTTPException(400, f"Shift type must be one of {SHIFT_TYPES}")
    await _validate_owned_refs(db, cid, payload.post_site_id, payload.officer_id, payload.vendor_id)

    conflict = await _check_conflict(db, payload.officer_id, payload.date,
                                     payload.start_time, payload.end_time)
    if conflict:
        raise HTTPException(409, f"Officer already has a shift on {conflict['date']} "
                                 f"{conflict['start_time']}–{conflict['end_time']}.")

    now = _now()
    doc = {
        "date": payload.date,
        "shift_type": payload.shift_type,
        "start_time": payload.start_time,
        "end_time": payload.end_time,
        "client_id": cid,  # forced to this client — never trust client input
        "vendor_id": payload.vendor_id,
        "post_site_id": payload.post_site_id,
        "officer_id": payload.officer_id,
        "remarks": payload.remarks,
        "duty_hours": _duty_hours(payload.start_time, payload.end_time),
        "duty_rate": None, "billing_rate": None, "work_order_number": None,
        "shift_status": "Not Started",
        "confirmation_status": "Not Confirmed",
        "confirmation_method": None,
        "confirmed_by_id": None, "confirmed_by_name": None, "confirmed_at": None,
        "actual_check_in": None, "actual_check_out": None, "actual_duty_hours": None,
        "late_minutes": 0, "early_minutes": 0, "overtime_minutes": 0,
        "created_by": str(user["_id"]), "created_at": now,
        "updated_by": str(user["_id"]), "updated_at": now,
        "last_modified_by_id": str(user["_id"]),
        "last_modified_by_name": user.get("name"),
        "last_modified_action": "Created (Client Portal)",
        "last_modified_at": now,
    }
    res = await db.dispatch_schedules.insert_one(doc)
    await _portal_audit(db, user, "create", res.inserted_id, f"{doc['date']} {doc['shift_type']}")
    return _strip_financial(_doc_out(await db.dispatch_schedules.find_one({"_id": res.inserted_id})))


@router.put("/schedules/{sid}")
async def portal_update_schedule(sid: str, payload: PortalScheduleUpdate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    existing = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not existing or str(existing.get("client_id") or "") != str(cid):
        raise HTTPException(404, "Schedule not found")

    upd = payload.model_dump(exclude_unset=True)
    upd.pop("client_id", None)  # client can never move a schedule to another client

    if "shift_type" in upd and upd["shift_type"] not in SHIFT_TYPES:
        raise HTTPException(400, f"Shift type must be one of {SHIFT_TYPES}")

    post_site_id = upd.get("post_site_id", existing.get("post_site_id"))
    officer_id = upd.get("officer_id", existing.get("officer_id"))
    vendor_id = upd.get("vendor_id", existing.get("vendor_id"))
    await _validate_owned_refs(db, cid, post_site_id, officer_id, vendor_id)

    st = upd.get("start_time", existing["start_time"])
    et = upd.get("end_time", existing["end_time"])
    if "start_time" in upd or "end_time" in upd:
        upd["duty_hours"] = _duty_hours(st, et)

    if any(k in upd for k in ("officer_id", "date", "start_time", "end_time")):
        conflict = await _check_conflict(db, officer_id, upd.get("date", existing["date"]),
                                         st, et, exclude_id=sid)
        if conflict:
            raise HTTPException(409, f"Officer already has a shift on {conflict['date']} "
                                     f"{conflict['start_time']}–{conflict['end_time']}.")

    upd["updated_by"] = str(user["_id"])
    upd["updated_at"] = _now()
    upd["last_modified_by_name"] = user.get("name")
    upd["last_modified_action"] = "Edited (Client Portal)"
    upd["last_modified_at"] = _now()
    await db.dispatch_schedules.update_one({"_id": _oid(sid)}, {"$set": upd})
    await _portal_audit(db, user, "update", sid, f"{existing.get('date')} {existing.get('shift_type')}")
    return _strip_financial(_doc_out(await db.dispatch_schedules.find_one({"_id": _oid(sid)})))


@router.delete("/schedules/{sid}")
async def portal_delete_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    existing = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not existing or str(existing.get("client_id") or "") != str(cid):
        raise HTTPException(404, "Schedule not found")
    await db.dispatch_schedules.delete_one({"_id": _oid(sid)})
    await _portal_audit(db, user, "delete", sid, f"{existing.get('date')} {existing.get('shift_type')}")
    return {"message": "Schedule deleted"}
