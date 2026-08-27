"""Dispatch client-to-vendor invoices — generate, preview, save, download.

An "invoice" summarises all Complete dispatch schedules between a given
Client (BILLING FROM) and Vendor (BILLING TO) inside a billing period. The
PDF layout matches the customer's Arseas Security mockup: yellow header bar,
BILLING FROM/TO columns, invoice metadata block, itemised table (Shift Date,
Location, Work Order, Actual Hour, Rate, Total Amount) and a footer with
"Thanks for business with us!".
"""
import io
import re
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from utils.auth import get_current_user
from utils.storage import to_public_url
from utils.permissions import has_permission, require_permission
from models.dispatch import DispatchInvoiceCreate, COMPLETED_STATUSES
from routes.dispatch import get_db  # reuse the same DB dependency

router = APIRouter(prefix="/dispatch/invoices", tags=["dispatch-invoices"])


def _now():
    return datetime.now(timezone.utc)


def _oid(x: str) -> ObjectId:
    if not ObjectId.is_valid(x):
        raise HTTPException(400, f"Invalid id {x!r}")
    return ObjectId(x)


def _doc_out(d: dict) -> dict:
    if not d:
        return {}
    d = dict(d)
    d["id"] = str(d.pop("_id"))
    return d


async def _gather_lines(db, client_id: str, vendor_id: str, date_from: str, date_to: str,
                        financial: bool, post_site_ids: list = None, vendor_code: str = None):
    """Fetch Complete schedules for the (client, vendor, period) triple and
    hydrate them with post-site info + row totals.

    ``post_site_ids`` (list) narrows to the given locations when supplied.
    ``vendor_code`` is the invoice-level vendor code used to build the
    ``pin_display`` field ("CODE # PIN") on each line.
    """
    schedule_query = {
        "client_id": client_id,
        "vendor_id": vendor_id,
        "date": {"$gte": date_from, "$lte": date_to},
        "shift_status": {"$in": COMPLETED_STATUSES},
    }
    ids = [pid for pid in (post_site_ids or []) if pid]
    if ids:
        schedule_query["post_site_id"] = {"$in": ids} if len(ids) > 1 else ids[0]
    schedules = await db.dispatch_schedules.find(schedule_query).sort("date", 1).to_list(2000)

    post_ids = list({s["post_site_id"] for s in schedules if s.get("post_site_id")})
    posts = {}
    if post_ids:
        obj_ids = [ObjectId(i) for i in post_ids if ObjectId.is_valid(i)]
        pdocs = await db.dispatch_post_sites.find(
            {"_id": {"$in": obj_ids}}, {"name": 1, "post_pin": 1, "location": 1, "city": 1}
        ).to_list(len(obj_ids))
        posts = {str(p["_id"]): p for p in pdocs}

    code = (vendor_code or "").strip()
    lines = []
    total_hours = 0.0
    total_amount = 0.0
    for s in schedules:
        p = posts.get(s.get("post_site_id", ""), {})
        actual = float(s.get("actual_duty_hours") or s.get("duty_hours") or 0)
        rate = float(s.get("billing_rate") or 0)
        line_total = round(actual * rate, 2)
        location = p.get("name") or p.get("location") or p.get("city") or "—"
        pin = p.get("post_pin")
        # Post pin is not shown on the invoice itself anymore — keep the raw
        # value on the line for reference / audit but don't build pin_display.
        pin_display = None
        lines.append({
            "schedule_id": str(s["_id"]),
            "shift_date": s.get("date"),
            "location": location,
            "post_pin": pin,
            "pin_display": pin_display,
            "post_site_name": p.get("name"),
            "work_order": s.get("work_order_number") or "—",
            "actual_hours": round(actual, 2),
            "rate": rate if financial else None,
            "total_amount": line_total if financial else None,
        })
        total_hours += actual
        total_amount += line_total
    return lines, round(total_hours, 2), round(total_amount, 2)


