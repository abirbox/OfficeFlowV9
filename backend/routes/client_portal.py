"""Client Portal routes.

Read-only, strictly client-scoped endpoints. Every response is limited to the
data that belongs to the logged-in client's own `client_id`. A client can never
see another client's data. Financial fields (duty/billing rate, work orders)
are never exposed here.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from utils.auth import get_current_user
from utils.storage import to_public_url
from utils.tz import dhaka_today_iso, dhaka_today
from models.dispatch import COMPLETED_STATUSES

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
