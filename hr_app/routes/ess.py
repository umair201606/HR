from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from ..extensions import db
from ..models.user import User, ChangeRequest
from ..models.leave import LeaveRequest, LeaveQuota, LeaveType
from ..models.timesheet import TimesheetWeek, TimesheetEntry
from ..models.loan import LoanAdvanceRequest, LoanRepayment
from ..models.compensation import PayrollSlip
from ..models.performance import PerformanceReview, PerformanceGoal
from ..models.communication import Notification, NotificationRecipient

ess_bp = Blueprint("ess", __name__, url_prefix="/ess")


@ess_bp.route("/")
@login_required
def index():
    user = current_user
    quotas = LeaveQuota.query.filter_by(user_id=user.id).all()
    loan_requests = LoanAdvanceRequest.query.filter_by(user_id=user.id).order_by(LoanAdvanceRequest.created_at.desc()).all()
    slips = PayrollSlip.query.filter_by(user_id=user.id).order_by(PayrollSlip.created_at.desc()).limit(12).all()
    reviews = PerformanceReview.query.filter_by(user_id=user.id).order_by(PerformanceReview.created_at.desc()).all()
    return render_template("ess/index.html", user=user, quotas=quotas,
                           loan_requests=loan_requests, slips=slips, reviews=reviews)


@ess_bp.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    fields = ["phone", "emergency_contact", "emergency_phone", "address"]
    for f in fields:
        val = request.form.get(f, "").strip()
        if val and getattr(current_user, f) != val:
            cr = ChangeRequest.query.filter_by(user_id=current_user.id, field_name=f, status="pending").first()
            if not cr:
                old = getattr(current_user, f) or ""
                db.session.add(ChangeRequest(user_id=current_user.id, field_name=f,
                                              old_value=str(old), new_value=val))
    sensitive = ["bank_name", "bank_account_title", "bank_account_number"]
    for f in sensitive:
        val = request.form.get(f, "").strip()
        if val and getattr(current_user, f) != val:
            cr = ChangeRequest.query.filter_by(user_id=current_user.id, field_name=f, status="pending").first()
            if not cr:
                old = getattr(current_user, f) or ""
                db.session.add(ChangeRequest(user_id=current_user.id, field_name=f,
                                              old_value=str(old), new_value=val))
    db.session.commit()
    flash("Profile update submitted for review.", "success")
    return redirect(url_for("ess.index"))


@ess_bp.route("/change-requests")
@login_required
def change_requests():
    if not current_user.is_admin():
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    pending = ChangeRequest.query.filter_by(status="pending").order_by(ChangeRequest.created_at.desc()).all()
    return render_template("ess/change_requests.html", requests=pending)


@ess_bp.route("/review-change/<int:cid>", methods=["POST"])
@login_required
def review_change(cid):
    if not current_user.is_admin():
        return jsonify({"error": "Access denied"}), 403
    cr = ChangeRequest.query.get_or_404(cid)
    action = request.form.get("action")
    notes = request.form.get("notes", "")
    if action == "approve":
        user = User.query.get(cr.user_id)
        setattr(user, cr.field_name, cr.new_value)
        cr.status = "approved"
    else:
        cr.status = "rejected"
    cr.reviewed_by = current_user.id
    cr.review_notes = notes
    cr.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Change request {action}d.", "success")
    return redirect(url_for("ess.change_requests"))


@ess_bp.route("/loans", methods=["GET", "POST"])
@login_required
def loans():
    if request.method == "POST":
        loan = LoanAdvanceRequest(
            user_id=current_user.id,
            request_type=request.form.get("type", "loan"),
            amount=float(request.form["amount"]),
            purpose=request.form["purpose"],
            installment_months=int(request.form.get("installments", 12)),
        )
        loan.monthly_installment = round(loan.amount / loan.installment_months, 2)
        loan.remaining_amount = loan.amount
        db.session.add(loan)
        if current_user.manager_id:
            notif = Notification(title="Loan Request", message=f"{current_user.full_name} requests a loan of Rs.{loan.amount:,.0f}",
                                 notification_type="info", module="loans", reference_id=loan.id, created_by=current_user.id)
            db.session.add(notif)
            db.session.flush()
            db.session.add(NotificationRecipient(notification_id=notif.id, user_id=current_user.manager_id))
        db.session.commit()
        flash("Loan request submitted.", "success")
        return redirect(url_for("ess.index"))
    loans = LoanAdvanceRequest.query.filter_by(user_id=current_user.id).order_by(LoanAdvanceRequest.created_at.desc()).all()
    return render_template("ess/loans.html", loans=loans)


@ess_bp.route("/slips")
@login_required
def slips():
    slips = PayrollSlip.query.filter_by(user_id=current_user.id).order_by(PayrollSlip.created_at.desc()).all()
    return render_template("ess/slips.html", slips=slips)


@ess_bp.route("/performance")
@login_required
def performance():
    reviews = PerformanceReview.query.filter_by(user_id=current_user.id).order_by(PerformanceReview.created_at.desc()).all()
    goals = PerformanceGoal.query.filter_by(user_id=current_user.id).order_by(PerformanceGoal.created_at.desc()).all()
    return render_template("ess/performance.html", reviews=reviews, goals=goals)