def _amount_in_words(amount: float) -> str:
    """Convert a USD amount to a natural English 'in-words' string."""
    from decimal import Decimal, ROUND_HALF_UP

    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    n = int(value)
    cents = int((value - Decimal(n)) * 100)

    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]

    tens = [
        "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty",
        "Seventy", "Eighty", "Ninety"
    ]

    def two(m):
        if m < 20:
            return ones[m]
        t, r = divmod(m, 10)
        return tens[t] + (" " + ones[r] if r else "")

    def three(m):
        h, r = divmod(m, 100)
        s = ""

        if h:
            s += ones[h] + " Hundred"
            if r:
                s += " & "

        if r:
            s += two(r)

        return s

    if n == 0:
        base = "Zero"
    else:
        parts = []

        for scale, name in [
            (1_000_000, "Million"),
            (1_000, "Thousand"),
            (1, "")
        ]:
            q, n = divmod(n, scale)

            if q:
                parts.append(
                    three(q) + ((" " + name) if name else "")
                )

        base = " ".join(parts)

    dollars = f"{base} Dollar" + ("s" if value != 1 else "")

    if cents:
        dollars += f" & {two(cents)} Cent" + ("s" if cents != 1 else "")

    return dollars + "."


async def _build_invoice_context(db, payload_client_id, payload_vendor_id,
                                 date_from, date_to, financial, post_site_ids=None,
                                 override_lines=None):
    """Build the full invoice context.

    When ``override_lines`` is provided (e.g. from the customise screen) it
    is used verbatim after re-computing per-line totals + grand totals so the
    ``amount_in_words`` matches what the user actually saved. Otherwise the
    lines are aggregated from schedules the usual way.
    """
    client = await db.dispatch_clients.find_one({"_id": _oid(payload_client_id)})
    if not client:
        raise HTTPException(404, "Client not found")
    vendor = await db.dispatch_vendors.find_one({"_id": _oid(payload_vendor_id)})
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    if override_lines is not None:
        lines = []
        total_hours = 0.0
        total_amount = 0.0
        code = (vendor.get("code") or "").strip()
        for raw in override_lines:
            ln = dict(raw) if isinstance(raw, dict) else raw.dict()
            hrs = float(ln.get("actual_hours") or 0)
            rate = float(ln.get("rate") or 0) if financial else None
            # Always recompute the row total from hours × rate — trusting the
            # client-supplied total_amount would let users craft an invoice
            # whose lines don't add up to the totals row.
            row_total = round(hrs * (rate or 0), 2) if financial else None
            ln["actual_hours"] = round(hrs, 2)
            ln["rate"] = rate
            ln["total_amount"] = row_total
            # Post pin is intentionally not shown on invoices — drop any
            # pin_display that might have been round-tripped from the UI.
            ln["pin_display"] = None
            lines.append(ln)
            total_hours += hrs
            if row_total is not None:
                total_amount += row_total
        total_hours = round(total_hours, 2)
        total_amount = round(total_amount, 2) if financial else None
    else:
        lines, total_hours, total_amount = await _gather_lines(
            db, payload_client_id, payload_vendor_id, date_from, date_to, financial, post_site_ids,
            vendor_code=vendor.get("code"),
        )
    client_out = _doc_out(client)
    vendor_out = _doc_out(vendor)
    if client_out.get("logo_path"):
        client_out["logo_url"] = to_public_url(client_out["logo_path"])
    return {
        "client": client_out,
        "vendor": vendor_out,
        "lines": lines,
        "total_hours": total_hours,
        "total_amount": total_amount if financial else None,
        "amount_in_words": _amount_in_words(total_amount) if financial and total_amount is not None else None,
    }


def _payload_site_ids(payload: DispatchInvoiceCreate) -> list:
    """Return the list of post_site_ids from either the new multi-select
    field or the legacy single-site field (backwards-compat)."""
    if payload.post_site_ids:
        return [p for p in payload.post_site_ids if p]
    if payload.post_site_id:
        return [payload.post_site_id]
    return []


