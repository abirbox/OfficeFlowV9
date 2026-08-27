"""Payment (SO) — per-client Security Officer payment records.

Landing page lists Clients (with officer counts). Inside a client, admins record
dated payment entries per Security Officer. Each entry has a Date and three
amounts: W2, W9 Direct Deposit and W9 Zelle Transfer. Derived values: W9 Total
(DD + Zelle) and Total (W2 + W9).

- Client view: one aggregated row per officer (summed across their entries).
- Officer detail: every dated entry for that officer + totals + PDF/Excel export.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId
import io

from utils.auth import get_current_user
from utils.permissions import require_permission
from utils.storage import to_public_url
from routes.dispatch import get_db, _oid, _doc_out

router = APIRouter(prefix="/so-payments", tags=["Payment (SO)"])


class PayComponent(BaseModel):
    date: Optional[str] = None
    amount: float = 0


class PaymentRecordCreate(BaseModel):
    officer_id: str
    w2: PayComponent = Field(default_factory=PayComponent)
    w9_direct_deposit: PayComponent = Field(default_factory=PayComponent)
    w9_zelle: PayComponent = Field(default_factory=PayComponent)


def _now():
    return datetime.now(timezone.utc)


def _amt(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def _record_out(doc: dict) -> dict:
    """Serialize a payment record with computed totals + a representative date."""
    d = _doc_out(doc)
    w2 = d.get("w2") or {}
    dd = d.get("w9_direct_deposit") or {}
    ze = d.get("w9_zelle") or {}
    w2_amt = _amt(w2.get("amount"))
    dd_amt = _amt(dd.get("amount"))
    ze_amt = _amt(ze.get("amount"))
    d["w2_amount"] = w2_amt
    d["w9_direct_deposit_amount"] = dd_amt
    d["w9_zelle_amount"] = ze_amt
    d["w9_total"] = round(dd_amt + ze_amt, 2)
    d["total"] = round(w2_amt + dd_amt + ze_amt, 2)
    d["date"] = w2.get("date") or dd.get("date") or ze.get("date")
    return d


async def _officer_snapshot(db, officer_id: str) -> dict:
    officer = await db.dispatch_officers.find_one({"_id": _oid(officer_id)})
    if not officer:
        raise HTTPException(404, "Security Officer not found")
    return {
        "officer_id": str(officer["_id"]),
        "officer_name": officer.get("name"),
        "officer_code": officer.get("officer_code"),
        "officer_address": officer.get("address"),
        "social_security_code": officer.get("social_security_code"),
        "client_id": officer.get("client_id"),
    }


def _client_public(client: dict) -> dict:
    """Full client details (incl. contact + logo) for headers/statements."""
    out = {
        "id": str(client["_id"]),
        "name": client.get("name"),
        "code": client.get("code"),
        "address": client.get("address"),
        "email": client.get("email"),
        "contact_number": client.get("contact_number"),
        "website": client.get("website"),
        "logo_path": client.get("logo_path"),
    }
    if client.get("logo_path"):
        out["logo_url"] = to_public_url(client["logo_path"])
    return out


def _in_range(date_str, date_from, date_to) -> bool:
    """ISO date (YYYY-MM-DD) inclusive range check; records with no date pass
    only when no range is set."""
    if not date_from and not date_to:
        return True
    if not date_str:
        return False
    if date_from and date_str < date_from:
        return False
    if date_to and date_str > date_to:
        return False
    return True


# =====================================================================
#  Landing page — Clients with officer counts
# =====================================================================
@router.get("/clients")
async def list_payment_clients(request: Request, db=Depends(get_db), search: str = ""):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    q = {}
    if search:
        q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                    {"code": {"$regex": search, "$options": "i"}}]
    clients = await db.dispatch_clients.find(q).sort("name", 1).to_list(1000)

    counts = {}
    async for row in db.dispatch_officers.aggregate([
        {"$group": {"_id": "$client_id", "n": {"$sum": 1}}}
    ]):
        counts[str(row["_id"])] = row["n"]

    return [{
        "id": str(c["_id"]),
        "name": c.get("name"),
        "code": c.get("code"),
        "officer_count": counts.get(str(c["_id"]), 0),
    } for c in clients]


# =====================================================================
#  Officer search (for the Add New Payment form)
# =====================================================================
@router.get("/officers/search")
async def search_officers(request: Request, db=Depends(get_db),
                          client_id: str = None, q: str = ""):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    query = {}
    if client_id:
        query["client_id"] = client_id
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"officer_code": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"contact_number": {"$regex": q, "$options": "i"}},
            {"social_security_code": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.dispatch_officers.find(query).sort("name", 1).to_list(50)
    return [{
        "id": str(d["_id"]),
        "name": d.get("name"),
        "officer_code": d.get("officer_code"),
        "email": d.get("email"),
        "contact_number": d.get("contact_number"),
        "address": d.get("address"),
        "social_security_code": d.get("social_security_code"),
    } for d in docs]


# =====================================================================
#  Client view — aggregated per officer
# =====================================================================
async def _client_context(db, client_id, search=None, date_from=None, date_to=None):
    client = await db.dispatch_clients.find_one({"_id": _oid(client_id)})
    if not client:
        raise HTTPException(404, "Client not found")

    docs = await db.dispatch_so_payment_records.find({"client_id": client_id}).to_list(10000)

    # Group records by officer and sum amounts (within the date range).
    by_officer = {}
    all_dates = []
    for doc in docs:
        r = _record_out(doc)
        if not _in_range(r.get("date"), date_from, date_to):
            continue
        if r.get("date"):
            all_dates.append(r["date"])
        oid = r.get("officer_id")
        agg = by_officer.get(oid)
        if not agg:
            agg = {
                "officer_id": oid,
                "officer_name": r.get("officer_name"),
                "officer_address": r.get("officer_address"),
                "social_security_code": r.get("social_security_code"),
                "officer_code": r.get("officer_code"),
                "w2_amount": 0.0, "w9_direct_deposit_amount": 0.0,
                "w9_zelle_amount": 0.0, "w9_total": 0.0, "total": 0.0,
                "entries": 0,
            }
            by_officer[oid] = agg
        agg["w2_amount"] += r["w2_amount"]
        agg["w9_direct_deposit_amount"] += r["w9_direct_deposit_amount"]
        agg["w9_zelle_amount"] += r["w9_zelle_amount"]
        agg["w9_total"] += r["w9_total"]
        agg["total"] += r["total"]
        agg["entries"] += 1

    rows = list(by_officer.values())
    for r in rows:
        for k in ("w2_amount", "w9_direct_deposit_amount", "w9_zelle_amount", "w9_total", "total"):
            r[k] = round(r[k], 2)

    if search:
        s = search.lower()
        rows = [r for r in rows if s in str(r.get("officer_name") or "").lower()
                or s in str(r.get("social_security_code") or "").lower()
                or s in str(r.get("officer_address") or "").lower()]

    rows.sort(key=lambda r: str(r.get("officer_name") or "").lower())
    for i, r in enumerate(rows, start=1):
        r["sl"] = i

    totals = {
        "w2": round(sum(r["w2_amount"] for r in rows), 2),
        "w9_direct_deposit": round(sum(r["w9_direct_deposit_amount"] for r in rows), 2),
        "w9_zelle": round(sum(r["w9_zelle_amount"] for r in rows), 2),
        "w9_total": round(sum(r["w9_total"] for r in rows), 2),
        "grand_total": round(sum(r["total"] for r in rows), 2),
    }
    period = {
        "from": date_from or (min(all_dates) if all_dates else None),
        "to": date_to or (max(all_dates) if all_dates else None),
    }
    return {
        "client": _client_public(client),
        "rows": rows,
        "totals": totals,
        "period": period,
    }


@router.get("/records")
async def list_records(request: Request, db=Depends(get_db),
                       client_id: str = None, search: str = None,
                       date_from: str = None, date_to: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    if not client_id:
        raise HTTPException(422, "client_id is required")
    return await _client_context(db, client_id, search, date_from, date_to)


# =====================================================================
#  Officer detail — every dated entry for one officer
# =====================================================================
async def _officer_context(db, officer_id, date_from=None, date_to=None):
    snap = await _officer_snapshot(db, officer_id)
    client = None
    if snap.get("client_id"):
        try:
            client = await db.dispatch_clients.find_one({"_id": _oid(snap["client_id"])})
        except Exception:
            client = None
    client_out = _client_public(client) if client else {}

    docs = await db.dispatch_so_payment_records.find({"officer_id": officer_id}).to_list(10000)
    records = [_record_out(d) for d in docs]
    records = [r for r in records if _in_range(r.get("date"), date_from, date_to)]
    records.sort(key=lambda r: str(r.get("date") or ""))

    totals = {
        "w2": round(sum(r["w2_amount"] for r in records), 2),
        "w9_direct_deposit": round(sum(r["w9_direct_deposit_amount"] for r in records), 2),
        "w9_zelle": round(sum(r["w9_zelle_amount"] for r in records), 2),
        "w9_total": round(sum(r["w9_total"] for r in records), 2),
        "grand_total": round(sum(r["total"] for r in records), 2),
    }
    dates = [r.get("date") for r in records if r.get("date")]
    period = {
        "from": date_from or (min(dates) if dates else None),
        "to": date_to or (max(dates) if dates else None),
    }
    return {
        "client": client_out,
        "officer": {
            "id": snap["officer_id"], "name": snap["officer_name"],
            "officer_code": snap["officer_code"], "address": snap["officer_address"],
            "social_security_code": snap["social_security_code"],
        },
        "records": records,
        "totals": totals,
        "period": period,
    }


@router.get("/records/officer")
async def officer_records(request: Request, db=Depends(get_db), officer_id: str = None,
                          date_from: str = None, date_to: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    if not officer_id:
        raise HTTPException(422, "officer_id is required")
    return await _officer_context(db, officer_id, date_from, date_to)


@router.post("/records")
async def create_record(payload: PaymentRecordCreate, request: Request, db=Depends(get_db)):
    """Create a new dated payment entry for an officer."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    snap = await _officer_snapshot(db, payload.officer_id)
    if not snap.get("client_id"):
        raise HTTPException(400, "Security Officer has no Client assigned")
    doc = {
        **snap,
        "w2": payload.w2.model_dump(),
        "w9_direct_deposit": payload.w9_direct_deposit.model_dump(),
        "w9_zelle": payload.w9_zelle.model_dump(),
        "created_at": _now(),
        "created_by": str(user["_id"]),
        "created_by_name": user.get("name"),
        "updated_at": _now(),
    }
    res = await db.dispatch_so_payment_records.insert_one(doc)
    return _record_out(await db.dispatch_so_payment_records.find_one({"_id": res.inserted_id}))


