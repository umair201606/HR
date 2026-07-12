import json
import io
import os
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from sqlalchemy import extract, func
from ..extensions import db
from ..models.compensation import PayrollProfile, PayrollComponent, PayrollRun, PayrollSlip, SalaryRevision
from ..models.user import User
from ..models.attendance import Attendance
from ..models.holiday import OvertimeAccount, PayrollAuditLog
from ..models.pf import ProvidentFundConfig, PFContribution, PFLedger
from ..models.communication import Notification, NotificationRecipient
from ..models.tax import IncomeTaxSlab
from ..models.loan import LoanAdvanceRequest, LoanRepayment
from ..config import Config

comp_bp = Blueprint("compensation", __name__, url_prefix="/compensation")


@comp_bp.route("/")
@login_required
def index():
    if current_user.is_admin():
        profiles = PayrollProfile.query.all()
        runs = PayrollRun.query.order_by(PayrollRun.run_date.desc()).limit(12).all()
        slabs = IncomeTaxSlab.query.filter_by(is_active=True).order_by(IncomeTaxSlab.min_income).all()
        return render_template("compensation/index.html", profiles=profiles, runs=runs, slabs=slabs)
    profile = PayrollProfile.query.filter_by(user_id=current_user.id).first()
    slips = PayrollSlip.query.filter_by(user_id=current_user.id).order_by(PayrollSlip.created_at.desc()).all()
    return render_template("compensation/employee.html", profile=profile, slips=slips)


# ── Income Tax Slabs ──

@comp_bp.route("/tax-settings", methods=["GET", "POST"])
@login_required
def tax_settings():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            slab = IncomeTaxSlab(
                min_income=float(request.form["min_income"]),
                max_income=float(request.form["max_income"]),
                rate_pct=float(request.form["rate_pct"]),
                fixed_amount=float(request.form.get("fixed_amount", 0)),
            )
            db.session.add(slab)
            flash("Tax slab added.", "success")
        elif action == "delete":
            slab = IncomeTaxSlab.query.get_or_404(int(request.form["slab_id"]))
            db.session.delete(slab)
            flash("Tax slab deleted.", "success")
        elif action == "seed_defaults":
            for s in [
                (0, 600000, 0, 0),
                (600000, 1200000, 5, 0),
                (1200000, 2400000, 15, 30000),
                (2400000, 3600000, 25, 210000),
                (3600000, 999999999, 35, 510000),
            ]:
                if not IncomeTaxSlab.query.filter_by(min_income=s[0]).first():
                    db.session.add(IncomeTaxSlab(min_income=s[0], max_income=s[1], rate_pct=s[2], fixed_amount=s[3]))
            flash("Default tax slabs seeded.", "success")
        db.session.commit()
        return redirect(url_for("compensation.tax_settings"))
    slabs = IncomeTaxSlab.query.order_by(IncomeTaxSlab.min_income).all()
    return render_template("compensation/tax_settings.html", slabs=slabs)


# ── Employee Salary Package Setup ──

@comp_bp.route("/edit-profile/<int:uid>", methods=["GET", "POST"])
@login_required
def edit_profile(uid):
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    profile = PayrollProfile.query.filter_by(user_id=uid).first()
    emp = User.query.get_or_404(uid)
    if request.method == "POST":
        if not profile:
            profile = PayrollProfile(user_id=uid, basic_salary=0, effective_from=date.today())
            db.session.add(profile)
            db.session.flush()
        profile.basic_salary = float(request.form["basic_salary"])
        profile.effective_from = datetime.strptime(request.form["effective_from"], "%Y-%m-%d").date()
        submitted = json.loads(request.form.get("components_json", "[]"))
        for old in profile.components.all():
            db.session.delete(old)
        for comp in submitted:
            db.session.add(PayrollComponent(
                profile_id=profile.id, name=comp["name"],
                type=comp["type"],
                calculation_method=comp.get("method", "fixed"),
                value=float(comp["value"]),
                is_taxable=comp.get("is_taxable", True),
            ))
        db.session.commit()
        flash(f"Salary package updated for {emp.full_name}.", "success")
        return redirect(url_for("compensation.index"))
    return render_template("compensation/edit_profile.html", profile=profile, employee=emp)


# ── Payroll Run with Per-Employee Control ──

