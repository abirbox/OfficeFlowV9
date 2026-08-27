"""Client Portal routes.

Read-only, strictly client-scoped endpoints. Every response is limited to the
data that belongs to the logged-in client's own `client_id`. A client can never
see another client's data. Financial fields (duty/billing rate, work orders)
are never exposed here.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel
from bson import ObjectId
import io

from utils.auth import get_current_user
from utils.storage import to_public_url
from utils.tz import dhaka_today_iso, dhaka_today
from models.dispatch import (
    COMPLETED_STATUSES, SHIFT_TYPES,
    ScheduleCreate, ScheduleUpdate, OfficerCreate, OfficerUpdate,
    PostSiteCreate, PostSiteUpdate, ShiftStatusUpdate, ConfirmationUpdate,
)
from fastapi import UploadFile
import routes.dispatch as adm

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


CLIENT_DISPATCH_PERMS = [
    "dispatch.dashboard.view",
    "dispatch.schedule.view", "dispatch.schedule.create", "dispatch.schedule.edit",
    "dispatch.schedule.cancel", "dispatch.schedule.delete",
    "dispatch.clients.view", "dispatch.vendors.view",
    "dispatch.officers.view", "dispatch.officers.create", "dispatch.officers.edit", "dispatch.officers.delete",
    "dispatch.post_sites.view", "dispatch.post_sites.create", "dispatch.post_sites.edit", "dispatch.post_sites.delete",
    "dispatch.confirmation.view", "dispatch.confirmation.manage", "dispatch.confirmation.history",
]


async def get_client_user(request: Request, db) -> dict:
    """Return the authenticated user, but only if they are a client with a
    linked client_id. Enforces the portal is client-only.

    Also ensures the client account carries the dispatch permissions needed by
    the reused Dispatch page components. Direct /api/dispatch/* access remains
    blocked for role=client, so these permissions only take effect through the
    client-scoped /api/portal/dispatch wrappers."""
    user = await get_current_user(request, db)
    if user.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client portal access only")
    if not user.get("client_id"):
        raise HTTPException(status_code=403, detail="No client is linked to this account")
    missing = set(CLIENT_DISPATCH_PERMS) - set(user.get("permissions") or [])
    if missing:
        perms = sorted(set(user.get("permissions") or []) | set(CLIENT_DISPATCH_PERMS))
        await db.users.update_one({"_id": ObjectId(str(user["_id"]))}, {"$set": {"permissions": perms}})
        user["permissions"] = perms
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


def _month_bounds():
    t = dhaka_today()
    first = t.replace(day=1).isoformat()
    if t.month == 12:
        nxt = t.replace(year=t.year + 1, month=1, day=1)
    else:
        nxt = t.replace(month=t.month + 1, day=1)
    last = (nxt - timedelta(days=1)).isoformat()
    return first, last


async def _own_officer(db, cid, officer_id):
    """Return the officer doc if it belongs to this client, else 404."""
    officer = await db.dispatch_officers.find_one({"_id": _oid(officer_id)})
    if not officer or str(officer.get("client_id") or "") != str(cid):
        raise HTTPException(404, "Officer not found")
    return officer


# =====================================================================
#  WAGE REPORT (scoped to this client's officers)
# =====================================================================
@router.get("/wage-report")
async def portal_wage_report(request: Request, db=Depends(get_db),
                             date_from: str = None, date_to: str = None):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    if not date_from or not date_to:
        date_from, date_to = _month_bounds()

    completed_cond = {"$in": ["$shift_status", COMPLETED_STATUSES]}
    pipeline = [
        {"$match": {"client_id": cid, "date": {"$gte": date_from, "$lte": date_to}}},
        {"$group": {
            "_id": "$officer_id",
            "total_shifts": {"$sum": 1},
            "completed": {"$sum": {"$cond": [completed_cond, 1, 0]}},
            "total_hours": {"$sum": {"$cond": [completed_cond, {"$ifNull": ["$duty_hours", 0]}, 0]}},
            "wage": {"$sum": {"$cond": [completed_cond,
                     {"$multiply": [{"$ifNull": ["$duty_hours", 0]}, {"$ifNull": ["$duty_rate", 0]}]}, 0]}},
        }},
        {"$sort": {"wage": -1}},
    ]
    rows = await db.dispatch_schedules.aggregate(pipeline).to_list(2000)
    out = []
    total_hours = 0.0
    total_wage = 0.0
    for r in rows:
        oid = r.pop("_id")
        if not oid or oid in SPECIAL_OFFICERS:
            continue
        officer = await db.dispatch_officers.find_one({"_id": _oid(oid)}, {"name": 1, "officer_code": 1})
        r["officer_id"] = oid
        r["officer_name"] = officer.get("name") if officer else "—"
        r["officer_code"] = officer.get("officer_code") if officer else None
        r["total_hours"] = round(r.get("total_hours", 0), 2)
        r["wage"] = round(r.get("wage", 0), 2)
        total_hours += r["total_hours"]
        total_wage += r["wage"]
        out.append(r)
    return {
        "items": out,
        "date_from": date_from, "date_to": date_to,
        "totals": {"hours": round(total_hours, 2), "wage": round(total_wage, 2), "officers": len(out)},
    }


@router.get("/officers/{officer_id}/payslip")
async def portal_officer_payslip(officer_id: str, request: Request, db=Depends(get_db),
                                 date_from: str = None, date_to: str = None,
                                 format: str = "pdf"):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    officer = await _own_officer(db, cid, officer_id)
    if not date_from or not date_to:
        date_from, date_to = _month_bounds()

    client = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    scheds = await db.dispatch_schedules.find(
        {"client_id": cid, "officer_id": officer_id, "date": {"$gte": date_from, "$lte": date_to}}
    ).sort([("date", 1), ("start_time", 1)]).to_list(3000)

    # Resolve post site names
    post_ids = {s.get("post_site_id") for s in scheds if s.get("post_site_id")}
    posts_map = {}
    if post_ids:
        obj_ids = [ObjectId(i) for i in post_ids if ObjectId.is_valid(i)]
        pdocs = await db.dispatch_post_sites.find({"_id": {"$in": obj_ids}}, {"name": 1, "post_pin": 1}).to_list(len(obj_ids))
        posts_map = {str(p["_id"]): p for p in pdocs}

    rows = []
    total_hours = 0.0
    total_amount = 0.0
    for s in scheds:
        is_complete = s.get("shift_status") in COMPLETED_STATUSES
        hours = _amt(s.get("duty_hours")) if is_complete else 0.0
        rate = _amt(s.get("duty_rate"))
        amount = round(hours * rate, 2)
        total_hours += hours
        total_amount += amount
        p = posts_map.get(str(s.get("post_site_id")), {})
        rows.append({
            "date": s.get("date"),
            "post_site": f"{p.get('post_pin', '')} {p.get('name', '')}".strip() or "—",
            "shift_type": s.get("shift_type"),
            "hours": hours,
            "rate": rate,
            "amount": amount,
        })
    rows.append({"date": "", "post_site": "", "shift_type": "TOTAL",
                 "hours": round(total_hours, 2), "rate": "", "amount": round(total_amount, 2)})

    columns = [
        {"key": "date", "label": "Date"},
        {"key": "post_site", "label": "Post Site"},
        {"key": "shift_type", "label": "Shift"},
        {"key": "hours", "label": "Hours"},
        {"key": "rate", "label": "Rate"},
        {"key": "amount", "label": "Amount"},
    ]
    title = f"Payslip — {officer.get('name')} ({officer.get('officer_code') or ''})"
    subtitle = f"{(client or {}).get('name', 'Client')}  |  {date_from} to {date_to}"

    fmt = (format or "pdf").lower()
    safe = (officer.get("name") or "officer").replace(" ", "-")
    if fmt == "xlsx":
        from utils.dispatch_reports import build_xlsx
        data = build_xlsx(rows, columns, title=title)
        return StreamingResponse(io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="Payslip-{safe}.xlsx"'})
    from utils.dispatch_reports import build_pdf
    data = build_pdf(title, subtitle, rows, columns)
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Payslip-{safe}.pdf"'})


# =====================================================================
#  PAYMENT (SO) — records for this client's officers (view + export)
# =====================================================================
@router.get("/payments")
async def portal_payments(request: Request, db=Depends(get_db),
                          search: str = None, date_from: str = None, date_to: str = None):
    user = await get_client_user(request, db)
    from routes.so_payments import _client_context
    return await _client_context(db, user["client_id"], search, date_from, date_to)


@router.get("/payments/officer/{officer_id}")
async def portal_payments_officer(officer_id: str, request: Request, db=Depends(get_db),
                                  date_from: str = None, date_to: str = None):
    user = await get_client_user(request, db)
    await _own_officer(db, user["client_id"], officer_id)
    from routes.so_payments import _officer_context
    return await _officer_context(db, officer_id, date_from, date_to)


@router.get("/payments/report/{fmt}")
async def portal_payments_report(fmt: str, request: Request, db=Depends(get_db),
                                 search: str = None, date_from: str = None, date_to: str = None):
    user = await get_client_user(request, db)
    from routes.so_payments import _client_context
    ctx = await _client_context(db, user["client_id"], search, date_from, date_to)
    name = (ctx["client"].get("name") or "client").replace(" ", "-")
    if fmt == "xlsx":
        from utils.dispatch_reports import build_client_payment_records_xlsx
        data = build_client_payment_records_xlsx(ctx=ctx)
        return StreamingResponse(io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="Payment-{name}.xlsx"'})
    from utils.dispatch_reports import build_client_payment_records_pdf
    data = build_client_payment_records_pdf(ctx=ctx)
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Payment-{name}.pdf"'})


@router.get("/payments/officer/{officer_id}/report/{fmt}")
async def portal_payments_officer_report(officer_id: str, fmt: str, request: Request, db=Depends(get_db),
                                         date_from: str = None, date_to: str = None):
    user = await get_client_user(request, db)
    await _own_officer(db, user["client_id"], officer_id)
    from routes.so_payments import _officer_context
    ctx = await _officer_context(db, officer_id, date_from, date_to)
    name = (ctx["officer"].get("name") or "officer").replace(" ", "-")
    if fmt == "xlsx":
        from utils.dispatch_reports import build_officer_payment_records_xlsx
        data = build_officer_payment_records_xlsx(ctx=ctx)
        return StreamingResponse(io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="Payment-{name}.xlsx"'})
    from utils.dispatch_reports import build_officer_payment_records_pdf
    data = build_officer_payment_records_pdf(ctx=ctx)
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Payment-{name}.pdf"'})


# =====================================================================
#  DISPATCH SECTION MIRROR  (client-scoped wrappers around admin logic)
#  Prefix: /portal/dispatch/*  — the reused Dispatch page components hit
#  /dispatch/* which the frontend rewrites to /portal/dispatch/*.
#  Every wrapper forces the logged-in client's scope and validates
#  ownership before delegating to the exact same admin route function.
# =====================================================================

async def _assert_owned_post_site(db, cid, post_site_id):
    p = await db.dispatch_post_sites.find_one({"_id": _oid(post_site_id)})
    if not p or str(p.get("client_id") or "") != str(cid):
        raise HTTPException(400, "Post site does not belong to your account")


async def _assert_owned_vendor(db, cid, vendor_id):
    v = await db.dispatch_vendors.find_one({"_id": _oid(vendor_id)})
    if not v or cid not in (v.get("client_ids") or []):
        raise HTTPException(400, "Vendor is not assigned to your account")


async def _assert_owned_officer(db, cid, officer_id):
    if officer_id in ("TEMP", "OPEN_SHIFT"):
        return
    o = await db.dispatch_officers.find_one({"_id": _oid(officer_id)})
    if not o or str(o.get("client_id") or "") != str(cid):
        raise HTTPException(400, "Officer does not belong to your account")


async def _assert_owned_schedule(db, cid, sid):
    s = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not s or str(s.get("client_id") or "") != str(cid):
        raise HTTPException(404, "Schedule not found")
    return s


# ---------- reference lists (dropdowns / filters) ----------
@router.get("/dispatch/clients")
async def pd_clients(request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    doc = await db.dispatch_clients.find_one({"_id": _oid(user["client_id"])})
    if not doc:
        return []
    out = _doc_out(doc)
    if out.get("logo_path"):
        out["logo_url"] = to_public_url(out["logo_path"])
    return [out]


@router.get("/dispatch/vendors")
async def pd_vendors(request: Request, db=Depends(get_db), search: str = "", status: str = None):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    q = {"client_ids": cid}
    ands = [{"client_ids": cid}]
    if status:
        ands.append({"status": status})
    if search:
        ands.append({"$or": [{"name": {"$regex": search, "$options": "i"}},
                             {"code": {"$regex": search, "$options": "i"}}]})
    q = {"$and": ands} if len(ands) > 1 else {"client_ids": cid}
    docs = await db.dispatch_vendors.find(q).limit(500).to_list(500)
    return [_doc_out(d) for d in docs]


# ---------- officers ----------
@router.get("/dispatch/officers")
async def pd_list_officers(request: Request, db=Depends(get_db), search: str = "",
                           client_id: str = None, type: str = None, status: str = None,
                           skip: int = 0, limit: int = 200):
    user = await get_client_user(request, db)
    return await adm.list_officers(request, db, search=search, client_id=user["client_id"],
                                   type=type, status=status, skip=skip, limit=limit)


@router.post("/dispatch/officers")
async def pd_create_officer(payload: OfficerCreate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    payload.client_id = user["client_id"]  # force to this client
    return await adm.create_officer(payload, request, db)


@router.put("/dispatch/officers/{oid}")
async def pd_update_officer(oid: str, payload: OfficerUpdate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    existing = await db.dispatch_officers.find_one({"_id": _oid(oid)})
    if not existing or str(existing.get("client_id") or "") != str(user["client_id"]):
        raise HTTPException(404, "Officer not found")
    payload.client_id = user["client_id"]  # cannot reassign to another client
    return await adm.update_officer(oid, payload, request, db)


@router.delete("/dispatch/officers/{oid}")
async def pd_delete_officer(oid: str, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    existing = await db.dispatch_officers.find_one({"_id": _oid(oid)})
    if not existing or str(existing.get("client_id") or "") != str(user["client_id"]):
        raise HTTPException(404, "Officer not found")
    return await adm.delete_officer(oid, request, db)


# ---------- post sites ----------
@router.get("/dispatch/post-sites")
async def pd_list_post_sites(request: Request, db=Depends(get_db), search: str = "",
                             client_id: str = None, vendor_id: str = None, status: str = None,
                             skip: int = 0, limit: int = 200):
    user = await get_client_user(request, db)
    return await adm.list_post_sites(request, db, search=search, client_id=user["client_id"],
                                     vendor_id=vendor_id, status=status, skip=skip, limit=limit)


@router.post("/dispatch/post-sites")
async def pd_create_post_site(payload: PostSiteCreate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    payload.client_id = user["client_id"]
    if getattr(payload, "vendor_id", None):
        await _assert_owned_vendor(db, user["client_id"], payload.vendor_id)
    return await adm.create_post_site(payload, request, db)


@router.put("/dispatch/post-sites/{pid}")
async def pd_update_post_site(pid: str, payload: PostSiteUpdate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    existing = await db.dispatch_post_sites.find_one({"_id": _oid(pid)})
    if not existing or str(existing.get("client_id") or "") != str(user["client_id"]):
        raise HTTPException(404, "Post Site not found")
    payload.client_id = user["client_id"]
    if getattr(payload, "vendor_id", None):
        await _assert_owned_vendor(db, user["client_id"], payload.vendor_id)
    return await adm.update_post_site(pid, payload, request, db)


@router.delete("/dispatch/post-sites/{pid}")
async def pd_delete_post_site(pid: str, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    existing = await db.dispatch_post_sites.find_one({"_id": _oid(pid)})
    if not existing or str(existing.get("client_id") or "") != str(user["client_id"]):
        raise HTTPException(404, "Post Site not found")
    return await adm.delete_post_site(pid, request, db)


# ---------- schedules ----------
@router.get("/dispatch/schedules")
async def pd_list_schedules(request: Request, db=Depends(get_db),
                            officer_id: str = None, vendor_id: str = None,
                            post_site_id: str = None, post_pin: str = None,
                            work_order: str = None, date_from: str = None, date_to: str = None,
                            shift_type: str = None, confirmation_status: str = None,
                            shift_status: str = None, search: str = "",
                            page: int = 1, limit: int = 50):
    user = await get_client_user(request, db)
    return await adm.list_schedules(
        request, db, officer_id=officer_id, vendor_id=vendor_id,
        client_id=user["client_id"], post_site_id=post_site_id, post_pin=post_pin,
        work_order=work_order, date_from=date_from, date_to=date_to,
        shift_type=shift_type, confirmation_status=confirmation_status,
        shift_status=shift_status, search=search, page=page, limit=limit)


@router.get("/dispatch/schedules/import-template")
async def pd_import_template(request: Request, db=Depends(get_db)):
    await get_client_user(request, db)
    return await adm.import_template(request, db) if hasattr(adm, "import_template") else {"detail": "n/a"}


@router.post("/dispatch/schedules/import")
async def pd_import_schedules(file: UploadFile, request: Request, db=Depends(get_db), dry_run: bool = False):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    result = await adm.import_schedules(file, request, db, dry_run=dry_run)
    # Defensive scope enforcement: remove anything that resolved to another client.
    removed = 0
    for sidx in list(result.get("created_ids", [])):
        doc = await db.dispatch_schedules.find_one({"_id": _oid(sidx)})
        if doc and str(doc.get("client_id") or "") != str(cid):
            await db.dispatch_schedules.delete_one({"_id": _oid(sidx)})
            result["created_ids"].remove(sidx)
            removed += 1
    if removed:
        result["created"] = max(0, result.get("created", 0) - removed)
        result.setdefault("errors", []).append(
            {"row": 0, "message": f"{removed} row(s) skipped: post site not in your account."})
    return result


@router.post("/dispatch/schedules")
async def pd_create_schedule(payload: ScheduleCreate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    payload.client_id = cid  # force
    await _assert_owned_post_site(db, cid, payload.post_site_id)
    await _assert_owned_vendor(db, cid, payload.vendor_id)
    await _assert_owned_officer(db, cid, payload.officer_id)
    return await adm.create_schedule(payload, request, db)


@router.get("/dispatch/schedules/{sid}")
async def pd_get_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    await _assert_owned_schedule(db, user["client_id"], sid)
    return await adm.get_schedule(sid, request, db)


@router.put("/dispatch/schedules/{sid}")
async def pd_update_schedule(sid: str, payload: ScheduleUpdate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    cid = user["client_id"]
    await _assert_owned_schedule(db, cid, sid)
    data = payload.model_dump(exclude_unset=True)
    if "client_id" in data:
        payload.client_id = cid  # never allow moving to another client
    if data.get("post_site_id"):
        await _assert_owned_post_site(db, cid, data["post_site_id"])
    if data.get("vendor_id"):
        await _assert_owned_vendor(db, cid, data["vendor_id"])
    if data.get("officer_id"):
        await _assert_owned_officer(db, cid, data["officer_id"])
    return await adm.update_schedule(sid, payload, request, db)


@router.delete("/dispatch/schedules/{sid}")
async def pd_delete_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    await _assert_owned_schedule(db, user["client_id"], sid)
    return await adm.delete_schedule(sid, request, db)


@router.post("/dispatch/schedules/{sid}/cancel")
async def pd_cancel_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    await _assert_owned_schedule(db, user["client_id"], sid)
    return await adm.cancel_schedule(sid, request, db)


@router.post("/dispatch/schedules/{sid}/status")
async def pd_status(sid: str, payload: ShiftStatusUpdate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    await _assert_owned_schedule(db, user["client_id"], sid)
    return await adm.update_shift_status(sid, payload, request, db)


@router.post("/dispatch/schedules/{sid}/confirm")
async def pd_confirm(sid: str, payload: ConfirmationUpdate, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    await _assert_owned_schedule(db, user["client_id"], sid)
    return await adm.confirm_schedule(sid, payload, request, db)


@router.get("/dispatch/schedules/{sid}/actions")
async def pd_actions(sid: str, request: Request, db=Depends(get_db)):
    user = await get_client_user(request, db)
    await _assert_owned_schedule(db, user["client_id"], sid)
    return await adm.schedule_actions(sid, request, db)


# ---------- upload logo (no client data) ----------
@router.post("/dispatch/upload-logo")
async def pd_upload_logo(file: UploadFile, request: Request, db=Depends(get_db)):
    await get_client_user(request, db)
    return await adm.upload_dispatch_logo(file, request)