@router.put("/records/{record_id}")
async def update_record(record_id: str, payload: PaymentRecordCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    existing = await db.dispatch_so_payment_records.find_one({"_id": _oid(record_id)})
    if not existing:
        raise HTTPException(404, "Record not found")
    upd = {
        "w2": payload.w2.model_dump(),
        "w9_direct_deposit": payload.w9_direct_deposit.model_dump(),
        "w9_zelle": payload.w9_zelle.model_dump(),
        "updated_at": _now(),
        "updated_by": str(user["_id"]),
        "updated_by_name": user.get("name"),
    }
    await db.dispatch_so_payment_records.update_one({"_id": _oid(record_id)}, {"$set": upd})
    return _record_out(await db.dispatch_so_payment_records.find_one({"_id": _oid(record_id)}))


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    r = await db.dispatch_so_payment_records.delete_one({"_id": _oid(record_id)})
    if r.deleted_count == 0:
        raise HTTPException(404, "Record not found")
    return {"message": "Record deleted"}


# =====================================================================
#  Exports
# =====================================================================
@router.get("/records/report/pdf")
async def client_report_pdf(request: Request, db=Depends(get_db),
                            client_id: str = None, search: str = None,
                            date_from: str = None, date_to: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    if not client_id:
        raise HTTPException(422, "client_id is required")
    ctx = await _client_context(db, client_id, search, date_from, date_to)
    from utils.dispatch_reports import build_client_payment_records_pdf
    pdf = build_client_payment_records_pdf(ctx=ctx)
    fname = f"Payment-{(ctx['client'].get('name') or 'client')}.pdf".replace(" ", "-")
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/records/report/xlsx")
async def client_report_xlsx(request: Request, db=Depends(get_db),
                             client_id: str = None, search: str = None,
                             date_from: str = None, date_to: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    if not client_id:
        raise HTTPException(422, "client_id is required")
    ctx = await _client_context(db, client_id, search, date_from, date_to)
    from utils.dispatch_reports import build_client_payment_records_xlsx
    xlsx = build_client_payment_records_xlsx(ctx=ctx)
    fname = f"Payment-{(ctx['client'].get('name') or 'client')}.xlsx".replace(" ", "-")
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/records/officer/report/pdf")
async def officer_report_pdf(request: Request, db=Depends(get_db), officer_id: str = None,
                             date_from: str = None, date_to: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    if not officer_id:
        raise HTTPException(422, "officer_id is required")
    ctx = await _officer_context(db, officer_id, date_from, date_to)
    from utils.dispatch_reports import build_officer_payment_records_pdf
    pdf = build_officer_payment_records_pdf(ctx=ctx)
    fname = f"Payment-{(ctx['officer'].get('name') or 'officer')}.pdf".replace(" ", "-")
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/records/officer/report/xlsx")
async def officer_report_xlsx(request: Request, db=Depends(get_db), officer_id: str = None,
                              date_from: str = None, date_to: str = None):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.payment_so.view")
    if not officer_id:
        raise HTTPException(422, "officer_id is required")
    ctx = await _officer_context(db, officer_id, date_from, date_to)
    from utils.dispatch_reports import build_officer_payment_records_xlsx
    xlsx = build_officer_payment_records_xlsx(ctx=ctx)
    fname = f"Payment-{(ctx['officer'].get('name') or 'officer')}.xlsx".replace(" ", "-")
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'})