@comp_bp.route("/run-payroll", methods=["GET", "POST"])
@login_required
def run_payroll():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        month = int(request.form["month"])
        year = int(request.form["year"])
        existing = PayrollRun.query.filter_by(month=month, year=year).first()
        if existing:
            flash(f"Payroll already run for {month}/{year}.", "danger")
            return redirect(url_for("compensation.index"))
        profiles = PayrollProfile.query.all()
        if not profiles:
            flash("No payroll profiles found.", "danger")
            return redirect(url_for("compensation.index"))
        adjustments = json.loads(request.form.get("adjustments", "{}"))
        pf_config = ProvidentFundConfig.query.first()
        pr = PayrollRun(month=month, year=year, processed_by=current_user.id, status="processing")
        db.session.add(pr)
        db.session.flush()
        total_gross = 0; total_ded = 0; total_net = 0; emp_count = 0
        for pp in profiles:
            if not pp.user.is_active:
                continue
            adj = adjustments.get(str(pp.user_id), {})
            hire_date = pp.user.date_of_joining
            days_in_month = 30
            worked_days = days_in_month
            if hire_date and (hire_date.year > year or (hire_date.year == year and hire_date.month > month)):
                continue
            if hire_date and hire_date.month == month and hire_date.year == year:
                worked_days = days_in_month - hire_date.day + 1
            pro_ratio = worked_days / days_in_month
            basic = pp.basic_salary * pro_ratio
            allowances = 0; deductions = 0
            comps = {"allowances": {}, "deductions": {}}
            for c in pp.components:
                val = c.value * pro_ratio
                if c.type == "allowance":
                    allowances += val
                    comps["allowances"][c.name] = round(val, 2)
                else:
                    deductions += val
                    comps["deductions"][c.name] = round(val, 2)
            ot_hours = db.session.query(func.sum(OvertimeAccount.overtime_hours)).filter(
                OvertimeAccount.user_id == pp.user_id,
                extract("month", OvertimeAccount.date) == month,
                extract("year", OvertimeAccount.date) == year
            ).scalar() or 0
            ot_pay = round(float(ot_hours) * (basic / 160) * 1.5, 2)
            allowances += ot_pay
            gross = basic + allowances
            monthly_tax = 0
            annual_gross = gross * 12
            tax_override = adj.get("income_tax")
            if tax_override is not None:
                monthly_tax = float(tax_override)
            else:
                annual_tax = IncomeTaxSlab.calculate_tax(annual_gross)
                monthly_tax = round(annual_tax / 12, 2)
            deductions += monthly_tax
            pf_employee = 0; pf_employer = 0
            if pf_config:
                pf_employee = round(gross * pf_config.employee_contribution_pct / 100, 2)
                pf_employer = round(gross * pf_config.employer_contribution_pct / 100, 2)
                deductions += pf_employee
            loan_deduction = 0
            active_loans = LoanAdvanceRequest.query.filter_by(
                user_id=pp.user_id, status="approved"
            ).all()
            for loan in active_loans:
                if loan.remaining_amount and loan.remaining_amount > 0:
                    installment = adj.get(f"loan_{loan.id}")
                    if installment is not None:
                        ded = float(installment)
                    else:
                        ded = loan.monthly_installment or (loan.amount / max(loan.installment_months, 1))
                    ded = min(ded, loan.remaining_amount)
                    if ded > 0:
                        loan_deduction += ded
                        loan.remaining_amount -= ded
                        if loan.remaining_amount <= 0:
                            loan.status = "paid"
                        db.session.add(LoanRepayment(loan_id=loan.id, amount=ded, payroll_run_id=pr.id,
                                                      notes=f"Deducted via payroll {month}/{year}"))
            deductions += loan_deduction
            custom_ded = adj.get("custom_deduction")
            if custom_ded:
                deductions += float(custom_ded)
            net = gross - deductions
            comps["deductions"]["Income Tax"] = round(monthly_tax, 2)
            comps["deductions"]["PF Employee"] = round(pf_employee, 2)
            if loan_deduction > 0:
                comps["deductions"]["Loan Repayment"] = round(loan_deduction, 2)
            if custom_ded:
                comps["deductions"]["Additional Deduction"] = round(float(custom_ded), 2)
            slip = PayrollSlip(
                payroll_run_id=pr.id, user_id=pp.user_id, basic_salary=round(basic, 2),
                allowances=round(allowances, 2), deductions=round(deductions, 2),
                gross_pay=round(gross, 2), total_deductions=round(deductions, 2),
                net_pay=round(net, 2), components_json=json.dumps(comps),
            )
            db.session.add(slip)
            total_gross += gross; total_ded += deductions; total_net += net; emp_count += 1
            if pf_config:
                contrib = PFContribution(user_id=pp.user_id, month=month, year=year,
                                          employee_amount=pf_employee, employer_amount=pf_employer,
                                          total_amount=round(pf_employee + pf_employer, 2))
                db.session.add(contrib)
                db.session.add(PFLedger(user_id=pp.user_id, transaction_date=date.today(),
                                         transaction_type="contribution",
                                         description=f"PF contribution {month}/{year}",
                                         credit=round(pf_employee + pf_employer, 2), debit=0))
            # Notify employee
            _notify(pp.user_id, "Salary Slip Generated",
                    f"Your salary slip for {month}/{year} is available.", "info", "compensation")
            # Notify manager
            if pp.user.manager_id:
                _notify(pp.user.manager_id, f"Salary Slip: {pp.user.full_name}",
                        f"Salary for {month}/{year}: Rs.{net:,.0f}", "info", "compensation")
        pr.status = "completed"
        pr.total_gross = round(total_gross, 2)
        pr.total_deductions = round(total_ded, 2)
        pr.total_net = round(total_net, 2)
        pr.employee_count = emp_count
        db.session.add(PayrollAuditLog(payroll_run_id=pr.id, action="payroll_run",
                                        performed_by=current_user.id, details=f"Run for {month}/{year}",
                                        ip_address=request.remote_addr))
        db.session.commit()
        flash(f"Payroll completed for {emp_count} employees. Net: Rs.{total_net:,.0f}", "success")
        return redirect(url_for("compensation.index"))
    profiles = PayrollProfile.query.all()
    employees_data = []
    for pp in profiles:
        if not pp.user.is_active:
            continue
        active_loans = LoanAdvanceRequest.query.filter_by(
            user_id=pp.user_id, status="approved"
        ).filter(LoanAdvanceRequest.remaining_amount > 0).all()
        employees_data.append({
            "profile": pp,
            "loans": active_loans,
        })
    return render_template("compensation/run_payroll.html", employees=employees_data)