@router.post("/preview")
async def preview_invoice(payload: DispatchInvoiceCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    financial = has_permission(user, "dispatch.financial.view")
    site_ids = _payload_site_ids(payload)
    ctx = await _build_invoice_context(
        db, payload.client_id, payload.vendor_id,
        payload.billing_period_from, payload.billing_period_to, financial, site_ids,
        override_lines=payload.lines,
    )
    return {
        **ctx,
        "invoice_number": payload.invoice_number,
        "invoice_date": payload.invoice_date,
        "billing_period_from": payload.billing_period_from,
        "billing_period_to": payload.billing_period_to,
        "post_site_id": payload.post_site_id,
        "post_site_ids": site_ids,
        "notes": payload.notes,
    }


@router.post("")
async def create_invoice(payload: DispatchInvoiceCreate, request: Request, db=Depends(get_db)):
    """Save the invoice record and link it to the underlying schedule ids."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.export")
    financial = has_permission(user, "dispatch.financial.view")
    if not financial:
        raise HTTPException(403, "Financial permission required to create invoices")

    # Reject duplicate invoice numbers so an admin can safely re-open the
    # dialog without silently creating a second row.
    existing = await db.dispatch_invoices.find_one({"invoice_number": payload.invoice_number})
    if existing:
        raise HTTPException(400, f"Invoice #{payload.invoice_number} already exists")

    site_ids = _payload_site_ids(payload)
    ctx = await _build_invoice_context(
        db, payload.client_id, payload.vendor_id,
        payload.billing_period_from, payload.billing_period_to, financial, site_ids,
        override_lines=payload.lines,
    )
    doc = {
        "invoice_number": payload.invoice_number,
        "invoice_date": payload.invoice_date,
        "billing_period_from": payload.billing_period_from,
        "billing_period_to": payload.billing_period_to,
        "client_id": payload.client_id,
        "vendor_id": payload.vendor_id,
        "post_site_id": payload.post_site_id,
        "post_site_ids": site_ids,
        "client_snapshot": ctx["client"],
        "vendor_snapshot": ctx["vendor"],
        "lines": ctx["lines"],
        "total_hours": ctx["total_hours"],
        "total_amount": ctx["total_amount"],
        "amount_in_words": ctx["amount_in_words"],
        "schedule_ids": [ln["schedule_id"] for ln in ctx["lines"] if ln.get("schedule_id")],
        "notes": payload.notes,
        "created_at": _now(),
        "created_by_id": str(user["_id"]),
        "created_by_name": user.get("name"),
    }
    try:
        r = await db.dispatch_invoices.insert_one(doc)
    except Exception as e:
        # Catch the DB-level unique-index race so two concurrent saves can't
        # both succeed with the same auto-number.
        from pymongo.errors import DuplicateKeyError
        if isinstance(e, DuplicateKeyError):
            raise HTTPException(400, f"Invoice #{payload.invoice_number} already exists")
        raise
    doc["_id"] = r.inserted_id
    return _doc_out(doc)


@router.put("/{inv_id}")
async def update_invoice(inv_id: str, payload: DispatchInvoiceCreate, request: Request, db=Depends(get_db)):
    """Update an existing invoice (details + line items) and recompute totals."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.export")
    financial = has_permission(user, "dispatch.financial.view")
    if not financial:
        raise HTTPException(403, "Financial permission required to edit invoices")

    existing = await db.dispatch_invoices.find_one({"_id": _oid(inv_id)})
    if not existing:
        raise HTTPException(404, "Invoice not found")

    dup = await db.dispatch_invoices.find_one({
        "invoice_number": payload.invoice_number,
        "_id": {"$ne": _oid(inv_id)},
    })
    if dup:
        raise HTTPException(400, f"Invoice #{payload.invoice_number} already exists")

    site_ids = _payload_site_ids(payload)
    ctx = await _build_invoice_context(
        db, payload.client_id, payload.vendor_id,
        payload.billing_period_from, payload.billing_period_to, financial, site_ids,
        override_lines=payload.lines,
    )
    update = {
        "invoice_number": payload.invoice_number,
        "invoice_date": payload.invoice_date,
        "billing_period_from": payload.billing_period_from,
        "billing_period_to": payload.billing_period_to,
        "client_id": payload.client_id,
        "vendor_id": payload.vendor_id,
        "post_site_id": payload.post_site_id,
        "post_site_ids": site_ids,
        "client_snapshot": ctx["client"],
        "vendor_snapshot": ctx["vendor"],
        "lines": ctx["lines"],
        "total_hours": ctx["total_hours"],
        "total_amount": ctx["total_amount"],
        "amount_in_words": ctx["amount_in_words"],
        "schedule_ids": [ln["schedule_id"] for ln in ctx["lines"] if ln.get("schedule_id")],
        "notes": payload.notes,
        "updated_at": _now(),
        "updated_by_id": str(user["_id"]),
        "updated_by_name": user.get("name"),
    }
    await db.dispatch_invoices.update_one({"_id": _oid(inv_id)}, {"$set": update})
    doc = await db.dispatch_invoices.find_one({"_id": _oid(inv_id)})
    return _doc_out(doc)


