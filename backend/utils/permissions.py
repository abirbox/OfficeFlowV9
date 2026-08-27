"""Permission infrastructure for OfficeFlow (extends existing role-based auth).

Roles: super_admin, admin, hr, manager, hd, employee
- super_admin: bypasses ALL permission checks
- hd: bypasses ALL dispatch.* permission checks (Head of Dispatch)
- everyone else: must have explicit permissions[]

Backward-compatible: users without a `permissions` field are treated as having [].
"""
from fastapi import HTTPException, Request
from typing import List, Optional

# ----- Permission code registry (Dispatch module) -----
DISPATCH_PERMISSIONS = {
    "dispatch.dashboard": ["view"],
    "dispatch.schedule": ["view", "create", "edit", "cancel", "delete"],
    "dispatch.clients": ["view", "create", "edit", "delete"],
    "dispatch.vendors": ["view", "create", "edit", "delete"],
    "dispatch.officers": ["view", "create", "edit", "delete"],
    "dispatch.payment_so": ["view"],
    "dispatch.post_sites": ["view", "create", "edit", "delete"],
    "dispatch.confirmation": ["view", "manage", "history"],
    "dispatch.reports": ["view", "export"],
    "dispatch.financial": ["view", "adjust"],
    "dispatch.billing": ["view"],
    "dispatch.audit": ["view"],
}

# Flat list of all valid permission codes
ALL_PERMISSIONS: List[str] = [
    f"{group}.{action}"
    for group, actions in DISPATCH_PERMISSIONS.items()
    for action in actions
]

# Sensitive Dispatch financial fields — stripped from responses unless perm
FINANCIAL_FIELDS = ("duty_rate", "billing_rate", "work_order_number")


def has_permission(user: dict, code: str) -> bool:
    """Check whether the given user has the given permission code."""
    if not user:
        return False
    role = user.get("role", "employee")
    if role == "super_admin":
        return True
    # HD has full Dispatch access
    if role == "hd" and code.startswith("dispatch."):
        return True
    perms = user.get("permissions") or []
    return code in perms


def user_has_any_dispatch_perm(user: dict) -> bool:
    if not user:
        return False
    role = user.get("role", "employee")
    if role in ("super_admin", "hd"):
        return True
    perms = user.get("permissions") or []
    return any(p.startswith("dispatch.") for p in perms)


def require_permission(user: dict, code: str):
    """Raise 403 if user lacks the given permission."""
    if not has_permission(user, code):
        raise HTTPException(
            status_code=403,
            detail=f"You do not have permission ({code}) to perform this action.",
        )


def strip_financial(doc: dict, user: dict) -> dict:
    """Return a copy of the doc with financial fields removed if user lacks perm."""
    if has_permission(user, "dispatch.financial.view"):
        return doc
    clean = dict(doc)
    for f in FINANCIAL_FIELDS:
        clean.pop(f, None)
    return clean


def validate_permission_codes(codes: Optional[List[str]]) -> List[str]:
    """Filter to only known permission codes."""
    if not codes:
        return []
    return [c for c in codes if c in ALL_PERMISSIONS]
