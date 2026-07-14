from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, render_template, request, jsonify, Response, send_file
from flask_login import login_required
from sqlalchemy import text
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from shared.extensions import db
from shared.models.ledger import ChartOfAccount, JournalEntry, JournalLine
from shared.models.base import User

finance_bp = Blueprint("finance", __name__, url_prefix="/finance")

ACCOUNT_TYPES = {"asset": "Asset", "liability": "Liability",
                 "equity": "Equity", "revenue": "Revenue", "expense": "Expense"}

THIN = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)
HEADER_FILL = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=16, color="1F4E79")
SUBTITLE_FONT = Font(bold=True, size=10, color="555555")
DATA_FONT = Font(size=10)
BOLD_FONT = Font(bold=True, size=10)
CENTER = Alignment(horizontal="center", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")
LEFT_ALIGN = Alignment(horizontal="left", vertical="center")


def _parse_date(d):
    if not d:
        return None
    if isinstance(d, date):
        return d
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _get_account_balance(account_id, as_of=None):
    q = db.session.query(
        db.func.coalesce(db.func.sum(JournalLine.debit), 0).label("dr"),
        db.func.coalesce(db.func.sum(JournalLine.credit), 0).label("cr"),
    ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
           ).filter(JournalLine.account_id == account_id,
                    JournalEntry.is_posted == True)
    if as_of:
        q = q.filter(JournalEntry.entry_date <= as_of)
    row = q.first()
    return Decimal(str(row.dr)), Decimal(str(row.cr))


def _all_account_balances(as_of=None, account_types=None):
    q = db.session.query(
        JournalLine.account_id,
        ChartOfAccount.code,
        ChartOfAccount.name,
        ChartOfAccount.type,
        db.func.coalesce(db.func.sum(JournalLine.debit), 0).label("dr"),
        db.func.coalesce(db.func.sum(JournalLine.credit), 0).label("cr"),
    ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
           ).join(ChartOfAccount, JournalLine.account_id == ChartOfAccount.id
                  ).filter(JournalEntry.is_posted == True)
    if as_of:
        q = q.filter(JournalEntry.entry_date <= as_of)
    if account_types:
        q = q.filter(ChartOfAccount.type.in_(account_types))
    q = q.group_by(JournalLine.account_id, ChartOfAccount.code,
                   ChartOfAccount.name, ChartOfAccount.type
                   ).order_by(ChartOfAccount.code)
    return q.all()


def _net_income(as_of=None):
    rev = _all_account_balances(as_of, ["revenue"])
    exp = _all_account_balances(as_of, ["expense"])
    total_rev = sum((r.cr - r.dr) for r in rev) if rev else Decimal("0")
    total_exp = sum((e.dr - e.cr) for e in exp) if exp else Decimal("0")
    return total_rev - total_exp


def _build_excel_wb(title, headers, rows, col_widths=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    cell = ws.cell(row=1, column=1, value=title)
    cell.font = TITLE_FONT
    cell.alignment = Alignment(horizontal="center")

    hdr_row = 3
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=hdr_row, column=ci, value=h)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = THIN

    for ri, row in enumerate(rows, hdr_row + 1):
        for ci, val in enumerate(row, 1):
            c = ws.cell(row=ri, column=ci, value=val)
            c.font = DATA_FONT
            c.border = THIN
            c.alignment = RIGHT if isinstance(val, (int, float, Decimal)) else LEFT_ALIGN

    if col_widths:
        for ci, w in enumerate(col_widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = w

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def _build_pdf_landscape(title, headers, rows, col_widths=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            rightMargin=10*mm, leftMargin=10*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Spacer(1, 6*mm))
    elements.append(Paragraph(f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
                              styles["Normal"]))
    elements.append(Spacer(1, 4*mm))

    data = [headers] + [[str(c) if not isinstance(c, (int, float, Decimal)) else
                         f"{c:,.2f}" for c in row] for row in rows]
    if not col_widths:
        col_widths = [doc.width / len(headers)] * len(headers)
    else:
        pw = doc.width
        tw = sum(col_widths)
        col_widths = [pw * (w / tw) for w in col_widths]

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7FB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    t.setStyle(TableStyle(style))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return buf


# ═══════════════════════════════════════════════
# 1. DASHBOARD
# ═══════════════════════════════════════════════

@finance_bp.route("/")
@login_required
def dashboard():
    return render_template("finance/dashboard.html", now=datetime.utcnow())


# ═══════════════════════════════════════════════
# 2. GENERAL LEDGER
# ═══════════════════════════════════════════════

@finance_bp.route("/ledger")
@login_required
def ledger():
    accounts = ChartOfAccount.query.filter_by(is_active=True).order_by(ChartOfAccount.code).all()
    account_id = request.args.get("account_id", type=int)
    from_date = _parse_date(request.args.get("from"))
    to_date = _parse_date(request.args.get("to"))

    rows = []
    account = None
    balance = Decimal("0")

    if account_id:
        account = ChartOfAccount.query.get(account_id)
        q = JournalLine.query.join(JournalEntry).filter(
            JournalLine.account_id == account_id,
            JournalEntry.is_posted == True,
        )
        if from_date:
            q = q.filter(JournalEntry.entry_date >= from_date)
        if to_date:
            q = q.filter(JournalEntry.entry_date <= to_date)
        q = q.order_by(JournalEntry.entry_date, JournalEntry.id)
        lines = q.all()

        for line in lines:
            dr = Decimal(str(line.debit))
            cr = Decimal(str(line.credit))
            balance += dr - cr
            rows.append({
                "date": line.entry.entry_date.strftime("%Y-%m-%d") if line.entry.entry_date else "",
                "voucher": line.entry.voucher_number or "",
                "description": line.description or line.entry.description or "",
                "debit": float(dr) if dr else 0,
                "credit": float(cr) if cr else 0,
                "balance": float(balance),
            })

    fmt = request.args.get("format")
    if fmt == "excel":
        headers = ["Date", "Voucher #", "Description", "Debit", "Credit", "Balance"]
        data = [[r["date"], r["voucher"], r["description"], r["debit"], r["credit"], r["balance"]]
                for r in rows]
        wb_out = _build_excel_wb(f"GL - {account.name if account else 'Ledger'}",
                                  headers, data, [14, 18, 40, 16, 16, 16])
        return send_file(wb_out, as_attachment=True,
                         download_name=f"gl_{account.code if account else 'ledger'}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if fmt == "pdf":
        headers = ["Date", "Voucher #", "Description", "Debit", "Credit", "Balance"]
        data = [[r["date"], r["voucher"], r["description"], r["debit"], r["credit"], r["balance"]]
                for r in rows]
        pdf_out = _build_pdf_landscape(f"General Ledger - {account.name if account else ''}",
                                        headers, data, [24, 28, 60, 24, 24, 24])
        return send_file(pdf_out, as_attachment=True,
                         download_name=f"gl_{account.code if account else 'ledger'}.pdf",
                         mimetype="application/pdf")

    return render_template("finance/ledger.html", accounts=accounts,
                           account=account, rows=rows,
                           from_date=from_date, to_date=to_date,
                           now=datetime.utcnow())


# ═══════════════════════════════════════════════
# 3. TRIAL BALANCE
# ═══════════════════════════════════════════════

@finance_bp.route("/trial-balance")
@login_required
def trial_balance():
    as_of = _parse_date(request.args.get("as_of")) or date.today()
    balances = _all_account_balances(as_of)

    rows = []
    total_dr = Decimal("0")
    total_cr = Decimal("0")
    for b in balances:
        dr = b.dr
        cr = b.cr
        if dr == cr == 0:
            continue
        total_dr += dr
        total_cr += cr
        rows.append({
            "code": b.code,
            "name": b.name,
            "type": ACCOUNT_TYPES.get(b.type, b.type),
            "debit": float(dr),
            "credit": float(cr),
        })

    fmt = request.args.get("format")
    if fmt == "excel":
        headers = ["Code", "Account", "Type", "Debit", "Credit"]
        data = [[r["code"], r["name"], r["type"], r["debit"], r["credit"]] for r in rows]
        data.append(["", "TOTAL", "", float(total_dr), float(total_cr)])
        wb_out = _build_excel_wb(f"Trial Balance as of {as_of}", headers, data, [12, 40, 16, 18, 18])
        return send_file(wb_out, as_attachment=True, download_name="trial_balance.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if fmt == "pdf":
        headers = ["Code", "Account", "Type", "Debit", "Credit"]
        data = [[r["code"], r["name"], r["type"],
                 f"{r['debit']:,.2f}" if r['debit'] else "0.00",
                 f"{r['credit']:,.2f}" if r['credit'] else "0.00"] for r in rows]
        data.append(["", "TOTAL", "", f"{float(total_dr):,.2f}", f"{float(total_cr):,.2f}"])
        pdf_out = _build_pdf_landscape(f"Trial Balance as of {as_of}", headers, data,
                                        [16, 60, 28, 30, 30])
        return send_file(pdf_out, as_attachment=True, download_name="trial_balance.pdf",
                         mimetype="application/pdf")

    return render_template("finance/trial_balance.html", rows=rows,
                           total_dr=float(total_dr), total_cr=float(total_cr),
                           as_of=as_of, now=datetime.utcnow())


# ═══════════════════════════════════════════════
# 4. PROFIT & LOSS
# ═══════════════════════════════════════════════

@finance_bp.route("/profit-loss")
@login_required
def profit_loss():
    from_date = _parse_date(request.args.get("from")) or date(date.today().year, 1, 1)
    to_date = _parse_date(request.args.get("to")) or date.today()

    rev_balances = _all_account_balances(to_date, ["revenue"])
    exp_balances = _all_account_balances(to_date, ["expense"])

    rev_rows = []
    total_rev = Decimal("0")
    for b in rev_balances:
        bal = b.cr - b.dr
        if bal == 0:
            continue
        total_rev += bal
        rev_rows.append({"code": b.code, "name": b.name, "amount": float(bal)})

    exp_rows = []
    total_exp = Decimal("0")
    for b in exp_balances:
        bal = b.dr - b.cr
        if bal == 0:
            continue
        total_exp += bal
        exp_rows.append({"code": b.code, "name": b.name, "amount": float(bal)})

    net_income = float(total_rev - total_exp)

    fmt = request.args.get("format")
    if fmt == "excel":
        headers = ["Code", "Account", "Amount"]
        rev_data = [[r["code"], r["name"], r["amount"]] for r in rev_rows]
        exp_data = [[r["code"], r["name"], r["amount"]] for r in exp_rows]
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "P&L"
        ws.merge_cells("A1:C1")
        ws.cell(row=1, column=1, value=f"Profit & Loss ({from_date} to {to_date})").font = TITLE_FONT

        def write_section(ws, start_row, section_title, headers, data, total_label, total_val):
            ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row, end_column=3)
            ws.cell(row=start_row, column=1, value=section_title).font = Font(bold=True, size=12)
            sr = start_row + 1
            for ci, h in enumerate(headers, 1):
                c = ws.cell(row=sr, column=ci, value=h)
                c.font = HEADER_FONT; c.fill = HEADER_FILL; c.alignment = CENTER; c.border = THIN
            for ri, row in enumerate(data, sr + 1):
                for ci, v in enumerate(row, 1):
                    c = ws.cell(row=ri, column=ci, value=v)
                    c.font = DATA_FONT; c.border = THIN
                    c.alignment = RIGHT if isinstance(v, (int, float, Decimal)) else LEFT_ALIGN
            total_row = sr + len(data) + 1
            ws.cell(row=total_row, column=2, value=total_label).font = BOLD_FONT
            ws.cell(row=total_row, column=3, value=total_val).font = BOLD_FONT
            ws.cell(row=total_row, column=2).border = THIN
            ws.cell(row=total_row, column=3).border = THIN
            return total_row + 2

        next_row = write_section(ws, 3, "REVENUE", headers, rev_data, "Total Revenue", float(total_rev))
        next_row = write_section(ws, next_row, "EXPENSES", headers, exp_data, "Total Expenses", float(total_exp))
        ws.merge_cells(start_row=next_row, start_column=1, end_row=next_row, end_column=3)
        ws.cell(row=next_row, column=1, value=f"NET INCOME / (LOSS)").font = Font(bold=True, size=13, color="1F4E79")
        ws.cell(row=next_row, column=3, value=net_income).font = Font(bold=True, size=13, color="1F4E79")
        out = BytesIO(); wb.save(out); out.seek(0)
        return send_file(out, as_attachment=True, download_name="profit_loss.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if fmt == "pdf":
        headers = ["Code", "Account", "Amount"]
        rev_data = [[r["code"], r["name"], f"{r['amount']:,.2f}"] for r in rev_rows]
        exp_data = [[r["code"], r["name"], f"{r['amount']:,.2f}"] for r in exp_rows]
        pdf_out = _build_pdf_landscape(f"Profit & Loss ({from_date} to {to_date})",
                                        headers, rev_data + [["", "", ""]] + exp_data, [20, 60, 30])
        return send_file(pdf_out, as_attachment=True, download_name="profit_loss.pdf",
                         mimetype="application/pdf")

    return render_template("finance/profit_loss.html", rev_rows=rev_rows,
                           exp_rows=exp_rows, total_rev=float(total_rev),
                           total_exp=float(total_exp), net_income=net_income,
                           from_date=from_date, to_date=to_date,
                           now=datetime.utcnow())


# ═══════════════════════════════════════════════
# 5. BALANCE SHEET
# ═══════════════════════════════════════════════

@finance_bp.route("/balance-sheet")
@login_required
def balance_sheet():
    as_of = _parse_date(request.args.get("as_of")) or date.today()
    as_of_end = as_of

    balances = _all_account_balances(as_of_end)
    ni = _net_income(as_of_end)

    assets, liabilities, equity = [], [], []
    total_assets = total_liabilities = total_equity = Decimal("0")

    for b in balances:
        if b.type == "asset":
            bal = b.dr - b.cr
            if bal != 0:
                assets.append({"code": b.code, "name": b.name, "amount": float(bal)})
                total_assets += bal
        elif b.type == "liability":
            bal = b.cr - b.dr
            if bal != 0:
                liabilities.append({"code": b.code, "name": b.name, "amount": float(bal)})
                total_liabilities += bal
        elif b.type == "equity":
            bal = b.cr - b.dr
            if bal != 0:
                equity.append({"code": b.code, "name": b.name, "amount": float(bal)})
                total_equity += bal

    if ni >= 0:
        equity.append({"code": "", "name": "Net Income (Current Period)", "amount": float(ni)})
    else:
        equity.append({"code": "", "name": "Net Loss (Current Period)", "amount": float(ni)})
    total_equity += Decimal(str(ni))

    fmt = request.args.get("format")
    if fmt == "excel":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Balance Sheet"
        ws.merge_cells("A1:C1")
        ws.cell(row=1, column=1, value=f"Balance Sheet as of {as_of_end}").font = TITLE_FONT

        def write_section(ws, sr, section_title, items, total_label, total_val):
            ws.merge_cells(start_row=sr, start_column=1, end_row=sr, end_column=3)
            ws.cell(row=sr, column=1, value=section_title).font = Font(bold=True, size=12)
            hdr = sr + 1
            for ci, h in enumerate(["Code", "Account", "Amount"], 1):
                c = ws.cell(row=hdr, column=ci, value=h)
                c.font = HEADER_FONT; c.fill = HEADER_FILL; c.alignment = CENTER; c.border = THIN
            for ri, item in enumerate(items, hdr + 1):
                ws.cell(row=ri, column=1, value=item["code"]).font = DATA_FONT
                ws.cell(row=ri, column=1).border = THIN
                ws.cell(row=ri, column=2, value=item["name"]).font = DATA_FONT
                ws.cell(row=ri, column=2).border = THIN
                ws.cell(row=ri, column=3, value=item["amount"]).font = DATA_FONT
                ws.cell(row=ri, column=3).border = THIN
                ws.cell(row=ri, column=3).alignment = RIGHT
            tr = hdr + len(items) + 1
            ws.cell(row=tr, column=2, value=total_label).font = BOLD_FONT
            ws.cell(row=tr, column=2).border = THIN
            ws.cell(row=tr, column=3, value=float(total_val)).font = BOLD_FONT
            ws.cell(row=tr, column=3).border = THIN
            ws.cell(row=tr, column=3).alignment = RIGHT
            return tr + 2

        nr = write_section(ws, 3, "ASSETS", assets, "Total Assets", total_assets)
        nr = write_section(ws, nr, "LIABILITIES", liabilities, "Total Liabilities", total_liabilities)
        nr = write_section(ws, nr, "EQUITY", equity, "Total Equity", total_equity)

        ws.merge_cells(start_row=nr, start_column=1, end_row=nr, end_column=3)
        ws.cell(row=nr, column=1, value="LIABILITIES + EQUITY").font = Font(bold=True, size=12)
        ws.cell(row=nr, column=3, value=float(total_liabilities + total_equity)).font = Font(bold=True, size=12)
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 40
        ws.column_dimensions["C"].width = 20
        out = BytesIO(); wb.save(out); out.seek(0)
        return send_file(out, as_attachment=True, download_name="balance_sheet.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if fmt == "pdf":
        headers = ["Code", "Account", "Amount"]
        all_data = ([[a["code"], a["name"], f"{a['amount']:,.2f}"] for a in assets] +
                    [["", "", ""]] +
                    [[l["code"], l["name"], f"{l['amount']:,.2f}"] for l in liabilities] +
                    [["", "", ""]] +
                    [[e["code"], e["name"], f"{e['amount']:,.2f}"] for e in equity])
        pdf_out = _build_pdf_landscape(f"Balance Sheet as of {as_of_end}", headers, all_data, [20, 60, 30])
        return send_file(pdf_out, as_attachment=True, download_name="balance_sheet.pdf",
                         mimetype="application/pdf")

    return render_template("finance/balance_sheet.html", assets=assets,
                           liabilities=liabilities, equity=equity,
                           total_assets=float(total_assets),
                           total_liabilities=float(total_liabilities),
                           total_equity=float(total_equity),
                           as_of=as_of_end, now=datetime.utcnow())


# ═══════════════════════════════════════════════
# 6. SOCIE
# ═══════════════════════════════════════════════

@finance_bp.route("/socie")
@login_required
def socie():
    from_date = _parse_date(request.args.get("from")) or date(date.today().year, 1, 1)
    to_date = _parse_date(request.args.get("to")) or date.today()

    ni = _net_income(to_date)
    eq_balances = _all_account_balances(to_date, ["equity"])

    opening_total = Decimal("0")
    movement_total = Decimal("0")
    rows = []

    for b in eq_balances:
        bal = b.cr - b.dr
        rows.append({"name": b.name, "opening": float(bal), "movement": 0, "closing": float(bal)})
        opening_total += bal
        closing_total = opening_total
    rows.append({"name": "Net Income / (Loss)", "opening": 0,
                 "movement": float(ni), "closing": float(ni)})
    movement_total += Decimal(str(ni))
    closing_total = opening_total + movement_total

    fmt = request.args.get("format")
    if fmt == "excel":
        headers = ["Component", "Opening Balance", "Movement", "Closing Balance"]
        data = [[r["name"], r["opening"], r["movement"], r["closing"]] for r in rows]
        data.append(["TOTAL", float(opening_total), float(movement_total), float(closing_total)])
        wb_out = _build_excel_wb(f"SOCIE ({from_date} to {to_date})", headers, data, [40, 20, 20, 20])
        return send_file(wb_out, as_attachment=True, download_name="socie.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if fmt == "pdf":
        headers = ["Component", "Opening", "Movement", "Closing"]
        data = [[r["name"], f"{r['opening']:,.2f}", f"{r['movement']:,.2f}",
                 f"{r['closing']:,.2f}"] for r in rows]
        data.append(["TOTAL", f"{float(opening_total):,.2f}", f"{float(movement_total):,.2f}",
                     f"{float(closing_total):,.2f}"])
        pdf_out = _build_pdf_landscape(f"SOCIE ({from_date} to {to_date})", headers, data, [60, 30, 30, 30])
        return send_file(pdf_out, as_attachment=True, download_name="socie.pdf",
                         mimetype="application/pdf")

    return render_template("finance/socie.html", rows=rows,
                           opening_total=float(opening_total),
                           movement_total=float(movement_total),
                           closing_total=float(closing_total),
                           from_date=from_date, to_date=to_date,
                           now=datetime.utcnow())


# ═══════════════════════════════════════════════
# 7. CASH FLOW STATEMENT (Indirect Method)
# ═══════════════════════════════════════════════

@finance_bp.route("/cash-flow")
@login_required
def cash_flow():
    from_date = _parse_date(request.args.get("from")) or date(date.today().year, 1, 1)
    to_date = _parse_date(request.args.get("to")) or date.today()
    prev_date = date(from_date.year - 1, from_date.month, from_date.day) if from_date else None

    ni = _net_income(to_date)

    cash_acct = ChartOfAccount.query.filter_by(code="1000").first()
    ar_acct = ChartOfAccount.query.filter_by(code="1100").first()
    inv_acct = ChartOfAccount.query.filter_by(code="1200").first()
    ap_acct = ChartOfAccount.query.filter_by(code="2000").first()
    accrued_acct = ChartOfAccount.query.filter_by(code="2100").first()
    loans_acct = ChartOfAccount.query.filter_by(code="2200").first()
    fa_acct = ChartOfAccount.query.filter_by(code="1300").first()

    def change(acct):
        if not acct:
            return 0
        dr_now, cr_now = _get_account_balance(acct.id, to_date)
        dr_prev, cr_prev = _get_account_balance(acct.id, prev_date) if prev_date else (Decimal("0"), Decimal("0"))

        if acct.type == "asset":
            now_bal = dr_now - cr_now
            prev_bal = dr_prev - cr_prev
            return float(prev_bal - now_bal)
        else:
            now_bal = cr_now - dr_now
            prev_bal = cr_prev - dr_prev
            return float(now_bal - prev_bal)

    op_items = [
        ("Net Income / (Loss)", float(ni), True),
        ("Change in Accounts Receivable", change(ar_acct), True),
        ("Change in Inventory", change(inv_acct), True),
        ("Change in Accounts Payable", change(ap_acct), True),
        ("Change in Accrued Expenses", change(accrued_acct), True),
    ]
    inv_items = [
        ("Change in Fixed Assets", change(fa_acct), False),
    ]
    fin_items = [
        ("Change in Loans Payable", change(loans_acct), True),
    ]

    net_operating = sum(v for _, v, _ in op_items)
    net_investing = sum(v for _, v, _ in inv_items)
    net_financing = sum(v for _, v, _ in fin_items)
    net_change = net_operating + net_investing + net_financing

    fmt = request.args.get("format")
    if fmt == "excel":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cash Flow"
        ws.merge_cells("A1:C1")
        ws.cell(row=1, column=1, value=f"Cash Flow Statement ({from_date} to {to_date})").font = TITLE_FONT

        def write_section(ws, sr, title, items, sign):
            ws.merge_cells(start_row=sr, start_column=1, end_row=sr, end_column=3)
            ws.cell(row=sr, column=1, value=title).font = Font(bold=True, size=12)
            hdr = sr + 1
            for ci, h in enumerate(["Item", "Amount", ""], 1):
                c = ws.cell(row=hdr, column=ci, value=h)
                c.font = HEADER_FONT; c.fill = HEADER_FILL; c.alignment = CENTER; c.border = THIN
            for ri, (name, val, _) in enumerate(items, hdr + 1):
                ws.cell(row=ri, column=1, value=name).font = DATA_FONT; ws.cell(row=ri, column=1).border = THIN
                ws.cell(row=ri, column=2, value=val).font = DATA_FONT; ws.cell(row=ri, column=2).border = THIN
                ws.cell(row=ri, column=2).alignment = RIGHT
            return hdr + len(items) + 2

        nr = write_section(ws, 3, "OPERATING ACTIVITIES", op_items, True)
        nr = write_section(ws, nr, "INVESTING ACTIVITIES", inv_items, False)
        nr = write_section(ws, nr, "FINANCING ACTIVITIES", fin_items, True)
        ws.merge_cells(start_row=nr, start_column=1, end_row=nr, end_column=3)
        ws.cell(row=nr, column=1, value="NET CASH CHANGE").font = BOLD_FONT
        ws.cell(row=nr, column=2, value=net_change).font = BOLD_FONT
        ws.column_dimensions["A"].width = 40; ws.column_dimensions["B"].width = 20
        out = BytesIO(); wb.save(out); out.seek(0)
        return send_file(out, as_attachment=True, download_name="cash_flow.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if fmt == "pdf":
        all_items = (op_items + [("", 0, True)] + inv_items +
                     [("", 0, True)] + fin_items)
        headers = ["Item", "Amount"]
        pdf_data = [[n, f"{v:,.2f}"] for n, v, _ in all_items]
        pdf_out = _build_pdf_landscape(f"Cash Flow Statement ({from_date} to {to_date})",
                                        headers, pdf_data, [80, 30])
        return send_file(pdf_out, as_attachment=True, download_name="cash_flow.pdf",
                         mimetype="application/pdf")

    return render_template("finance/cash_flow.html", op_items=op_items,
                           inv_items=inv_items, fin_items=fin_items,
                           net_operating=net_operating, net_investing=net_investing,
                           net_financing=net_financing, net_change=net_change,
                           from_date=from_date, to_date=to_date,
                           now=datetime.utcnow())
