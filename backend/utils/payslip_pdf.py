"""Payslip PDF generation reused across email and download endpoints."""
from io import BytesIO
from datetime import datetime, timezone
from bson import ObjectId

from utils.tz import dhaka_today


async def build_payslip_pdf(db, record: dict) -> tuple[bytes, str]:
    """Return (pdf_bytes, invoice_no) for a payroll record dict."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    try:
        emp = await db.users.find_one({"_id": ObjectId(record["user_id"])}, {"password_hash": 0})
    except Exception:
        emp = None
    settings = await db.app_settings.find_one({"key": "app_settings_singleton"}, {"_id": 0}) or {}
    brand = settings.get("brand_name", "OfficeFlow")
    currency_symbol = settings.get("currency_symbol", "৳")
    currency_code = settings.get("currency", "BDT")

    company = None
    if emp and emp.get("company_id"):
        company = await db.companies.find_one({"id": emp["company_id"]}, {"_id": 0})

    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    period = f"{months[record['month']]} {record['year']}"
    invoice_no = f"PAY-{record['year']}{record['month']:02d}-{record['id'][:8].upper()}"

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='H1c', parent=styles['Title'], textColor=colors.HexColor('#4F46E5'), alignment=0, fontSize=22))
    styles.add(ParagraphStyle(name='Muted', parent=styles['Normal'], textColor=colors.HexColor('#64748B'), fontSize=9))
    styles.add(ParagraphStyle(name='LabelR', parent=styles['Normal'], textColor=colors.HexColor('#64748B'), fontSize=10, alignment=2))
    styles.add(ParagraphStyle(name='ValueR', parent=styles['Normal'], fontSize=11, alignment=2))

    story = []
    header = Table([[
        Paragraph(f"<b>{brand}</b>", styles['H1c']),
        Paragraph(f"<b>PAYSLIP</b><br/><font size=9 color='#64748B'>Invoice #{invoice_no}</font>", styles['LabelR']),
    ]], colWidths=[100 * mm, 70 * mm])
    header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 12)]))
    story.append(header)
    story.append(Spacer(1, 6))

    info_left = [
        Paragraph("<b>Employee</b>", styles['Normal']),
        Paragraph(emp.get("name", "-") if emp else "-", styles['Normal']),
        Paragraph(emp.get("email", "") if emp else "", styles['Muted']),
    ]
    info_right = [
        Paragraph("<b>Pay Period</b>", styles['LabelR']),
        Paragraph(period, styles['ValueR']),
        Paragraph(f"Issued: {dhaka_today().isoformat()} (Asia/Dhaka)", styles['LabelR']),
    ]
    if company:
        info_left.append(Paragraph(f"<font color='#64748B'>Company: {company.get('name', '')}</font>", styles['Muted']))

    info = Table([[info_left, info_right]], colWidths=[100 * mm, 70 * mm])
    info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(info)
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Attendance Summary</b>", styles['Heading3']))
    story.append(Spacer(1, 4))
    att_data = [
        ["Total Work Hours", f"{record.get('total_hours', 0)} h"],
        ["Overtime Hours", f"{record.get('overtime_hours', 0)} h"],
        ["Leave Days", f"{record.get('leave_days', 0)}"],
        ["Late Days", f"{record.get('late_days', 0)}"],
    ]
    att = Table(att_data, colWidths=[100 * mm, 70 * mm])
    att.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E2E8F0')),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(att)
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>Salary Breakdown</b>", styles['Heading3']))
    story.append(Spacer(1, 4))

    def fmt(v):
        return f"{currency_symbol} {float(v):,.2f}"

    bonus = float(record.get('bonuses', 0) or 0)
    ded = float(record.get('deductions', 0) or 0)
    base = float(record.get('base_salary', 0) or 0)
    net = float(record.get('net_salary', 0) or 0)
    sal_data = [
        ["Description", "Amount"],
        ["Base Salary", fmt(base)],
    ]
    for label, key in [("House Rent Allowance", "house_rent"), ("Medical", "medical"),
                       ("Transport", "transport"), ("Communication Allowance", "communication"),
                       ("Mobile Bill", "mobile_bill")]:
        amt = float(record.get(key, 0) or 0)
        if amt:
            sal_data.append([label, fmt(amt)])
    for a in (record.get("allowances") or []):
        amt = float(a.get("amount", 0) or 0)
        if amt:
            sal_data.append([a.get("label", "Allowance"), fmt(amt)])
    if bonus:
        sal_data.append(["Bonuses", f"+ {fmt(bonus)}"])
    if ded:
        sal_data.append(["Deductions", f"- {fmt(ded)}"])
    sal_data.append(["", ""])
    sal_data.append(["NET SALARY", fmt(net)])
    sal = Table(sal_data, colWidths=[100 * mm, 70 * mm])
    sal.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#22C55E')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(sal)
    story.append(Spacer(1, 20))

    if record.get('notes'):
        story.append(Paragraph(f"<b>Notes:</b> {record['notes']}", styles['Normal']))
        story.append(Spacer(1, 10))

    story.append(Paragraph(f"<font size=8 color='#64748B'>This is a system-generated payslip and does not require a signature. Currency: {currency_code}. Generated by {brand}.</font>", styles['Normal']))

    doc.build(story)
    buf.seek(0)
    return buf.read(), invoice_no