# ── View & Download Slip ──

@comp_bp.route("/slip/<int:sid>")
@login_required
def view_slip(sid):
    slip = PayrollSlip.query.get_or_404(sid)
    if slip.user_id != current_user.id and not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    comps = json.loads(slip.components_json) if slip.components_json else {"allowances": {}, "deductions": {}}
    return render_template("compensation/slip.html", slip=slip, comps=comps)


@comp_bp.route("/slip/<int:sid>/pdf")
@login_required
def download_slip_pdf(sid):
    slip = PayrollSlip.query.get_or_404(sid)
    if slip.user_id != current_user.id and not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
    except ImportError:
        flash("PDF library not installed.", "danger")
        return redirect(url_for("compensation.index"))
    comps = json.loads(slip.components_json) if slip.components_json else {"allowances": {}, "deductions": {}}
    pdf_dir = os.path.join(Config.UPLOAD_FOLDER, "slips")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"slip_{slip.id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(w / 2, h - 40, "Solarkon (Private) Limited")
    c.setFont("Helvetica", 11)
    c.drawCentredString(w / 2, h - 58, f"Salary Slip - {slip.payroll_run.month}/{slip.payroll_run.year}")
    c.setStrokeColor(colors.HexColor("#1a237e"))
    c.setLineWidth(2)
    c.line(40, h - 65, w - 40, h - 65)
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    y = h - 90
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Employee: {slip.user.full_name}")
    c.drawString(320, y, f"Designation: {slip.user.designation or '-'}")
    y -= 18
    c.drawString(40, y, f"Department: {slip.user.department or '-'}")
    c.drawString(320, y, f"Employee Code: {slip.user.employee_code}")
    y -= 18
    c.drawString(40, y, f"CNIC: {slip.user.cnic or '-'}")
    y -= 26
    c.setFillColor(colors.HexColor("#1a237e"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Earnings")
    c.drawString(300, y, "Deductions")
    c.setFillColor(colors.black)
    y -= 18
    c.setFont("Helvetica", 10)
    earnings = [("Basic Salary", slip.basic_salary)]
    for name, val in comps.get("allowances", {}).items():
        earnings.append((name, val))
    earnings.append(("Overtime Pay", 0))
    deductions_list = []
    for name, val in comps.get("deductions", {}).items():
        deductions_list.append((name, val))
    max_rows = max(len(earnings), len(deductions_list), 1)
    for i in range(max_rows):
        if i < len(earnings):
            label, val = earnings[i]
            c.drawString(40, y, label)
            c.drawRightString(280, y, f"Rs. {val:,.2f}")
        if i < len(deductions_list):
            label, val = deductions_list[i]
            c.drawString(300, y, label)
            c.drawRightString(w - 40, y, f"Rs. {val:,.2f}")
        y -= 16
    y -= 4
    c.setFont("Helvetica-Bold", 10)
    c.line(40, y + 2, w - 40, y + 2)
    c.line(40, y, w - 40, y)
    c.drawString(40, y - 16, "Total Earnings")
    c.drawRightString(280, y - 16, f"Rs. {slip.gross_pay:,.2f}")
    c.drawString(300, y - 16, "Total Deductions")
    c.drawRightString(w - 40, y - 16, f"Rs. {slip.total_deductions:,.2f}")
    y -= 40
    c.setStrokeColor(colors.HexColor("#1b5e20"))
    c.setLineWidth(2)
    c.line(40, y, w - 40, y)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#1b5e20"))
    c.drawString(40, y - 22, "Net Payable: Rs. {:,}".format(int(slip.net_pay)))
    c.drawRightString(w - 40, y - 22, "(Rupees {})".format(_num_to_words(int(slip.net_pay))))
    c.save()
    return send_file(pdf_path, mimetype="application/pdf", as_attachment=False,
                     download_name=f"salary_slip_{slip.payroll_run.month}_{slip.payroll_run.year}.pdf")


def _num_to_words(n):
    if n == 0: return "Zero"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    def _convert(num):
        if num < 20: return ones[num]
        if num < 100: return tens[num // 10] + (" " + ones[num % 10] if num % 10 else "")
        if num < 1000: return ones[num // 100] + " Hundred" + (" " + _convert(num % 100) if num % 100 else "")
        if num < 100000: return _convert(num // 1000) + " Thousand" + (" " + _convert(num % 1000) if num % 1000 else "")
        if num < 10000000: return _convert(num // 100000) + " Lakh" + (" " + _convert(num % 100000) if num % 100000 else "")
        return _convert(num // 10000000) + " Crore" + (" " + _convert(num % 10000000) if num % 10000000 else "")
    return _convert(n) + " Only"


def _notify(user_id, title, message, ntype="info", module="compensation", ref_id=None):
    notif = Notification(title=title, message=message, notification_type=ntype,
                         module=module, reference_id=ref_id, created_by=current_user.id)
    db.session.add(notif)
    db.session.flush()
    db.session.add(NotificationRecipient(notification_id=notif.id, user_id=user_id))


# ── Bank Ledger & Revisions ──

@comp_bp.route("/export-bank-ledger/<int:rid>")
@login_required
def export_bank_ledger(rid):
    if not current_user.is_admin():
        return jsonify({"error": "Access denied"}), 403
    run = PayrollRun.query.get_or_404(rid)
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return jsonify({"error": "openpyxl not installed"}), 500
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Payroll_{run.month}_{run.year}"
    headers = ["Employee Code", "Employee Name", "Bank Name", "Account Title", "Account Number", "Net Pay"]
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="1A237E", end_color="1A237E", fill_type="solid")
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=ci, value=h)
        c.font = hf; c.fill = hfill; c.alignment = Alignment(horizontal="center")
    for ri, slip in enumerate(run.slips, 2):
        u = slip.user
        for ci, val in enumerate([u.employee_code, u.full_name, u.bank_name or "",
                                   u.bank_account_title or "", u.bank_account_number or "",
                                   slip.net_pay], 1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.alignment = Alignment(horizontal="center")
    from openpyxl.utils import get_column_letter
    for ci in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 22
    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"bank_ledger_{run.month}_{run.year}.xlsx")


@comp_bp.route("/revisions")
@login_required
def revisions():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    all_revisions = SalaryRevision.query.order_by(SalaryRevision.created_at.desc()).all()
    return render_template("compensation/revisions.html", revisions=all_revisions)