@router.get("")
async def list_invoices(
    request: Request,
    db=Depends(get_db),
    client_id: str = None,
    vendor_id: str = None,
    post_site_id: str = None,
    date_from: str = None,
    date_to: str = None,
    invoice_number: str = None,
    skip: int = 0,
    limit: int = 50,
):
    """List saved invoices with server-side filters.

    Supported filters:
      - client_id
      - vendor_id
      - post_site_id
      - date_from / date_to: invoice_date range
      - invoice_number: case-insensitive partial AJAX search
    """
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")

    q = {}

    if client_id:
        q["client_id"] = client_id

    if vendor_id:
        q["vendor_id"] = vendor_id

    if post_site_id:
        # post_site_ids is the canonical field on newer invoices.
        # The $or also supports older invoices that only have post_site_id.
        q["$or"] = [
            {"post_site_ids": post_site_id},
            {"post_site_id": post_site_id},
        ]

    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to
        q["invoice_date"] = date_query

    if invoice_number:
        # Escape user input so it is treated as plain search text.
        # Case-insensitive partial matching gives AJAX-style searching.
        q["invoice_number"] = {
            "$regex": re.escape(invoice_number.strip()),
            "$options": "i",
        }

    total = await db.dispatch_invoices.count_documents(q)

    docs = await (
        db.dispatch_invoices
        .find(q)
        .sort("invoice_date", -1)
        .skip(max(skip, 0))
        .limit(min(max(limit, 1), 200))
        .to_list(min(max(limit, 1), 200))
    )

    return {
        "items": [_doc_out(d) for d in docs],
        "total": total,
        "filters": {
            "client_id": client_id,
            "vendor_id": vendor_id,
            "post_site_id": post_site_id,
            "date_from": date_from,
            "date_to": date_to,
            "invoice_number": invoice_number,
        },
    }


