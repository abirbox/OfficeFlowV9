"""Unit-level check: build_invoice_pdf renders the requested accent colour.

Scans the PDF for Flate streams, inflates them and looks for the RGB colour
operators (`r g b rg/RG`) that should match the accent colour.
"""
import base64
import re
import sys
import zlib

sys.path.insert(0, "/app/backend")
from utils.dispatch_reports import build_invoice_pdf  # noqa: E402

LINES = [{"shift_date": "2026-07-02", "location": "TESTLOC", "work_order": "WO1",
          "actual_hours": 8.0, "rate": 30.0, "total_amount": 240.0}]


def colours(accent):
    pdf = build_invoice_pdf(client={"name": "TEST_C"}, vendor={"name": "TEST_V"},
                            invoice_number="9999", invoice_date="2026-07-31",
                            billing_period_from="2026-07-01", billing_period_to="2026-07-31",
                            lines=LINES, total_hours=8.0, total_amount=240.0,
                            amount_in_words="Two Hundred & Forty Dollars.", accent_color=accent)
    assert pdf.startswith(b"%PDF-")
    blobs = []
    for m in re.finditer(rb"stream[\r\n]{1,2}", pdf):
        start = m.end()
        end = pdf.find(b"endstream", start)
        raw = pdf[start:end]
        data = raw
        try:
            data = base64.a85decode(raw.strip(), adobe=True)
        except Exception:
            pass
        try:
            data = zlib.decompress(data)
        except Exception:
            pass
        blobs.append(data)
    found = set()
    for b in blobs:
        for c in re.finditer(rb"([\d.]+) ([\d.]+) ([\d.]+) (rg|RG)", b):
            found.add(tuple(round(float(x), 2) for x in c.groups()[:3]))
    return found


GOLD = (0.83, 0.63, 0.09)
for accent, expect in [("#3B82F6", (0.23, 0.51, 0.96)), (None, GOLD), ("bogus", GOLD), ("", GOLD)]:
    got = colours(accent)
    hit = any(all(abs(g[i] - expect[i]) < 0.03 for i in range(3)) for g in got)
    print(f"accent={accent!r}: expected~{expect} present={hit} | colours={sorted(got)}")
