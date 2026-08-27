#!/usr/bin/env python3
"""
Backend test for OfficeFlow Dispatch payslip deduction decoupling.

Tests the REVISED behavior where manual deductions are plain net-pay reducers,
UNRELATED to advances. No cap. They do NOT touch the advance ledger.
Advances have ZERO effect on net pay.
"""

import requests
import sys
import json

# Backend URL from frontend/.env
BACKEND_URL = "https://git-preview-build-1.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"


def log(msg):
    """Print test progress."""
    print(f"[TEST] {msg}")


def fail(msg):
    """Print failure and exit."""
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main():
    log("Starting backend test for payslip deduction decoupling...")
    
    # Create a session to preserve cookies
    session = requests.Session()
    
    # ========================================================================
    # STEP 1: Authenticate
    # ========================================================================
    log("Step 1: Authenticating as admin...")
    auth_resp = session.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30
    )
    if auth_resp.status_code != 200:
        fail(f"Auth failed: {auth_resp.status_code} {auth_resp.text}")
    log(f"✓ Authenticated successfully")
    
    # ========================================================================
    # STEP 2: Setup - Create/find dispatch client and officer
    # ========================================================================
    log("Step 2: Setting up test client and officer...")
    
    # Create a test client
    client_resp = session.post(
        f"{BACKEND_URL}/dispatch/clients",
        json={
            "name": "Test Client Deduction Decoupling",
            "code": "TESTDC",
            "status": "active"
        },
        timeout=30
    )
    if client_resp.status_code != 200:
        fail(f"Client creation failed: {client_resp.status_code} {client_resp.text}")
    client_data = client_resp.json()
    client_id = client_data["id"]
    log(f"✓ Created test client: {client_id}")
    
    # Create a test officer linked to this client
    officer_resp = session.post(
        f"{BACKEND_URL}/dispatch/officers",
        json={
            "name": "Test Officer Deduction",
            "client_id": client_id,
            "type": "Unarmed",
            "status": "active",
            "contact_number": "1234567890"
        },
        timeout=30
    )
    if officer_resp.status_code != 200:
        fail(f"Officer creation failed: {officer_resp.status_code} {officer_resp.text}")
    officer_data = officer_resp.json()
    officer_id = officer_data["id"]
    log(f"✓ Created test officer: {officer_id}")
    
    # ========================================================================
    # STEP 3: Create an advance of $1000
    # ========================================================================
    log("Step 3: Creating advance of $1000...")
    advance_resp = session.post(
        f"{BACKEND_URL}/dispatch/advance-salary",
        json={
            "officer_id": officer_id,
            "client_id": client_id,
            "type": "advance",
            "amount": 1000,
            "entry_date": "2026-08-20"
        },
        timeout=30
    )
    if advance_resp.status_code != 200:
        fail(f"Advance creation failed: {advance_resp.status_code} {advance_resp.text}")
    advance_data = advance_resp.json()
    log(f"✓ Created advance: balance_after={advance_data.get('balance_after')}")
    
    # ========================================================================
    # STEP 4: Verify initial advance balance
    # ========================================================================
    log("Step 4: Verifying initial advance balance...")
    adv_get_resp = session.get(
        f"{BACKEND_URL}/dispatch/advance-salary",
        params={
            "officer_id": officer_id,
            "client_id": client_id
        },
        timeout=30
    )
    if adv_get_resp.status_code != 200:
        fail(f"Get advance failed: {adv_get_resp.status_code} {adv_get_resp.text}")
    adv_data = adv_get_resp.json()
    
    initial_balance = adv_data.get("remaining_balance")
    initial_repaid = adv_data.get("total_repaid")
    initial_entries_count = len(adv_data.get("entries", []))
    
    log(f"✓ Initial state: remaining_balance={initial_balance}, total_repaid={initial_repaid}, entries_count={initial_entries_count}")
    
    if initial_balance != 1000:
        fail(f"Expected initial balance 1000, got {initial_balance}")
    if initial_repaid != 0:
        fail(f"Expected initial repaid 0, got {initial_repaid}")
    
    # ========================================================================
    # STEP 5: Test deduction does NOT affect advance balance & NO cap
    # ========================================================================
    log("Step 5: Testing deduction of $5000 (> advance balance) - should be accepted with NO cap...")
    
    date_from = "2026-08-18"
    date_to = "2026-08-26"
    
    # PUT a deduction of $5000 (larger than $1000 advance)
    # Expected: HTTP 200 (NO 400), deduction saved, advance balance UNCHANGED
    deduction_resp = session.put(
        f"{BACKEND_URL}/dispatch/payslip-adjustment",
        params={
            "officer_id": officer_id,
            "client_id": client_id,
            "date_from": date_from,
            "date_to": date_to
        },
        json={
            "extra_payments": [],
            "deductions": [
                {
                    "date": "2026-08-22",
                    "purpose": "Uniform",
                    "amount": 5000
                }
            ]
        },
        timeout=30
    )
    
    if deduction_resp.status_code != 200:
        fail(f"Deduction PUT failed (expected 200): {deduction_resp.status_code} {deduction_resp.text}")
    
    deduction_data = deduction_resp.json()
    saved_deductions = deduction_data.get("deductions", [])
    log(f"✓ Deduction saved: {saved_deductions}")
    
    if len(saved_deductions) != 1:
        fail(f"Expected 1 deduction saved, got {len(saved_deductions)}")
    if saved_deductions[0].get("amount") != 5000:
        fail(f"Expected deduction amount 5000, got {saved_deductions[0].get('amount')}")
    
    # ========================================================================
    # STEP 6: Verify advance balance is STILL 1000 (unchanged)
    # ========================================================================
    log("Step 6: Verifying advance balance is STILL 1000 (deduction did NOT change it)...")
    
    adv_get_resp2 = session.get(
        f"{BACKEND_URL}/dispatch/advance-salary",
        params={
            "officer_id": officer_id,
            "client_id": client_id
        },
        timeout=30
    )
    if adv_get_resp2.status_code != 200:
        fail(f"Get advance failed: {adv_get_resp2.status_code} {adv_get_resp2.text}")
    adv_data2 = adv_get_resp2.json()
    
    balance_after_deduction = adv_data2.get("remaining_balance")
    repaid_after_deduction = adv_data2.get("total_repaid")
    entries_after_deduction = adv_data2.get("entries", [])
    
    log(f"✓ After deduction: remaining_balance={balance_after_deduction}, total_repaid={repaid_after_deduction}, entries_count={len(entries_after_deduction)}")
    
    if balance_after_deduction != 1000:
        fail(f"CRITICAL: Advance balance changed! Expected 1000, got {balance_after_deduction}")
    if repaid_after_deduction != 0:
        fail(f"CRITICAL: total_repaid changed! Expected 0, got {repaid_after_deduction}")
    
    # Verify no new ledger entries were created by the deduction
    if len(entries_after_deduction) != initial_entries_count:
        fail(f"CRITICAL: Ledger entries changed! Expected {initial_entries_count}, got {len(entries_after_deduction)}")
    
    log("✓ PASS: Deduction did NOT affect advance balance or create ledger entries")
    
    # ========================================================================
    # STEP 7: Verify net pay math (advances have zero effect)
    # ========================================================================
    log("Step 7: Verifying net pay calculation (advances have ZERO effect)...")
    
    entity_detail_resp = session.get(
        f"{BACKEND_URL}/dispatch/reports/entity-detail",
        params={
            "entity_type": "officer",
            "entity_id": officer_id,
            "client_id": client_id,
            "date_from": date_from,
            "date_to": date_to
        },
        timeout=30
    )
    if entity_detail_resp.status_code != 200:
        fail(f"Entity detail failed: {entity_detail_resp.status_code} {entity_detail_resp.text}")
    
    detail_data = entity_detail_resp.json()
    
    deductions_in_report = detail_data.get("deductions", [])
    deductions_total = detail_data.get("deductions_total", 0)
    net_payment = detail_data.get("net_payment")
    summary = detail_data.get("summary", {})
    total_amount = summary.get("total_amount", 0)
    extra_payments_total = detail_data.get("extra_payments_total", 0)
    
    log(f"✓ Report data: deductions={deductions_in_report}, deductions_total={deductions_total}")
    log(f"✓ Report data: total_amount={total_amount}, extra_payments_total={extra_payments_total}, net_payment={net_payment}")
    
    # Verify deductions are present
    if len(deductions_in_report) != 1:
        fail(f"Expected 1 deduction in report, got {len(deductions_in_report)}")
    if deductions_in_report[0].get("purpose") != "Uniform":
        fail(f"Expected deduction purpose 'Uniform', got {deductions_in_report[0].get('purpose')}")
    if deductions_total != 5000:
        fail(f"Expected deductions_total 5000, got {deductions_total}")
    
    # Verify net payment calculation: net = total_amount + extra_payments_total - deductions_total
    # Advances (taken/repaid) should have ZERO effect
    expected_net = round(total_amount + extra_payments_total - deductions_total, 2)
    
    if net_payment != expected_net:
        fail(f"CRITICAL: Net payment calculation wrong! Expected {expected_net}, got {net_payment}")
    
    log(f"✓ PASS: Net payment = {net_payment} (correct: total_amount + extra - deductions, advances have zero effect)")
    
    # ========================================================================
    # STEP 8: Verify advance ledger is still independent
    # ========================================================================
    log("Step 8: Testing advance ledger independence - creating manual repayment...")
    
    # POST a manual repayment of $300
    repayment_resp = session.post(
        f"{BACKEND_URL}/dispatch/advance-salary",
        json={
            "officer_id": officer_id,
            "client_id": client_id,
            "type": "repayment",
            "amount": 300,
            "entry_date": "2026-08-23"
        },
        timeout=30
    )
    if repayment_resp.status_code != 200:
        fail(f"Repayment creation failed: {repayment_resp.status_code} {repayment_resp.text}")
    
    repayment_data = repayment_resp.json()
    log(f"✓ Created manual repayment: balance_after={repayment_data.get('balance_after')}")
    
    # Verify advance balance is now 700 (1000 - 300)
    adv_get_resp3 = session.get(
        f"{BACKEND_URL}/dispatch/advance-salary",
        params={
            "officer_id": officer_id,
            "client_id": client_id
        },
        timeout=30
    )
    if adv_get_resp3.status_code != 200:
        fail(f"Get advance failed: {adv_get_resp3.status_code} {adv_get_resp3.text}")
    adv_data3 = adv_get_resp3.json()
    
    final_balance = adv_data3.get("remaining_balance")
    final_repaid = adv_data3.get("total_repaid")
    final_entries = adv_data3.get("entries", [])
    
    log(f"✓ After manual repayment: remaining_balance={final_balance}, total_repaid={final_repaid}, entries_count={len(final_entries)}")
    
    if final_balance != 700:
        fail(f"Expected balance 700 after repayment, got {final_balance}")
    if final_repaid != 300:
        fail(f"Expected total_repaid 300, got {final_repaid}")
    
    # Verify entries list contains advance and manual repayment, but NOT the payslip deduction
    # Expected: 2 entries (1 advance + 1 manual repayment)
    if len(final_entries) != 2:
        fail(f"Expected 2 visible entries (advance + manual repayment), got {len(final_entries)}")
    
    # Check that no entry has source='payslip_deduction'
    for entry in final_entries:
        if entry.get("source") == "payslip_deduction":
            fail(f"CRITICAL: Found payslip_deduction entry in visible entries list!")
    
    log("✓ PASS: Advance ledger is independent, no payslip_deduction entries visible")
    
    # ========================================================================
    # STEP 9: Test payslip PDF export
    # ========================================================================
    log("Step 9: Testing payslip PDF export...")
    
    pdf_resp = session.get(
        f"{BACKEND_URL}/dispatch/reports/export/entity-detail",
        params={
            "entity_type": "officer",
            "entity_id": officer_id,
            "client_id": client_id,
            "date_from": date_from,
            "date_to": date_to,
            "format": "pdf",
            "template": "payslip"
        },
        timeout=30
    )
    
    if pdf_resp.status_code != 200:
        fail(f"PDF export failed: {pdf_resp.status_code} {pdf_resp.text}")
    
    content_type = pdf_resp.headers.get("content-type", "")
    if "application/pdf" not in content_type:
        fail(f"Expected content-type application/pdf, got {content_type}")
    
    pdf_body = pdf_resp.content
    if len(pdf_body) == 0:
        fail("PDF body is empty")
    
    # Check PDF magic bytes
    if not pdf_body.startswith(b"%PDF"):
        fail("PDF body does not start with %PDF magic bytes")
    
    log(f"✓ PASS: PDF export successful, size={len(pdf_body)} bytes, content-type={content_type}")
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    log("Cleaning up test data...")
    
    # Delete officer
    session.delete(f"{BACKEND_URL}/dispatch/officers/{officer_id}", timeout=30)
    
    # Delete client
    session.delete(f"{BACKEND_URL}/dispatch/clients/{client_id}", timeout=30)
    
    log("✓ Cleanup complete")
    
    # ========================================================================
    # ALL TESTS PASSED
    # ========================================================================
    print("\n" + "="*70)
    print("✅ ALL BACKEND TESTS PASSED")
    print("="*70)
    print("\nVerified:")
    print("  1. Deductions have NO cap (accepted $5000 deduction > $1000 advance)")
    print("  2. Deductions do NOT affect advance balance (remained 1000)")
    print("  3. Deductions do NOT create advance ledger entries")
    print("  4. Net pay = total_amount + extra - deductions (advances have ZERO effect)")
    print("  5. Advance ledger is independent (manual repayment works correctly)")
    print("  6. Payslip PDF export works (HTTP 200, valid PDF)")
    print("\nDeductions are now fully decoupled from the advance ledger! ✓")
    print("="*70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        fail(f"Unexpected error: {e}")