@router.get("/locations")
async def list_invoice_locations(request: Request, db=Depends(get_db),
                                 client_id: str = None, vendor_id: str = None,
                                 date_from: str = None, date_to: str = None):
    """Return locations used by schedules matching the current invoice filters."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    query = {"shift_status": {"$in": COMPLETED_STATUSES}}
    if client_id:
        query["client_id"] = client_id
    if vendor_id:
        query["vendor_id"] = vendor_id
    if date_from or date_to:
        date_query = {}
        if date_from:
            date_query["$gte"] = date_from
        if date_to:
            date_query["$lte"] = date_to
        query["date"] = date_query

    schedules = await db.dispatch_schedules.find(query, {"post_site_id": 1}).to_list(5000)
    post_ids = {s.get("post_site_id") for s in schedules if s.get("post_site_id")}
    obj_ids = [ObjectId(pid) for pid in post_ids if ObjectId.is_valid(pid)]
    if not obj_ids:
        return []
    posts = await db.dispatch_post_sites.find(
        {"_id": {"$in": obj_ids}},
        {"name": 1, "post_pin": 1, "location": 1, "city": 1},
    ).to_list(len(obj_ids))
    options = []
    for post in posts:
        options.append({
            "id": str(post["_id"]),
            "name": post.get("name"),
            "post_pin": post.get("post_pin"),
            "location": post.get("location"),
            "city": post.get("city"),
        })
    return sorted(options, key=lambda p: (p.get("location") or p.get("city") or p.get("name") or "").lower())


@router.get("/next-number")
async def next_invoice_number(request: Request, db=Depends(get_db)):
    """Return the next auto-generated invoice number (starts at 5250).

    Handles invoice_number strings with alpha prefixes / suffixes such as
    ``INV-5301`` or ``#5330-A`` by extracting the largest embedded integer.
    """
    import re
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    START = 5250
    max_num = START - 1
    async for row in db.dispatch_invoices.find({}, {"invoice_number": 1}):
        raw = str(row.get("invoice_number") or "")
        for chunk in re.findall(r"\d+", raw):
            try:
                n = int(chunk)
                if n > max_num:
                    max_num = n
            except ValueError:
                pass
    return {"invoice_number": str(max(max_num + 1, START))}


@router.get("/{inv_id}")
async def get_invoice(inv_id: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    doc = await db.dispatch_invoices.find_one({"_id": _oid(inv_id)})
    if not doc:
        raise HTTPException(404, "Invoice not found")
    return _doc_out(doc)


@router.get("/{inv_id}/pdf")
async def download_invoice_pdf(inv_id: str, request: Request, db=Depends(get_db), inline: bool = False):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    doc = await db.dispatch_invoices.find_one({"_id": _oid(inv_id)})
    if not doc:
        raise HTTPException(404, "Invoice not found")
    from utils.dispatch_reports import build_invoice_pdf
    client_snap = doc.get("client_snapshot") or {}
    pdf = build_invoice_pdf(
        client=client_snap,
        vendor=doc["vendor_snapshot"],
        invoice_number=doc["invoice_number"],
        invoice_date=doc["invoice_date"],
        billing_period_from=doc["billing_period_from"],
        billing_period_to=doc["billing_period_to"],
        lines=doc["lines"],
        total_hours=doc["total_hours"],
        total_amount=doc["total_amount"],
        amount_in_words=doc["amount_in_words"],
        accent_color=client_snap.get("accent_color"),
    )
    disp = "inline" if inline else "attachment"
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'{disp}; filename="Invoice-{doc["invoice_number"]}.pdf"'})


@router.post("/preview/pdf")
async def preview_invoice_pdf(payload: DispatchInvoiceCreate, request: Request, db=Depends(get_db)):
    """Stream a PDF without saving — used by the Preview → Download flow."""
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.view")
    financial = has_permission(user, "dispatch.financial.view")
    site_ids = _payload_site_ids(payload)
    ctx = await _build_invoice_context(
        db, payload.client_id, payload.vendor_id,
        payload.billing_period_from, payload.billing_period_to, financial, site_ids,
        override_lines=payload.lines,
    )
    from utils.dispatch_reports import build_invoice_pdf
    pdf = build_invoice_pdf(
        client=ctx["client"], vendor=ctx["vendor"],
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        billing_period_from=payload.billing_period_from,
        billing_period_to=payload.billing_period_to,
        lines=ctx["lines"],
        total_hours=ctx["total_hours"],
        total_amount=ctx["total_amount"] or 0,
        amount_in_words=ctx["amount_in_words"] or "",
        accent_color=(ctx["client"] or {}).get("accent_color"),
    )
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Invoice-{payload.invoice_number}.pdf"'})


@router.delete("/{inv_id}")
async def delete_invoice(inv_id: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.reports.export")
    r = await db.dispatch_invoices.delete_one({"_id": _oid(inv_id)})
    if r.deleted_count == 0:
        raise HTTPException(404, "Invoice not found")
    return {"message": "Invoice deleted"}
